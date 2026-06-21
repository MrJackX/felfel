from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message, ErrorEvent
from aiogram.client.default import DefaultBotProperties

from config import Settings, load_settings
from database import Database
from pasarguard_client import PasarGuardClient
from runtime_config import apply_panel_client_config, load_effective_panel_config, panel_is_configured
from shop_handlers import (
    AdminFilter,
    _maintenance_block,
    cmd_start as shop_cmd_start,
    main_menu_kb,
    register_admin_bot_fsm,
    register_admin_shop_callbacks,
    register_shop_customer,
)
from backup_handlers import register_backup_handlers
from menu_config import repair_stored_main_menu_layout
from button_styles import refresh_global_button_styles
from traffic_cleanup import volume_cleanup_loop

log = logging.getLogger(__name__)


class AdminCbFilter(Filter):
    def __init__(self, settings: Settings, db: Database):
        self._settings = settings
        self._db = db

    async def __call__(self, event: CallbackQuery) -> bool:
        u = event.from_user
        if not u:
            return False
        return await self._db.is_bot_admin(u.id, self._settings.bot_admin_ids)


def _plain() -> dict[str, Any]:
    return {"parse_mode": None}


async def cmd_start(message: Message, settings: Settings, db: Database) -> None:
    await shop_cmd_start(message, settings, db)


async def _on_error(event: ErrorEvent) -> None:
    log.exception("Unhandled handler exception: %s", event.exception)
    upd = event.update
    try:
        if upd.message:
            await upd.message.answer("⚠️ خطای داخلی رخ داد. لطفاً دوباره تلاش کنید.")
        elif upd.callback_query:
            await upd.callback_query.answer("⚠️ خطای داخلی رخ داد.", show_alert=True)
    except Exception:
        pass


def _setup_dp(settings: Settings, pg: PasarGuardClient, db: Database) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.errors.register(_on_error)

    pub = Router(name="public")

    @pub.message(CommandStart())
    @pub.message(Command("start"))
    async def _start(m: Message, state: FSMContext) -> None:
        await state.clear()
        await cmd_start(m, settings, db)

    admin_cb = Router(name="admin_cb")
    admin_cb.callback_query.filter(AdminCbFilter(settings, db))
    register_admin_shop_callbacks(admin_cb, settings=settings, pg=pg, db=db)

    shop_router = Router(name="shop")
    register_shop_customer(shop_router, settings=settings, pg=pg, db=db)

    admin_fsm = Router(name="admin_fsm")
    admin_fsm.message.filter(AdminFilter(settings, db))
    register_admin_bot_fsm(admin_fsm, settings=settings, db=db, pg=pg)
    register_backup_handlers(admin_cb, admin_fsm, settings=settings, pg=pg, db=db)

    dp.include_router(pub)
    dp.include_router(admin_cb)
    dp.include_router(admin_fsm)
    dp.include_router(shop_router)
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    settings = load_settings()
    db = Database(settings.bot_db_path)
    await db.init()
    await repair_stored_main_menu_layout(db)
    await refresh_global_button_styles(db)

    cfg = await load_effective_panel_config(db)
    pg = PasarGuardClient(
        cfg.pasarguard_base_url or "http://127.0.0.1",
        cfg.pasarguard_username or "-",
        cfg.pasarguard_password or "-",
        verify_ssl=settings.verify_ssl,
    )
    if panel_is_configured(cfg):
        try:
            await apply_panel_client_config(pg, db)
            groups = await pg.list_groups_simple()
            log.info("PasarGuard connected. groups: %s", groups)
        except Exception as e:
            log.warning("Could not connect to PasarGuard at startup: %s", e)
    else:
        log.info("PasarGuard panel not configured yet — add it from the bot admin menu.")

    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Webhook cleared — polling mode active.")
    dp = _setup_dp(settings, pg, db)
    cleanup_task = asyncio.create_task(volume_cleanup_loop(pg, db, bot, settings))
    try:
        await dp.start_polling(bot)
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        await pg.aclose()


if __name__ == "__main__":
    asyncio.run(main())

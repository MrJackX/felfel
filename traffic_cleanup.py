"""حذف خودکار کانفیگ‌هایی که حجمشان تمام شده و پس از مهلت شارژ نشده‌اند."""

from __future__ import annotations

import asyncio
import html
import logging
import time
from typing import Any

from aiogram import Bot

from bot_texts import T
from config import Settings
from database import Database
from pasarguard_client import PasarGuardAPIError, PasarGuardClient

log = logging.getLogger(__name__)

VOLUME_EXHAUSTED_KEY = "volume_exhausted_at"
CHECK_INTERVAL_SEC = 3600
STARTUP_DELAY_SEC = 90


def is_volume_exhausted(live: dict[str, Any]) -> bool:
    """حجم تمام شده: وضعیت limited یا مصرف >= سقف (فقط برای سقف مشخص)."""
    status = str(live.get("status") or "").lower()
    if status == "limited":
        return True
    limit_b = int(live.get("data_limit") or 0)
    if limit_b <= 0:
        return False
    used_b = int(live.get("used_traffic") or 0)
    return used_b >= limit_b


async def delete_service_from_panel_and_db(
    pg: PasarGuardClient,
    db: Database,
    *,
    order_id: int,
    username: str,
) -> None:
    try:
        await pg.delete_user(username)
    except PasarGuardAPIError as e:
        if e.status_code != 404:
            raise
    await db.update_order(
        order_id,
        status="user_deleted",
        pasarguard_username="",
        subscription_url="",
    )
    await db.update_order_extra(order_id, **{VOLUME_EXHAUSTED_KEY: None})


async def run_volume_exhausted_cleanup(
    pg: PasarGuardClient,
    db: Database,
    bot: Bot | None,
    *,
    grace_hours: int,
) -> int:
    """یک دور بررسی؛ تعداد حذف‌شده را برمی‌گرداند."""
    grace_sec = max(1, grace_hours) * 3600
    now = int(time.time())
    deleted = 0
    orders = await db.list_active_buy_config_orders()
    for row in orders:
        oid = int(row["id"])
        un = str(row.get("pasarguard_username") or "").strip()
        if not un:
            continue
        extra = row.get("extra") or {}
        try:
            live = await asyncio.wait_for(pg.get_user(un), timeout=30.0)
        except asyncio.TimeoutError:
            log.warning("volume cleanup get_user %s timed out", un)
            continue
        except PasarGuardAPIError as e:
            if e.status_code == 404:
                await db.update_order(
                    oid,
                    status="user_deleted",
                    pasarguard_username="",
                    subscription_url="",
                )
                await db.update_order_extra(oid, **{VOLUME_EXHAUSTED_KEY: None})
                deleted += 1
            else:
                log.warning("volume cleanup get_user %s: %s", un, e)
            continue

        if not is_volume_exhausted(live):
            if extra.get(VOLUME_EXHAUSTED_KEY) is not None:
                await db.update_order_extra(oid, **{VOLUME_EXHAUSTED_KEY: None})
            continue

        started = extra.get(VOLUME_EXHAUSTED_KEY)
        if started is None:
            await db.update_order_extra(oid, **{VOLUME_EXHAUSTED_KEY: now})
            continue

        try:
            started_ts = int(started)
        except (TypeError, ValueError):
            started_ts = now
            await db.update_order_extra(oid, **{VOLUME_EXHAUSTED_KEY: now})
            continue

        if now - started_ts < grace_sec:
            continue

        uid = int(row.get("user_id") or 0)
        try:
            await asyncio.wait_for(
                delete_service_from_panel_and_db(pg, db, order_id=oid, username=un),
                timeout=30.0,
            )
            deleted += 1
            log.info("auto-deleted exhausted service order=%s user=%s panel=%s", oid, uid, un)
            if bot and uid > 0:
                try:
                    await bot.send_message(
                        uid,
                        T.msg_svc_auto_deleted_volume.format(
                            un=html.escape(un),
                            hours=grace_hours,
                        ),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
        except asyncio.TimeoutError:
            log.warning("auto-delete timed out order=%s %s", oid, un)
        except PasarGuardAPIError as e:
            log.warning("auto-delete failed order=%s %s: %s", oid, un, e)
        except Exception:
            log.exception("auto-delete order=%s", oid)

    return deleted


async def volume_cleanup_loop(
    pg: PasarGuardClient,
    db: Database,
    bot: Bot,
    settings: Settings,
) -> None:
    await asyncio.sleep(STARTUP_DELAY_SEC)
    while True:
        try:
            hours = await db.get_int_setting("auto_delete_volume_grace_hours", 24)
            n = await run_volume_exhausted_cleanup(pg, db, bot, grace_hours=hours)
            if n:
                log.info("volume cleanup: deleted %s service(s)", n)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("volume cleanup loop error")
        await asyncio.sleep(CHECK_INTERVAL_SEC)

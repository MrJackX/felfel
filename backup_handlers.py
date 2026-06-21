# -*- coding: utf-8 -*-
"""هندلرهای بک‌اپ و بازگردانی داده‌های ربات و پنل."""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import json
import logging
from typing import Any

import aiosqlite
from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Settings
from database import Database
from pasarguard_client import PasarGuardAPIError, PasarGuardClient

log = logging.getLogger(__name__)


class BackupStates(StatesGroup):
    waiting_restore_file = State()
    waiting_db_restore_file = State()
    waiting_settings_restore_file = State()


def backup_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 تهیه نسخه پشتیبان دیتابیس", callback_data="adm:bkp:db")],
        [InlineKeyboardButton(text="♻️ بازیابی دیتابیس", callback_data="adm:bkp:db:restore")],
        [InlineKeyboardButton(text="⚙️ تهیه نسخه پشتیبان تنظیمات", callback_data="adm:bkp:settings")],
        [InlineKeyboardButton(text="♻️ بازیابی تنظیمات", callback_data="adm:bkp:settings:restore")],
        [InlineKeyboardButton(text="👥 تهیه نسخه پشتیبان کاربران پنل", callback_data="adm:bkp:panel")],
        [InlineKeyboardButton(text="📤 انتقال کاربران به پنل جدید", callback_data="adm:bkp:restore")],
        [InlineKeyboardButton(text="🏭 بازگشت به تنظیمات کارخانه", callback_data="adm:bkp:factory")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="adm:root")],
    ])


def _factory_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، بازگردانی کن", callback_data="adm:bkp:factory:yes")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="adm:bkp:menu")],
    ])


def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="adm:bkp:menu")],
    ])


async def _send_file(bot, chat_id: int, data: bytes, filename: str, caption: str) -> None:
    f = BufferedInputFile(data, filename=filename)
    await bot.send_document(chat_id, f, caption=caption, parse_mode=ParseMode.HTML)


def register_backup_handlers(
    admin_cb: Router,
    admin_fsm: Router,
    *,
    settings: Settings,
    pg: PasarGuardClient,
    db: Database,
) -> None:

    @admin_cb.callback_query(F.data == "adm:bkp:menu")
    async def bkp_menu(cq: CallbackQuery) -> None:
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                "🗄 <b>پشتیبان‌گیری و بازیابی</b>\n\nیک گزینه را انتخاب کنید:",
                parse_mode=ParseMode.HTML,
                reply_markup=backup_menu_kb(),
            )

    # ─── بازگشت به تنظیمات کارخانه ──────────────────────────────────────────

    @admin_cb.callback_query(F.data == "adm:bkp:factory")
    async def bkp_factory_confirm(cq: CallbackQuery) -> None:
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                "🏭 <b>بازگشت به تنظیمات کارخانه</b>\n\n"
                "⚠️ تمام تنظیمات ربات (قیمت‌ها، متن‌ها، اطلاعات پنل، بسته‌ها، "
                "تخفیف‌ها و ...) به حالت <b>پیش‌فرض</b> برمی‌گردد.\n\n"
                "✅ کاربران، سفارش‌ها و موجودی‌ها <b>دست‌نخورده</b> می‌مانند.\n\n"
                "آیا مطمئن هستید؟",
                parse_mode=ParseMode.HTML,
                reply_markup=_factory_confirm_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:bkp:factory:yes")
    async def bkp_factory_do(cq: CallbackQuery) -> None:
        await cq.answer("در حال بازگردانی...")
        try:
            n = await db.reset_settings_to_defaults()
            text = (
                f"✅ <b>تنظیمات به حالت کارخانه بازگشت.</b>\n\n"
                f"🔧 تعداد تنظیم بازنشانی‌شده: {n}\n"
                f"⚠️ برای اعمال کامل تغییرات، ربات را ری‌استارت کنید."
            )
        except Exception as e:
            text = f"❌ خطا در بازنشانی:\n<code>{e}</code>"
        if cq.message:
            await cq.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=backup_menu_kb())

    # ─── بک‌اپ دیتابیس SQLite ───────────────────────────────────────────────

    @admin_cb.callback_query(F.data == "adm:bkp:db")
    async def bkp_db(cq: CallbackQuery) -> None:
        await cq.answer("در حال آماده‌سازی...")
        uid = cq.from_user.id if cq.from_user else 0
        try:
            with open(db._path, "rb") as f:
                data = f.read()
            now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            await _send_file(
                cq.bot, uid, data,
                f"bot_backup_{now}.sqlite",
                f"💾 <b>بک‌اپ دیتابیس ربات</b>\n📅 {now}\n📦 حجم: {len(data) // 1024} KB",
            )
        except Exception as e:
            await cq.bot.send_message(uid, f"❌ خطا در ساخت بک‌اپ دیتابیس:\n<code>{e}</code>",
                                       parse_mode=ParseMode.HTML)

    # ─── بازگردانی دیتابیس ربات ─────────────────────────────────────────────

    @admin_cb.callback_query(F.data == "adm:bkp:db:restore")
    async def bkp_db_restore_start(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(BackupStates.waiting_db_restore_file)
        if cq.message:
            await cq.message.answer(
                "♻️ <b>بازگردانی دیتابیس ربات</b>\n\n"
                "فایل <code>.sqlite</code> بک‌اپ را ارسال کنید.\n\n"
                "⚠️ <b>هشدار:</b> دیتابیس فعلی با فایل ارسال‌شده جایگزین می‌شود. "
                "این عملیات برگشت‌پذیر نیست.",
                parse_mode=ParseMode.HTML,
                reply_markup=_cancel_kb(),
            )

    @admin_fsm.message(BackupStates.waiting_db_restore_file, F.document)
    async def bkp_db_restore_file(m: Message, state: FSMContext) -> None:
        await state.clear()
        doc = m.document
        name = doc.file_name if doc else ""
        if not doc or not (name or "").endswith(".sqlite"):
            await m.answer("❌ فقط فایل <code>.sqlite</code> ارسال کنید.", parse_mode=ParseMode.HTML)
            return

        status = await m.answer("⏳ در حال دانلود فایل...")

        try:
            file = await m.bot.get_file(doc.file_id)
            buf = io.BytesIO()
            await m.bot.download_file(file.file_path, buf)
            data = buf.getvalue()
        except Exception as e:
            await status.edit_text(f"❌ خطا در دانلود:\n<code>{e}</code>", parse_mode=ParseMode.HTML)
            return

        # اعتبارسنجی: باید هدر SQLite باشد
        if not data.startswith(b"SQLite format 3\x00"):
            await status.edit_text("❌ فایل معتبر SQLite نیست.")
            return

        await status.edit_text("⏳ در حال جایگزینی دیتابیس...")

        # ایجاد بک‌اپ از نسخه فعلی قبل از جایگزینی
        import os
        import shutil
        db_path = db._path
        backup_path = db_path + f".before_restore_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copy2(db_path, backup_path)
        except Exception:
            pass

        try:
            with open(db_path, "wb") as f:
                f.write(data)
        except Exception as e:
            await status.edit_text(f"❌ خطا در نوشتن فایل:\n<code>{e}</code>", parse_mode=ParseMode.HTML)
            return

        await status.edit_text(
            f"✅ <b>دیتابیس با موفقیت بازگردانی شد.</b>\n\n"
            f"📦 حجم: {len(data) // 1024} KB\n"
            f"⚠️ برای اعمال کامل تغییرات، ربات را ری‌استارت کنید.",
            parse_mode=ParseMode.HTML,
        )

    # ─── بک‌اپ تنظیمات ربات (جدول kv) ─────────────────────────────────────

    @admin_cb.callback_query(F.data == "adm:bkp:settings")
    async def bkp_settings(cq: CallbackQuery) -> None:
        await cq.answer("در حال آماده‌سازی...")
        uid = cq.from_user.id if cq.from_user else 0
        try:
            async with aiosqlite.connect(db._path) as conn:
                conn.row_factory = aiosqlite.Row
                cur = await conn.execute("SELECT key, value FROM kv ORDER BY key")
                rows = await cur.fetchall()
            kv = {r["key"]: r["value"] for r in rows}
            now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            payload = {"exported_at": now, "kv": kv}
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            await _send_file(
                cq.bot, uid, data,
                f"bot_settings_{now}.json",
                f"⚙️ <b>بک‌اپ تنظیمات ربات</b>\n📅 {now}\n🔑 تعداد کلید: {len(kv)}",
            )
        except Exception as e:
            await cq.bot.send_message(uid, f"❌ خطا:\n<code>{e}</code>", parse_mode=ParseMode.HTML)

    # ─── بازگردانی تنظیمات ربات ─────────────────────────────────────────────

    @admin_cb.callback_query(F.data == "adm:bkp:settings:restore")
    async def bkp_settings_restore_start(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(BackupStates.waiting_settings_restore_file)
        if cq.message:
            await cq.message.answer(
                "♻️ <b>بازگردانی تنظیمات ربات</b>\n\n"
                "فایل <code>bot_settings_*.json</code> بک‌اپ را ارسال کنید.\n\n"
                "⚠️ تنظیمات فعلی با مقادیر فایل بازنویسی می‌شوند.",
                parse_mode=ParseMode.HTML,
                reply_markup=_cancel_kb(),
            )

    @admin_fsm.message(BackupStates.waiting_settings_restore_file, F.document)
    async def bkp_settings_restore_file(m: Message, state: FSMContext) -> None:
        await state.clear()
        doc = m.document
        if not doc or not (doc.file_name or "").endswith(".json"):
            await m.answer("❌ فقط فایل <code>.json</code> ارسال کنید.", parse_mode=ParseMode.HTML)
            return

        status = await m.answer("⏳ در حال خواندن فایل...")

        try:
            file = await m.bot.get_file(doc.file_id)
            buf = io.BytesIO()
            await m.bot.download_file(file.file_path, buf)
            buf.seek(0)
            payload: Any = json.loads(buf.read().decode("utf-8"))
        except Exception as e:
            await status.edit_text(f"❌ خطا در خواندن فایل:\n<code>{e}</code>", parse_mode=ParseMode.HTML)
            return

        kv: dict[str, str] = {}
        if isinstance(payload, dict):
            raw = payload.get("kv") or {}
            if isinstance(raw, dict):
                kv = {str(k): str(v) for k, v in raw.items() if v is not None}
        if not kv:
            await status.edit_text("❌ فایل خالی است یا فرمت نادرست دارد.")
            return

        await status.edit_text(f"⏳ در حال بازگردانی {len(kv)} تنظیم...")

        try:
            async with aiosqlite.connect(db._path) as conn:
                await conn.executemany(
                    "INSERT INTO kv (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    list(kv.items()),
                )
                await conn.commit()
        except Exception as e:
            await status.edit_text(f"❌ خطا در نوشتن تنظیمات:\n<code>{e}</code>", parse_mode=ParseMode.HTML)
            return

        await status.edit_text(
            f"✅ <b>تنظیمات با موفقیت بازگردانی شد.</b>\n\n"
            f"🔑 تعداد تنظیم بازگردانی‌شده: {len(kv)}\n"
            f"⚠️ برای اعمال کامل تغییرات، ربات را ری‌استارت کنید.",
            parse_mode=ParseMode.HTML,
        )

    # ─── بک‌اپ یوزرهای پنل ──────────────────────────────────────────────────

    @admin_cb.callback_query(F.data == "adm:bkp:panel")
    async def bkp_panel(cq: CallbackQuery) -> None:
        await cq.answer("در حال دریافت از پنل...")
        uid = cq.from_user.id if cq.from_user else 0
        status = await cq.bot.send_message(uid, "⏳ در حال دریافت لیست یوزرهای پنل...")
        try:
            users = await pg.list_all_users()
            now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            payload = {"exported_at": now, "count": len(users), "users": users}
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            await status.delete()
            await _send_file(
                cq.bot, uid, data,
                f"panel_users_{now}.json",
                (
                    f"👥 <b>بک‌اپ یوزرهای پنل</b>\n"
                    f"📊 تعداد یوزر: {len(users)}\n"
                    f"📅 {now}"
                ),
            )
        except PasarGuardAPIError as e:
            await status.edit_text(f"❌ خطای پنل: <code>{e}</code>", parse_mode=ParseMode.HTML)
        except Exception as e:
            await status.edit_text(f"❌ خطا: <code>{e}</code>", parse_mode=ParseMode.HTML)

    # ─── انتقال یوزرها به پنل جدید ─────────────────────────────────────────

    @admin_cb.callback_query(F.data == "adm:bkp:restore")
    async def bkp_restore_start(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(BackupStates.waiting_restore_file)
        if cq.message:
            await cq.message.answer(
                "📤 <b>انتقال یوزرها به پنل جدید</b>\n\n"
                "فایل JSON بک‌اپ یوزرهای پنل را ارسال کنید.\n\n"
                "⚠️ <b>نکته:</b> قبل از انتقال، آدرس پنل جدید را در تنظیمات پنل ربات وارد کنید.",
                parse_mode=ParseMode.HTML,
                reply_markup=_cancel_kb(),
            )

    @admin_fsm.message(BackupStates.waiting_restore_file, F.document)
    async def bkp_restore_file(m: Message, state: FSMContext) -> None:
        await state.clear()
        doc = m.document
        if not doc or not (doc.file_name or "").endswith(".json"):
            await m.answer("❌ فقط فایل JSON ارسال کنید.")
            return

        status = await m.answer("⏳ در حال خواندن فایل...")

        try:
            file = await m.bot.get_file(doc.file_id)
            buf = io.BytesIO()
            await m.bot.download_file(file.file_path, buf)
            buf.seek(0)
            payload: Any = json.loads(buf.read().decode("utf-8"))
        except Exception as e:
            await status.edit_text(f"❌ خطا در خواندن فایل:\n<code>{e}</code>",
                                    parse_mode=ParseMode.HTML)
            return

        users: list[dict] = []
        if isinstance(payload, dict):
            raw = payload.get("users")
            if isinstance(raw, list):
                users = [u for u in raw if isinstance(u, dict)]
        elif isinstance(payload, list):
            users = [u for u in payload if isinstance(u, dict)]

        if not users:
            await status.edit_text("❌ فایل خالی است یا فرمت نادرست دارد.")
            return

        await status.edit_text(f"⏳ شروع انتقال <b>{len(users)}</b> یوزر...", parse_mode=ParseMode.HTML)

        from runtime_config import load_effective_panel_config
        cfg = await load_effective_panel_config(db)
        default_group_ids: list[int] = list(cfg.default_group_ids or [])

        ok = skip = fail = 0
        fail_samples: list[str] = []

        for i, user in enumerate(users):
            username = str(user.get("username") or "").strip()
            if not username:
                skip += 1
                continue

            # محاسبه روزهای باقی‌مانده از expire
            expire_raw = user.get("expire")
            days: int | None = None
            if expire_raw and str(expire_raw).strip() not in ("", "0", "null", "None"):
                try:
                    v = expire_raw
                    if isinstance(v, (int, float)) and int(v) > 0:
                        exp_dt = dt.datetime.fromtimestamp(int(v), tz=dt.timezone.utc)
                    else:
                        s = str(v).replace("Z", "+00:00")
                        exp_dt = dt.datetime.fromisoformat(s)
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=dt.timezone.utc)
                    remaining = (exp_dt - dt.datetime.now(dt.timezone.utc)).days
                    days = max(1, remaining) if remaining > 0 else 1
                except Exception:
                    days = 30

            data_limit = int(user.get("data_limit") or 0)

            # group_ids: از بک‌اپ اگر وجود دارد؛ وگرنه پیش‌فرض
            group_ids = default_group_ids
            raw_groups = user.get("group_ids") or []
            if isinstance(raw_groups, list) and raw_groups:
                parsed_groups: list[int] = []
                for g in raw_groups:
                    if isinstance(g, int):
                        parsed_groups.append(g)
                    elif isinstance(g, dict):
                        try:
                            parsed_groups.append(int(g["id"]))
                        except (KeyError, TypeError, ValueError):
                            pass
                if parsed_groups:
                    group_ids = parsed_groups

            try:
                await pg.create_user(
                    username=username,
                    days=days,
                    data_limit_bytes=data_limit,
                    group_ids=group_ids,
                    note=str(user.get("note") or ""),
                )
                ok += 1
            except PasarGuardAPIError as e:
                if e.status_code == 409:
                    skip += 1
                else:
                    fail += 1
                    if len(fail_samples) < 5:
                        fail_samples.append(f"{username}: {e}")
            except Exception as e:
                fail += 1
                if len(fail_samples) < 5:
                    fail_samples.append(f"{username}: {e}")

            if (i + 1) % 25 == 0:
                try:
                    await status.edit_text(
                        f"⏳ {i + 1}/{len(users)} ...\n✅ {ok} | ⏭ {skip} | ❌ {fail}",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass

            await asyncio.sleep(0.05)

        result = (
            f"✅ <b>انتقال تمام شد</b>\n\n"
            f"✅ منتقل‌شده: <b>{ok}</b>\n"
            f"⏭ رد شده (تکراری): <b>{skip}</b>\n"
            f"❌ ناموفق: <b>{fail}</b>"
        )
        if fail_samples:
            result += "\n\n<b>نمونه خطاها:</b>\n" + "\n".join(f"• {s}" for s in fail_samples)

        await status.edit_text(result, parse_mode=ParseMode.HTML)

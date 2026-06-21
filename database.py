from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite

DEFAULT_SETTINGS: dict[str, str] = {
    "price_per_gb": "100000",
    "payment_card_text": "",
    "show_payment_card": "1",
    "show_crypto_text": "1",
    "channel_join_required": "0",
    "mandatory_channel_id": "",
    "mandatory_channel_invite_url": "",
    "trust_wallet_text": (
        "💎 آدرس ارز دیجیتال (نمونه):\n"
        "TRX/USDT TRC20: YOUR_WALLET_HERE\n\n"
        "⏱ پس از واریز، رسید را در ربات ارسال کنید."
    ),
    "buying_disabled": "0",
    "maintenance_mode": "0",
    "maintenance_message": "⏳ ربات در حال به‌روزرسانی است. لطفاً کمی بعد دوباره تلاش کنید.",
    "default_config_days": "30",
    "auto_delete_volume_grace_hours": "24",
    "test_service_enabled": "0",
    "test_service_gb": "1",
    "volume_discount_tiers": "[]",
    "partner_volume_discount_tiers": "[]",
    "partner_price_per_gb": "100000",
    "buy_packages": "[]",
    "partner_buy_packages": "[]",
    "buy_sell_mode": "volume",
    "welcome_message": "",
    "pasarguard_base_url": "",
    "pasarguard_username": "",
    "pasarguard_password": "",
    "default_group_ids": "",
    "panel_username_prefix": "",
    "panel_username_start": "",
    "receipt_channel_id": "",
    "main_menu_buttons_json": "",
    "global_button_styles_json": "",
    "support_text": "💬 برای پشتیبانی با ادمین تماس بگیرید.",
    "connection_guide_text": (
        "📖 <b>راهنمای اتصال</b>\n\n"
        "۱) لینک اشتراک را از «سرویس های من» کپی کنید.\n"
        "۲) در اپ v2rayNG / Streisand / Hiddify وارد کنید.\n"
        "۳) اتصال را روشن کنید."
    ),
    "nowpayments_api_key": "",
    "nowpayments_usd_rate": "50000",
    "show_nowpayments": "0",
    "discount_codes_enabled": "0",
    "mandatory_channel_ids_json": "",
    "bot_admin_ids_json": "[]",
    "receipt_admin_ids_json": "[]",
}


class Database:
    def __init__(self, path: str | Path):
        self._path = str(path)

    async def init(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    balance REAL NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    gb REAL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    receipt_file_id TEXT,
                    receipt_unique_id TEXT,
                    receipt_chat_id INTEGER,
                    created_at INTEGER NOT NULL,
                    pasarguard_username TEXT,
                    subscription_url TEXT,
                    panel_user_id INTEGER,
                    extra_json TEXT
                )
                """
            )
            await self._migrate_orders_schema(db)
            await self._migrate_users_schema(db)
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS partners (
                    telegram_id INTEGER PRIMARY KEY,
                    label TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL,
                    unsettled_gb REAL NOT NULL DEFAULT 0,
                    unsettled_amount REAL NOT NULL DEFAULT 0
                )
                """
            )
            await self._migrate_partners_schema(db)
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS discount_codes (
                    code TEXT PRIMARY KEY COLLATE NOCASE,
                    percent REAL NOT NULL,
                    max_uses INTEGER NOT NULL DEFAULT 0,
                    used_count INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL
                )
                """
            )
            for k, v in DEFAULT_SETTINGS.items():
                await db.execute(
                    "INSERT OR IGNORE INTO kv (key, value) VALUES (?, ?)",
                    (k, v),
                )
            await db.commit()

    async def _migrate_orders_schema(self, db: Any) -> None:
        cur = await db.execute("PRAGMA table_info(orders)")
        cols = {str(r[1]) for r in await cur.fetchall()}
        if "receipt_message_id" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN receipt_message_id INTEGER")

    async def _migrate_users_schema(self, db: Any) -> None:
        cur = await db.execute("PRAGMA table_info(users)")
        cols = {str(r[1]) for r in await cur.fetchall()}
        if "test_service_claimed" not in cols:
            await db.execute(
                "ALTER TABLE users ADD COLUMN test_service_claimed INTEGER NOT NULL DEFAULT 0"
            )
            await db.execute(
                """
                UPDATE users SET test_service_claimed = 1
                WHERE telegram_id IN (
                    SELECT DISTINCT user_id FROM orders
                    WHERE kind = 'test_config'
                      AND status IN ('approved_done', 'user_deleted')
                )
                """
            )

    async def get_setting(self, key: str, default: str = "") -> str:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute("SELECT value FROM kv WHERE key = ?", (key,))
            row = await cur.fetchone()
            return str(row[0]) if row else default

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await db.commit()

    async def reset_settings_to_defaults(self) -> int:
        """همهٔ تنظیمات جدول kv را به مقادیر پیش‌فرض کارخانه بازمی‌گرداند.

        فقط روی کلیدهای موجود در DEFAULT_SETTINGS اثر می‌گذارد؛
        داده‌های دیگر (کاربران، سفارش‌ها، کدهای تخفیف و ...) دست‌نخورده می‌مانند.
        """
        async with aiosqlite.connect(self._path) as db:
            await db.execute("DELETE FROM kv WHERE key IN (%s)" % ",".join("?" * len(DEFAULT_SETTINGS)),
                             tuple(DEFAULT_SETTINGS.keys()))
            await db.executemany(
                "INSERT INTO kv (key, value) VALUES (?, ?)",
                list(DEFAULT_SETTINGS.items()),
            )
            await db.commit()
        return len(DEFAULT_SETTINGS)

    async def get_float_setting(self, key: str, default: float = 0.0) -> float:
        raw = await self.get_setting(key, str(default))
        try:
            return float(raw.replace(",", "."))
        except ValueError:
            return default

    async def get_int_setting(self, key: str, default: int = 0) -> int:
        raw = await self.get_setting(key, str(default))
        try:
            return int(float(raw.replace(",", ".")))
        except ValueError:
            return default

    async def get_bool_setting(self, key: str) -> bool:
        v = (await self.get_setting(key, "0")).strip().lower()
        return v in ("1", "true", "yes", "on")

    async def set_bool_setting(self, key: str, value: bool) -> None:
        await self.set_setting(key, "1" if value else "0")

    async def get_volume_discount_tiers_raw(self) -> str:
        return await self.get_setting("volume_discount_tiers", "[]")

    async def set_volume_discount_tiers_json(self, tiers_json: str) -> None:
        await self.set_setting("volume_discount_tiers", tiers_json)

    async def get_partner_volume_discount_tiers_raw(self) -> str:
        return await self.get_setting("partner_volume_discount_tiers", "[]")

    async def set_partner_volume_discount_tiers_json(self, tiers_json: str) -> None:
        await self.set_setting("partner_volume_discount_tiers", tiers_json)

    async def get_buy_packages_raw(self) -> str:
        return await self.get_setting("buy_packages", "[]")

    async def set_buy_packages_json(self, packages_json: str) -> None:
        await self.set_setting("buy_packages", packages_json)

    async def get_partner_buy_packages_raw(self) -> str:
        return await self.get_setting("partner_buy_packages", "[]")

    async def set_partner_buy_packages_json(self, packages_json: str) -> None:
        await self.set_setting("partner_buy_packages", packages_json)

    async def ensure_user(self, telegram_id: int) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, balance, created_at) VALUES (?, 0, ?)",
                (telegram_id, now),
            )
            await db.commit()

    async def list_users_with_balance(
        self,
        *,
        min_balance: float = 0.01,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT telegram_id, balance, created_at FROM users
                WHERE balance >= ?
                ORDER BY balance DESC
                LIMIT ?
                """,
                (min_balance, limit),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def get_balance(self, telegram_id: int) -> float:
        await self.ensure_user(telegram_id)
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cur.fetchone()
            return float(row[0]) if row else 0.0

    async def add_balance(self, telegram_id: int, delta: float) -> float:
        await self.ensure_user(telegram_id)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
                (delta, telegram_id),
            )
            cur = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cur.fetchone()
            await db.commit()
            return float(row[0]) if row else 0.0

    async def try_deduct_balance(self, telegram_id: int, amount: float) -> float | None:
        """اگر موجودی کافی باشد مبلغ را کم می‌کند و موجودی جدید را برمی‌گرداند؛ وگرنه None."""
        if amount <= 0:
            return None
        await self.ensure_user(telegram_id)
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "UPDATE users SET balance = balance - ? WHERE telegram_id = ? AND balance >= ?",
                (amount, telegram_id, amount),
            )
            if cur.rowcount == 0:
                await db.commit()
                return None
            cur2 = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cur2.fetchone()
            await db.commit()
            return float(row[0]) if row else None

    async def create_order(
        self,
        *,
        user_id: int,
        kind: str,
        gb: float | None,
        amount: float,
        status: str,
        receipt_file_id: str | None,
        receipt_unique_id: str | None,
        receipt_chat_id: int | None,
        receipt_message_id: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> int:
        now = int(time.time())
        extra_json = json.dumps(extra or {}, ensure_ascii=False)
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                """
                INSERT INTO orders (user_id, kind, gb, amount, status, receipt_file_id, receipt_unique_id,
                    receipt_chat_id, receipt_message_id, created_at, extra_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    kind,
                    gb,
                    amount,
                    status,
                    receipt_file_id,
                    receipt_unique_id,
                    receipt_chat_id,
                    receipt_message_id,
                    now,
                    extra_json,
                ),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def get_order(self, order_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["extra"] = json.loads(d.get("extra_json") or "{}")
            except json.JSONDecodeError:
                d["extra"] = {}
            return d

    async def update_order(
        self,
        order_id: int,
        *,
        status: str | None = None,
        pasarguard_username: str | None = None,
        subscription_url: str | None = None,
        panel_user_id: int | None = None,
    ) -> None:
        parts: list[str] = []
        vals: list[Any] = []
        if status is not None:
            parts.append("status = ?")
            vals.append(status)
        if pasarguard_username is not None:
            parts.append("pasarguard_username = ?")
            vals.append(pasarguard_username)
        if subscription_url is not None:
            parts.append("subscription_url = ?")
            vals.append(subscription_url)
        if panel_user_id is not None:
            parts.append("panel_user_id = ?")
            vals.append(panel_user_id)
        if not parts:
            return
        vals.append(order_id)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(f"UPDATE orders SET {', '.join(parts)} WHERE id = ?", vals)
            await db.commit()

    async def count_pending_orders(self) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE status = ?",
                ("pending",),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def list_pending_orders(self, limit: int = 20) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM orders WHERE status = 'pending' ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                try:
                    d["extra"] = json.loads(d.get("extra_json") or "{}")
                except json.JSONDecodeError:
                    d["extra"] = {}
                out.append(d)
            return out

    async def list_user_orders_done(self, user_id: int, limit: int = 15) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM orders
                WHERE user_id = ? AND status = ?
                ORDER BY id DESC LIMIT ?
                """,
                (user_id, "approved_done", limit),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def update_order_extra(self, order_id: int, **fields: Any) -> None:
        row = await self.get_order(order_id)
        if not row:
            return
        extra = dict(row.get("extra") or {})
        for key, val in fields.items():
            if val is None:
                extra.pop(key, None)
            else:
                extra[key] = val
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE orders SET extra_json = ? WHERE id = ?",
                (json.dumps(extra, ensure_ascii=False), order_id),
            )
            await db.commit()

    async def list_active_buy_config_orders(self, limit: int = 500) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM orders
                WHERE kind IN ('buy_config', 'test_config') AND status = 'approved_done'
                  AND pasarguard_username IS NOT NULL AND TRIM(pasarguard_username) != ''
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                try:
                    d["extra"] = json.loads(d.get("extra_json") or "{}")
                except json.JSONDecodeError:
                    d["extra"] = {}
                out.append(d)
            return out

    async def list_orders_with_panel_username(self, limit: int = 5000) -> list[dict[str, Any]]:
        """سفارش‌های دارای اکانت پنل (برای اتصال به خروجی انتقال)."""
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM orders
                WHERE pasarguard_username IS NOT NULL AND TRIM(pasarguard_username) != ''
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                try:
                    d["extra"] = json.loads(d.get("extra_json") or "{}")
                except json.JSONDecodeError:
                    d["extra"] = {}
                out.append(d)
            return out

    async def user_has_test_service(self, user_id: int) -> bool:
        """هر کاربر فقط یک‌بار تست — حتی بعد از حذف سرویس از لیست."""
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT test_service_claimed FROM users WHERE telegram_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if row and int(row[0]):
                return True
            cur2 = await db.execute(
                """
                SELECT 1 FROM orders
                WHERE user_id = ? AND kind = 'test_config'
                  AND status IN ('approved_done', 'user_deleted')
                LIMIT 1
                """,
                (user_id,),
            )
            return (await cur2.fetchone()) is not None

    async def mark_test_service_claimed(self, user_id: int) -> None:
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE users SET test_service_claimed = 1 WHERE telegram_id = ?",
                (user_id,),
            )
            await db.commit()

    async def reset_user_test_eligibility(self, user_id: int) -> int:
        """اجازهٔ تست مجدد برای یک کاربر؛ تعداد رکوردهای حذف‌شده را برمی‌گرداند."""
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE users SET test_service_claimed = 0 WHERE telegram_id = ?",
                (user_id,),
            )
            cur = await db.execute(
                "DELETE FROM orders WHERE user_id = ? AND kind = 'test_config'",
                (user_id,),
            )
            await db.commit()
            return int(cur.rowcount)

    async def count_user_completed_buy_configs(self, user_id: int) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                """
                SELECT COUNT(*) FROM orders
                WHERE user_id = ? AND kind = 'buy_config' AND status = 'approved_done'
                """,
                (user_id,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def _migrate_partners_schema(self, db: Any) -> None:
        cur = await db.execute("PRAGMA table_info(partners)")
        cols = {str(r[1]) for r in await cur.fetchall()}
        if "unsettled_gb" not in cols:
            await db.execute(
                "ALTER TABLE partners ADD COLUMN unsettled_gb REAL NOT NULL DEFAULT 0"
            )
        if "unsettled_amount" not in cols:
            await db.execute(
                "ALTER TABLE partners ADD COLUMN unsettled_amount REAL NOT NULL DEFAULT 0"
            )

    async def get_partner(self, telegram_id: int) -> dict[str, Any] | None:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT telegram_id, label, created_at, unsettled_gb, unsettled_amount
                FROM partners WHERE telegram_id = ?
                """,
                (telegram_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def add_partner_usage(self, telegram_id: int, *, gb: float, amount: float) -> None:
        if gb <= 0 and amount <= 0:
            return
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                UPDATE partners
                SET unsettled_gb = unsettled_gb + ?,
                    unsettled_amount = unsettled_amount + ?
                WHERE telegram_id = ?
                """,
                (float(gb), float(amount), telegram_id),
            )
            await db.commit()

    async def subtract_partner_usage(self, telegram_id: int, *, gb: float, amount: float) -> None:
        if gb <= 0 and amount <= 0:
            return
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                """
                UPDATE partners
                SET unsettled_gb = CASE WHEN unsettled_gb - ? < 0 THEN 0 ELSE unsettled_gb - ? END,
                    unsettled_amount = CASE WHEN unsettled_amount - ? < 0 THEN 0 ELSE unsettled_amount - ? END
                WHERE telegram_id = ?
                """,
                (float(gb), float(gb), float(amount), float(amount), telegram_id),
            )
            await db.commit()

    async def reverse_partner_order_usage(self, order: dict[str, Any]) -> None:
        if str(order.get("kind") or "") != "buy_config":
            return
        uid = int(order.get("user_id") or 0)
        if uid <= 0 or not await self.is_partner(uid):
            return
        try:
            gb = float(order.get("gb") or 0)
        except (TypeError, ValueError):
            gb = 0.0
        try:
            amount = float(order.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        await self.subtract_partner_usage(uid, gb=gb, amount=amount)

    async def alloc_panel_username_number(self, *, start: int = 100) -> int:
        """شمارهٔ ترتیبی برای نام کاربری پنل (از start شروع می‌شود)."""
        async with aiosqlite.connect(self._path) as db:
            await db.execute("BEGIN IMMEDIATE")
            cur = await db.execute(
                "SELECT value FROM kv WHERE key = 'panel_username_seq'"
            )
            row = await cur.fetchone()
            if row:
                n = int(float(str(row[0]).strip()))
            else:
                n = int(start)
            await db.execute(
                """
                INSERT INTO kv (key, value) VALUES ('panel_username_seq', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (str(n + 1),),
            )
            await db.commit()
            return n

    async def reset_partner_settlement(
        self, telegram_id: int
    ) -> tuple[float, float, str] | None:
        """صفر کردن بدهی؛ برمی‌گرداند (گیگ، مبلغ، برچسب) قبل از تسویه."""
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT unsettled_gb, unsettled_amount, label FROM partners
                WHERE telegram_id = ?
                """,
                (telegram_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            gb = float(row["unsettled_gb"] or 0)
            amt = float(row["unsettled_amount"] or 0)
            label = str(row["label"] or "").strip()
            await db.execute(
                """
                UPDATE partners
                SET unsettled_gb = 0, unsettled_amount = 0
                WHERE telegram_id = ?
                """,
                (telegram_id,),
            )
            await db.commit()
            return gb, amt, label

    async def is_partner(self, telegram_id: int) -> bool:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT 1 FROM partners WHERE telegram_id = ? LIMIT 1",
                (telegram_id,),
            )
            return (await cur.fetchone()) is not None

    async def add_partner(self, telegram_id: int, *, label: str = "") -> bool:
        """True اگر تازه اضافه شد؛ False اگر از قبل بود."""
        now = int(time.time())
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                """
                INSERT INTO partners (telegram_id, label, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_id) DO NOTHING
                """,
                (telegram_id, (label or "").strip(), now),
            )
            await db.commit()
            return int(cur.rowcount) > 0

    async def remove_partner(self, telegram_id: int) -> bool:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "DELETE FROM partners WHERE telegram_id = ?",
                (telegram_id,),
            )
            await db.commit()
            return int(cur.rowcount) > 0

    async def list_partners(self, limit: int = 100) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT telegram_id, label, created_at, unsettled_gb, unsettled_amount
                FROM partners ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def count_partners(self) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM partners")
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def list_db_admin_ids(self) -> list[int]:
        raw = await self.get_setting("bot_admin_ids_json", "[]")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        out: list[int] = []
        for x in data:
            try:
                tid = int(x)
            except (TypeError, ValueError):
                continue
            if tid > 0:
                out.append(tid)
        return sorted(set(out))

    async def _save_db_admin_ids(self, ids: list[int]) -> None:
        clean = sorted(set(int(x) for x in ids if int(x) > 0))
        await self.set_setting("bot_admin_ids_json", json.dumps(clean, ensure_ascii=False))

    async def is_bot_admin(self, telegram_id: int, env_admin_ids: frozenset[int]) -> bool:
        if telegram_id in env_admin_ids:
            return True
        return telegram_id in await self.list_db_admin_ids()

    async def add_db_admin(self, telegram_id: int) -> bool:
        ids = await self.list_db_admin_ids()
        if telegram_id in ids:
            return False
        ids.append(telegram_id)
        await self._save_db_admin_ids(ids)
        return True

    async def remove_db_admin(self, telegram_id: int, env_admin_ids: frozenset[int]) -> bool:
        if telegram_id in env_admin_ids:
            return False
        ids = await self.list_db_admin_ids()
        if telegram_id not in ids:
            return False
        ids = [x for x in ids if x != telegram_id]
        await self._save_db_admin_ids(ids)
        return True

    async def list_receipt_admin_ids(self) -> list[int]:
        raw = await self.get_setting("receipt_admin_ids_json", "[]")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        out: list[int] = []
        for x in data:
            try:
                tid = int(x)
            except (TypeError, ValueError):
                continue
            if tid > 0:
                out.append(tid)
        return sorted(set(out))

    async def _save_receipt_admin_ids(self, ids: list[int]) -> None:
        clean = sorted(set(int(x) for x in ids if int(x) > 0))
        await self.set_setting("receipt_admin_ids_json", json.dumps(clean, ensure_ascii=False))

    async def add_receipt_admin(self, telegram_id: int) -> bool:
        ids = await self.list_receipt_admin_ids()
        if telegram_id in ids:
            return False
        ids.append(telegram_id)
        await self._save_receipt_admin_ids(ids)
        return True

    async def remove_receipt_admin(self, telegram_id: int) -> bool:
        ids = await self.list_receipt_admin_ids()
        if telegram_id not in ids:
            return False
        ids = [x for x in ids if x != telegram_id]
        await self._save_receipt_admin_ids(ids)
        return True

    async def list_all_user_telegram_ids(self, limit: int = 50000) -> list[int]:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT telegram_id FROM users ORDER BY created_at ASC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
            return [int(r[0]) for r in rows]

    async def list_user_orders(self, user_id: int, limit: int = 30) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM orders
                WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cur.fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                d = dict(row)
                try:
                    d["extra"] = json.loads(d.get("extra_json") or "{}")
                except json.JSONDecodeError:
                    d["extra"] = {}
                out.append(d)
            return out

    async def count_users_with_balance(self, min_balance: float = 0.01) -> int:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM users WHERE balance >= ?",
                (min_balance,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def add_discount_code(
        self,
        code: str,
        percent: float,
        *,
        max_uses: int = 0,
    ) -> bool:
        c = code.strip().upper()
        if not c or percent <= 0 or percent > 100:
            return False
        now = int(time.time())
        async with aiosqlite.connect(self._path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO discount_codes (code, percent, max_uses, used_count, created_at)
                    VALUES (?, ?, ?, 0, ?)
                    """,
                    (c, percent, max(0, int(max_uses)), now),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_discount_code(self, code: str) -> bool:
        c = code.strip().upper()
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute("DELETE FROM discount_codes WHERE code = ?", (c,))
            await db.commit()
            return int(cur.rowcount) > 0

    async def list_discount_codes(self, limit: int = 50) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT code, percent, max_uses, used_count, created_at
                FROM discount_codes ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def get_discount_code(self, code: str) -> dict[str, Any] | None:
        c = code.strip().upper()
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT code, percent, max_uses, used_count, created_at
                FROM discount_codes WHERE code = ?
                """,
                (c,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def use_discount_code(self, code: str) -> dict[str, Any] | None:
        """اتمیک: کد را مصرف می‌کند؛ اگر کد نباشد یا به سقف رسیده باشد None."""
        c = code.strip().upper()
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                UPDATE discount_codes SET used_count = used_count + 1
                WHERE code = ? AND (max_uses = 0 OR used_count < max_uses)
                """,
                (c,),
            )
            if cur.rowcount == 0:
                await db.commit()
                return None
            cur2 = await db.execute(
                "SELECT code, percent, max_uses, used_count, created_at FROM discount_codes WHERE code = ?",
                (c,),
            )
            row = await cur2.fetchone()
            await db.commit()
            return dict(row) if row else None

    async def get_mandatory_channel_ids(self) -> list[str]:
        raw_json = (await self.get_setting("mandatory_channel_ids_json", "")).strip()
        if raw_json:
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, list):
                out = [str(x).strip() for x in data if str(x).strip()]
                if out:
                    return out
        legacy = (await self.get_setting("mandatory_channel_id", "")).strip()
        return [legacy] if legacy else []

    async def set_mandatory_channel_ids(self, ids: list[str]) -> None:
        clean = [x.strip() for x in ids if x.strip()]
        await self.set_setting(
            "mandatory_channel_ids_json",
            json.dumps(clean, ensure_ascii=False),
        )
        if clean:
            await self.set_setting("mandatory_channel_id", clean[0])
        else:
            await self.set_setting("mandatory_channel_id", "")

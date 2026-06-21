import os
from dataclasses import dataclass

from dotenv import load_dotenv

# ابتدا .env استاندارد؛ در صورت نبود، .env.txt (سازگاری با نصب‌های قدیمی)
if not load_dotenv():
    load_dotenv(".env.txt")


def _parse_admin_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return frozenset(int(x) for x in parts)


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    bot_admin_ids: frozenset[int]
    verify_ssl: bool
    bot_db_path: str


def load_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    admins = _parse_admin_ids(os.environ.get("BOT_ADMIN_IDS"))
    if not admins:
        raise RuntimeError("BOT_ADMIN_IDS is required (comma-separated Telegram user ids)")

    verify = os.environ.get("VERIFY_SSL", "true").strip().lower() in ("1", "true", "yes", "on")

    db_path = os.environ.get("BOT_DB_PATH", "bot_data.sqlite").strip() or "bot_data.sqlite"

    return Settings(
        telegram_bot_token=token,
        bot_admin_ids=admins,
        verify_ssl=verify,
        bot_db_path=db_path,
    )

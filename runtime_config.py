from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from database import Database
from bot_texts import T


def _parse_group_ids(raw: str) -> list[int]:
    if not raw.strip():
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return [int(x) for x in parts]


@dataclass(frozen=True)
class EffectivePanelConfig:
    pasarguard_base_url: str
    pasarguard_username: str
    pasarguard_password: str
    default_group_ids: list[int]
    panel_username_prefix: str
    panel_username_start: int
    receipt_channel_id: int | None


def panel_is_configured(cfg: EffectivePanelConfig) -> bool:
    return bool(
        cfg.pasarguard_base_url.strip()
        and cfg.pasarguard_username.strip()
        and cfg.pasarguard_password.strip()
    )


async def get_welcome_message(db: Database) -> str:
    raw = (await db.get_setting("welcome_message", "")).strip()
    if raw:
        return raw
    return T.msg_cmd_start


async def load_effective_panel_config(db: Database) -> EffectivePanelConfig:
    base = (await db.get_setting("pasarguard_base_url", "")).strip()
    user = (await db.get_setting("pasarguard_username", "")).strip()
    pw = (await db.get_setting("pasarguard_password", "")).strip()

    groups_raw = (await db.get_setting("default_group_ids", "")).strip()
    groups = _parse_group_ids(groups_raw) if groups_raw else [1]
    if not groups:
        groups = [1]

    prefix_raw = (await db.get_setting("panel_username_prefix", "")).strip()
    prefix = prefix_raw or "via"
    prefix = re.sub(r"[^a-zA-Z0-9_]", "", prefix).lower() or "via"
    prefix = prefix[:20]

    start_raw = (await db.get_setting("panel_username_start", "")).strip()
    if start_raw:
        try:
            panel_start = int(float(start_raw))
        except ValueError:
            panel_start = 100
    else:
        panel_start = 100
    if panel_start < 1:
        panel_start = 100

    ch_raw = (await db.get_setting("receipt_channel_id", "")).strip()
    receipt_channel_id: int | None = None
    if ch_raw:
        if ch_raw.startswith("-") or ch_raw.isdigit():
            try:
                receipt_channel_id = int(ch_raw)
            except ValueError:
                receipt_channel_id = None

    return EffectivePanelConfig(
        pasarguard_base_url=base.rstrip("/"),
        pasarguard_username=user,
        pasarguard_password=pw,
        default_group_ids=groups,
        panel_username_prefix=prefix,
        panel_username_start=panel_start,
        receipt_channel_id=receipt_channel_id,
    )


if TYPE_CHECKING:
    from pasarguard_client import PasarGuardClient


async def apply_panel_client_config(pg: PasarGuardClient, db: Database) -> None:
    """به‌روزرسانی کلاینت پنل از تنظیمات ذخیره‌شده در دیتابیس."""
    cfg = await load_effective_panel_config(db)
    if not panel_is_configured(cfg):
        raise RuntimeError("panel is not configured")
    await pg.reconfigure(
        cfg.pasarguard_base_url,
        cfg.pasarguard_username,
        cfg.pasarguard_password,
    )

# -*- coding: utf-8 -*-
"""پیکربندی دکمه‌های منوی اصلی — نام، فعال/غیرفعال، چیدمان."""

from __future__ import annotations

import json
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from button_styles import (
    DEFAULT_MAIN_MENU_STYLES,
    button_style_label,
    make_button,
    normalize_button_style,
    style_label_fa,
)
from database import Database

APP = "app"

MAIN_MENU_BUTTON_ORDER: list[str] = [
    "buy",
    "services",
    "account",
    "topup",
    "test",
    "guide",
    "support",
    "partner",
    "admin",
]

DEFAULT_MAIN_MENU_LAYOUT: list[list[str]] = [
    ["buy", "services"],
    ["account", "topup"],
    ["test", "guide"],
    ["support", "admin"],
]

MAIN_MENU_BUTTON_DEFS: dict[str, dict[str, Any]] = {
    "buy": {
        "default_label": "🛒 خرید سرویس",
        "callback": f"{APP}:buy",
        "admin_only": False,
        "partner_only": False,
    },
    "services": {
        "default_label": "📦 سرویس های من",
        "callback": f"{APP}:services",
        "admin_only": False,
        "partner_only": False,
    },
    "account": {
        "default_label": "👤 حساب کاربری",
        "callback": f"{APP}:account",
        "admin_only": False,
        "partner_only": False,
    },
    "topup": {
        "default_label": "💰 افزایش موجودی",
        "callback": f"{APP}:topup",
        "admin_only": False,
        "partner_only": False,
    },
    "support": {
        "default_label": "💬 پشتیبانی",
        "callback": f"{APP}:support",
        "admin_only": False,
        "partner_only": False,
    },
    "test": {
        "default_label": "🧪 اکانت تست",
        "callback": f"{APP}:test",
        "admin_only": False,
        "partner_only": False,
        "requires_test_eligible": True,
    },
    "guide": {
        "default_label": "📖 راهنمای اتصال",
        "callback": f"{APP}:guide",
        "admin_only": False,
        "partner_only": False,
    },
    "admin": {
        "default_label": "🛠 پنل ادمین",
        "callback": "adm:root",
        "admin_only": True,
        "partner_only": False,
    },
    "partner": {
        "default_label": "👥 پنل همکاری",
        "callback": f"{APP}:partner",
        "admin_only": False,
        "partner_only": True,
    },
}


def pair_inline_buttons(
    buttons: list[InlineKeyboardButton],
    *,
    per_row: int = 2,
    trailing: list[InlineKeyboardButton] | None = None,
) -> list[list[InlineKeyboardButton]]:
    """دکمه‌ها را دو تا دو تا (یا per_row) در ردیف می‌چیند."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for btn in buttons:
        row.append(btn)
        if len(row) >= per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if trailing:
        rows.append(trailing)
    return rows


def _main_menu_styles_map(buttons_cfg: dict[str, dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for bid in MAIN_MENU_BUTTON_DEFS:
        entry = buttons_cfg.get(bid) or {}
        style = normalize_button_style(entry.get("style"))
        if style:
            out[bid] = style
        elif DEFAULT_MAIN_MENU_STYLES.get(bid):
            out[bid] = DEFAULT_MAIN_MENU_STYLES[bid]
    return out


def default_main_menu_config() -> dict[str, Any]:
    buttons: dict[str, dict[str, Any]] = {}
    for bid, meta in MAIN_MENU_BUTTON_DEFS.items():
        buttons[bid] = {
            "enabled": True,
            "label": meta["default_label"],
            "style": DEFAULT_MAIN_MENU_STYLES.get(bid, ""),
        }
    return {"layout": DEFAULT_MAIN_MENU_LAYOUT, "buttons": buttons}


def _parse_config(raw: str) -> dict[str, Any]:
    default = default_main_menu_config()
    if not raw.strip():
        return default
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return default
    if not isinstance(data, dict):
        return default
    buttons = default["buttons"].copy()
    stored = data.get("buttons")
    if isinstance(stored, dict):
        for bid, meta in MAIN_MENU_BUTTON_DEFS.items():
            entry = stored.get(bid)
            if not isinstance(entry, dict):
                continue
            enabled = entry.get("enabled", buttons[bid]["enabled"])
            label = str(entry.get("label") or buttons[bid]["label"]).strip()
            if not label:
                label = meta["default_label"]
            style = normalize_button_style(entry.get("style")) or ""
            buttons[bid] = {"enabled": bool(enabled), "label": label[:64], "style": style}
    return {"layout": DEFAULT_MAIN_MENU_LAYOUT, "buttons": buttons}


def default_main_menu_entry(button_id: str) -> dict[str, Any]:
    meta = MAIN_MENU_BUTTON_DEFS.get(button_id, {})
    return {
        "enabled": True,
        "label": meta.get("default_label", button_id),
        "style": DEFAULT_MAIN_MENU_STYLES.get(button_id, ""),
    }


async def load_main_menu_config(db: Database) -> dict[str, Any]:
    raw = await db.get_setting("main_menu_buttons_json", "")
    return _parse_config(raw)


async def repair_stored_main_menu_layout(db: Database) -> None:
    """چیدمان ذخیره‌شدهٔ قدیمی (تک‌ستونی) را به حالت دو‌تایی اصلاح می‌کند."""
    cfg = await load_main_menu_config(db)
    await save_main_menu_config(db, cfg)


async def save_main_menu_config(db: Database, config: dict[str, Any]) -> None:
    stored = {
        "layout": DEFAULT_MAIN_MENU_LAYOUT,
        "buttons": config.get("buttons") or default_main_menu_config()["buttons"],
    }
    await db.set_setting(
        "main_menu_buttons_json",
        json.dumps(stored, ensure_ascii=False),
    )


async def build_main_menu_keyboard(
    db: Database,
    *,
    is_admin: bool,
    uid: int | None,
    is_partner: bool,
    test_eligible: bool,
) -> InlineKeyboardMarkup:
    cfg = await load_main_menu_config(db)
    buttons_cfg: dict[str, dict[str, Any]] = cfg["buttons"]
    visible: list[InlineKeyboardButton] = []

    for bid in MAIN_MENU_BUTTON_ORDER:
        meta = MAIN_MENU_BUTTON_DEFS.get(bid)
        if not meta:
            continue
        btn_cfg = buttons_cfg.get(bid) or default_main_menu_entry(bid)
        if not btn_cfg.get("enabled", True):
            continue
        if meta.get("admin_only") and not is_admin:
            continue
        if meta.get("partner_only") and not is_partner:
            continue
        label = str(btn_cfg.get("label") or meta["default_label"])[:64]
        visible.append(
            make_button(
                label,
                callback_data=str(meta["callback"]),
                main_menu_button_id=bid,
            )
        )

    rows = pair_inline_buttons(visible, per_row=2)
    if not rows:
        rows = [
            [
                make_button(
                    MAIN_MENU_BUTTON_DEFS["buy"]["default_label"],
                    callback_data=MAIN_MENU_BUTTON_DEFS["buy"]["callback"],
                    main_menu_button_id="buy",
                )
            ]
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def color_table_button_label(key: str, main_menu_cfg: dict[str, Any] | None = None) -> str:
    if key.startswith("mm_"):
        bid = key[3:]
        if bid in MAIN_MENU_BUTTON_DEFS:
            entry = (main_menu_cfg or {}).get("buttons", {}).get(bid) or default_main_menu_entry(bid)
            return str(entry.get("label") or MAIN_MENU_BUTTON_DEFS[bid]["default_label"])
    return button_style_label(key)


async def admin_colors_table_kb(db: Database, page: int = 0) -> InlineKeyboardMarkup:
    from button_styles import (
        COLOR_PICK_OPTIONS,
        COLORS_TABLE_PAGE_SIZE,
        all_color_table_keys,
        clamp_colors_page,
        colors_table_page_count,
        get_effective_style,
    )

    main_menu_cfg = await load_main_menu_config(db)
    page = clamp_colors_page(page)
    keys = all_color_table_keys()
    total_pages = colors_table_page_count()
    start = page * COLORS_TABLE_PAGE_SIZE
    chunk = keys[start : start + COLORS_TABLE_PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    for key in chunk:
        cur = (get_effective_style(key) or "primary").strip().lower()
        label = color_table_button_label(key, main_menu_cfg)[:22]
        row: list[InlineKeyboardButton] = [
            InlineKeyboardButton(
                text=label,
                callback_data=f"adm:colors:noop:{page}:{key}",
            ),
        ]
        for token, title, tg_style in COLOR_PICK_OPTIONS:
            active = bool(cur) and cur == token
            btn_text = f"• {title}" if active else title
            row.append(
                make_button(
                    btn_text,
                    callback_data=f"adm:colors:apply:{page}:{token}:{key}",
                    style=tg_style,
                )
            )
        rows.append(row)
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            make_button("◀️ قبلی", callback_data=f"adm:colors:pg:{page - 1}", style_key="admin_nav")
        )
    nav.append(
        make_button(
            f"📄 {page + 1}/{total_pages}",
            callback_data=f"adm:colors:pg:{page}",
            style_key="admin_nav",
        )
    )
    if page < total_pages - 1:
        nav.append(
            make_button("بعدی ▶️", callback_data=f"adm:colors:pg:{page + 1}", style_key="admin_nav")
        )
    if nav:
        rows.append(nav)
    rows.append([make_button("⬅️ بازگشت", callback_data="adm:root", style_key="admin_nav")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_main_buttons_kb(config: dict[str, Any]) -> InlineKeyboardMarkup:
    buttons_cfg = config.get("buttons") or {}
    items: list[InlineKeyboardButton] = []
    for bid, meta in MAIN_MENU_BUTTON_DEFS.items():
        if bid in ("partner", "admin"):
            continue
        entry = buttons_cfg.get(bid) or {"enabled": True, "label": meta["default_label"]}
        enabled = bool(entry.get("enabled", True))
        label = str(entry.get("label") or meta["default_label"])[:32]
        status = "🟢" if enabled else "⚪"
        items.append(
            make_button(
                f"{status} {label}",
                callback_data=f"adm:mbtn:pick:{bid}",
                main_menu_button_id=bid,
            )
        )
    items.append(make_button("⬅️ بازگشت", callback_data="adm:root", style_key="admin_nav"))
    return InlineKeyboardMarkup(inline_keyboard=pair_inline_buttons(items, per_row=2))


def admin_main_button_edit_kb(button_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=pair_inline_buttons(
            [
                make_button("✏️ تغییر نام", callback_data=f"adm:mbtn:rename:{button_id}", style_key="admin_nav"),
                make_button("🔄 روشن/خاموش", callback_data=f"adm:mbtn:toggle:{button_id}", style_key="admin_nav"),
                make_button("⬅️ بازگشت", callback_data="adm:btns", style_key="admin_nav"),
            ],
            per_row=2,
        )
    )


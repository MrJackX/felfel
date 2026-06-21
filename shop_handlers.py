from __future__ import annotations

import asyncio
import datetime as dt
import html
import io
import json
import math
import re
import time
import zoneinfo
from typing import Any

import jdatetime as jdt
import qrcode
from aiogram import F, Router
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Settings
from database import Database
from pasarguard_client import PasarGuardAPIError, PasarGuardClient, subscription_url_with_base
from runtime_config import (
    apply_panel_client_config,
    get_welcome_message,
    load_effective_panel_config,
    panel_is_configured,
)
from bot_texts import (
    T,
    buy_payment_choice_text,
    fmt_admin_bot_settings,
    fmt_admin_channel,
    fmt_admin_colors_table,
    fmt_admin_financial,
    fmt_admin_panel_menu,
    fmt_admin_shop,
    fmt_admin_test,
    notif_caption_extra_receipt,
    notif_caption_extra_wallet,
    notif_caption_topup,
    notif_caption_topup_short,
    status_label_fa,
)
from button_styles import (
    COLOR_PICK_TOKENS,
    USER_COLOR_TABLE_KEYS,
    button_style_label,
    clamp_colors_page,
    colors_table_page_count,
    get_effective_style,
    make_button,
    set_global_button_style,
    style_label_fa,
)
from menu_config import (
    MAIN_MENU_BUTTON_DEFS,
    admin_colors_table_kb,
    admin_main_button_edit_kb,
    admin_main_buttons_kb,
    build_main_menu_keyboard,
    default_main_menu_entry,
    load_main_menu_config,
    pair_inline_buttons,
    save_main_menu_config,
)
from buy_packages import (
    BuyPackage,
    format_packages_admin_current,
    format_packages_preview_fa,
    packages_to_json,
    parse_admin_packages_text,
    parse_packages_from_json,
)
from volume_discount import (
    compute_volume_price,
    format_tiers_preview_fa,
    parse_admin_discount_text,
    parse_tiers_from_json,
    tiers_to_json,
)
from nowpayments_client import NOWPaymentsClient, NOWPaymentsError

APP = "app"
SERVICES_PER_PAGE = 10
_USER_BUYS_LIST_LIMIT = 500
WALLET_PAY_DELAY_SEC = 15.0


def _ib(
    text: str,
    callback_data: str,
    *,
    style_key: str | None = None,
    style: str | None = None,
) -> InlineKeyboardButton:
    return make_button(text, callback_data=callback_data, style_key=style_key, style=style)


def _menu_kb(
    buttons: list[InlineKeyboardButton],
    *,
    back: InlineKeyboardButton | None = None,
    per_row: int = 2,
) -> InlineKeyboardMarkup:
    items = list(buttons)
    if back is not None:
        items.append(back)
    return InlineKeyboardMarkup(inline_keyboard=pair_inline_buttons(items, per_row=per_row))
_wallet_pay_in_progress: set[int] = set()
_wallet_pay_cooldown_until: dict[int, float] = {}
_admin_export_in_progress: set[int] = set()

_PD = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_EN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def _to_en_digits(s: str) -> str:
    return (s or "").translate(_EN_DIGITS)


def _parse_credit_target_user_id(m: Message) -> int | None:
    fu = getattr(m, "forward_from", None)
    if fu is not None and getattr(fu, "id", None) is not None:
        t = int(fu.id)
        return t if t > 0 else None
    origin = getattr(m, "forward_origin", None)
    su = getattr(origin, "sender_user", None) if origin is not None else None
    if su is not None and getattr(su, "id", None) is not None:
        t = int(su.id)
        return t if t > 0 else None
    raw = _to_en_digits((m.text or "").strip())
    for ch in ("\u200c", "\u200f", "\u202a", "\u202c", "\ufeff", " ", "\n", "\t"):
        raw = raw.replace(ch, "")
    if not raw:
        return None
    m2 = re.search(r"\d{4,15}", raw)
    if not m2:
        return None
    t = int(m2.group(0))
    return t if 0 < t < (1 << 63) else None


def _parse_credit_amount_toman(text: str) -> float | None:
    t = _to_en_digits((text or "").strip()).replace("\u200c", "").replace(" ", "")
    t = t.replace("٫", ".").replace("،", "").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _fa_digits(s: str) -> str:
    return str(s).translate(_PD)


def _wallet_pay_gate(uid: int) -> str | None:
    if uid in _wallet_pay_in_progress:
        return "busy"
    if time.monotonic() < _wallet_pay_cooldown_until.get(uid, 0):
        return "cooldown"
    return None


async def _wallet_pay_wait(cq: CallbackQuery) -> bool:
    """قفل ضد اسپم + تأخیر ۱۵ ثانیه قبل از پردازش. False = مسدود."""
    uid = cq.from_user.id if cq.from_user else 0
    gate = _wallet_pay_gate(uid)
    if gate == "busy":
        await cq.answer(T.alert_wallet_busy, show_alert=True)
        return False
    if gate == "cooldown":
        await cq.answer(T.alert_wallet_cooldown, show_alert=True)
        return False
    _wallet_pay_in_progress.add(uid)
    await cq.answer(T.alert_please_wait)
    if cq.message:
        try:
            await cq.message.edit_text(T.msg_wallet_processing, parse_mode=ParseMode.HTML)
        except Exception:
            pass
    await asyncio.sleep(WALLET_PAY_DELAY_SEC)
    return True


def _wallet_pay_release(uid: int, *, apply_cooldown: bool) -> None:
    _wallet_pay_in_progress.discard(uid)
    if apply_cooldown:
        _wallet_pay_cooldown_until[uid] = time.monotonic() + WALLET_PAY_DELAY_SEC


def _parse_iso_datetime(val: Any) -> dt.datetime | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if int(val) == 0:
            return None
        try:
            return dt.datetime.fromtimestamp(int(val), tz=dt.timezone.utc)
        except (OSError, OverflowError):
            return None
    s = str(val).strip()
    if not s or s == "0":
        return None
    try:
        r = s.replace("Z", "+00:00")
        d = dt.datetime.fromisoformat(r)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _gregorian_to_jalali_str(d: dt.datetime, *, with_time: bool) -> str:
    d = d.astimezone(dt.timezone.utc)
    jd = jdt.datetime.fromgregorian(datetime=d)
    if with_time:
        return _fa_digits(jd.strftime("%Y/%m/%d %H:%M:%S"))
    return _fa_digits(jd.strftime("%Y/%m/%d"))


def _fmt_countdown_fa(delta: dt.timedelta) -> str:
    if delta.total_seconds() <= 0:
        return T.countdown_expired
    secs = int(delta.total_seconds())
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{_fa_digits(str(days))} {T.unit_day}")
    if hours:
        parts.append(f"{_fa_digits(str(hours))} {T.unit_hour}")
    parts.append(f"{_fa_digits(str(minutes))} {T.unit_minute}")
    return " ".join(parts) + T.countdown_suffix


def _traffic_block(live: dict[str, Any], order_gb: float | None) -> tuple[str, str, str, str]:
    """total label, used, remaining, percent text"""
    used_b = int(live.get("used_traffic") or 0)
    limit_b = int(live.get("data_limit") or 0)
    used_gb = round(used_b / (1024**3), 2)
    og = float(order_gb or 0)
    used_s = f"{_fa_digits(str(used_gb))} {T.unit_gb}"
    if limit_b <= 0:
        total = f"{_fa_digits(str(og))} {T.unit_gb}" if og > 0 else T.traffic_unlimited
        rem = T.traffic_unlimited
        pct = T.dash
    else:
        total = f"{_fa_digits(str(round(limit_b / (1024**3), 2)))} {T.unit_gb}"
        rem_b = max(0, limit_b - used_b)
        rem_gb = round(rem_b / (1024**3), 2)
        pct_val = (rem_b / limit_b * 100.0) if limit_b else 0.0
        rem = f"{_fa_digits(str(rem_gb))} {T.unit_gb}"
        pct = f"{_fa_digits(f'{pct_val:.2f}')}%"
    return total, used_s, rem, pct


def format_service_card_html(
    order: dict[str, Any],
    live: dict[str, Any],
    sub_updates: list[dict[str, Any]],
) -> str:
    un = str(live.get("username") or order.get("pasarguard_username") or "—")
    st = status_label_fa(str(live.get("status")))
    groups = live.get("group_names")
    if isinstance(groups, list) and groups:
        loc = html.escape(str(groups[0]))
    else:
        loc = T.svc_default_location
    gb_o = order.get("gb")
    amt_o = float(order.get("amount") or 0)
    try:
        gb_f = float(gb_o) if gb_o is not None else 0.0
    except (TypeError, ValueError):
        gb_f = 0.0
    product = T.svc_product_fmt.format(
        gb=_fa_digits(str(gb_f)).replace("٫", "."),
        amt=_fa_digits(f"{amt_o:,.0f}"),
    )
    total_tr, used_tr, rem_tr, pct_tr = _traffic_block(live, gb_f)

    exp_raw = live.get("expire")
    exp_dt = _parse_iso_datetime(exp_raw)
    now = dt.datetime.now(dt.timezone.utc)
    if exp_dt is None or exp_raw == 0 or str(exp_raw).strip() == "0":
        exp_line = T.svc_exp_unlimited
    else:
        exp_line = T.svc_exp_fmt.format(
            jalali=_gregorian_to_jalali_str(exp_dt, with_time=False),
            countdown=_fmt_countdown_fa(exp_dt - now),
        )

    st_raw = str(live.get("status") or "").lower()
    st_icon = T.icon_status_ok if st_raw == "active" else T.icon_status_warn

    online_at = _parse_iso_datetime(live.get("online_at"))
    if online_at:
        online_line = T.svc_online_fmt.format(jalali=_gregorian_to_jalali_str(online_at, with_time=True))
    else:
        online_line = T.svc_online_none

    sub_line = T.svc_sub_none
    client_line = T.svc_client_none
    if sub_updates:
        u0 = sub_updates[0]
        ca = _parse_iso_datetime(u0.get("created_at"))
        if ca:
            sub_line = T.svc_sub_fmt.format(jalali=_gregorian_to_jalali_str(ca, with_time=True))
        ua = u0.get("user_agent")
        if ua:
            client_line = T.svc_client_fmt.format(ua=html.escape(str(ua)[:200]))

    lines = [
        T.svc_status_line.format(icon=st_icon, status=st),
        T.svc_name_line.format(un=html.escape(un)),
        "",
        T.svc_loc_line.format(loc=loc),
        T.svc_product_line.format(product=product),
        "",
        T.svc_traffic_line.format(total=total_tr),
        T.svc_used_line.format(used=used_tr),
        T.svc_remain_line.format(rem=rem_tr, pct=pct_tr),
        "",
        exp_line,
        "",
        online_line,
        sub_line,
        client_line,
        "",
        T.svc_tip,
    ]
    return "\n".join(lines)


async def _user_buy_services(db: Database, uid: int) -> list[dict[str, Any]]:
    rows = await db.list_user_orders_done(uid, limit=_USER_BUYS_LIST_LIMIT)
    return [
        r
        for r in rows
        if r.get("kind") in ("buy_config", "test_config") and r.get("pasarguard_username")
    ]


def services_list_hint(buys: list[dict[str, Any]], *, page: int) -> str:
    total = len(buys)
    pages = max(1, math.ceil(total / SERVICES_PER_PAGE))
    page = max(0, min(page, pages - 1))
    hint = T.msg_services_pick_hint
    if pages > 1:
        hint = f"{hint}\n\n{T.msg_services_page.format(page=page + 1, pages=pages, n=total)}"
    return hint


def services_list_kb(buys: list[dict[str, Any]], *, page: int = 0) -> InlineKeyboardMarkup:
    total = len(buys)
    pages = max(1, math.ceil(total / SERVICES_PER_PAGE))
    page = max(0, min(page, pages - 1))
    start = page * SERVICES_PER_PAGE
    service_btns: list[InlineKeyboardButton] = []
    for order in buys[start : start + SERVICES_PER_PAGE]:
        oid = int(order["id"])
        un = str(order.get("pasarguard_username") or "")
        prefix = "🧪 " if order.get("kind") == "test_config" else "🔹 "
        label = f"{prefix}{un.replace('_', '.')}"
        if len(label) > 64:
            label = label[:61] + "…"
        service_btns.append(_ib(label, f"{APP}:svcopen:{oid}"))
    rows = pair_inline_buttons(service_btns, per_row=2)
    if pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(_ib(T.btn_page_prev, f"{APP}:svcpg:{page - 1}"))
        nav.append(
            _ib(T.btn_page_indicator.format(page=page + 1, pages=pages), f"{APP}:svcpg:{page}")
        )
        if page < pages - 1:
            nav.append(_ib(T.btn_page_next, f"{APP}:svcpg:{page + 1}"))
        rows.extend(pair_inline_buttons(nav, per_row=2))
    rows.extend(pair_inline_buttons([_ib(T.btn_main_home, f"{APP}:home")], per_row=2))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_actions_kb(order_id: int, *, is_test: bool = False) -> InlineKeyboardMarkup:
    p = f"{APP}:sv:{order_id}"
    row_vol: list[InlineKeyboardButton] = [_ib(T.btn_svc_revoke, f"{p}:s")]
    if not is_test:
        row_vol.insert(0, _ib(T.btn_svc_extra, f"{p}:v"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_ib(T.btn_svc_link, f"{p}:l"), _ib(T.btn_svc_qr, f"{p}:q")],
            row_vol,
            [_ib(T.btn_svc_disable, f"{p}:d"), _ib(T.btn_svc_enable, f"{p}:e")],
            [_ib(T.btn_svc_delete, f"{p}:x"), _ib(T.btn_main_home, f"{APP}:home")],
        ]
    )


def service_delete_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    p = f"{APP}:sv:{order_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_button(T.btn_svc_delete_yes, callback_data=f"{p}:xy", style_key="confirm_yes"),
                make_button(T.btn_svc_delete_no, callback_data=f"{p}:xn", style_key="confirm_no"),
            ]
        ]
    )


def service_disable_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    p = f"{APP}:sv:{order_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_button(T.btn_svc_disable_yes, callback_data=f"{p}:dy", style_key="confirm_yes"),
                make_button(T.btn_svc_disable_no, callback_data=f"{p}:dn", style_key="confirm_no"),
            ]
        ]
    )


def service_enable_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    p = f"{APP}:sv:{order_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_button(T.btn_svc_enable_yes, callback_data=f"{p}:ey", style_key="confirm_yes"),
                make_button(T.btn_svc_enable_no, callback_data=f"{p}:ex", style_key="confirm_no"),
            ]
        ]
    )


def _plain() -> dict[str, Any]:
    return {"parse_mode": None}


async def _edit_or_send_service_html(
    cq: CallbackQuery,
    chat_id: int,
    *,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """کارت/تأیید سرویس را روی همان پیام callback ویرایش می‌کند؛ اگر ممکن نبود، پیام جدید می‌فرستد."""
    body = text[:4096]
    if cq.message:
        try:
            await cq.message.edit_text(body, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            return
        except Exception:
            pass
    await cq.bot.send_message(chat_id, body, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def cmd_start(message: Message, settings: Settings, db: Database) -> None:
    uid = message.from_user.id if message.from_user else 0
    is_adm = await db.is_bot_admin(uid, settings.bot_admin_ids)
    if not is_adm and not await _channel_join_ok(message.bot, uid, db):
        kb = await _mandatory_channel_join_kb(message.bot, db)
        if kb:
            await message.answer(
                T.msg_channel_join_start,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
            )
            return
    extra = ""
    if not is_adm:
        m = await _maintenance_block(db, uid, settings=settings)
        if m:
            extra = f"\n\n{m}"
    text = await get_welcome_message(db)
    if extra:
        text += extra
    if is_adm:
        text += T.msg_cmd_start_admin_suffix
    kb = await main_menu_kb(is_adm, db, uid if uid else None)
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


def fsm_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[make_button(T.btn_cancel_fsm, callback_data=f"{APP}:cancel", style_key="cancel")]]
    )


async def buy_payment_method_kb(db: Database, *, show_promo: bool = True) -> InlineKeyboardMarkup:
    return await _payment_method_kb(db, pay_prefix="buypay", show_promo=show_promo)


async def extra_payment_method_kb(db: Database) -> InlineKeyboardMarkup:
    return await _payment_method_kb(db, pay_prefix="extrapay", show_promo=False)


async def _payment_method_kb(
    db: Database,
    *,
    pay_prefix: str,
    show_promo: bool = True,
) -> InlineKeyboardMarkup:
    card_ok = await _card_pay_available(db)
    crypto_ok = await _crypto_pay_available(db)
    nowpay_ok = await _nowpay_available(db)
    items: list[InlineKeyboardButton] = [
        _ib(T.btn_pay_wallet, f"{APP}:{pay_prefix}:wallet"),
    ]
    if card_ok:
        items.append(_ib(T.btn_pay_card, f"{APP}:{pay_prefix}:card"))
    if crypto_ok:
        items.append(_ib(T.btn_pay_crypto, f"{APP}:{pay_prefix}:crypto"))
    if nowpay_ok and pay_prefix == "buypay":
        items.append(_ib(T.btn_pay_nowpayments, f"{APP}:{pay_prefix}:nowpay"))
    if show_promo and pay_prefix == "buypay" and await db.get_bool_setting("discount_codes_enabled"):
        items.append(_ib(T.btn_apply_discount, f"{APP}:{pay_prefix}:promo"))
    items.append(_ib(T.btn_cancel_fsm, f"{APP}:cancel"))
    return InlineKeyboardMarkup(inline_keyboard=pair_inline_buttons(items, per_row=2))


async def topup_payment_method_kb(db: Database) -> InlineKeyboardMarkup | None:
    card_ok = await _card_pay_available(db)
    crypto_ok = await _crypto_pay_available(db)
    if not card_ok and not crypto_ok:
        return None
    items: list[InlineKeyboardButton] = []
    if card_ok:
        items.append(_ib(T.btn_pay_card, f"{APP}:topay:card"))
    if crypto_ok:
        items.append(_ib(T.btn_pay_crypto, f"{APP}:topay:crypto"))
    items.append(_ib(T.btn_cancel_fsm, f"{APP}:cancel"))
    return InlineKeyboardMarkup(inline_keyboard=pair_inline_buttons(items, per_row=2))


def admin_input_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[make_button(T.btn_cancel_admin_input, callback_data="adm:cancel", style_key="cancel")]]
    )


async def main_menu_kb(is_admin: bool, db: Database, uid: int | None = None) -> InlineKeyboardMarkup:
    test_eligible = True
    if uid is not None:
        test_eligible = not await db.user_has_test_service(uid)
    is_partner = bool(uid is not None and await db.is_partner(uid))
    return await build_main_menu_keyboard(
        db,
        is_admin=is_admin,
        uid=uid,
        is_partner=is_partner,
        test_eligible=test_eligible,
    )


def partner_panel_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_partner_settle, f"{APP}:partner:settle"),
            _ib(T.btn_main_home, f"{APP}:home"),
        ],
        per_row=2,
    )


def compact_home_kb() -> InlineKeyboardMarkup:
    """منوی کامل اصلی نیست — فقط برگشت به خانه (برای جریان «سرویس‌های من»)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[_ib(T.btn_main_home, f"{APP}:home")]]
    )


def admin_root_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_financial, "adm:fin"),
            _ib(T.btn_admin_shop, "adm:shop"),
            _ib(T.btn_admin_channel, "adm:chan"),
            _ib(T.btn_admin_admins, "adm:admins"),
            _ib(T.btn_admin_discount_codes, "adm:disc"),
            _ib(T.btn_admin_messaging, "adm:msg"),
            _ib(T.btn_admin_main_buttons, "adm:btns"),
            _ib(T.btn_admin_texts, "adm:texts"),
            _ib(T.btn_admin_user_stats, "adm:ustats"),
            _ib(T.btn_admin_partner_manage, "adm:pmenu"),
            _ib(T.btn_admin_panel_section, "adm:panel:menu"),
            _ib(T.btn_admin_bot_settings, "adm:bot"),
            _ib(T.btn_admin_test_section, "adm:test:menu"),
            _ib(T.btn_admin_colors, "adm:colors"),
            _ib(T.btn_admin_backup, "adm:bkp:menu"),
        ],
        back=_ib(T.btn_admin_home, f"{APP}:home", style_key="adm_home"),
    )


def admin_financial_kb(pending_count: int) -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_balance_list, "adm:b:ballist"),
            _ib(T.btn_admin_add_balance, "adm:b:addbal"),
            _ib(T.btn_admin_deduct_balance, "adm:b:dedbal"),
            _ib(T.btn_admin_orders.format(n=pending_count), "adm:b:orders"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


async def admin_shop_kb(db: Database) -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_product_settings, "adm:shop:product"),
            _ib(T.btn_admin_card_edit, "adm:b:card"),
            _ib(T.btn_admin_crypto_edit, "adm:b:trust"),
            _ib(T.btn_admin_nowpayments_key, "adm:b:nowpaykey"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


async def admin_shop_product_kb(db: Database) -> InlineKeyboardMarkup:
    pkg_mode = await _buy_sell_mode_packages(db)
    mode_label = T.label_buy_mode_packages if pkg_mode else T.label_buy_mode_volume
    return _menu_kb(
        [
            _ib(T.btn_admin_toggle_buy_mode.format(mode=mode_label), "adm:b:togglebuymode"),
            _ib(T.btn_admin_price_gb, "adm:b:price"),
            _ib(T.btn_admin_volume_discount, "adm:b:voldisc"),
            _ib(T.btn_admin_buy_packages, "adm:b:packages"),
        ],
        back=_ib(T.btn_admin_back, "adm:shop"),
    )


def admin_channel_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_chan_id, "adm:b:chanid"),
            _ib(T.btn_admin_chan_toggle, "adm:b:togglechan"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def admin_admins_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_list_admins, "adm:adm:list"),
            _ib(T.btn_admin_add_admin, "adm:adm:add"),
            _ib(T.btn_admin_remove_admin, "adm:adm:rm"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def admin_discount_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_create_discount, "adm:disc:add"),
            _ib(T.btn_admin_remove_discount, "adm:disc:rm"),
            _ib(T.btn_admin_list_discount, "adm:disc:list"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def admin_messaging_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_broadcast, "adm:msg:bcast"),
            _ib(T.btn_admin_message_user, "adm:msg:user"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def admin_texts_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_welcome_text, "adm:b:welcome"),
            _ib(T.btn_admin_support_text, "adm:b:support"),
            _ib(T.btn_admin_guide_text, "adm:b:guide"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def admin_bot_settings_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_maint, "adm:b:togglemaint"),
            _ib(T.btn_admin_maint_text, "adm:b:mtext"),
            _ib(T.btn_admin_card_toggle, "adm:b:togglecard"),
            _ib(T.btn_admin_crypto_toggle, "adm:b:togglecrypto"),
            _ib(T.btn_admin_toggle_buy, "adm:b:togglebuy"),
            _ib(T.btn_admin_nowpayments_toggle, "adm:b:togglenowpay"),
            _ib(T.btn_admin_discount_toggle, "adm:b:toggledisc"),
            _ib(T.btn_admin_receipt_channel, "adm:b:receiptchan"),
            _ib(T.btn_admin_receipt_admins, "adm:b:rcptadmins"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def admin_receipt_admins_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_receipt_admin_list, "adm:b:rcptadm:list"),
            _ib(T.btn_admin_receipt_admin_add, "adm:b:rcptadm:add"),
            _ib(T.btn_admin_receipt_admin_rm, "adm:b:rcptadm:rm"),
        ],
        back=_ib(T.btn_admin_back, "adm:bot"),
    )


def admin_test_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_test_gb, "adm:b:testgb"),
            _ib(T.btn_admin_reset_test, "adm:b:resettest"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def admin_settings_kb() -> InlineKeyboardMarkup:
    return admin_bot_settings_kb()


def admin_export_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [_ib(T.btn_admin_export_configs, "adm:export:run")],
        back=_ib(T.btn_admin_back, "adm:bot"),
    )


def admin_panel_unconfigured_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [_ib(T.btn_admin_panel_add, "adm:panel:add")],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def admin_panel_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_panel_add, "adm:panel:add"),
            _ib(T.btn_admin_panel_remove, "adm:panel:remove"),
            _ib(T.btn_admin_panel_url, "adm:panel:url"),
            _ib(T.btn_admin_panel_user, "adm:panel:user"),
            _ib(T.btn_admin_panel_pass, "adm:panel:pass"),
            _ib(T.btn_admin_panel_groups, "adm:panel:groups"),
            _ib(T.btn_admin_panel_prefix, "adm:panel:prefix"),
            _ib(T.btn_admin_panel_start, "adm:panel:start"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def partner_manage_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_admin_partner_price, "adm:p:price"),
            _ib(T.btn_admin_partner_add, "adm:p:add"),
            _ib(T.btn_admin_partner_list, "adm:p:list"),
            _ib(T.btn_admin_partner_usage, "adm:p:usage"),
            _ib(T.btn_admin_partner_volume_discount, "adm:p:voldisc"),
            _ib(T.btn_admin_partner_packages, "adm:p:packages"),
        ],
        back=_ib(T.btn_admin_back, "adm:root"),
    )


def _fmt_partner_gb(gb: float) -> str:
    return f"{int(gb)}" if gb == int(gb) else f"{gb:g}"


def partners_list_kb(partners: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    items: list[InlineKeyboardButton] = []
    for p in partners[:25]:
        tid = int(p["telegram_id"])
        items.append(_ib(f"{T.btn_admin_partner_remove} {tid}", f"adm:p:rm:{tid}"))
    rows = pair_inline_buttons(items, per_row=2)
    rows.extend(pair_inline_buttons([_ib(T.btn_admin_back, "adm:pmenu")], per_row=2))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_moderation_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                make_button(T.btn_order_approve, callback_data=f"adm:o:{order_id}:a", style="success"),
                make_button(T.btn_order_reject, callback_data=f"adm:o:{order_id}:r", style="danger"),
            ]
        ]
    )


class ShopBuyStates(StatesGroup):
    waiting_package = State()
    waiting_gb = State()
    waiting_payment_choice = State()
    waiting_promo_code = State()
    waiting_receipt = State()
    waiting_nowpay = State()


class ShopTopupStates(StatesGroup):
    waiting_amount = State()
    waiting_pay_kind = State()
    waiting_receipt = State()


class ShopServiceExtraStates(StatesGroup):
    waiting_gb = State()
    waiting_payment_choice = State()
    waiting_receipt = State()


class AdminBotInputStates(StatesGroup):
    price_per_gb = State()
    volume_discount_tiers = State()
    partner_price_per_gb = State()
    partner_add = State()
    partner_volume_discount_tiers = State()
    partner_buy_packages = State()
    test_service_gb = State()
    reset_test_user = State()
    trust_wallet = State()
    payment_card = State()
    channel_join_id = State()
    maintenance_message = State()
    buy_packages = State()
    welcome_message = State()
    support_text = State()
    connection_guide_text = State()
    nowpayments_api_key = State()
    main_button_rename = State()
    broadcast_message = State()
    message_user_id = State()
    message_user_text = State()
    add_admin_id = State()
    remove_admin_id = State()
    create_discount_code = State()
    remove_discount_code = State()
    user_stats_lookup = State()
    panel_base_url = State()
    panel_username = State()
    panel_password = State()
    panel_username_prefix = State()
    panel_username_start = State()
    receipt_channel_id = State()
    receipt_admin_add = State()
    receipt_admin_rm = State()


class AdminCreditUserStates(StatesGroup):
    waiting_target_id = State()
    waiting_amount = State()


class AdminDeductUserStates(StatesGroup):
    waiting_target_id = State()
    waiting_amount = State()


class AdminFilter(Filter):
    def __init__(self, settings: Settings, db: Database):
        self._settings = settings
        self._db = db

    async def __call__(self, message: Message) -> bool:
        u = message.from_user
        if not u:
            return False
        return await self._db.is_bot_admin(u.id, self._settings.bot_admin_ids)


async def _is_admin(user_id: int | None, settings: Settings, db: Database) -> bool:
    if user_id is None:
        return False
    return await db.is_bot_admin(user_id, settings.bot_admin_ids)


async def _maintenance_block(
    db: Database,
    user_id: int | None = None,
    *,
    settings: Settings | None = None,
) -> str | None:
    if settings is not None and user_id is not None and await _is_admin(user_id, settings, db):
        return None
    if await db.get_bool_setting("maintenance_mode"):
        msg = await db.get_setting("maintenance_message", "")
        return msg.strip() or T.default_maintenance
    return None


async def _buying_blocked(db: Database) -> bool:
    return await db.get_bool_setting("buying_disabled")


def _valid_invite_url(url: str) -> bool:
    u = url.strip()
    return u.startswith("http://") or u.startswith("https://")


def _validate_chan_id(s: str) -> bool:
    t = s.strip()
    if t.startswith("@") and len(t) >= 4:
        return True
    if t.lstrip("-").isdigit():
        try:
            return int(t) < 0
        except ValueError:
            return False
    return False


def _channel_raw_to_chat_id(raw: str) -> str | int:
    if raw.lstrip("-").isdigit():
        try:
            return int(raw)
        except ValueError:
            return raw
    return raw


async def _resolve_channel_open_url(bot: Any, raw: str, *, fallback_url: str = "") -> tuple[str, str] | None:
    """لینک باز شدن مستقیم کانال و عنوان دکمه؛ بدون نمایش URL در متن پیام."""
    if raw.startswith("@") and len(raw) >= 4:
        return f"https://t.me/{raw[1:]}", raw
    chat_id = _channel_raw_to_chat_id(raw)
    try:
        chat = await bot.get_chat(chat_id)
        title = (getattr(chat, "title", None) or raw).strip()
        username = (getattr(chat, "username", None) or "").strip()
        if username:
            return f"https://t.me/{username}", title
        invite = (getattr(chat, "invite_link", None) or "").strip()
        if _valid_invite_url(invite):
            return invite, title
    except Exception:
        pass
    fb = fallback_url.strip()
    if _valid_invite_url(fb):
        return fb, raw
    return None


async def _mandatory_channel_join_kb(bot: Any, db: Database) -> InlineKeyboardMarkup | None:
    channel_ids = await db.get_mandatory_channel_ids()
    if not channel_ids:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for index, raw in enumerate(channel_ids, start=1):
        resolved = await _resolve_channel_open_url(bot, raw)
        if not resolved:
            continue
        url, _label = resolved
        btn_text = T.btn_join_channel if len(channel_ids) == 1 else f"channel {index}"
        rows.append([make_button(btn_text, url=url, style_key="channel_join")])
    if not rows:
        return None
    rows.append([make_button(T.btn_check_channel_join, callback_data=f"{APP}:checkjoin", style_key="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _channel_join_ok(bot: Any, uid: int, db: Database) -> bool:
    if not await db.get_bool_setting("channel_join_required"):
        return True
    channel_ids = await db.get_mandatory_channel_ids()
    if not channel_ids:
        return True
    for raw in channel_ids:
        chat_id: str | int = raw
        if raw.lstrip("-").isdigit():
            try:
                chat_id = int(raw)
            except ValueError:
                chat_id = raw
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=uid)
        except Exception:
            continue
        st = member.status
        if st in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
            return False
        if st == ChatMemberStatus.RESTRICTED:
            if not bool(getattr(member, "is_member", True)):
                return False
    return True


async def _callback_blocked_by_channel(cq: CallbackQuery, settings: Settings, db: Database) -> bool:
    """اگر کاربر عضو کانال اجباری نباشد True برمی‌گرداند (پیام ارسال شده)."""
    uid = cq.from_user.id if cq.from_user else 0
    if await _is_admin(uid, settings, db):
        return False
    if await _channel_join_ok(cq.bot, uid, db):
        return False
    kb = await _mandatory_channel_join_kb(cq.bot, db)
    if cq.message:
        await cq.message.answer(
            T.msg_channel_join_required,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    return True


async def _payment_instruction_html_for_kind(db: Database, kind: str) -> str:
    """kind: card | crypto — فقط همان بلوک؛ اگر خالی باشد رشتهٔ خالی."""
    if kind == "card":
        if not await db.get_bool_setting("show_payment_card"):
            return ""
        c = (await db.get_setting("payment_card_text", "")).strip()
        if not c:
            return ""
        return f"\n\n🏦 <b>شماره کارت و واریز بانکی</b>\n{html.escape(c)}\n\n"
    if kind == "crypto":
        if not await db.get_bool_setting("show_crypto_text"):
            return ""
        tw = (await db.get_setting("trust_wallet_text", "")).strip()
        if not tw:
            return ""
        return f"\n\n💎 <b>ارز دیجیتال</b>\n{html.escape(tw)}\n\n"
    return ""


async def _card_pay_available(db: Database) -> bool:
    return await db.get_bool_setting("show_payment_card") and bool(
        (await db.get_setting("payment_card_text", "")).strip()
    )


async def _crypto_pay_available(db: Database) -> bool:
    return await db.get_bool_setting("show_crypto_text") and bool(
        (await db.get_setting("trust_wallet_text", "")).strip()
    )


async def _nowpay_available(db: Database) -> bool:
    if not await db.get_bool_setting("show_nowpayments"):
        return False
    key = (await db.get_setting("nowpayments_api_key", "")).strip()
    return bool(key)


def _parse_channel_ids_text(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw or raw == "-":
        return []
    parts = re.split(r"[\n,;]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _channels_preview(ids: list[str]) -> str:
    if not ids:
        return "—"
    joined = "\n".join(ids)
    if len(joined) > 200:
        return joined[:197] + "…"
    return joined


def _apply_promo_percent(amount: float, promo_pct: float) -> float:
    if promo_pct <= 0:
        return amount
    return max(0.0, amount * (1.0 - promo_pct / 100.0))


async def _nowpayments_client(db: Database) -> NOWPaymentsClient:
    key = (await db.get_setting("nowpayments_api_key", "")).strip()
    return NOWPaymentsClient(key)


async def _toman_to_usd_amount(db: Database, toman: float) -> float:
    rate = await db.get_float_setting("nowpayments_usd_rate", 50_000.0)
    if rate <= 0:
        rate = 50_000.0
    return max(0.01, float(toman) / rate)


def _buy_order_extra_promo(data: dict[str, Any]) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    code = str(data.get("promo_code") or "").strip()
    pct = float(data.get("promo_percent") or 0)
    if code and pct > 0:
        extra["promo_code"] = code
        extra["promo_percent"] = pct
    return extra


async def _consume_order_promo(db: Database, extra: dict[str, Any] | None) -> None:
    if not extra:
        return
    code = str(extra.get("promo_code") or "").strip()
    if code:
        await db.use_discount_code(code)


def nowpay_check_kb(order_id: int, pay_url: str) -> InlineKeyboardMarkup:
    items: list[InlineKeyboardButton] = []
    if pay_url.startswith("http://") or pay_url.startswith("https://"):
        items.append(make_button(T.btn_pay_nowpayments, url=pay_url, style_key="pay_nowpay"))
    items.append(_ib(T.btn_check_nowpay, f"{APP}:nowcheck:{order_id}"))
    items.append(_ib(T.btn_cancel_fsm, f"{APP}:cancel"))
    return InlineKeyboardMarkup(inline_keyboard=pair_inline_buttons(items, per_row=2))


async def _buy_receipt_step_html(db: Database, *, amount: float, gb: float, kind: str) -> str:
    inst = await _payment_instruction_html_for_kind(db, kind)
    if not inst.strip():
        inst = "\n"
    return T.msg_buy_receipt_step.format(amount=amount, gb=gb, instructions=inst)


async def _topup_receipt_step_html(db: Database, *, amt: float, kind: str) -> str:
    inst = await _payment_instruction_html_for_kind(db, kind)
    if not inst.strip():
        inst = "\n"
    return T.msg_topup_receipt_step.format(amt=amt, instructions=inst)


async def _extra_receipt_step_html(
    db: Database, *, amount: float, gb: float, kind: str, panel_user: str
) -> str:
    inst = await _payment_instruction_html_for_kind(db, kind)
    if not inst.strip():
        inst = "\n"
    return T.msg_extra_receipt_step.format(
        amount=amount,
        gb=gb,
        panel_user=html.escape(panel_user, quote=False),
        instructions=inst,
    )


async def _flow_edit(
    bot: Any,
    state: FSMContext,
    *,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = ParseMode.HTML,
) -> bool:
    data = await state.get_data()
    cid = data.get("flow_chat_id")
    mid = data.get("flow_message_id")
    if cid is None or mid is None:
        return False
    try:
        await bot.edit_message_text(
            chat_id=int(cid),
            message_id=int(mid),
            text=text[:4096],
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return True
    except Exception:
        return False


async def _flow_set_anchor(state: FSMContext, msg: Message) -> None:
    await state.update_data(flow_chat_id=msg.chat.id, flow_message_id=msg.message_id)


async def _buy_open_receipt_flow(cq: CallbackQuery, state: FSMContext, db: Database, kind: str) -> None:
    if kind == "card":
        if not await _card_pay_available(db):
            await cq.answer(T.err_pay_card_unavailable, show_alert=True)
            return
    else:
        if not await _crypto_pay_available(db):
            await cq.answer(T.err_pay_crypto_unavailable, show_alert=True)
            return
    await cq.answer()
    data = await state.get_data()
    gb = float(data.get("gb", 0))
    amount = float(data.get("amount", 0))
    await state.update_data(receipt_kind=kind)
    await state.set_state(ShopBuyStates.waiting_receipt)
    text = await _buy_receipt_step_html(db, amount=amount, gb=gb, kind=kind)
    if cq.message:
        try:
            await cq.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=fsm_cancel_kb())
        except Exception:
            await cq.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=fsm_cancel_kb())
        await state.update_data(flow_chat_id=cq.message.chat.id, flow_message_id=cq.message.message_id)


async def _extra_open_receipt_flow(cq: CallbackQuery, state: FSMContext, db: Database, kind: str) -> None:
    if kind == "card":
        if not await _card_pay_available(db):
            await cq.answer(T.err_pay_card_unavailable, show_alert=True)
            return
    else:
        if not await _crypto_pay_available(db):
            await cq.answer(T.err_pay_crypto_unavailable, show_alert=True)
            return
    await cq.answer()
    data = await state.get_data()
    gb = float(data.get("gb", 0))
    amount = float(data.get("amount", 0))
    panel_user = str(data.get("extra_panel_username") or "").strip()
    await state.update_data(receipt_kind=kind)
    await state.set_state(ShopServiceExtraStates.waiting_receipt)
    text = await _extra_receipt_step_html(db, amount=amount, gb=gb, kind=kind, panel_user=panel_user)
    if cq.message:
        try:
            await cq.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=fsm_cancel_kb())
        except Exception:
            await cq.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=fsm_cancel_kb())
        await state.update_data(flow_chat_id=cq.message.chat.id, flow_message_id=cq.message.message_id)


async def _topup_open_receipt_flow(cq: CallbackQuery, state: FSMContext, db: Database, kind: str) -> None:
    if kind == "card":
        if not await _card_pay_available(db):
            await cq.answer(T.err_pay_card_unavailable, show_alert=True)
            return
    else:
        if not await _crypto_pay_available(db):
            await cq.answer(T.err_pay_crypto_unavailable, show_alert=True)
            return
    await cq.answer()
    data = await state.get_data()
    amt = float(data.get("topup_amount", 0))
    await state.update_data(receipt_kind=kind)
    await state.set_state(ShopTopupStates.waiting_receipt)
    text = await _topup_receipt_step_html(db, amt=amt, kind=kind)
    if cq.message:
        try:
            await cq.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=fsm_cancel_kb())
        except Exception:
            await cq.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=fsm_cancel_kb())
        await state.update_data(flow_chat_id=cq.message.chat.id, flow_message_id=cq.message.message_id)


def _chan_preview(raw_ch: str) -> str:
    ch_pv = raw_ch if raw_ch else "—"
    if len(ch_pv) > 96:
        ch_pv = ch_pv[:93] + "…"
    return html.escape(ch_pv, quote=False)


async def _admin_financial_html(db: Database) -> str:
    pending = await db.count_pending_orders()
    wallet_users = await db.count_users_with_balance(min_balance=0.01)
    return fmt_admin_financial(pending, wallet_users)


async def _load_buy_packages(db: Database) -> list[BuyPackage]:
    raw = await db.get_buy_packages_raw()
    return parse_packages_from_json(raw)


async def _load_partner_buy_packages(db: Database) -> list[BuyPackage]:
    raw = await db.get_partner_buy_packages_raw()
    return parse_packages_from_json(raw)


async def _load_packages_for_buyer(db: Database, uid: int) -> list[BuyPackage]:
    if await db.is_partner(uid):
        partner_pkgs = await _load_partner_buy_packages(db)
        if partner_pkgs:
            return partner_pkgs
    return await _load_buy_packages(db)


async def _buy_sell_mode_packages(db: Database) -> bool:
    return (await db.get_setting("buy_sell_mode", "volume")).strip().lower() == "packages"


async def _buy_offers_packages(db: Database) -> bool:
    if not await _buy_sell_mode_packages(db):
        return False
    return bool(await _load_buy_packages(db))


async def _buy_offers_packages_for_user(db: Database, uid: int) -> bool:
    if await db.is_partner(uid) and await _load_partner_buy_packages(db):
        return True
    return await _buy_offers_packages(db)


async def _admin_shop_html(db: Database) -> str:
    pkgs = await _load_buy_packages(db)
    buy_mode = T.label_buy_mode_packages if await _buy_sell_mode_packages(db) else T.label_buy_mode_volume
    ppg = await db.get_float_setting("price_per_gb", 0.0)
    return fmt_admin_shop(
        card_on=await db.get_bool_setting("show_payment_card"),
        crypto_on=await db.get_bool_setting("show_crypto_text"),
        nowpay_on=await db.get_bool_setting("show_nowpayments"),
        packages=html.escape(format_packages_preview_fa(pkgs), quote=False),
        buy_mode=buy_mode,
        ppg=ppg,
    )


async def _admin_shop_product_html(db: Database) -> str:
    pkgs = await _load_buy_packages(db)
    buy_mode = T.label_buy_mode_packages if await _buy_sell_mode_packages(db) else T.label_buy_mode_volume
    ppg = await db.get_float_setting("price_per_gb", 0.0)
    tiers = await _load_volume_discount_tiers(db)
    return T.msg_admin_shop_product_menu.format(
        buy_mode=buy_mode,
        ppg=ppg,
        volume_discount=html.escape(format_tiers_preview_fa(tiers), quote=False),
        packages=html.escape(format_packages_preview_fa(pkgs), quote=False),
    )


async def _admin_channel_html(db: Database) -> str:
    ids = await db.get_mandatory_channel_ids()
    preview = _channels_preview(ids)
    return fmt_admin_channel(
        chan_on=await db.get_bool_setting("channel_join_required"),
        chan_preview=html.escape(preview, quote=False),
        chan_count=len(ids),
    )


async def _admin_admins_html(db: Database, settings: Settings) -> str:
    db_ids = await db.list_db_admin_ids()
    return T.msg_admin_admins_menu.format(
        env_count=len(settings.bot_admin_ids),
        db_count=len(db_ids),
    )


async def _admin_bot_settings_html(db: Database) -> str:
    cfg = await load_effective_panel_config(db)
    receipt = str(cfg.receipt_channel_id) if cfg.receipt_channel_id is not None else "—"
    return fmt_admin_bot_settings(
        maint_on=await db.get_bool_setting("maintenance_mode"),
        card_on=await db.get_bool_setting("show_payment_card"),
        crypto_on=await db.get_bool_setting("show_crypto_text"),
        nowpay_on=await db.get_bool_setting("show_nowpayments"),
        buy_on=not await _buying_blocked(db),
        disc_on=await db.get_bool_setting("discount_codes_enabled"),
        receipt_preview=receipt,
    )


async def buy_packages_kb(db: Database, uid: int) -> InlineKeyboardMarkup:
    packages = await _load_packages_for_buyer(db, uid)
    items: list[InlineKeyboardButton] = []
    for idx, pkg in enumerate(packages):
        label = pkg.title.strip()
        btn_text = f"📦 {label}"
        if len(btn_text) > 64:
            btn_text = f"📦 {label[:61]}…"
        items.append(_ib(btn_text, f"{APP}:buypkg:{idx}"))
    items.append(_ib(T.btn_cancel_fsm, f"{APP}:cancel"))
    return InlineKeyboardMarkup(inline_keyboard=pair_inline_buttons(items, per_row=2))


def _buy_order_extra_from_fsm(
    data: dict[str, Any],
    *,
    receipt_kind: str = "",
    pay_wallet: bool = False,
) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    if receipt_kind in ("card", "crypto"):
        extra["receipt_pay"] = receipt_kind
    if pay_wallet:
        extra["pay_wallet"] = True
    if data.get("config_days") is not None:
        extra["config_days"] = int(data["config_days"])
    if data.get("package_title"):
        extra["package_title"] = str(data["package_title"])
    extra.update(_buy_order_extra_promo(data))
    return extra


async def _buy_config_days_from_data(data: dict[str, Any], db: Database) -> int:
    raw = data.get("config_days")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    return await db.get_int_setting("default_config_days", 30)


async def _proceed_buy_payment_step(
    bot: Any,
    state: FSMContext,
    db: Database,
    settings: Settings,
    uid: int,
    *,
    gb: float,
    fixed_price: float | None = None,
    config_days: int | None = None,
    package_title: str = "",
) -> None:
    amount, disc_pct, subtotal, ppg, is_partner = await _quote_buy_amount(db, gb, user_id=uid)
    if fixed_price is not None:
        amount = float(fixed_price)
        disc_pct = 0.0
        subtotal = amount
    data = await state.get_data()
    promo_pct = float(data.get("promo_percent") or 0)
    promo_code = str(data.get("promo_code") or "")
    if promo_pct > 0:
        amount = _apply_promo_percent(amount, promo_pct)
    upd: dict[str, Any] = {
        "gb": gb,
        "amount": amount,
        "price_per_gb": ppg,
        "discount_percent": disc_pct,
        "subtotal_before_discount": subtotal,
        "fixed_price": fixed_price,
    }
    if promo_code and promo_pct > 0:
        upd["promo_code"] = promo_code
        upd["promo_percent"] = promo_pct
    else:
        upd["promo_code"] = ""
        upd["promo_percent"] = 0.0
    if config_days is not None:
        upd["config_days"] = int(config_days)
    else:
        upd["config_days"] = await db.get_int_setting("default_config_days", 30)
    if package_title:
        upd["package_title"] = package_title
    await state.update_data(**upd)
    await state.set_state(ShopBuyStates.waiting_payment_choice)
    await db.ensure_user(uid)
    bal = await db.get_balance(uid)
    cfg_days = upd.get("config_days")
    pay_txt = buy_payment_choice_text(
        amount=amount,
        gb=gb,
        ppg=ppg,
        bal=bal,
        discount_percent=disc_pct,
        subtotal=subtotal,
        is_partner=is_partner,
        package_title=str(package_title or upd.get("package_title") or ""),
        config_days=int(cfg_days) if cfg_days is not None else None,
        promo_code=promo_code,
        promo_percent=promo_pct,
    )
    pay_kb = await buy_payment_method_kb(db)
    if not await _flow_edit(bot, state, text=pay_txt, reply_markup=pay_kb):
        am = await bot.send_message(uid, pay_txt, parse_mode=ParseMode.HTML, reply_markup=pay_kb)
        await _flow_set_anchor(state, am)


async def _admin_test_html(db: Database) -> str:
    return fmt_admin_test(
        test_gb=await db.get_float_setting("test_service_gb", 1.0),
    )


async def _admin_settings_html(db: Database) -> str:
    return await _admin_bot_settings_html(db)


async def _admin_panel_html(db: Database) -> str:
    cfg = await load_effective_panel_config(db)
    if not panel_is_configured(cfg):
        return T.msg_admin_panel_not_configured
    pw = cfg.pasarguard_password
    mask = "•" * min(8, len(pw)) if pw else "—"
    groups = ",".join(str(g) for g in cfg.default_group_ids)
    return fmt_admin_panel_menu(
        url=cfg.pasarguard_base_url,
        user=cfg.pasarguard_username,
        pass_mask=mask,
        groups=groups,
        prefix=cfg.panel_username_prefix,
        start_num=cfg.panel_username_start,
    )


async def _admin_panel_reply_kb(db: Database) -> InlineKeyboardMarkup:
    cfg = await load_effective_panel_config(db)
    if panel_is_configured(cfg):
        return admin_panel_kb()
    return admin_panel_unconfigured_kb()


def _parse_panel_groups_from_api(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("groups") or raw.get("items") or []
    else:
        items = []
    out: list[dict[str, Any]] = []
    for g in items:
        if not isinstance(g, dict):
            continue
        gid = g.get("id")
        if gid is None:
            continue
        try:
            gid_int = int(gid)
        except (TypeError, ValueError):
            continue
        name = str(g.get("name") or g.get("title") or f"Group {gid_int}")
        out.append({"id": gid_int, "name": name})
    return out


async def _fetch_panel_groups_list(pg: PasarGuardClient, db: Database) -> list[dict[str, Any]]:
    await apply_panel_client_config(pg, db)
    raw = await pg.list_groups_simple()
    return _parse_panel_groups_from_api(raw)


def admin_panel_groups_kb(groups: list[dict[str, Any]], selected: set[int]) -> InlineKeyboardMarkup:
    items: list[InlineKeyboardButton] = []
    for g in groups:
        gid = int(g["id"])
        mark = "✅" if gid in selected else "⬜"
        name = str(g.get("name") or gid)
        label = f"{mark} {name} ({gid})"
        if len(label) > 64:
            label = label[:61] + "…"
        items.append(_ib(label, f"adm:panel:grptgl:{gid}"))
    rows = pair_inline_buttons(items, per_row=2)
    rows.extend(pair_inline_buttons([_ib(T.btn_admin_back, "adm:panel:menu")], per_row=2))
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _admin_panel_groups_html(db: Database, groups: list[dict[str, Any]]) -> str:
    cfg = await load_effective_panel_config(db)
    selected = set(cfg.default_group_ids)
    lines = [T.msg_admin_panel_groups_pick, ""]
    for g in groups:
        gid = int(g["id"])
        mark = "✅" if gid in selected else "⬜"
        name = html.escape(str(g.get("name") or gid))
        lines.append(f"{mark} {name} — <code>{gid}</code>")
    return "\n".join(lines)


def _valid_panel_url(url: str) -> bool:
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")


async def _try_reconnect_panel(pg: PasarGuardClient, db: Database) -> str | None:
    try:
        await apply_panel_client_config(pg, db)
        await pg.get_me()
        return None
    except Exception as e:
        return str(e)[:300]


async def _show_panel_groups_picker(
    cq: CallbackQuery,
    *,
    pg: PasarGuardClient,
    db: Database,
) -> None:
    if not cq.message:
        return
    cfg = await load_effective_panel_config(db)
    if not panel_is_configured(cfg):
        await cq.message.edit_text(
            T.msg_admin_panel_not_configured,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_panel_unconfigured_kb(),
        )
        return
    try:
        groups = await _fetch_panel_groups_list(pg, db)
    except Exception as e:
        err = html.escape(str(e)[:300])
        await cq.message.edit_text(
            T.msg_admin_panel_groups_fail.format(err=err),
            parse_mode=ParseMode.HTML,
            reply_markup=await _admin_panel_reply_kb(db),
        )
        return
    if not groups:
        await cq.message.edit_text(
            T.msg_admin_panel_groups_empty,
            parse_mode=ParseMode.HTML,
            reply_markup=await _admin_panel_reply_kb(db),
        )
        return
    selected = set(cfg.default_group_ids)
    await cq.message.edit_text(
        await _admin_panel_groups_html(db, groups),
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel_groups_kb(groups, selected),
    )


def _panel_username_from_seq(prefix: str, seq: int) -> str:
    num = str(int(seq))
    max_prefix = max(1, 32 - len(num))
    p = re.sub(r"[^a-z0-9_]", "", prefix.lower())[:max_prefix] or "u"
    return f"{p}{num}"


def _comma_money_amount(n: float) -> str:
    return f"{int(round(n)):,}"


def _service_display_code(panel_username: str) -> str:
    return str(panel_username).replace("_", ".")


def _traffic_gb_label(gb: float) -> str:
    if math.isfinite(gb) and abs(gb - round(gb)) < 1e-6:
        return f"{int(round(gb))} گیگ"
    s = ("%g" % gb).replace(".", "٫")
    return f"{s} گیگ"


def _period_fa(days: int) -> str:
    if days <= 0:
        return "نامحدود"
    return f"{days} روزه"


def _invoice_caption_html(
    *,
    new_balance: float | None,
    amount: float,
    panel_username: str,
    days: int,
    gb: float,
    sub_url: str,
    include_buyer_footer: bool,
    buyer_tg_id: int,
    buyer_username_plain: str | None,
) -> str:
    period = _period_fa(days)
    traffic = _traffic_gb_label(gb)
    amt_s = _comma_money_amount(amount)
    lines: list[str] = [T.invoice_hashtag, ""]
    if new_balance is not None:
        lines.append(T.invoice_balance.format(bal=_comma_money_amount(new_balance)))
        lines.append("")
    lines.extend(
        [
            T.invoice_paid,
            "",
            T.invoice_svc_title,
            "",
            "",
            T.invoice_cost.format(amt=amt_s),
            T.invoice_code.format(code=html.escape(str(panel_username).strip())),
            T.invoice_period.format(period=html.escape(period)),
            T.invoice_traffic.format(traffic=html.escape(traffic)),
            "",
            T.invoice_link_intro,
            f"<code>{html.escape(sub_url)}</code>",
        ]
    )
    if include_buyer_footer:
        lines.append("")
        lines.append(html.escape(T.invoice_footer_id.format(uid=buyer_tg_id)))
        un = buyer_username_plain or "—"
        if buyer_username_plain and not un.startswith("@"):
            un = "@" + un
        lines.append(html.escape(T.invoice_footer_username.format(uname=un)))
    return "\n".join(lines)


async def _tg_buyer_username(bot: Any, uid: int) -> str | None:
    try:
        ch = await bot.get_chat(uid)
        return ch.username
    except Exception:
        return None


async def _send_subscription_qr_photo(
    bot: Any,
    chat_id: int | None,
    caption: str | None,
    sub_url: str,
) -> None:
    if chat_id is None or not str(sub_url).strip():
        return
    bio = io.BytesIO()
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(sub_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(bio, format="PNG")
    bio.seek(0)
    photo = BufferedInputFile(bio.read(), filename="subscription.png")
    cap = (caption or "").strip()
    if cap:
        cap = cap[:1024] if len(cap) > 1024 else cap
        await bot.send_photo(chat_id, photo, caption=cap, parse_mode=ParseMode.HTML)
    else:
        await bot.send_photo(chat_id, photo)


async def _post_channel_receipt_buy_approved(
    bot: Any,
    settings: Settings,
    db: Database,
    *,
    cap_ch: str,
    sub_abs: str,
) -> None:
    """فقط فاکتور/QR به کانال؛ ارسال رسید تأییدشده به کانال غیرفعال است."""
    cfg = await load_effective_panel_config(db)
    cid = cfg.receipt_channel_id
    if cid is None:
        return
    try:
        await _send_subscription_qr_photo(bot, cid, cap_ch, sub_abs)
    except Exception:
        pass


async def _post_channel_test_service(
    bot: Any,
    settings: Settings,
    db: Database,
    *,
    uid: int,
    gb: float,
    panel_username: str,
    tg_username: str | None,
) -> None:
    cfg = await load_effective_panel_config(db)
    cid = cfg.receipt_channel_id
    if cid is None:
        return
    if tg_username:
        tg_disp = f"@{html.escape(tg_username)}"
    else:
        tg_disp = "—"
    cap = T.notif_channel_test_service.format(
        uid=uid,
        gb=gb,
        panel_user=html.escape(panel_username),
        tg_user=tg_disp,
    )
    try:
        await bot.send_message(cid, cap, parse_mode=ParseMode.HTML)
    except Exception:
        pass


async def _post_channel_service_deleted(
    bot: Any,
    settings: Settings,
    db: Database,
    *,
    uid: int,
    panel_user: str,
    gb: float | None,
    tg_username: str | None,
) -> None:
    cfg = await load_effective_panel_config(db)
    cid = cfg.receipt_channel_id
    if cid is None:
        return
    if tg_username:
        tg_disp = f"@{html.escape(tg_username)}"
    else:
        tg_disp = "—"
    gb_val = gb if gb is not None else 0.0
    cap = T.notif_channel_service_deleted.format(
        uid=uid,
        tg_user=tg_disp,
        panel_user=html.escape(panel_user),
        gb=gb_val if gb_val == int(gb_val) else gb_val,
    )
    try:
        await bot.send_message(cid, cap, parse_mode=ParseMode.HTML)
    except Exception:
        pass


async def _user_main_menu(db: Database, settings: Settings, uid: int) -> InlineKeyboardMarkup:
    adm = await _is_admin(uid, settings, db)
    return await main_menu_kb(adm, db, uid if uid else None)


async def _partner_display_name(db: Database, bot: Any, uid: int) -> str:
    row = await db.get_partner(uid)
    if row:
        lbl = str(row.get("label") or "").strip()
        if lbl:
            return lbl
    un = await _tg_buyer_username(bot, uid)
    if un:
        return f"@{un}"
    return str(uid)


async def _partner_panel_html(db: Database, uid: int) -> str:
    row = await db.get_partner(uid)
    gb = float((row or {}).get("unsettled_gb") or 0)
    amount = float((row or {}).get("unsettled_amount") or 0)
    bal = await db.get_balance(uid)
    ppg, _ = await _price_per_gb_for_user(db, uid)
    return T.msg_partner_panel.format(
        gb=_fmt_partner_gb(gb), amount=amount, bal=bal, ppg=ppg
    )


async def _record_partner_purchase(
    db: Database, uid: int, *, gb: float, amount: float
) -> None:
    if gb <= 0:
        return
    if not await db.is_partner(uid):
        return
    await db.add_partner_usage(uid, gb=gb, amount=amount)


async def _post_channel_partner_settlement(
    bot: Any,
    settings: Settings,
    db: Database,
    *,
    name: str,
    uid: int,
    gb: float,
    amount: float,
) -> None:
    cfg = await load_effective_panel_config(db)
    cid = cfg.receipt_channel_id
    if cid is None:
        return
    gb_s = f"{int(gb)}" if gb == int(gb) else f"{gb:g}"
    cap = T.notif_partner_settlement_fmt.format(
        name=html.escape(name, quote=False),
        uid=uid,
        gb=gb_s,
        amount=amount,
    )
    try:
        await bot.send_message(cid, cap, parse_mode=ParseMode.HTML)
    except Exception:
        pass


async def _load_volume_discount_tiers(db: Database) -> list[tuple[float, float]]:
    raw = await db.get_volume_discount_tiers_raw()
    return parse_tiers_from_json(raw)


async def _load_partner_volume_discount_tiers(db: Database) -> list[tuple[float, float]]:
    raw = await db.get_partner_volume_discount_tiers_raw()
    return parse_tiers_from_json(raw)


async def _price_per_gb_for_user(db: Database, user_id: int) -> tuple[float, bool]:
    if await db.is_partner(user_id):
        ppg = await db.get_float_setting("partner_price_per_gb", 0.0)
        if ppg <= 0:
            ppg = await db.get_float_setting("price_per_gb", 100_000)
        return ppg, True
    return await db.get_float_setting("price_per_gb", 100_000), False


async def _quote_buy_amount(
    db: Database, gb: float, *, user_id: int | None = None
) -> tuple[float, float, float, float, bool]:
    """مبلغ نهایی، درصد تخفیف، قبل تخفیف، قیمت هر گیگ، آیا همکار."""
    if user_id is not None:
        ppg, is_partner = await _price_per_gb_for_user(db, user_id)
    else:
        ppg = await db.get_float_setting("price_per_gb", 100_000)
        is_partner = False
    if is_partner:
        tiers = await _load_partner_volume_discount_tiers(db)
        amount, disc_pct, subtotal = compute_volume_price(gb, ppg, tiers)
        return amount, disc_pct, subtotal, ppg, True
    tiers = await _load_volume_discount_tiers(db)
    amount, disc_pct, subtotal = compute_volume_price(gb, ppg, tiers)
    return amount, disc_pct, subtotal, ppg, False


async def _admin_partner_menu_html(db: Database) -> str:
    ppg = await db.get_float_setting("partner_price_per_gb", 0.0)
    if ppg <= 0:
        ppg = await db.get_float_setting("price_per_gb", 0.0)
    n = await db.count_partners()
    p_tiers = await _load_partner_volume_discount_tiers(db)
    p_pkgs = await _load_partner_buy_packages(db)
    return T.msg_admin_partner_menu.format(
        ppg=ppg,
        count=n,
        partner_volume_discount=html.escape(format_tiers_preview_fa(p_tiers), quote=False),
        partner_packages=html.escape(format_packages_preview_fa(p_pkgs), quote=False),
    )


def test_claim_kb() -> InlineKeyboardMarkup:
    return _menu_kb(
        [
            _ib(T.btn_test_claim, f"{APP}:testgo"),
            _ib(T.btn_cancel_fsm, f"{APP}:cancel"),
        ],
        per_row=2,
    )


def _orders_map_latest_by_username(orders: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for o in orders:
        un = str(o.get("pasarguard_username") or "").strip().lower()
        if un and un not in out:
            out[un] = o
    return out


def _panel_user_export_record(
    live: dict[str, Any],
    order: dict[str, Any] | None,
) -> dict[str, Any]:
    username = str(live.get("username") or "")
    limit_b = int(live.get("data_limit") or 0)
    rec: dict[str, Any] = {
        "panel_username": username,
        "status": live.get("status"),
        "expire": live.get("expire"),
        "data_limit_bytes": limit_b,
        "data_limit_gb": round(limit_b / (1024**3), 4) if limit_b > 0 else 0,
        "used_traffic_bytes": int(live.get("used_traffic") or 0),
        "lifetime_used_traffic_bytes": int(live.get("lifetime_used_traffic") or 0),
        "proxies": live.get("proxies"),
        "inbounds": live.get("inbounds"),
        "excluded_inbounds": live.get("excluded_inbounds"),
        "subscription_url": live.get("subscription_url"),
        "links": live.get("links"),
        "note": live.get("note"),
        "data_limit_reset_strategy": live.get("data_limit_reset_strategy"),
        "on_hold_expire_duration": live.get("on_hold_expire_duration"),
        "on_hold_timeout": live.get("on_hold_timeout"),
        "created_at": live.get("created_at"),
        "sub_updated_at": live.get("sub_updated_at"),
    }
    if order:
        extra = order.get("extra") or {}
        rec["bot"] = {
            "order_id": order.get("id"),
            "telegram_user_id": order.get("user_id"),
            "order_kind": order.get("kind"),
            "order_status": order.get("status"),
            "order_gb": order.get("gb"),
            "order_amount": order.get("amount"),
            "order_created_at": order.get("created_at"),
            "subscription_url_stored": order.get("subscription_url"),
            "extra": extra,
        }
    return rec


async def build_migration_export_payload(
    pg: PasarGuardClient,
    db: Database,
    settings: Settings,
) -> tuple[bytes, int, int]:
    """JSON خروجی + تعداد کاربران پنل + تعداد متصل به سفارش ربات."""
    panel_users = await pg.list_all_users()
    orders = await db.list_orders_with_panel_username()
    by_un = _orders_map_latest_by_username(orders)
    records: list[dict[str, Any]] = []
    linked = 0
    for live in panel_users:
        un = str(live.get("username") or "").strip().lower()
        order = by_un.get(un)
        if order:
            linked += 1
        records.append(_panel_user_export_record(live, order))
    cfg = await load_effective_panel_config(db)
    payload = {
        "format": "pasarguard_bot_migration_export",
        "version": 1,
        "exported_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "panel_base_url": cfg.pasarguard_base_url,
        "panel_username_prefix": cfg.panel_username_prefix,
        "default_group_ids": list(cfg.default_group_ids),
        "users_count": len(records),
        "users_linked_to_bot_orders": linked,
        "users": records,
        "pasarguard_create_user_hint": {
            "username": "panel_username",
            "expire": "unix timestamp or ISO; 0 = unlimited",
            "data_limit": "data_limit_bytes",
            "group_ids": "DEFAULT_GROUP_IDS in .env",
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    return raw, len(records), linked


async def _try_create_panel_user_for_buy(
    pg: PasarGuardClient,
    *,
    uid: int,
    gb: float,
    settings: Settings,
    db: Database,
    config_days: int | None = None,
) -> tuple[bool, str | None, str | None, int | None, PasarGuardAPIError | None]:
    if config_days is None:
        days = await db.get_int_setting("default_config_days", 30)
    else:
        days = int(config_days)
    d = None if days <= 0 else days
    limit_bytes = int(gb * (1024**3)) if gb > 0 else 0
    last_err: PasarGuardAPIError | None = None
    cfg = await load_effective_panel_config(db)
    if not panel_is_configured(cfg):
        return False, None, None, None, PasarGuardAPIError(T.err_panel_not_configured)
    try:
        await apply_panel_client_config(pg, db)
    except Exception as e:
        return False, None, None, None, PasarGuardAPIError(str(e)[:300])
    prefix = cfg.panel_username_prefix
    start = cfg.panel_username_start
    for _ in range(45):
        seq = await db.alloc_panel_username_number(start=start)
        cand = _panel_username_from_seq(prefix, seq)
        if not re.fullmatch(r"[a-z0-9_]{3,32}", cand):
            continue
        try:
            u = await pg.create_user(
                username=cand,
                days=d,
                data_limit_bytes=limit_bytes,
                group_ids=list(cfg.default_group_ids),
            )
            username = cand
            sub = str(u.get("subscription_url") or "")
            pid = u.get("id")
            return True, username, sub, int(pid) if pid is not None else None, None
        except PasarGuardAPIError as e:
            last_err = e
            if e.status_code == 409:
                continue
            break
    return False, None, None, None, last_err


async def _admin_receipt_buy_caption(db: Database, *, uid: int, amount: float) -> str:
    svc_n = await db.count_user_completed_buy_configs(uid)
    clock, jdate = _now_tehran_admin_receipt_stamp()
    return T.admin_receipt_buy_caption.format(
        uid=uid,
        referrals=0,
        svc_count=svc_n,
        amount=int(round(amount)),
        clock=clock,
        jdate=jdate,
    )


async def _admin_receipt_extra_caption(
    db: Database,
    *,
    uid: int,
    amount: float,
    gb: float,
    panel_user: str,
    parent_oid: int,
) -> str:
    svc_n = await db.count_user_completed_buy_configs(uid)
    clock, jdate = _now_tehran_admin_receipt_stamp()
    return T.admin_receipt_extra_caption.format(
        uid=uid,
        panel_user=panel_user,
        parent_oid=parent_oid,
        referrals=0,
        svc_count=svc_n,
        amount=int(round(amount)),
        gb=gb if gb == int(gb) else gb,
        clock=clock,
        jdate=jdate,
    )


async def _apply_extra_volume_gb(
    pg: PasarGuardClient,
    *,
    panel_username: str,
    gb: float,
    current_limit_b: int | None = None,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    try:
        if current_limit_b is None:
            live = await pg.get_user(panel_username)
            current_limit_b = int(live.get("data_limit") or 0)
        if current_limit_b <= 0:
            return False, None, "unlimited"
        add_bytes = int(gb * (1024**3))
        new_limit = current_limit_b + add_bytes
        live2 = await pg.modify_user(panel_username, {"data_limit": new_limit})
        return True, live2, None
    except PasarGuardAPIError as e:
        return False, None, str(e)


async def _post_channel_extra_volume(
    bot: Any,
    settings: Settings,
    db: Database,
    *,
    uid: int,
    panel_user: str,
    gb: float,
    amount: float,
    new_bal: float,
) -> None:
    cfg = await load_effective_panel_config(db)
    cid = cfg.receipt_channel_id
    if cid is None:
        return
    cap = notif_caption_extra_wallet(uid, panel_user=panel_user, gb=gb, amount=amount, new_bal=new_bal)
    try:
        await bot.send_message(cid, cap, parse_mode=ParseMode.HTML)
    except Exception:
        pass


def _now_tehran_admin_receipt_stamp() -> tuple[str, str]:
    tz = zoneinfo.ZoneInfo("Asia/Tehran")
    now = dt.datetime.now(tz)
    jd = jdt.datetime.fromgregorian(datetime=now)
    clock = _fa_digits(now.strftime("%H:%M:%S"))
    jdate = _fa_digits(jd.strftime("%Y/%m/%d"))
    return clock, jdate


async def _get_receipt_target_ids(settings: Settings, db: Database) -> list[int]:
    """لیست ادمین‌های رسید؛ اگر خالی باشد همه ادمین‌های env."""
    ids = await db.list_receipt_admin_ids()
    return ids if ids else list(settings.bot_admin_ids)


async def _notify_admins_text_order(
    bot: Any,
    settings: Settings,
    db: Database,
    *,
    order_id: int,
    caption: str,
) -> None:
    kb = order_moderation_kb(order_id)
    for aid in await _get_receipt_target_ids(settings, db):
        try:
            await bot.send_message(aid, caption, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception:
            pass
    cfg = await load_effective_panel_config(db)
    cid = cfg.receipt_channel_id
    if cid is not None:
        cap_ch = caption + T.notif_channel_order_copy
        try:
            await bot.send_message(cid, cap_ch, parse_mode=ParseMode.HTML)
        except Exception:
            pass


async def _notify_admins_new_order(
    message: Message,
    settings: Settings,
    db: Database,
    *,
    order_id: int,
    user_id: int,
    admin_caption: str,
    file_id: str,
    post_to_channel: bool = True,
    admin_parse_mode: str | None = ParseMode.HTML,
) -> None:
    bot = message.bot
    kb = order_moderation_kb(order_id)
    cap_ad = admin_caption[:1024] if len(admin_caption) > 1024 else admin_caption
    for aid in await _get_receipt_target_ids(settings, db):
        try:
            await bot.send_photo(
                aid,
                file_id,
                caption=cap_ad,
                parse_mode=admin_parse_mode,
                reply_markup=kb,
            )
        except Exception:
            try:
                await bot.send_message(
                    aid,
                    cap_ad + T.notif_photo_fail_suffix,
                    **_plain(),
                )
            except Exception:
                pass
    cfg = await load_effective_panel_config(db)
    cid = cfg.receipt_channel_id
    if post_to_channel and cid is not None:
        cap_ch = cap_ad + T.notif_channel_receipt_copy
        try:
            await bot.send_photo(cid, file_id, caption=cap_ch, parse_mode=admin_parse_mode)
        except Exception:
            try:
                await bot.send_message(cid, cap_ch, parse_mode=admin_parse_mode)
            except Exception:
                pass


async def _fetch_owned_buy_order(db: Database, order_id: int, uid: int) -> dict[str, Any] | None:
    row = await db.get_order(order_id)
    if not row or int(row.get("user_id", -1)) != uid:
        return None
    if row.get("kind") not in ("buy_config", "test_config") or row.get("status") != "approved_done":
        return None
    if not row.get("pasarguard_username"):
        return None
    return row


async def _support_message_html(db: Database) -> str:
    raw = (await db.get_setting("support_text", "")).strip()
    return raw or T.msg_support_default


async def _guide_message_html(db: Database) -> str:
    raw = (await db.get_setting("connection_guide_text", "")).strip()
    return raw or T.msg_guide_default


async def _format_user_stats_html(db: Database, tid: int) -> str:
    await db.ensure_user(tid)
    bal = await db.get_balance(tid)
    orders = await db.list_user_orders(tid, limit=15)
    configs = await db.list_user_orders_done(tid, limit=20)
    svc_count = len(configs)
    order_lines: list[str] = []
    for o in orders[:10]:
        gb = o.get("gb")
        gb_part = f"{gb} GB" if gb is not None else "—"
        order_lines.append(
            T.msg_user_stats_order_line.format(
                oid=o["id"],
                kind=html.escape(str(o.get("kind") or "")),
                status=html.escape(str(o.get("status") or "")),
                amount=float(o.get("amount") or 0),
                gb_part=gb_part,
            )
        )
    orders_block = "".join(order_lines) if order_lines else T.msg_user_stats_no_orders
    config_lines: list[str] = []
    for c in configs[:10]:
        un = str(c.get("pasarguard_username") or "—")
        gb = c.get("gb")
        gb_s = f"{gb:g}" if gb is not None else "—"
        config_lines.append(T.msg_user_stats_config_line.format(un=html.escape(un), gb=gb_s))
    configs_block = "".join(config_lines) if config_lines else T.msg_user_stats_no_orders
    return T.msg_user_stats_result.format(
        tid=tid,
        bal=bal,
        svc_count=svc_count,
        n=min(10, len(orders)),
        orders_block=orders_block,
        configs_block=configs_block,
    )


def register_shop_customer(
    router: Router,
    *,
    settings: Settings,
    pg: PasarGuardClient,
    db: Database,
) -> None:
    @router.callback_query(F.data == f"{APP}:checkjoin")
    async def app_check_channel_join(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        uid = cq.from_user.id if cq.from_user else 0
        adm = await _is_admin(uid, settings, db)
        if adm or await _channel_join_ok(cq.bot, uid, db):
            await cq.answer(T.cq_channel_join_ok, show_alert=True)
            text = await get_welcome_message(db)
            if adm:
                text += T.msg_cmd_start_admin_suffix
            kb = await main_menu_kb(adm, db, uid if uid else None)
            if cq.message:
                try:
                    await cq.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
                except Exception:
                    await cq.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        await cq.answer(T.err_channel_join_pending, show_alert=True)

    @router.callback_query(F.data == f"{APP}:home")
    async def app_home(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        uid = cq.from_user.id if cq.from_user else 0
        adm = await _is_admin(uid, settings, db)
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk and not adm:
            text = blk
        else:
            text = T.msg_home
            if adm:
                text += T.msg_home_admin_suffix
        kb = await main_menu_kb(adm, db, uid if uid else None)
        if cq.message:
            try:
                await cq.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                await cq.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await cq.answer(T.alert_no_message, show_alert=True)

    @router.callback_query(F.data == f"{APP}:partner")
    async def app_partner_panel(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        uid = cq.from_user.id if cq.from_user else 0
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk:
            await cq.answer()
            if cq.message:
                await cq.message.answer(blk, **_plain())
            return
        if not await db.is_partner(uid):
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        await cq.answer()
        text = await _partner_panel_html(db, uid)
        if cq.message:
            try:
                await cq.message.edit_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=partner_panel_kb(),
                )
            except Exception:
                await cq.message.answer(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=partner_panel_kb(),
                )

    @router.callback_query(F.data == f"{APP}:partner:settle")
    async def app_partner_settle(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        uid = cq.from_user.id if cq.from_user else 0
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk:
            await cq.answer(blk[:180], show_alert=True)
            return
        if not await db.is_partner(uid):
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        row = await db.get_partner(uid)
        if not row:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        gb_before = float(row.get("unsettled_gb") or 0)
        amt_before = float(row.get("unsettled_amount") or 0)
        if gb_before <= 0 and amt_before <= 0:
            await cq.answer(T.msg_partner_settle_empty, show_alert=True)
            return
        settled = await db.reset_partner_settlement(uid)
        if not settled:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        gb_s, amt_s, _label = settled
        name = await _partner_display_name(db, cq.bot, uid)
        await _post_channel_partner_settlement(
            cq.bot,
            settings,
            db,
            name=name,
            uid=uid,
            gb=gb_s,
            amount=amt_s,
        )
        gb_disp = f"{int(gb_s)}" if gb_s == int(gb_s) else f"{gb_s:g}"
        await cq.answer(f"✅ تسویه: {amt_s:,.0f} تومان — {gb_disp} گیگ")
        text = await _partner_panel_html(db, uid)
        if cq.message:
            try:
                await cq.message.edit_text(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=partner_panel_kb(),
                )
            except Exception:
                await cq.message.answer(
                    text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=partner_panel_kb(),
                )

    @router.callback_query(F.data == f"{APP}:cancel")
    async def app_cancel(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer(T.cq_cancelled)
        uid = cq.from_user.id if cq.from_user else 0
        adm = await _is_admin(uid, settings, db)
        kb = await main_menu_kb(adm, db, uid if uid else None)
        if cq.message:
            try:
                await cq.message.edit_text(
                    T.msg_cancel_done,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
            except Exception:
                await cq.message.answer(
                    T.msg_cancel_done,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )

    @router.callback_query(F.data == f"{APP}:test")
    async def app_test(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        uid = cq.from_user.id if cq.from_user else 0
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk:
            if cq.message:
                await cq.message.answer(blk, **_plain())
            return
        if await _callback_blocked_by_channel(cq, settings, db):
            return
        if await db.user_has_test_service(uid):
            await cq.answer(T.err_test_already_used, show_alert=True)
            return
        await state.clear()
        gb = await db.get_float_setting("test_service_gb", 1.0)
        if cq.message:
            await cq.message.answer(
                T.msg_test_intro.format(gb=gb),
                parse_mode=ParseMode.HTML,
                reply_markup=test_claim_kb(),
            )

    @router.callback_query(F.data == f"{APP}:testgo")
    async def app_test_go(cq: CallbackQuery, state: FSMContext) -> None:
        uid = cq.from_user.id if cq.from_user else 0
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk:
            await cq.answer(blk[:180], show_alert=True)
            return
        if await db.user_has_test_service(uid):
            await cq.answer(T.err_test_already_used, show_alert=True)
            return
        await cq.answer(T.alert_please_wait)
        await db.ensure_user(uid)
        gb = await db.get_float_setting("test_service_gb", 1.0)
        if gb < 0.1:
            gb = 1.0
        oid = await db.create_order(
            user_id=uid,
            kind="test_config",
            gb=gb,
            amount=0.0,
            status="pending",
            receipt_file_id=None,
            receipt_unique_id=None,
            receipt_chat_id=cq.message.chat.id if cq.message else None,
            receipt_message_id=None,
            extra={"test_service": True},
        )
        ok, username, sub_raw, pid, last_err = await _try_create_panel_user_for_buy(
            pg, uid=uid, gb=gb, settings=settings, db=db
        )
        adm = await _is_admin(uid, settings, db)
        kb = await main_menu_kb(adm, db, uid)
        if ok and username and sub_raw is not None:
            await db.update_order(
                oid,
                status="approved_done",
                pasarguard_username=username,
                subscription_url=sub_raw,
                panel_user_id=pid,
            )
            await db.mark_test_service_claimed(uid)
            uname = await _tg_buyer_username(cq.bot, uid)
            await _post_channel_test_service(
                cq.bot,
                settings,
                db,
                uid=uid,
                gb=gb,
                panel_username=username,
                tg_username=uname,
            )
            panel_cfg = await load_effective_panel_config(db)
            sub_abs = subscription_url_with_base(panel_cfg.pasarguard_base_url, sub_raw)
            days = await db.get_int_setting("default_config_days", 30)
            bal = await db.get_balance(uid)
            cap_user = _invoice_caption_html(
                new_balance=bal,
                amount=0.0,
                panel_username=username,
                days=days,
                gb=gb,
                sub_url=sub_abs,
                include_buyer_footer=False,
                buyer_tg_id=uid,
                buyer_username_plain=uname,
            )
            try:
                await _send_subscription_qr_photo(cq.bot, uid, cap_user, sub_abs)
            except Exception:
                pass
            done_txt = T.msg_test_done.format(gb=gb)
            if cq.message:
                try:
                    await cq.message.edit_text(done_txt, parse_mode=ParseMode.HTML, reply_markup=kb)
                except Exception:
                    await cq.message.answer(done_txt, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await cq.bot.send_message(uid, done_txt, parse_mode=ParseMode.HTML, reply_markup=kb)
            await state.clear()
            return
        await db.update_order(oid, status="rejected")
        err_txt = html.escape(str(last_err) if last_err else "?")
        fail = f"{T.msg_test_fail}\n\n{T.err_panel_html.format(err=err_txt)}"
        if cq.message:
            try:
                await cq.message.edit_text(fail, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                await cq.message.answer(fail, parse_mode=ParseMode.HTML, reply_markup=kb)
        await state.clear()

    @router.callback_query(F.data == f"{APP}:buy")
    async def app_buy(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        uid = cq.from_user.id if cq.from_user else 0
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk:
            await cq.message.answer(blk, **_plain()) if cq.message else None
            return
        if await _buying_blocked(db):
            if cq.message:
                await cq.message.answer(T.msg_buy_blocked, **_plain())
            return
        if await _callback_blocked_by_channel(cq, settings, db):
            return
        await state.clear()
        if await _buy_offers_packages_for_user(db, uid):
            if not await _load_packages_for_buyer(db, uid):
                if cq.message:
                    await cq.message.answer(
                        T.msg_buy_packages_mode_empty,
                        parse_mode=ParseMode.HTML,
                        reply_markup=await _user_main_menu(db, settings, uid),
                    )
                return
            await state.set_state(ShopBuyStates.waiting_package)
            pay_kb = await buy_packages_kb(db, uid)
            intro = T.msg_buy_packages_intro
            if cq.message:
                try:
                    await cq.message.edit_text(intro, parse_mode=ParseMode.HTML, reply_markup=pay_kb)
                    await state.update_data(
                        flow_chat_id=cq.message.chat.id,
                        flow_message_id=cq.message.message_id,
                    )
                except Exception:
                    msg = await cq.message.answer(intro, parse_mode=ParseMode.HTML, reply_markup=pay_kb)
                    await state.update_data(flow_chat_id=msg.chat.id, flow_message_id=msg.message_id)
            return
        await state.set_state(ShopBuyStates.waiting_gb)
        if cq.message:
            msg = await cq.message.answer(
                T.msg_buy_intro,
                parse_mode=ParseMode.HTML,
                reply_markup=fsm_cancel_kb(),
            )
            await state.update_data(flow_chat_id=msg.chat.id, flow_message_id=msg.message_id)

    @router.callback_query(ShopBuyStates.waiting_package, F.data.startswith(f"{APP}:buypkg:"))
    async def buy_pick_package(cq: CallbackQuery, state: FSMContext) -> None:
        uid = cq.from_user.id if cq.from_user else 0
        raw = (cq.data or "").split(":")
        if len(raw) < 3:
            await cq.answer()
            return
        try:
            pkg_idx = int(raw[2])
        except ValueError:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        packages = await _load_packages_for_buyer(db, uid)
        if pkg_idx < 0 or pkg_idx >= len(packages):
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        pkg = packages[pkg_idx]
        await cq.answer(T.alert_please_wait)
        await _proceed_buy_payment_step(
            cq.bot,
            state,
            db,
            settings,
            uid,
            gb=pkg.gb,
            fixed_price=pkg.fixed_price,
            config_days=pkg.days,
            package_title=pkg.title,
        )

    @router.callback_query(ShopBuyStates.waiting_package, F.data == f"{APP}:buycustom")
    async def buy_custom_gb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(ShopBuyStates.waiting_gb)
        if cq.message:
            try:
                await cq.message.edit_text(
                    T.msg_buy_intro,
                    parse_mode=ParseMode.HTML,
                    reply_markup=fsm_cancel_kb(),
                )
                await state.update_data(
                    flow_chat_id=cq.message.chat.id,
                    flow_message_id=cq.message.message_id,
                )
            except Exception:
                msg = await cq.message.answer(
                    T.msg_buy_intro,
                    parse_mode=ParseMode.HTML,
                    reply_markup=fsm_cancel_kb(),
                )
                await state.update_data(flow_chat_id=msg.chat.id, flow_message_id=msg.message_id)

    @router.callback_query(F.data == f"{APP}:account")
    async def app_account(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.clear()
        uid = cq.from_user.id if cq.from_user else 0
        await db.ensure_user(uid)
        bal = await db.get_balance(uid)
        if cq.message:
            await cq.message.answer(
                T.msg_account.format(uid=uid, bal=bal),
                parse_mode=ParseMode.HTML,
                reply_markup=await _user_main_menu(db, settings, uid),
            )

    @router.callback_query(F.data == f"{APP}:support")
    async def app_support(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.clear()
        uid = cq.from_user.id if cq.from_user else 0
        text = await _support_message_html(db)
        if cq.message:
            await cq.message.answer(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=await _user_main_menu(db, settings, uid),
            )

    @router.callback_query(F.data == f"{APP}:guide")
    async def app_guide(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.clear()
        uid = cq.from_user.id if cq.from_user else 0
        text = await _guide_message_html(db)
        if cq.message:
            await cq.message.answer(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=await _user_main_menu(db, settings, uid),
            )

    @router.callback_query(F.data == f"{APP}:services")
    async def app_services(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.clear()
        uid = cq.from_user.id if cq.from_user else 0
        buys = await _user_buy_services(db, uid)
        if not buys:
            if cq.message:
                await cq.message.answer(
                    T.msg_services_empty,
                    parse_mode=ParseMode.HTML,
                    reply_markup=compact_home_kb(),
                )
            return
        kb = services_list_kb(buys, page=0)
        hint = services_list_hint(buys, page=0)
        if cq.message:
            try:
                await cq.message.edit_text(hint, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                await cq.message.answer(hint, parse_mode=ParseMode.HTML, reply_markup=kb)

    @router.callback_query(F.data.startswith(f"{APP}:svcpg:"))
    async def app_services_page(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.clear()
        uid = cq.from_user.id if cq.from_user else 0
        raw = (cq.data or "")[len(f"{APP}:svcpg:") :]
        try:
            page = int(raw)
        except ValueError:
            page = 0
        buys = await _user_buy_services(db, uid)
        if not buys:
            if cq.message:
                await cq.message.answer(
                    T.msg_services_empty,
                    parse_mode=ParseMode.HTML,
                    reply_markup=compact_home_kb(),
                )
            return
        kb = services_list_kb(buys, page=page)
        hint = services_list_hint(buys, page=page)
        if cq.message:
            try:
                await cq.message.edit_text(hint, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                await cq.message.answer(hint, parse_mode=ParseMode.HTML, reply_markup=kb)

    @router.callback_query(F.data.startswith(f"{APP}:svcopen:"))
    async def app_service_open(cq: CallbackQuery) -> None:
        prefix = f"{APP}:svcopen:"
        raw_data = cq.data or ""
        if not raw_data.startswith(prefix):
            await cq.answer()
            return
        uid = cq.from_user.id if cq.from_user else None
        if uid is None:
            await cq.answer()
            return
        try:
            oid = int(raw_data[len(prefix) :])
        except ValueError:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        row = await _fetch_owned_buy_order(db, oid, uid)
        if not row:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        await cq.answer(T.alert_please_wait)
        un = str(row["pasarguard_username"])
        try:
            live = await pg.get_user(un)
            sub_u: list[dict[str, Any]] = []
            try:
                upd = await pg.list_sub_updates(un, limit=5)
                sub_u = list(upd.get("updates") or [])
            except PasarGuardAPIError:
                pass
            card = format_service_card_html(row, live, sub_u)
        except PasarGuardAPIError as e:
            try:
                await cq.bot.send_message(
                    uid,
                    T.msg_services_error.format(oid=oid, un=html.escape(un), err=html.escape(str(e))),
                    parse_mode=ParseMode.HTML,
                    reply_markup=compact_home_kb(),
                )
            except Exception:
                pass
            return
        try:
            await cq.bot.send_message(
                uid,
                card,
                parse_mode=ParseMode.HTML,
                reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config"),
            )
        except Exception:
            try:
                await cq.bot.send_message(
                    uid,
                    T.msg_services_open_fail,
                    reply_markup=compact_home_kb(),
                    **_plain(),
                )
            except Exception:
                pass

    @router.callback_query(F.data.regexp(rf"^{APP}:sv:\d+:(?:xy|xn|dy|dn|ey|ex|l|v|s|d|e|q|x)$"))
    async def app_service_action(cq: CallbackQuery, state: FSMContext) -> None:
        m = re.match(rf"^{APP}:sv:(\d+):(xy|xn|dy|dn|ey|ex|l|v|s|d|e|q|x)$", cq.data or "")
        if not m:
            await cq.answer()
            return
        oid = int(m.group(1))
        act = m.group(2)
        uid = cq.from_user.id if cq.from_user else 0
        row = await _fetch_owned_buy_order(db, oid, uid)
        if not row:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        un = str(row["pasarguard_username"])
        chat_id = uid

        try:
            if act == "l":
                await cq.answer()
                live = await pg.get_user(un)
                panel_cfg = await load_effective_panel_config(db)
                sub = subscription_url_with_base(panel_cfg.pasarguard_base_url, live.get("subscription_url") or "")
                await cq.bot.send_message(
                    chat_id,
                    T.msg_sub_link_title + (f"<code>{html.escape(sub)}</code>" if sub else T.dash),
                    parse_mode=ParseMode.HTML,
                )
                return

            if act == "q":
                await cq.answer()
                live = await pg.get_user(un)
                sub_raw = str(live.get("subscription_url") or "")
                panel_cfg = await load_effective_panel_config(db)
                sub = subscription_url_with_base(panel_cfg.pasarguard_base_url, sub_raw)
                if not sub:
                    await cq.bot.send_message(
                        chat_id,
                        T.msg_sub_link_title + T.dash,
                        parse_mode=ParseMode.HTML,
                    )
                    return
                try:
                    await _send_subscription_qr_photo(cq.bot, chat_id, None, sub)
                except Exception:
                    await cq.bot.send_message(
                        chat_id,
                        T.msg_sub_link_title + f"<code>{html.escape(sub)}</code>",
                        parse_mode=ParseMode.HTML,
                    )
                return

            if act == "v":
                if row.get("kind") == "test_config":
                    await cq.answer(T.err_test_no_extra, show_alert=True)
                    return
                blk = await _maintenance_block(db, uid, settings=settings)
                if blk:
                    await cq.answer(blk[:180], show_alert=True)
                    return
                await cq.answer()
                await state.set_state(ShopServiceExtraStates.waiting_gb)
                await state.set_data({"extra_order_id": oid, "extra_panel_username": un})
                await cq.bot.send_message(
                    chat_id,
                    T.msg_extra_gb_intro,
                    parse_mode=ParseMode.HTML,
                    reply_markup=fsm_cancel_kb(),
                )
                return

            if act == "s":
                await cq.answer()
                newu = await pg.revoke_subscription(un)
                sub_new = str(newu.get("subscription_url") or "")
                if sub_new:
                    await db.update_order(oid, subscription_url=sub_new)
                live2 = await pg.get_user(un)
                sub_u: list[dict[str, Any]] = []
                try:
                    sub_u = list((await pg.list_sub_updates(un, limit=5)).get("updates") or [])
                except PasarGuardAPIError:
                    pass
                card = format_service_card_html(row, live2, sub_u)
                await cq.bot.send_message(chat_id, T.msg_revoke_ok, **_plain())
                await cq.bot.send_message(chat_id, card, parse_mode=ParseMode.HTML, reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config"))
                return

            if act == "d":
                await cq.answer()
                await _edit_or_send_service_html(
                    cq,
                    chat_id,
                    text=T.msg_disable_confirm,
                    reply_markup=service_disable_confirm_kb(oid),
                )
                return

            if act == "e":
                await cq.answer()
                await _edit_or_send_service_html(
                    cq,
                    chat_id,
                    text=T.msg_enable_confirm,
                    reply_markup=service_enable_confirm_kb(oid),
                )
                return

            if act == "x":
                await cq.answer()
                await _edit_or_send_service_html(
                    cq,
                    chat_id,
                    text=T.msg_delete_confirm,
                    reply_markup=service_delete_confirm_kb(oid),
                )
                return

            if act == "dn":
                await cq.answer(T.cq_disable_cancel)
                live = await pg.get_user(un)
                sub_u: list[dict[str, Any]] = []
                try:
                    sub_u = list((await pg.list_sub_updates(un, limit=5)).get("updates") or [])
                except PasarGuardAPIError:
                    pass
                card = format_service_card_html(row, live, sub_u)
                await _edit_or_send_service_html(
                    cq, chat_id, text=card, reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config")
                )
                return

            if act == "ex":
                await cq.answer(T.cq_enable_cancel)
                live = await pg.get_user(un)
                sub_u: list[dict[str, Any]] = []
                try:
                    sub_u = list((await pg.list_sub_updates(un, limit=5)).get("updates") or [])
                except PasarGuardAPIError:
                    pass
                card = format_service_card_html(row, live, sub_u)
                await _edit_or_send_service_html(
                    cq, chat_id, text=card, reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config")
                )
                return

            if act == "dy":
                await cq.answer()
                await pg.modify_user(un, {"status": "disabled"})
                live2 = await pg.get_user(un)
                sub_u2: list[dict[str, Any]] = []
                try:
                    sub_u2 = list((await pg.list_sub_updates(un, limit=5)).get("updates") or [])
                except PasarGuardAPIError:
                    pass
                card2 = format_service_card_html(row, live2, sub_u2)
                head = T.msg_disabled_ok.format(un=html.escape(un))
                await _edit_or_send_service_html(
                    cq,
                    chat_id,
                    text=f"{head}\n\n{card2}",
                    reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config"),
                )
                return

            if act == "ey":
                await cq.answer()
                await pg.modify_user(un, {"status": "active"})
                live2 = await pg.get_user(un)
                sub_u2: list[dict[str, Any]] = []
                try:
                    sub_u2 = list((await pg.list_sub_updates(un, limit=5)).get("updates") or [])
                except PasarGuardAPIError:
                    pass
                card2 = format_service_card_html(row, live2, sub_u2)
                head = T.msg_enabled_ok.format(un=html.escape(un))
                await _edit_or_send_service_html(
                    cq,
                    chat_id,
                    text=f"{head}\n\n{card2}",
                    reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config"),
                )
                return

            if act == "xn":
                await cq.answer(T.cq_delete_cancel)
                live = await pg.get_user(un)
                sub_u: list[dict[str, Any]] = []
                try:
                    sub_u = list((await pg.list_sub_updates(un, limit=5)).get("updates") or [])
                except PasarGuardAPIError:
                    pass
                card = format_service_card_html(row, live, sub_u)
                await _edit_or_send_service_html(
                    cq, chat_id, text=card, reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config")
                )
                return

            if act == "xy":
                await cq.answer(T.alert_please_wait)
                try:
                    await pg.delete_user(un)
                except PasarGuardAPIError as e:
                    if e.status_code != 404:
                        raise
                await db.update_order(
                    oid,
                    status="user_deleted",
                    pasarguard_username="",
                    subscription_url="",
                )
                await db.reverse_partner_order_usage(row)
                tg_un = await _tg_buyer_username(cq.bot, uid)
                try:
                    gb_f = float(row.get("gb") or 0)
                except (TypeError, ValueError):
                    gb_f = 0.0
                await _post_channel_service_deleted(
                    cq.bot,
                    settings,
                    db,
                    uid=uid,
                    panel_user=un,
                    gb=gb_f,
                    tg_username=tg_un,
                )
                done_kb = InlineKeyboardMarkup(
                    inline_keyboard=pair_inline_buttons(
                        [
                            _ib(T.btn_services, f"{APP}:services"),
                            _ib(T.btn_main_home, f"{APP}:home"),
                        ],
                        per_row=2,
                    )
                )
                await _edit_or_send_service_html(
                    cq,
                    chat_id,
                    text=T.msg_deleted_ok.format(un=html.escape(un)),
                    reply_markup=done_kb,
                )
                return
        except PasarGuardAPIError as e:
            err = html.escape(str(e)[:500])
            try:
                await cq.bot.send_message(
                    chat_id,
                    T.err_panel_html.format(err=err),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

    @router.callback_query(F.data == f"{APP}:topup")
    async def app_topup(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        uid = cq.from_user.id if cq.from_user else 0
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk:
            if cq.message:
                await cq.message.answer(blk, **_plain())
            return
        if await _callback_blocked_by_channel(cq, settings, db):
            return
        await state.clear()
        await state.set_state(ShopTopupStates.waiting_amount)
        if cq.message:
            msg = await cq.message.answer(
                T.msg_topup_intro,
                parse_mode=ParseMode.HTML,
                reply_markup=fsm_cancel_kb(),
            )
        else:
            msg = await cq.bot.send_message(
                uid,
                T.msg_topup_intro,
                parse_mode=ParseMode.HTML,
                reply_markup=fsm_cancel_kb(),
            )
        await state.update_data(flow_chat_id=msg.chat.id, flow_message_id=msg.message_id)

    @router.message(ShopBuyStates.waiting_gb, F.text)
    async def buy_gb(m: Message, state: FSMContext) -> None:
        uid = m.from_user.id if m.from_user else 0
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk:
            await state.clear()
            await m.answer(blk, reply_markup=await _user_main_menu(db, settings, uid), **_plain())
            return
        try:
            gb = float((m.text or "").strip().replace(",", "."))
        except ValueError:
            if not await _flow_edit(
                m.bot,
                state,
                text=T.err_buy_gb_number,
                reply_markup=fsm_cancel_kb(),
                parse_mode=None,
            ):
                await m.answer(T.err_buy_gb_number, reply_markup=fsm_cancel_kb(), **_plain())
            return
        if gb < 0.1 or gb > 5000:
            if not await _flow_edit(
                m.bot,
                state,
                text=T.err_buy_gb_range,
                reply_markup=fsm_cancel_kb(),
                parse_mode=None,
            ):
                await m.answer(T.err_buy_gb_range, reply_markup=fsm_cancel_kb(), **_plain())
            return
        uid = m.from_user.id if m.from_user else 0
        await _proceed_buy_payment_step(m.bot, state, db, settings, uid, gb=gb)

    @router.message(ShopServiceExtraStates.waiting_gb, F.text)
    async def service_extra_gb(m: Message, state: FSMContext) -> None:
        uid = m.from_user.id if m.from_user else 0
        blk = await _maintenance_block(db, uid, settings=settings)
        if blk:
            await state.clear()
            await m.answer(blk, reply_markup=await _user_main_menu(db, settings, uid), **_plain())
            return
        data = await state.get_data()
        oid = int(data.get("extra_order_id") or 0)
        un = str(data.get("extra_panel_username") or "").strip()
        row = await _fetch_owned_buy_order(db, oid, uid) if oid else None
        if not row or not un:
            await state.clear()
            await m.answer(T.msg_services_open_fail, **_plain())
            return
        if row.get("kind") == "test_config":
            await state.clear()
            await m.answer(T.err_test_no_extra, reply_markup=service_actions_kb(oid, is_test=True), **_plain())
            return
        try:
            gb = float((m.text or "").strip().replace(",", "."))
        except ValueError:
            await m.answer(T.err_extra_gb_number, reply_markup=fsm_cancel_kb(), **_plain())
            return
        if gb < 0.1 or gb > 5000:
            await m.answer(T.err_extra_gb_range, reply_markup=fsm_cancel_kb(), **_plain())
            return
        try:
            live = await pg.get_user(un)
        except PasarGuardAPIError as e:
            await m.answer(
                T.msg_services_error.format(oid=oid, un=html.escape(un), err=html.escape(str(e))),
                parse_mode=ParseMode.HTML,
                reply_markup=fsm_cancel_kb(),
            )
            return
        limit_b = int(live.get("data_limit") or 0)
        if limit_b <= 0:
            await state.clear()
            await m.answer(
                T.msg_extra_unlimited,
                parse_mode=ParseMode.HTML,
                reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config"),
            )
            return
        amount, disc_pct, subtotal, ppg, is_partner = await _quote_buy_amount(db, gb, user_id=uid)
        await state.update_data(
            gb=gb,
            amount=amount,
            price_per_gb=ppg,
            discount_percent=disc_pct,
            subtotal_before_discount=subtotal,
            extra_limit_bytes=limit_b,
        )
        await state.set_state(ShopServiceExtraStates.waiting_payment_choice)
        await db.ensure_user(uid)
        bal = await db.get_balance(uid)
        pay_txt = buy_payment_choice_text(
            amount=amount,
            gb=gb,
            ppg=ppg,
            bal=bal,
            discount_percent=disc_pct,
            subtotal=subtotal,
            is_partner=is_partner,
        )
        pay_kb = await extra_payment_method_kb(db)
        if not await _flow_edit(m.bot, state, text=pay_txt, reply_markup=pay_kb):
            am = await m.answer(pay_txt, parse_mode=ParseMode.HTML, reply_markup=pay_kb)
            await _flow_set_anchor(state, am)

    @router.callback_query(ShopServiceExtraStates.waiting_payment_choice, F.data == f"{APP}:extrapay:wallet")
    async def extra_pay_wallet(cq: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        gb = float(data.get("gb", 0))
        amount = float(data.get("amount", 0))
        oid = int(data.get("extra_order_id") or 0)
        un = str(data.get("extra_panel_username") or "").strip()
        uid = cq.from_user.id if cq.from_user else 0
        row = await _fetch_owned_buy_order(db, oid, uid) if oid else None
        if not row or not un:
            await state.clear()
            await cq.answer(T.msg_services_open_fail, show_alert=True)
            return
        if not await _wallet_pay_wait(cq):
            return
        cooldown = False
        try:
            new_bal = await db.try_deduct_balance(uid, amount)
            if new_bal is None:
                if cq.message:
                    try:
                        await cq.message.edit_text(
                            T.alert_wallet_insufficient,
                            reply_markup=await extra_payment_method_kb(db),
                            **_plain(),
                        )
                    except Exception:
                        pass
                return
            limit_b = int(data.get("extra_limit_bytes") or 0)
            ok, live2, err = await _apply_extra_volume_gb(
                pg, panel_username=un, gb=gb, current_limit_b=limit_b or None
            )
            if not ok:
                await db.add_balance(uid, amount)
                if err == "unlimited":
                    if cq.message:
                        try:
                            await cq.message.edit_text(
                                T.msg_extra_unlimited,
                                parse_mode=ParseMode.HTML,
                                reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config"),
                            )
                        except Exception:
                            pass
                elif cq.message:
                    await cq.message.answer(
                        T.err_extra_panel,
                        parse_mode=ParseMode.HTML,
                        reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config"),
                    )
                await state.clear()
                return
            await db.update_order_extra(oid, volume_exhausted_at=None)
            await _record_partner_purchase(db, uid, gb=gb, amount=amount)
            await _post_channel_extra_volume(
                cq.bot,
                settings,
                db,
                uid=uid,
                panel_user=un,
                gb=gb,
                amount=amount,
                new_bal=new_bal,
            )
            sub_u: list[dict[str, Any]] = []
            try:
                sub_u = list((await pg.list_sub_updates(un, limit=5)).get("updates") or [])
            except PasarGuardAPIError:
                pass
            card = format_service_card_html(row, live2 or {}, sub_u)
            disc_pct = float(data.get("discount_percent") or 0)
            subtotal = float(data.get("subtotal_before_discount") or amount)
            extra_note = T.msg_extra_wallet_done.format(gb=gb, bal=new_bal)
            if disc_pct > 0:
                extra_note += (
                    f"\n🎁 تخفیف حجم {disc_pct:g}٪ — مبلغ پرداختی: {amount:,.0f} تومان"
                    f" (قبل تخفیف: {subtotal:,.0f})"
                )
            await state.clear()
            if cq.message:
                try:
                    await cq.message.edit_text(extra_note, parse_mode=ParseMode.HTML)
                except Exception:
                    await cq.message.answer(extra_note, parse_mode=ParseMode.HTML)
            if cq.message:
                await cq.bot.send_message(
                    cq.message.chat.id,
                    card,
                    parse_mode=ParseMode.HTML,
                    reply_markup=service_actions_kb(oid, is_test=row.get("kind") == "test_config"),
                )
            cooldown = True
        finally:
            _wallet_pay_release(uid, apply_cooldown=cooldown)

    @router.callback_query(ShopServiceExtraStates.waiting_payment_choice, F.data == f"{APP}:extrapay:card")
    async def extra_pay_card(cq: CallbackQuery, state: FSMContext) -> None:
        await _extra_open_receipt_flow(cq, state, db, "card")

    @router.callback_query(ShopServiceExtraStates.waiting_payment_choice, F.data == f"{APP}:extrapay:crypto")
    async def extra_pay_crypto(cq: CallbackQuery, state: FSMContext) -> None:
        await _extra_open_receipt_flow(cq, state, db, "crypto")

    @router.message(ShopServiceExtraStates.waiting_receipt, F.photo)
    async def extra_receipt_photo(m: Message, state: FSMContext) -> None:
        data = await state.get_data()
        gb = float(data.get("gb", 0))
        amount = float(data.get("amount", 0))
        parent_oid = int(data.get("extra_order_id") or 0)
        panel_user = str(data.get("extra_panel_username") or "").strip()
        rk = str(data.get("receipt_kind") or "").strip()
        extra: dict[str, Any] = {"parent_order_id": parent_oid, "panel_username": panel_user}
        if rk in ("card", "crypto"):
            extra["receipt_pay"] = rk
        uid = m.from_user.id if m.from_user else 0
        photo = m.photo[-1]
        oid = await db.create_order(
            user_id=uid,
            kind="add_volume",
            gb=gb,
            amount=amount,
            status="pending",
            receipt_file_id=photo.file_id,
            receipt_unique_id=photo.file_unique_id,
            receipt_chat_id=m.chat.id,
            receipt_message_id=m.message_id,
            extra=extra,
        )
        fc = data.get("flow_chat_id")
        fm = data.get("flow_message_id")
        await state.clear()
        done = T.msg_extra_order_done.format(oid=oid)
        adm = await _is_admin(uid, settings, db)
        menu_kb = await main_menu_kb(adm, db, uid)
        if fc is not None and fm is not None:
            try:
                await m.bot.edit_message_text(
                    chat_id=int(fc),
                    message_id=int(fm),
                    text=done,
                    parse_mode=ParseMode.HTML,
                    reply_markup=menu_kb,
                )
            except Exception:
                await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        else:
            await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        cap_ad = await _admin_receipt_extra_caption(
            db,
            uid=uid,
            amount=amount,
            gb=gb,
            panel_user=panel_user,
            parent_oid=parent_oid,
        )
        await _notify_admins_new_order(
            m,
            settings,
            db,
            order_id=oid,
            user_id=uid,
            admin_caption=cap_ad,
            file_id=photo.file_id,
            post_to_channel=True,
            admin_parse_mode=None,
        )

    @router.message(ShopServiceExtraStates.waiting_receipt, F.document)
    async def extra_receipt_doc(m: Message, state: FSMContext) -> None:
        if not m.document or not (m.document.mime_type or "").startswith("image/"):
            await m.answer(T.err_image_only, **_plain())
            return
        data = await state.get_data()
        gb = float(data.get("gb", 0))
        amount = float(data.get("amount", 0))
        parent_oid = int(data.get("extra_order_id") or 0)
        panel_user = str(data.get("extra_panel_username") or "").strip()
        rk = str(data.get("receipt_kind") or "").strip()
        extra: dict[str, Any] = {"parent_order_id": parent_oid, "panel_username": panel_user}
        if rk in ("card", "crypto"):
            extra["receipt_pay"] = rk
        uid = m.from_user.id if m.from_user else 0
        doc = m.document
        oid = await db.create_order(
            user_id=uid,
            kind="add_volume",
            gb=gb,
            amount=amount,
            status="pending",
            receipt_file_id=doc.file_id,
            receipt_unique_id=doc.file_unique_id,
            receipt_chat_id=m.chat.id,
            receipt_message_id=m.message_id,
            extra=extra,
        )
        fc = data.get("flow_chat_id")
        fm = data.get("flow_message_id")
        await state.clear()
        done = T.msg_extra_order_done.format(oid=oid)
        adm = await _is_admin(uid, settings, db)
        menu_kb = await main_menu_kb(adm, db, uid)
        if fc is not None and fm is not None:
            try:
                await m.bot.edit_message_text(
                    chat_id=int(fc),
                    message_id=int(fm),
                    text=done,
                    parse_mode=ParseMode.HTML,
                    reply_markup=menu_kb,
                )
            except Exception:
                await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        else:
            await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        cap_ad = await _admin_receipt_extra_caption(
            db,
            uid=uid,
            amount=amount,
            gb=gb,
            panel_user=panel_user,
            parent_oid=parent_oid,
        )
        await _notify_admins_new_order(
            m,
            settings,
            db,
            order_id=oid,
            user_id=uid,
            admin_caption=cap_ad,
            file_id=doc.file_id,
            post_to_channel=True,
            admin_parse_mode=None,
        )

    @router.callback_query(ShopBuyStates.waiting_payment_choice, F.data == f"{APP}:buypay:wallet")
    async def buy_pay_wallet(cq: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        gb = float(data.get("gb", 0))
        amount = float(data.get("amount", 0))
        uid = cq.from_user.id if cq.from_user else 0
        if not await _wallet_pay_wait(cq):
            return
        cooldown = False
        try:
            new_bal = await db.try_deduct_balance(uid, amount)
            if new_bal is None:
                if cq.message:
                    try:
                        await cq.message.edit_text(
                            T.alert_wallet_insufficient,
                            reply_markup=await buy_payment_method_kb(db),
                            **_plain(),
                        )
                    except Exception:
                        pass
                return
            fsm_data = await state.get_data()
            config_days = await _buy_config_days_from_data(fsm_data, db)
            order_extra: dict[str, Any] = {"pay_wallet": True, "config_days": config_days}
            if fsm_data.get("package_title"):
                order_extra["package_title"] = str(fsm_data["package_title"])
            order_extra.update(_buy_order_extra_promo(fsm_data))
            oid = await db.create_order(
                user_id=uid,
                kind="buy_config",
                gb=gb,
                amount=amount,
                status="pending",
                receipt_file_id=None,
                receipt_unique_id=None,
                receipt_chat_id=cq.message.chat.id if cq.message else None,
                receipt_message_id=None,
                extra=order_extra,
            )
            ok, username, sub_raw, pid, last_err = await _try_create_panel_user_for_buy(
                pg,
                uid=uid,
                gb=gb,
                settings=settings,
                db=db,
                config_days=config_days,
            )
            if ok and username and sub_raw is not None:
                await db.update_order(
                    oid,
                    status="approved_done",
                    pasarguard_username=username,
                    subscription_url=sub_raw,
                    panel_user_id=pid,
                )
                await _consume_order_promo(db, order_extra)
                await _record_partner_purchase(db, uid, gb=gb, amount=amount)
                panel_cfg = await load_effective_panel_config(db)
                sub_abs = subscription_url_with_base(panel_cfg.pasarguard_base_url, sub_raw)
                days = config_days
                uname = await _tg_buyer_username(cq.bot, uid)
                cap_user = _invoice_caption_html(
                    new_balance=new_bal,
                    amount=amount,
                    panel_username=username,
                    days=days,
                    gb=gb,
                    sub_url=sub_abs,
                    include_buyer_footer=False,
                    buyer_tg_id=uid,
                    buyer_username_plain=uname,
                )
                cap_ch = _invoice_caption_html(
                    new_balance=new_bal,
                    amount=amount,
                    panel_username=username,
                    days=days,
                    gb=gb,
                    sub_url=sub_abs,
                    include_buyer_footer=True,
                    buyer_tg_id=uid,
                    buyer_username_plain=uname,
                )
                try:
                    ch_cfg = await load_effective_panel_config(db)
                    await _send_subscription_qr_photo(cq.bot, ch_cfg.receipt_channel_id, cap_ch, sub_abs)
                except Exception:
                    pass
                try:
                    await _send_subscription_qr_photo(cq.bot, uid, cap_user, sub_abs)
                except Exception:
                    pass
                if cq.message:
                    try:
                        await cq.message.edit_text(
                            T.msg_buy_wallet_done.format(new_bal=new_bal),
                            parse_mode=ParseMode.HTML,
                            reply_markup=await _user_main_menu(db, settings, uid),
                        )
                    except Exception:
                        await cq.message.answer(
                            T.msg_buy_wallet_done.format(new_bal=new_bal),
                            parse_mode=ParseMode.HTML,
                            reply_markup=await _user_main_menu(db, settings, uid),
                        )
                await state.clear()
                cooldown = True
                return

            await db.add_balance(uid, amount)
            await db.update_order(oid, status="rejected")
            err_txt = html.escape(str(last_err) if last_err else "unknown")
            if cq.message:
                try:
                    await cq.message.edit_text(
                        T.msg_buy_wallet_fail.format(err=err_txt),
                        parse_mode=ParseMode.HTML,
                        reply_markup=await _user_main_menu(db, settings, uid),
                    )
                except Exception:
                    await cq.message.answer(
                        T.msg_buy_wallet_fail.format(err=err_txt),
                        parse_mode=ParseMode.HTML,
                        reply_markup=await _user_main_menu(db, settings, uid),
                    )
            await state.clear()
        finally:
            _wallet_pay_release(uid, apply_cooldown=cooldown)

    @router.callback_query(ShopBuyStates.waiting_payment_choice, F.data == f"{APP}:buypay:card")
    async def buy_pay_card(cq: CallbackQuery, state: FSMContext) -> None:
        await _buy_open_receipt_flow(cq, state, db, "card")

    @router.callback_query(ShopBuyStates.waiting_payment_choice, F.data == f"{APP}:buypay:crypto")
    async def buy_pay_crypto(cq: CallbackQuery, state: FSMContext) -> None:
        await _buy_open_receipt_flow(cq, state, db, "crypto")

    @router.callback_query(ShopBuyStates.waiting_payment_choice, F.data == f"{APP}:buypay:promo")
    async def buy_pay_promo(cq: CallbackQuery, state: FSMContext) -> None:
        if not await db.get_bool_setting("discount_codes_enabled"):
            await cq.answer(T.err_promo_invalid, show_alert=True)
            return
        await cq.answer()
        await state.set_state(ShopBuyStates.waiting_promo_code)
        if cq.message:
            try:
                await cq.message.edit_text(
                    T.msg_ask_promo_code,
                    parse_mode=ParseMode.HTML,
                    reply_markup=fsm_cancel_kb(),
                )
                await state.update_data(flow_chat_id=cq.message.chat.id, flow_message_id=cq.message.message_id)
            except Exception:
                sent = await cq.message.answer(
                    T.msg_ask_promo_code,
                    parse_mode=ParseMode.HTML,
                    reply_markup=fsm_cancel_kb(),
                )
                await state.update_data(flow_chat_id=sent.chat.id, flow_message_id=sent.message_id)

    @router.message(ShopBuyStates.waiting_promo_code, F.text)
    async def buy_promo_entered(m: Message, state: FSMContext) -> None:
        uid = m.from_user.id if m.from_user else 0
        raw = (m.text or "").strip()
        data = await state.get_data()
        gb = float(data.get("gb", 0))
        fp_raw = data.get("fixed_price")
        fixed_price: float | None = float(fp_raw) if fp_raw is not None else None
        config_days = data.get("config_days")
        package_title = str(data.get("package_title") or "")
        if raw == "-":
            await state.update_data(promo_code="", promo_percent=0)
            await _proceed_buy_payment_step(
                m.bot, state, db, settings, uid, gb=gb,
                fixed_price=fixed_price,
                config_days=config_days,
                package_title=package_title,
            )
            return
        row = await db.get_discount_code(raw)
        if not row:
            await _flow_edit(m.bot, state, text=T.err_promo_invalid + "\n\n" + T.msg_ask_promo_code, reply_markup=fsm_cancel_kb(), parse_mode=None)
            return
        max_u = int(row.get("max_uses") or 0)
        used = int(row.get("used_count") or 0)
        if max_u > 0 and used >= max_u:
            await _flow_edit(m.bot, state, text=T.err_promo_invalid + "\n\n" + T.msg_ask_promo_code, reply_markup=fsm_cancel_kb(), parse_mode=None)
            return
        pct = float(row.get("percent") or 0)
        code = str(row["code"])
        await state.update_data(promo_code=code, promo_percent=pct)
        await _proceed_buy_payment_step(
            m.bot, state, db, settings, uid, gb=gb,
            fixed_price=fixed_price,
            config_days=config_days,
            package_title=package_title,
        )

    @router.callback_query(ShopBuyStates.waiting_payment_choice, F.data == f"{APP}:buypay:nowpay")
    async def buy_pay_nowpay(cq: CallbackQuery, state: FSMContext) -> None:
        if not await _nowpay_available(db):
            await cq.answer(T.err_nowpay_unavailable, show_alert=True)
            return
        await cq.answer()
        data = await state.get_data()
        gb = float(data.get("gb", 0))
        amount = float(data.get("amount", 0))
        uid = cq.from_user.id if cq.from_user else 0
        config_days = await _buy_config_days_from_data(data, db)
        order_extra: dict[str, Any] = {"pay_nowpay": True, "config_days": config_days}
        order_extra.update(_buy_order_extra_promo(data))
        if data.get("package_title"):
            order_extra["package_title"] = str(data["package_title"])
        oid = await db.create_order(
            user_id=uid,
            kind="buy_config",
            gb=gb,
            amount=amount,
            status="pending",
            receipt_file_id=None,
            receipt_unique_id=None,
            receipt_chat_id=cq.message.chat.id if cq.message else None,
            receipt_message_id=None,
            extra=order_extra,
        )
        np = await _nowpayments_client(db)
        try:
            usd = await _toman_to_usd_amount(db, amount)
            inv = await np.create_invoice(
                price_amount=usd,
                price_currency="usd",
                order_id=str(oid),
                order_description=f"VPN buy #{oid} — {gb:g} GB",
            )
        except NOWPaymentsError as e:
            await db.update_order(oid, status="rejected")
            err = html.escape(str(e)[:400])
            if cq.message:
                await cq.message.answer(
                    T.msg_nowpay_fail.format(err=err),
                    parse_mode=ParseMode.HTML,
                    reply_markup=await buy_payment_method_kb(db),
                )
            return
        invoice_id = str(inv.get("id") or inv.get("invoice_id") or "")
        pay_url = str(inv.get("invoice_url") or inv.get("pay_url") or "")
        await db.update_order_extra(oid, nowpay_invoice_id=invoice_id)
        await state.set_state(ShopBuyStates.waiting_nowpay)
        await state.update_data(nowpay_order_id=oid)
        txt = T.msg_nowpay_invoice.format(amount=amount, gb=gb, oid=oid)
        kb = nowpay_check_kb(oid, pay_url)
        if cq.message:
            try:
                await cq.message.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                msg = await cq.message.answer(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
                await _flow_set_anchor(state, msg)

    @router.callback_query(F.data.startswith(f"{APP}:nowcheck:"))
    async def buy_nowpay_check(cq: CallbackQuery, state: FSMContext) -> None:
        uid = cq.from_user.id if cq.from_user else 0
        raw = (cq.data or "")[len(f"{APP}:nowcheck:") :]
        try:
            oid = int(raw)
        except ValueError:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        order = await db.get_order(oid)
        if not order or int(order["user_id"]) != uid:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        if order["status"] != "pending":
            await cq.answer(T.alert_order_stale, show_alert=True)
            return
        extra = order.get("extra") or {}
        invoice_id = str(extra.get("nowpay_invoice_id") or "").strip()
        if not invoice_id:
            await cq.answer(T.err_nowpay_unavailable, show_alert=True)
            return
        np = await _nowpayments_client(db)
        try:
            inv = await np.get_invoice(invoice_id)
        except NOWPaymentsError as e:
            await cq.answer(str(e)[:180], show_alert=True)
            return
        if not np.invoice_is_paid(inv):
            await cq.answer(T.msg_nowpay_pending, show_alert=True)
            return
        await cq.answer(T.msg_nowpay_paid_ok[:120])
        gb = float(order.get("gb") or 0)
        amount = float(order.get("amount") or 0)
        config_days = int(extra.get("config_days") or await db.get_int_setting("default_config_days", 30))
        ok, username, sub_raw, pid, last_err = await _try_create_panel_user_for_buy(
            pg, uid=uid, gb=gb, settings=settings, db=db, config_days=config_days,
        )
        adm = await _is_admin(uid, settings, db)
        menu_kb = await main_menu_kb(adm, db, uid)
        if ok and username and sub_raw is not None:
            await db.update_order(
                oid,
                status="approved_done",
                pasarguard_username=username,
                subscription_url=sub_raw,
                panel_user_id=pid,
            )
            await _consume_order_promo(db, extra)
            await _record_partner_purchase(db, uid, gb=gb, amount=amount)
            panel_cfg = await load_effective_panel_config(db)
            sub_abs = subscription_url_with_base(panel_cfg.pasarguard_base_url, sub_raw)
            bal = await db.get_balance(uid)
            uname = await _tg_buyer_username(cq.bot, uid)
            cap_user = _invoice_caption_html(
                new_balance=bal,
                amount=amount,
                panel_username=username,
                days=config_days,
                gb=gb,
                sub_url=sub_abs,
                include_buyer_footer=False,
                buyer_tg_id=uid,
                buyer_username_plain=uname,
            )
            try:
                await _send_subscription_qr_photo(cq.bot, uid, cap_user, sub_abs)
            except Exception:
                pass
            done = T.msg_buy_wallet_done.format(new_bal=bal)
            if cq.message:
                try:
                    await cq.message.edit_text(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
                except Exception:
                    await cq.message.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
            await state.clear()
            return
        await db.update_order(oid, status="rejected")
        err_txt = html.escape(str(last_err) if last_err else "unknown")
        fail = T.msg_buy_wallet_fail.format(err=err_txt)
        if cq.message:
            await cq.message.answer(fail, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        await state.clear()

    @router.message(ShopBuyStates.waiting_payment_choice, F.text)
    async def buy_payment_choice_reminder(m: Message, state: FSMContext) -> None:
        pay_kb = await buy_payment_method_kb(db)
        if not await _flow_edit(
            m.bot,
            state,
            text=T.msg_buy_payment_reminder,
            reply_markup=pay_kb,
            parse_mode=None,
        ):
            await m.answer(T.msg_buy_payment_reminder, reply_markup=pay_kb, **_plain())

    @router.message(ShopBuyStates.waiting_receipt, F.photo)
    async def buy_receipt_photo(m: Message, state: FSMContext) -> None:
        data = await state.get_data()
        gb = float(data.get("gb", 0))
        amount = float(data.get("amount", 0))
        rk = str(data.get("receipt_kind") or "").strip()
        extra = _buy_order_extra_from_fsm(data, receipt_kind=rk)
        uid = m.from_user.id if m.from_user else 0
        photo = m.photo[-1]
        oid = await db.create_order(
            user_id=uid,
            kind="buy_config",
            gb=gb,
            amount=amount,
            status="pending",
            receipt_file_id=photo.file_id,
            receipt_unique_id=photo.file_unique_id,
            receipt_chat_id=m.chat.id,
            receipt_message_id=m.message_id,
            extra=extra or None,
        )
        fc = data.get("flow_chat_id")
        fm = data.get("flow_message_id")
        await state.clear()
        done = T.msg_buy_order_done.format(oid=oid)
        adm = await _is_admin(uid, settings, db)
        menu_kb = await main_menu_kb(adm, db, uid)
        if fc is not None and fm is not None:
            try:
                await m.bot.edit_message_text(
                    chat_id=int(fc),
                    message_id=int(fm),
                    text=done,
                    parse_mode=ParseMode.HTML,
                    reply_markup=menu_kb,
                )
            except Exception:
                await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        else:
            await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        cap_ad = await _admin_receipt_buy_caption(db, uid=uid, amount=amount)
        await _notify_admins_new_order(
            m,
            settings,
            db,
            order_id=oid,
            user_id=uid,
            admin_caption=cap_ad,
            file_id=photo.file_id,
            post_to_channel=False,
            admin_parse_mode=None,
        )

    @router.message(ShopBuyStates.waiting_receipt, F.document)
    async def buy_receipt_doc(m: Message, state: FSMContext) -> None:
        if not m.document or not (m.document.mime_type or "").startswith("image/"):
            await m.answer(T.err_image_only, **_plain())
            return
        data = await state.get_data()
        gb = float(data.get("gb", 0))
        amount = float(data.get("amount", 0))
        rk = str(data.get("receipt_kind") or "").strip()
        extra = _buy_order_extra_from_fsm(data, receipt_kind=rk)
        uid = m.from_user.id if m.from_user else 0
        doc = m.document
        oid = await db.create_order(
            user_id=uid,
            kind="buy_config",
            gb=gb,
            amount=amount,
            status="pending",
            receipt_file_id=doc.file_id,
            receipt_unique_id=doc.file_unique_id,
            receipt_chat_id=m.chat.id,
            receipt_message_id=m.message_id,
            extra=extra or None,
        )
        fc = data.get("flow_chat_id")
        fm = data.get("flow_message_id")
        await state.clear()
        done = T.msg_buy_order_done_short.format(oid=oid)
        adm = await _is_admin(uid, settings, db)
        menu_kb = await main_menu_kb(adm, db, uid)
        if fc is not None and fm is not None:
            try:
                await m.bot.edit_message_text(
                    chat_id=int(fc),
                    message_id=int(fm),
                    text=done,
                    parse_mode=ParseMode.HTML,
                    reply_markup=menu_kb,
                )
            except Exception:
                await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        else:
            await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        cap_ad = await _admin_receipt_buy_caption(db, uid=uid, amount=amount)
        await _notify_admins_new_order(
            m,
            settings,
            db,
            order_id=oid,
            user_id=uid,
            admin_caption=cap_ad,
            file_id=doc.file_id,
            post_to_channel=False,
            admin_parse_mode=None,
        )

    @router.message(ShopTopupStates.waiting_amount, F.text)
    async def topup_amount(m: Message, state: FSMContext) -> None:
        amt = _parse_credit_amount_toman(m.text or "")
        if amt is None:
            if not await _flow_edit(
                m.bot,
                state,
                text=T.err_topup_amount,
                reply_markup=fsm_cancel_kb(),
                parse_mode=None,
            ):
                await m.answer(T.err_topup_amount, reply_markup=fsm_cancel_kb(), **_plain())
            return
        if amt < 10_000 or amt > 500_000_000:
            if not await _flow_edit(
                m.bot,
                state,
                text=T.err_topup_range,
                reply_markup=fsm_cancel_kb(),
                parse_mode=None,
            ):
                await m.answer(
                    T.err_topup_range,
                    reply_markup=fsm_cancel_kb(),
                    **_plain(),
                )
            return
        top_kb = await topup_payment_method_kb(db)
        if top_kb is None:
            if not await _flow_edit(
                m.bot,
                state,
                text=T.err_topup_no_payment_method,
                reply_markup=fsm_cancel_kb(),
                parse_mode=None,
            ):
                await m.answer(T.err_topup_no_payment_method, reply_markup=fsm_cancel_kb(), **_plain())
            return
        await state.update_data(topup_amount=amt)
        await state.set_state(ShopTopupStates.waiting_pay_kind)
        cho = T.msg_topup_payment_choice.format(amt=amt)
        edited = await _flow_edit(m.bot, state, text=cho, reply_markup=top_kb, parse_mode=None)
        if not edited:
            am = await m.answer(cho, reply_markup=top_kb, **_plain())
            await _flow_set_anchor(state, am)
        else:
            try:
                await m.answer(T.msg_topup_amount_ack, **_plain())
            except Exception:
                pass

    @router.callback_query(ShopTopupStates.waiting_pay_kind, F.data == f"{APP}:topay:card")
    async def topup_pay_card(cq: CallbackQuery, state: FSMContext) -> None:
        await _topup_open_receipt_flow(cq, state, db, "card")

    @router.callback_query(ShopTopupStates.waiting_pay_kind, F.data == f"{APP}:topay:crypto")
    async def topup_pay_crypto(cq: CallbackQuery, state: FSMContext) -> None:
        await _topup_open_receipt_flow(cq, state, db, "crypto")

    @router.message(ShopTopupStates.waiting_receipt, F.photo)
    async def topup_photo(m: Message, state: FSMContext) -> None:
        data = await state.get_data()
        amt = float(data.get("topup_amount", 0))
        rk = str(data.get("receipt_kind") or "").strip()
        extra: dict[str, Any] = {}
        if rk in ("card", "crypto"):
            extra["receipt_pay"] = rk
        uid = m.from_user.id if m.from_user else 0
        photo = m.photo[-1]
        oid = await db.create_order(
            user_id=uid,
            kind="topup",
            gb=None,
            amount=amt,
            status="pending",
            receipt_file_id=photo.file_id,
            receipt_unique_id=photo.file_unique_id,
            receipt_chat_id=m.chat.id,
            receipt_message_id=m.message_id,
            extra=extra or None,
        )
        fc = data.get("flow_chat_id")
        fm = data.get("flow_message_id")
        await state.clear()
        done = T.msg_topup_pending.format(oid=oid)
        adm = await _is_admin(uid, settings, db)
        menu_kb = await main_menu_kb(adm, db, uid)
        if fc is not None and fm is not None:
            try:
                await m.bot.edit_message_text(
                    chat_id=int(fc),
                    message_id=int(fm),
                    text=done,
                    parse_mode=ParseMode.HTML,
                    reply_markup=menu_kb,
                )
            except Exception:
                await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        else:
            await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        cap = notif_caption_topup(oid, uid, amt)
        await _notify_admins_new_order(
            m,
            settings,
            db,
            order_id=oid,
            user_id=uid,
            admin_caption=cap,
            file_id=photo.file_id,
            post_to_channel=False,
            admin_parse_mode=ParseMode.HTML,
        )

    @router.message(ShopTopupStates.waiting_receipt, F.document)
    async def topup_doc(m: Message, state: FSMContext) -> None:
        if not m.document or not (m.document.mime_type or "").startswith("image/"):
            await m.answer(T.err_image_only_short, **_plain())
            return
        data = await state.get_data()
        amt = float(data.get("topup_amount", 0))
        rk = str(data.get("receipt_kind") or "").strip()
        extra: dict[str, Any] = {}
        if rk in ("card", "crypto"):
            extra["receipt_pay"] = rk
        uid = m.from_user.id if m.from_user else 0
        doc = m.document
        oid = await db.create_order(
            user_id=uid,
            kind="topup",
            gb=None,
            amount=amt,
            status="pending",
            receipt_file_id=doc.file_id,
            receipt_unique_id=doc.file_unique_id,
            receipt_chat_id=m.chat.id,
            receipt_message_id=m.message_id,
            extra=extra or None,
        )
        fc = data.get("flow_chat_id")
        fm = data.get("flow_message_id")
        await state.clear()
        done = T.msg_topup_pending_short.format(oid=oid)
        adm = await _is_admin(uid, settings, db)
        menu_kb = await main_menu_kb(adm, db, uid)
        if fc is not None and fm is not None:
            try:
                await m.bot.edit_message_text(
                    chat_id=int(fc),
                    message_id=int(fm),
                    text=done,
                    parse_mode=ParseMode.HTML,
                    reply_markup=menu_kb,
                )
            except Exception:
                await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        else:
            await m.answer(done, parse_mode=ParseMode.HTML, reply_markup=menu_kb)
        cap = notif_caption_topup_short(oid, uid, amt)
        await _notify_admins_new_order(
            m,
            settings,
            db,
            order_id=oid,
            user_id=uid,
            admin_caption=cap,
            file_id=doc.file_id,
            post_to_channel=False,
            admin_parse_mode=ParseMode.HTML,
        )


def register_admin_shop_callbacks(
    admin_cb: Router,
    *,
    settings: Settings,
    pg: PasarGuardClient,
    db: Database,
) -> None:
    @admin_cb.callback_query(F.data == "adm:cancel")
    async def adm_cancel_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer(T.cq_cancelled)
        if cq.message:
            await cq.message.answer(
                T.msg_admin_input_cancelled,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_root_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:addbal")
    async def adm_b_addbal(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminCreditUserStates.waiting_target_id)
        await state.set_data({})
        if cq.message:
            await cq.message.answer(
                T.msg_admin_addbal_intro,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:root")
    async def adm_root(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                T.msg_admin_root,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_root_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:bmenu")
    async def adm_bmenu_legacy(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                T.msg_admin_root,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_root_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:fin")
    async def adm_fin_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        n = await db.count_pending_orders()
        if cq.message:
            await cq.message.edit_text(
                await _admin_financial_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_financial_kb(n),
            )

    @admin_cb.callback_query(F.data == "adm:shop")
    async def adm_shop_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                await _admin_shop_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=await admin_shop_kb(db),
            )

    @admin_cb.callback_query(F.data == "adm:shop:product")
    async def adm_shop_product_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                await _admin_shop_product_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=await admin_shop_product_kb(db),
            )

    @admin_cb.callback_query(F.data.in_({"adm:tmenu", "adm:test:menu"}))
    async def adm_test_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                await _admin_test_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_test_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:chan")
    async def adm_chan_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                await _admin_channel_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_channel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:admins")
    async def adm_admins_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                await _admin_admins_html(db, settings),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_admins_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:disc")
    async def adm_disc_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        codes = await db.list_discount_codes()
        if cq.message:
            await cq.message.edit_text(
                T.msg_admin_discount_menu.format(count=len(codes)),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_discount_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:msg")
    async def adm_msg_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                T.msg_admin_messaging_menu,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_messaging_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:btns")
    async def adm_btns_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        cfg = await load_main_menu_config(db)
        if cq.message:
            await cq.message.edit_text(
                T.msg_admin_buttons_menu,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_main_buttons_kb(cfg),
            )

    @admin_cb.callback_query(F.data == "adm:texts")
    async def adm_texts_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                T.msg_admin_texts_menu,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_texts_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:ustats")
    async def adm_ustats_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        await state.set_state(AdminBotInputStates.user_stats_lookup)
        if cq.message:
            await cq.message.answer(
                T.msg_admin_user_stats_menu,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:bot")
    async def adm_bot_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                await _admin_bot_settings_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_bot_settings_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:cfg")
    async def adm_cfg_menu_legacy(cq: CallbackQuery, state: FSMContext) -> None:
        await adm_bot_menu(cq, state)

    @admin_cb.callback_query(F.data == "adm:export:configs")
    async def adm_export_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                T.msg_admin_export_intro,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_export_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:export:run")
    async def adm_export_run(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        adm_id = cq.from_user.id if cq.from_user else 0
        if adm_id in _admin_export_in_progress:
            await cq.answer(T.msg_admin_export_busy, show_alert=True)
            return
        _admin_export_in_progress.add(adm_id)
        await cq.answer()
        chat_id = cq.message.chat.id if cq.message else adm_id
        if cq.message:
            try:
                await cq.message.edit_text(T.msg_admin_export_start, parse_mode=ParseMode.HTML)
            except Exception:
                pass
        try:
            raw, panel_count, linked = await build_migration_export_payload(pg, db, settings)
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
            doc = BufferedInputFile(raw, filename=f"panel_migration_{ts}.json")
            await cq.bot.send_document(
                chat_id,
                doc,
                caption=T.msg_admin_export_done.format(
                    panel_count=panel_count,
                    linked_count=linked,
                ),
                parse_mode=ParseMode.HTML,
            )
            if cq.message:
                try:
                    await cq.message.edit_text(
                        T.msg_admin_export_intro,
                        parse_mode=ParseMode.HTML,
                        reply_markup=admin_export_kb(),
                    )
                except Exception:
                    pass
        except Exception as e:
            err = html.escape(str(e)[:500])
            await cq.bot.send_message(
                chat_id,
                T.msg_admin_export_fail.format(err=err),
                parse_mode=ParseMode.HTML,
            )
        finally:
            _admin_export_in_progress.discard(adm_id)

    @admin_cb.callback_query(F.data == "adm:panel:menu")
    async def adm_panel_menu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                await _admin_panel_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=await _admin_panel_reply_kb(db),
            )

    @admin_cb.callback_query(F.data == "adm:panel:add")
    async def adm_panel_add_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.panel_base_url)
        await state.update_data(panel_setup=1)
        if cq.message:
            await cq.message.answer(
                T.msg_panel_add_step_url,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:panel:remove")
    async def adm_panel_remove_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        await db.set_setting("pasarguard_base_url", "")
        await db.set_setting("pasarguard_username", "")
        await db.set_setting("pasarguard_password", "")
        await db.set_setting("default_group_ids", "")
        if cq.message:
            await cq.message.edit_text(
                T.msg_panel_removed,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_panel_unconfigured_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:panel:url")
    async def adm_panel_url_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.panel_base_url)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_panel_url,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:panel:user")
    async def adm_panel_user_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.panel_username)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_panel_user,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:panel:pass")
    async def adm_panel_pass_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.panel_password)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_panel_pass,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:panel:prefix")
    async def adm_panel_prefix_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.panel_username_prefix)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_panel_prefix,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:panel:start")
    async def adm_panel_start_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.panel_username_start)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_panel_start,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:panel:groups")
    async def adm_panel_groups_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        await _show_panel_groups_picker(cq, pg=pg, db=db)

    @admin_cb.callback_query(F.data.startswith("adm:panel:grptgl:"))
    async def adm_panel_grp_toggle(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        try:
            gid = int((cq.data or "").split(":")[-1])
        except ValueError:
            await cq.answer()
            return
        cfg = await load_effective_panel_config(db)
        selected = list(cfg.default_group_ids)
        if gid in selected:
            if len(selected) <= 1:
                await cq.answer(T.err_panel_groups_need_one, show_alert=True)
                return
            selected.remove(gid)
        else:
            selected.append(gid)
        await db.set_setting("default_group_ids", ",".join(str(x) for x in sorted(selected)))
        await cq.answer(T.cq_panel_group_toggled)
        await _show_panel_groups_picker(cq, pg=pg, db=db)

    @admin_cb.callback_query(F.data == "adm:b:welcome")
    async def adm_welcome_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.welcome_message)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_welcome,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:receiptchan")
    async def adm_receipt_chan_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.receipt_channel_id)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_receipt_channel,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:rcptadmins")
    async def adm_receipt_admins_menu(cq: CallbackQuery) -> None:
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                T.btn_admin_receipt_admins,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_receipt_admins_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:rcptadm:list")
    async def adm_receipt_admins_list(cq: CallbackQuery) -> None:
        await cq.answer()
        ids = await db.list_receipt_admin_ids()
        if not ids:
            text = T.msg_receipt_admins_list_empty
        else:
            lines = T.msg_receipt_admins_list_header
            lines += "".join(T.msg_receipt_admin_list_line.format(tid=tid) for tid in ids)
            text = lines
        if cq.message:
            await cq.message.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_receipt_admins_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:rcptadm:add")
    async def adm_receipt_admin_add_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.receipt_admin_add)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_receipt_admin_add,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:rcptadm:rm")
    async def adm_receipt_admin_rm_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.receipt_admin_rm)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_receipt_admin_rm,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:ballist")
    async def adm_balance_list(cq: CallbackQuery) -> None:
        await cq.answer()
        rows = await db.list_users_with_balance(min_balance=0.01, limit=50)
        n = await db.count_pending_orders()
        kb = admin_financial_kb(n)
        if not rows:
            if cq.message:
                await cq.message.answer(
                    T.msg_balance_list_empty,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
            return
        lines = [T.msg_balance_list_header.format(n=len(rows))]
        for r in rows:
            lines.append(
                T.msg_balance_list_line.format(
                    tid=int(r["telegram_id"]),
                    bal=float(r["balance"]),
                )
            )
        if cq.message:
            await cq.message.answer("".join(lines)[:4096], parse_mode=ParseMode.HTML, reply_markup=kb)

    @admin_cb.callback_query(F.data == "adm:b:dedbal")
    async def adm_b_dedbal(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminDeductUserStates.waiting_target_id)
        await state.set_data({})
        if cq.message:
            await cq.message.answer(
                T.msg_admin_deduct_intro,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:pmenu")
    async def adm_pmenu(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        if cq.message:
            await cq.message.edit_text(
                await _admin_partner_menu_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=partner_manage_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:p:price")
    async def adm_partner_ask_price(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.partner_price_per_gb)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_partner_price,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:p:voldisc")
    async def adm_partner_ask_volume_discount(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.partner_volume_discount_tiers)
        tiers = await _load_partner_volume_discount_tiers(db)
        if tiers:
            cur = "\n".join(
                f"{int(t[0]) if t[0] == int(t[0]) else t[0]},"
                f"{int(t[1]) if t[1] == int(t[1]) else t[1]}"
                for t in tiers
            )
        else:
            cur = "—"
        if cq.message:
            await cq.message.answer(
                T.msg_ask_partner_volume_discount.format(current=html.escape(cur)),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:p:packages")
    async def adm_partner_ask_packages(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.partner_buy_packages)
        pkgs = await _load_partner_buy_packages(db)
        cur = html.escape(format_packages_admin_current(pkgs))
        if cq.message:
            await cq.message.answer(
                T.msg_ask_partner_buy_packages.format(current=cur),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:p:add")
    async def adm_partner_ask_add(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.partner_add)
        if cq.message:
            await cq.message.answer(
                T.msg_admin_partner_add_intro,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:p:usage")
    async def adm_partner_usage_list(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        partners = await db.list_partners(100)
        active = [
            p
            for p in partners
            if float(p.get("unsettled_gb") or 0) > 0 or float(p.get("unsettled_amount") or 0) > 0
        ]
        active.sort(
            key=lambda p: (float(p.get("unsettled_gb") or 0), float(p.get("unsettled_amount") or 0)),
            reverse=True,
        )
        if not active:
            if cq.message:
                await cq.message.answer(
                    T.msg_partner_usage_empty,
                    parse_mode=ParseMode.HTML,
                    reply_markup=partner_manage_kb(),
                )
            return
        lines = [T.msg_partner_usage_header.format(n=len(active))]
        for p in active:
            tid = int(p["telegram_id"])
            lbl = str(p.get("label") or "").strip()
            label_s = f" — {html.escape(lbl)}" if lbl else ""
            lines.append(
                T.msg_partner_usage_line.format(
                    tid=tid,
                    label=label_s,
                    gb=_fmt_partner_gb(float(p.get("unsettled_gb") or 0)),
                    amount=float(p.get("unsettled_amount") or 0),
                )
            )
        if cq.message:
            await cq.message.answer(
                "".join(lines)[:4096],
                parse_mode=ParseMode.HTML,
                reply_markup=partner_manage_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:p:list")
    async def adm_partner_list(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        partners = await db.list_partners(100)
        if not partners:
            if cq.message:
                await cq.message.answer(
                    T.msg_partners_list_empty,
                    parse_mode=ParseMode.HTML,
                    reply_markup=partner_manage_kb(),
                )
            return
        lines = [T.msg_partners_list_header.format(n=len(partners))]
        for p in partners:
            tid = int(p["telegram_id"])
            lbl = str(p.get("label") or "").strip()
            label_s = f" — {html.escape(lbl)}" if lbl else ""
            lines.append(T.msg_partners_list_line.format(tid=tid, label=label_s))
        text = "".join(lines)[:4096]
        if cq.message:
            await cq.message.answer(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=partners_list_kb(partners),
            )

    @admin_cb.callback_query(F.data.regexp(r"^adm:p:rm:\d+$"))
    async def adm_partner_remove(cq: CallbackQuery) -> None:
        m = re.match(r"^adm:p:rm:(\d+)$", cq.data or "")
        if not m:
            await cq.answer()
            return
        tid = int(m.group(1))
        ok = await db.remove_partner(tid)
        if ok:
            await cq.answer(T.msg_partner_removed.format(tid=tid)[:180], show_alert=True)
        else:
            await cq.answer(T.msg_partner_remove_fail, show_alert=True)
        if cq.message:
            partners = await db.list_partners(100)
            if not partners:
                await cq.message.edit_text(
                    T.msg_partners_list_empty,
                    parse_mode=ParseMode.HTML,
                    reply_markup=partner_manage_kb(),
                )
                return
            lines = [T.msg_partners_list_header.format(n=len(partners))]
            for p in partners:
                ptid = int(p["telegram_id"])
                lbl = str(p.get("label") or "").strip()
                label_s = f" — {html.escape(lbl)}" if lbl else ""
                lines.append(T.msg_partners_list_line.format(tid=ptid, label=label_s))
            try:
                await cq.message.edit_text(
                    "".join(lines)[:4096],
                    parse_mode=ParseMode.HTML,
                    reply_markup=partners_list_kb(partners),
                )
            except Exception:
                pass

    @admin_cb.callback_query(F.data == "adm:b:togglebuy")
    async def toggle_buy(cq: CallbackQuery) -> None:
        cur = await _buying_blocked(db)
        await db.set_bool_setting("buying_disabled", not cur)
        await cq.answer(T.cq_buy_toggled)
        if cq.message:
            await cq.message.edit_text(
                await _admin_bot_settings_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_bot_settings_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:testgb")
    async def ask_test_gb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.test_service_gb)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_test_gb,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:resettest")
    async def ask_reset_test(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.reset_test_user)
        if cq.message:
            await cq.message.answer(
                T.msg_admin_reset_test_intro,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:togglemaint")
    async def toggle_maint(cq: CallbackQuery) -> None:
        cur = await db.get_bool_setting("maintenance_mode")
        await db.set_bool_setting("maintenance_mode", not cur)
        await cq.answer(T.cq_maint_toggled)
        if cq.message:
            await cq.message.edit_text(
                await _admin_bot_settings_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_bot_settings_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:price")
    async def ask_price(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.price_per_gb)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_price,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:voldisc")
    async def ask_volume_discount(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.volume_discount_tiers)
        tiers = await _load_volume_discount_tiers(db)
        if tiers:
            cur = "\n".join(
                f"{int(t[0]) if t[0] == int(t[0]) else t[0]},"
                f"{int(t[1]) if t[1] == int(t[1]) else t[1]}"
                for t in tiers
            )
        else:
            cur = "—"
        if cq.message:
            await cq.message.answer(
                T.msg_ask_volume_discount.format(current=html.escape(cur)),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:packages")
    async def ask_buy_packages(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.buy_packages)
        pkgs = await _load_buy_packages(db)
        cur = html.escape(format_packages_admin_current(pkgs))
        if cq.message:
            await cq.message.answer(
                T.msg_ask_buy_packages.format(current=cur),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:trust")
    async def ask_trust(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.trust_wallet)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_trust,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:card")
    async def adm_b_card(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.payment_card)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_card,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:togglebuymode")
    async def adm_toggle_buy_mode(cq: CallbackQuery) -> None:
        cur = await _buy_sell_mode_packages(db)
        await db.set_setting("buy_sell_mode", "volume" if cur else "packages")
        await cq.answer(T.cq_buy_mode_toggled)
        if cq.message:
            await cq.message.edit_text(
                await _admin_shop_product_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=await admin_shop_product_kb(db),
            )

    @admin_cb.callback_query(F.data == "adm:b:togglecard")
    async def adm_toggle_card(cq: CallbackQuery) -> None:
        cur = await db.get_bool_setting("show_payment_card")
        await db.set_bool_setting("show_payment_card", not cur)
        await cq.answer(T.cq_toggle_card)
        if cq.message:
            await cq.message.edit_text(
                await _admin_bot_settings_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_bot_settings_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:togglecrypto")
    async def adm_toggle_crypto(cq: CallbackQuery) -> None:
        cur = await db.get_bool_setting("show_crypto_text")
        await db.set_bool_setting("show_crypto_text", not cur)
        await cq.answer(T.cq_toggle_crypto)
        if cq.message:
            await cq.message.edit_text(
                await _admin_bot_settings_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_bot_settings_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:togglenowpay")
    async def adm_toggle_nowpay(cq: CallbackQuery) -> None:
        cur = await db.get_bool_setting("show_nowpayments")
        await db.set_bool_setting("show_nowpayments", not cur)
        await cq.answer(T.cq_nowpay_toggled)
        if cq.message:
            await cq.message.edit_text(
                await _admin_bot_settings_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_bot_settings_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:toggledisc")
    async def adm_toggle_disc_codes(cq: CallbackQuery) -> None:
        cur = await db.get_bool_setting("discount_codes_enabled")
        await db.set_bool_setting("discount_codes_enabled", not cur)
        await cq.answer(T.cq_disc_toggled)
        if cq.message:
            await cq.message.edit_text(
                await _admin_bot_settings_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_bot_settings_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:nowpaykey")
    async def adm_nowpay_key_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.nowpayments_api_key)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_nowpayments_key,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:support")
    async def adm_support_text_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.support_text)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_support_text,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:guide")
    async def adm_guide_text_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.connection_guide_text)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_guide_text,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:chanid")
    async def adm_chan_id_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.channel_join_id)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_chan_id,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:togglechan")
    async def adm_toggle_chan(cq: CallbackQuery) -> None:
        cur = await db.get_bool_setting("channel_join_required")
        if not cur:
            ids = await db.get_mandatory_channel_ids()
            if not ids:
                await cq.answer(T.err_chan_required_fields, show_alert=True)
                return
            open_ok = False
            for raw in ids:
                if await _resolve_channel_open_url(cq.bot, raw):
                    open_ok = True
                    break
            if not open_ok:
                await cq.answer(T.err_chan_required_fields, show_alert=True)
                return
        await db.set_bool_setting("channel_join_required", not cur)
        await cq.answer(T.cq_toggle_chan)
        if cq.message:
            await cq.message.edit_text(
                await _admin_channel_html(db),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_channel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:mtext")
    async def ask_mtext(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.maintenance_message)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_maint,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data.startswith("adm:mbtn:pick:"))
    async def adm_mbtn_pick(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        bid = (cq.data or "").split(":")[-1]
        if bid not in MAIN_MENU_BUTTON_DEFS or bid == "partner":
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        await cq.answer()
        cfg = await load_main_menu_config(db)
        entry = cfg["buttons"].get(bid) or default_main_menu_entry(bid)
        label = html.escape(str(entry.get("label") or MAIN_MENU_BUTTON_DEFS[bid]["default_label"]))
        status = T.label_tgl_on if entry.get("enabled", True) else T.label_tgl_off
        if cq.message:
            await cq.message.edit_text(
                f"🔘 <b>{label}</b>\nوضعیت: {status}",
                parse_mode=ParseMode.HTML,
                reply_markup=admin_main_button_edit_kb(bid),
            )

    def _colors_table_text(page: int) -> str:
        from button_styles import all_color_table_keys

        page = clamp_colors_page(page)
        return fmt_admin_colors_table(
            page=page + 1,
            pages=colors_table_page_count(),
            total=len(all_color_table_keys()),
        )

    async def _show_colors_table(cq: CallbackQuery, page: int) -> None:
        page = clamp_colors_page(page)
        if not cq.message:
            return
        try:
            await cq.message.edit_text(
                _colors_table_text(page),
                parse_mode=ParseMode.HTML,
                reply_markup=await admin_colors_table_kb(db, page),
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise

    @admin_cb.callback_query(F.data.in_({"adm:colors", "adm:btnstyles"}))
    async def adm_colors_table(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        await _show_colors_table(cq, 0)

    @admin_cb.callback_query(F.data.startswith("adm:colors:pg:"))
    async def adm_colors_page(cq: CallbackQuery, state: FSMContext) -> None:
        raw = (cq.data or "").removeprefix("adm:colors:pg:")
        try:
            page = int(raw)
        except ValueError:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        await state.clear()
        await cq.answer()
        await _show_colors_table(cq, page)

    @admin_cb.callback_query(F.data.startswith("adm:colors:noop:"))
    async def adm_colors_name_noop(cq: CallbackQuery) -> None:
        await cq.answer()

    @admin_cb.callback_query(F.data.startswith("adm:colors:apply:"))
    async def adm_colors_apply(cq: CallbackQuery, state: FSMContext) -> None:
        parts = (cq.data or "").split(":")
        if len(parts) < 6:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        try:
            page = int(parts[3])
        except ValueError:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        token = parts[4]
        key = parts[5]
        if key not in USER_COLOR_TABLE_KEYS or token not in COLOR_PICK_TOKENS:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        style = token
        current = get_effective_style(key) or ""
        new_norm = style or ""
        if current == new_norm:
            await cq.answer(T.cq_color_same, show_alert=False)
            return
        await set_global_button_style(db, key, style)
        await cq.answer(T.cq_color_cycled.format(style=style_label_fa(style)))
        await _show_colors_table(cq, page)

    @admin_cb.callback_query(
        F.data.startswith(("adm:colors:admin", "adm:colors:cat:", "adm:colors:cycle:"))
    )
    async def adm_colors_legacy_to_table(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        await _show_colors_table(cq, 0)

    @admin_cb.callback_query(F.data.startswith("adm:gstyle:set:"))
    async def adm_gstyle_set_legacy(cq: CallbackQuery, state: FSMContext) -> None:
        parts = (cq.data or "").split(":")
        if len(parts) < 5:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        key = parts[3]
        st_raw = parts[4]
        if key not in USER_COLOR_TABLE_KEYS:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        style = None if st_raw == "default" else st_raw
        await set_global_button_style(db, key, style)
        await cq.answer(T.msg_global_style_saved.format(style=style_label_fa(style)))
        await _show_colors_table(cq, 0)

    @admin_cb.callback_query(F.data.startswith(("adm:gstyle:pick:", "adm:mbtn:style:")))
    async def adm_colors_legacy_pick_to_table(cq: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await cq.answer()
        await _show_colors_table(cq, 0)

    @admin_cb.callback_query(F.data.startswith("adm:mbtn:setstyle:"))
    async def adm_mbtn_setstyle_legacy(cq: CallbackQuery, state: FSMContext) -> None:
        parts = (cq.data or "").split(":")
        if len(parts) < 5:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        key = f"mm_{parts[3]}"
        st_raw = parts[4]
        if key not in USER_COLOR_TABLE_KEYS:
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        style = None if st_raw == "default" else st_raw
        await set_global_button_style(db, key, style)
        await cq.answer(T.msg_global_style_saved.format(style=style_label_fa(style)))
        await _show_colors_table(cq, 0)

    @admin_cb.callback_query(F.data.startswith("adm:mbtn:toggle:"))
    async def adm_mbtn_toggle(cq: CallbackQuery, state: FSMContext) -> None:
        bid = (cq.data or "").split(":")[-1]
        if bid not in MAIN_MENU_BUTTON_DEFS or bid == "partner":
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        cfg = await load_main_menu_config(db)
        entry = dict(cfg["buttons"].get(bid) or default_main_menu_entry(bid))
        entry["enabled"] = not bool(entry.get("enabled", True))
        cfg["buttons"][bid] = entry
        await save_main_menu_config(db, cfg)
        await cq.answer(T.msg_main_button_toggled)
        if cq.message:
            await cq.message.edit_text(
                T.msg_admin_buttons_menu,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_main_buttons_kb(cfg),
            )

    @admin_cb.callback_query(F.data.startswith("adm:mbtn:rename:"))
    async def adm_mbtn_rename(cq: CallbackQuery, state: FSMContext) -> None:
        bid = (cq.data or "").split(":")[-1]
        if bid not in MAIN_MENU_BUTTON_DEFS or bid == "partner":
            await cq.answer(T.alert_order_invalid, show_alert=True)
            return
        await cq.answer()
        await state.set_state(AdminBotInputStates.main_button_rename)
        await state.update_data(main_button_id=bid)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_main_button_rename,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:adm:list")
    async def adm_admin_list(cq: CallbackQuery) -> None:
        await cq.answer()
        db_ids = await db.list_db_admin_ids()
        env_ids = sorted(settings.bot_admin_ids)
        lines = [T.msg_admins_list_header]
        for tid in env_ids:
            lines.append(T.msg_admins_list_line.format(tid=tid, tag=" (env)"))
        for tid in db_ids:
            if tid in settings.bot_admin_ids:
                continue
            lines.append(T.msg_admins_list_line.format(tid=tid, tag=""))
        if len(lines) == 1:
            text = T.msg_admins_list_empty
        else:
            text = "".join(lines)[:4096]
        if cq.message:
            await cq.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=admin_admins_kb())

    @admin_cb.callback_query(F.data == "adm:adm:add")
    async def adm_admin_add_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.add_admin_id)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_add_admin,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:adm:rm")
    async def adm_admin_rm_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.remove_admin_id)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_remove_admin,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:disc:add")
    async def adm_disc_add_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.create_discount_code)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_create_discount,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:disc:rm")
    async def adm_disc_rm_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.remove_discount_code)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_remove_discount,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:disc:list")
    async def adm_disc_list_cb(cq: CallbackQuery) -> None:
        await cq.answer()
        codes = await db.list_discount_codes()
        if not codes:
            text = T.msg_discount_list_empty
        else:
            lines = [T.msg_discount_list_header]
            for row in codes:
                max_u = int(row.get("max_uses") or 0)
                used = int(row.get("used_count") or 0)
                max_part = f" / {max_u}" if max_u > 0 else ""
                lines.append(
                    T.msg_discount_list_line.format(
                        code=html.escape(str(row["code"])),
                        pct=float(row.get("percent") or 0),
                        used=used,
                        max_part=max_part,
                    )
                )
            text = "".join(lines)[:4096]
        if cq.message:
            await cq.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=admin_discount_kb())

    @admin_cb.callback_query(F.data == "adm:msg:bcast")
    async def adm_msg_bcast_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.broadcast_message)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_broadcast,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:msg:user")
    async def adm_msg_user_cb(cq: CallbackQuery, state: FSMContext) -> None:
        await cq.answer()
        await state.set_state(AdminBotInputStates.message_user_id)
        if cq.message:
            await cq.message.answer(
                T.msg_ask_message_user_id,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )

    @admin_cb.callback_query(F.data == "adm:b:orders")
    async def list_orders(cq: CallbackQuery) -> None:
        await cq.answer()
        rows = await db.list_pending_orders(10)
        n = await db.count_pending_orders()
        fin_kb = admin_financial_kb(n)
        if not rows:
            if cq.message:
                await cq.message.answer(
                    T.msg_orders_empty,
                    reply_markup=fin_kb,
                    **_plain(),
                )
            return
        for r in rows:
            oid = r["id"]
            extra = r.get("extra") or {}
            wallet_buy = r["kind"] == "buy_config" and bool(extra.get("pay_wallet"))
            cap = T.msg_order_cap.format(
                oid=oid,
                kind=html.escape(str(r["kind"])),
                user_id=r["user_id"],
                amount=float(r["amount"]),
                gb=r.get("gb"),
            )
            kb = order_moderation_kb(oid)
            if wallet_buy and cq.message:
                await cq.message.answer(
                    cap + T.msg_order_wallet_note,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
                continue
            fid = r.get("receipt_file_id")
            if fid and cq.message:
                try:
                    await cq.message.answer_photo(
                        fid,
                        caption=cap,
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb,
                    )
                except Exception:
                    await cq.message.answer(cap + f"\nfile_id={fid}", reply_markup=kb, **_plain())

    @admin_cb.callback_query(F.data.regexp(r"^adm:o:\d+:[ar]$"))
    async def order_decide(cq: CallbackQuery) -> None:
        parts = cq.data.split(":")
        oid = int(parts[2])
        act = parts[3]
        order = await db.get_order(oid)
        if not order or order["status"] != "pending":
            await cq.answer(T.alert_order_stale, show_alert=True)
            return
        await cq.answer()

        if act == "r":
            extra = order.get("extra") or {}
            wallet_reject = order["kind"] == "buy_config" and extra.get("pay_wallet")
            if wallet_reject:
                await db.add_balance(int(order["user_id"]), float(order["amount"]))
            await db.update_order(oid, status="rejected")
            if cq.message:
                await cq.message.edit_reply_markup(reply_markup=None)
            try:
                if wallet_reject:
                    await cq.bot.send_message(
                        int(order["user_id"]),
                        T.msg_user_reject_wallet.format(oid=oid),
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    await cq.bot.send_message(
                        order["user_id"],
                        T.msg_user_reject_plain.format(oid=oid),
                        **_plain(),
                    )
            except Exception:
                pass
            return

        if order["kind"] == "topup":
            new_bal = await db.add_balance(int(order["user_id"]), float(order["amount"]))
            await db.update_order(oid, status="approved_done")
            if cq.message:
                await cq.message.edit_reply_markup(reply_markup=None)
            try:
                await cq.bot.send_message(
                    int(order["user_id"]),
                    T.msg_user_topup_ok.format(oid=oid, bal=new_bal),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
            return

        uid = int(order["user_id"])
        gb = float(order["gb"] or 0)
        amt = float(order["amount"] or 0)

        if order["kind"] == "add_volume":
            extra_o = order.get("extra") or {}
            un = str(extra_o.get("panel_username") or "").strip()
            parent_oid = int(extra_o.get("parent_order_id") or 0)
            if not un:
                if cq.message:
                    await cq.message.answer(
                        T.err_panel_html.format(err=html.escape("اکانت پنل نامشخص")),
                        parse_mode=ParseMode.HTML,
                    )
                return
            ok_vol, _live2, vol_err = await _apply_extra_volume_gb(pg, panel_username=un, gb=gb)
            if ok_vol:
                await db.update_order(oid, status="approved_done")
                if parent_oid:
                    await db.update_order_extra(parent_oid, volume_exhausted_at=None)
                await _record_partner_purchase(db, uid, gb=gb, amount=amt)
                if cq.message:
                    await cq.message.edit_reply_markup(reply_markup=None)
                try:
                    await cq.bot.send_message(
                        uid,
                        T.msg_user_extra_ok.format(oid=oid, gb=gb),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass
                return
            if cq.message:
                await cq.message.answer(
                    T.err_panel_html.format(err=html.escape(str(vol_err or "?"))),
                    parse_mode=ParseMode.HTML,
                )
            return

        extra_buy = order.get("extra") or {}
        cfg_days_raw = extra_buy.get("config_days")
        config_days: int | None
        if cfg_days_raw is not None:
            try:
                config_days = int(cfg_days_raw)
            except (TypeError, ValueError):
                config_days = None
        else:
            config_days = None

        ok, username, sub_raw, pid, last_err = await _try_create_panel_user_for_buy(
            pg,
            uid=uid,
            gb=gb,
            settings=settings,
            db=db,
            config_days=config_days,
        )
        if ok and username and sub_raw is not None:
            await db.update_order(
                oid,
                status="approved_done",
                pasarguard_username=username,
                subscription_url=sub_raw,
                panel_user_id=pid,
            )
            await _consume_order_promo(db, extra_buy)
            await _record_partner_purchase(db, uid, gb=gb, amount=amt)
            if cq.message:
                await cq.message.edit_reply_markup(reply_markup=None)
            panel_cfg = await load_effective_panel_config(db)
            sub_abs = subscription_url_with_base(panel_cfg.pasarguard_base_url, sub_raw)
            days = (
                config_days
                if config_days is not None
                else await db.get_int_setting("default_config_days", 30)
            )
            uname = await _tg_buyer_username(cq.bot, uid)
            new_bal = await db.get_balance(uid)
            cap_user = _invoice_caption_html(
                new_balance=new_bal,
                amount=amt,
                panel_username=username,
                days=days,
                gb=gb,
                sub_url=sub_abs,
                include_buyer_footer=False,
                buyer_tg_id=uid,
                buyer_username_plain=uname,
            )
            cap_ch = _invoice_caption_html(
                new_balance=new_bal,
                amount=amt,
                panel_username=username,
                days=days,
                gb=gb,
                sub_url=sub_abs,
                include_buyer_footer=True,
                buyer_tg_id=uid,
                buyer_username_plain=uname,
            )
            await _post_channel_receipt_buy_approved(
                cq.bot,
                settings,
                db,
                cap_ch=cap_ch,
                sub_abs=sub_abs,
            )
            try:
                await _send_subscription_qr_photo(cq.bot, uid, cap_user, sub_abs)
            except Exception:
                pass
            return

        if cq.message:
            await cq.message.answer(
                T.err_panel_html.format(err=html.escape(str(last_err or "?"))),
                parse_mode=ParseMode.HTML,
            )
        extra_o = order.get("extra") or {}
        if extra_o.get("pay_wallet"):
            await db.add_balance(uid, float(order["amount"]))
            await db.update_order(oid, status="rejected")
        try:
            msg_fail = T.msg_user_buy_fail.format(oid=oid)
            if extra_o.get("pay_wallet"):
                msg_fail += T.msg_user_buy_fail_wallet_suffix
            else:
                msg_fail += T.msg_user_buy_fail_support_suffix
            await cq.bot.send_message(uid, msg_fail, **_plain())
        except Exception:
            pass


def register_admin_bot_fsm(
    admin_fsm: Router,
    *,
    settings: Settings,
    db: Database,
    pg: PasarGuardClient,
) -> None:
    @admin_fsm.message(AdminCreditUserStates.waiting_target_id, AdminFilter(settings, db))
    async def adm_credit_target_id(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if tid is None:
            await m.answer(
                T.err_credit_tid,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )
            return
        if tid <= 0:
            await m.answer(T.err_credit_tid_bad, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        await state.update_data(target_user_id=tid)
        await state.set_state(AdminCreditUserStates.waiting_amount)
        await m.answer(
            T.msg_credit_ask_amount.format(tid=tid),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_input_cancel_kb(),
        )

    @admin_fsm.message(AdminCreditUserStates.waiting_amount, F.text, AdminFilter(settings, db))
    async def adm_credit_amount(m: Message, state: FSMContext) -> None:
        data = await state.get_data()
        tid = int(data.get("target_user_id", 0))
        if tid <= 0:
            await state.clear()
            await m.answer(T.err_credit_tid_bad, reply_markup=admin_root_kb(), **_plain())
            return
        amt = _parse_credit_amount_toman(m.text or "")
        if amt is None:
            await m.answer(T.err_credit_amt, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        if amt < 1_000 or amt > 500_000_000:
            await m.answer(
                T.err_credit_range,
                reply_markup=admin_input_cancel_kb(),
                **_plain(),
            )
            return
        await db.ensure_user(tid)
        new_bal = await db.add_balance(tid, amt)
        await state.clear()
        n = await db.count_pending_orders()
        await m.answer(
            T.msg_credit_done_admin.format(amt=amt, tid=tid, bal=new_bal),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_financial_kb(n),
        )
        try:
            await m.bot.send_message(
                tid,
                T.msg_credit_done_user.format(amt=amt, bal=new_bal),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await m.answer(
                T.msg_credit_notify_fail,
                **_plain(),
            )

    @admin_fsm.message(AdminDeductUserStates.waiting_target_id, AdminFilter(settings, db))
    async def adm_deduct_target_id(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if tid is None:
            await m.answer(
                T.err_credit_tid,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )
            return
        if tid <= 0:
            await m.answer(T.err_credit_tid_bad, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        await state.update_data(target_user_id=tid)
        await state.set_state(AdminDeductUserStates.waiting_amount)
        await m.answer(
            T.msg_deduct_ask_amount.format(tid=tid),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_input_cancel_kb(),
        )

    @admin_fsm.message(AdminDeductUserStates.waiting_amount, F.text, AdminFilter(settings, db))
    async def adm_deduct_amount(m: Message, state: FSMContext) -> None:
        data = await state.get_data()
        tid = int(data.get("target_user_id", 0))
        if tid <= 0:
            await state.clear()
            await m.answer(T.err_credit_tid_bad, reply_markup=admin_root_kb(), **_plain())
            return
        amt = _parse_credit_amount_toman(m.text or "")
        if amt is None:
            await m.answer(T.err_credit_amt, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        if amt < 1_000 or amt > 500_000_000:
            await m.answer(
                T.err_credit_range,
                reply_markup=admin_input_cancel_kb(),
                **_plain(),
            )
            return
        await db.ensure_user(tid)
        new_bal = await db.try_deduct_balance(tid, amt)
        if new_bal is None:
            await m.answer(
                T.err_deduct_insufficient,
                reply_markup=admin_input_cancel_kb(),
                **_plain(),
            )
            return
        await state.clear()
        n = await db.count_pending_orders()
        await m.answer(
            T.msg_deduct_done_admin.format(amt=amt, tid=tid, bal=new_bal),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_financial_kb(n),
        )
        try:
            await m.bot.send_message(
                tid,
                T.msg_deduct_done_user.format(amt=amt, bal=new_bal),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await m.answer(T.msg_credit_notify_fail, **_plain())

    @admin_fsm.message(AdminBotInputStates.partner_price_per_gb, F.text, AdminFilter(settings, db))
    async def save_partner_price(m: Message, state: FSMContext) -> None:
        try:
            v = float((m.text or "").strip().replace(",", "."))
        except ValueError:
            await m.answer(T.err_price_invalid, **_plain())
            return
        if v <= 0:
            await m.answer(T.err_price_positive, **_plain())
            return
        await db.set_setting("partner_price_per_gb", str(int(v) if v == int(v) else v))
        await state.clear()
        await m.answer(
            T.msg_partner_price_saved.format(v=v),
            parse_mode=ParseMode.HTML,
            reply_markup=partner_manage_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.partner_volume_discount_tiers, F.text, AdminFilter(settings, db))
    async def save_partner_volume_discount(m: Message, state: FSMContext) -> None:
        parsed = parse_admin_discount_text(m.text or "")
        if parsed is None:
            await m.answer(
                T.err_partner_volume_discount_parse,
                reply_markup=admin_input_cancel_kb(),
                **_plain(),
            )
            return
        await db.set_partner_volume_discount_tiers_json(tiers_to_json(parsed))
        await state.clear()
        tiers = parse_tiers_from_json(tiers_to_json(parsed))
        preview = format_tiers_preview_fa(tiers)
        await m.answer(
            T.msg_partner_volume_discount_saved.format(preview=preview),
            parse_mode=ParseMode.HTML,
            reply_markup=partner_manage_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.partner_add, AdminFilter(settings, db))
    async def save_partner_add(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if tid is None:
            await m.answer(
                T.err_credit_tid,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )
            return
        label = ""
        raw_lines = [ln.strip() for ln in (m.text or "").splitlines() if ln.strip()]
        if len(raw_lines) >= 2:
            label = raw_lines[1]
        added = await db.add_partner(tid, label=label)
        await state.clear()
        if added:
            await m.answer(
                T.msg_partner_added.format(tid=tid),
                parse_mode=ParseMode.HTML,
                reply_markup=partner_manage_kb(),
            )
        else:
            await m.answer(
                T.msg_partner_already,
                parse_mode=ParseMode.HTML,
                reply_markup=partner_manage_kb(),
            )

    @admin_fsm.message(AdminBotInputStates.partner_buy_packages, F.text, AdminFilter(settings, db))
    async def save_partner_buy_packages(m: Message, state: FSMContext) -> None:
        parsed = parse_admin_packages_text(m.text or "")
        if parsed is None:
            await m.answer(
                T.err_buy_packages_parse,
                reply_markup=admin_input_cancel_kb(),
                **_plain(),
            )
            return
        await db.set_partner_buy_packages_json(packages_to_json(parsed))
        await state.clear()
        pkgs = parse_packages_from_json(packages_to_json(parsed))
        preview = format_packages_preview_fa(pkgs)
        await m.answer(
            T.msg_partner_buy_packages_saved.format(preview=preview),
            parse_mode=ParseMode.HTML,
            reply_markup=partner_manage_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.buy_packages, F.text, AdminFilter(settings, db))
    async def save_buy_packages(m: Message, state: FSMContext) -> None:
        parsed = parse_admin_packages_text(m.text or "")
        if parsed is None:
            await m.answer(
                T.err_buy_packages_parse,
                reply_markup=admin_input_cancel_kb(),
                **_plain(),
            )
            return
        await db.set_buy_packages_json(packages_to_json(parsed))
        await state.clear()
        pkgs = parse_packages_from_json(packages_to_json(parsed))
        preview = format_packages_preview_fa(pkgs)
        await m.answer(
            T.msg_buy_packages_saved.format(preview=preview),
            parse_mode=ParseMode.HTML,
            reply_markup=await admin_shop_product_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.volume_discount_tiers, F.text, AdminFilter(settings, db))
    async def save_volume_discount(m: Message, state: FSMContext) -> None:
        parsed = parse_admin_discount_text(m.text or "")
        if parsed is None:
            await m.answer(T.err_volume_discount_parse, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        await db.set_volume_discount_tiers_json(tiers_to_json(parsed))
        await state.clear()
        tiers = parse_tiers_from_json(tiers_to_json(parsed))
        preview = format_tiers_preview_fa(tiers)
        await m.answer(
            T.msg_volume_discount_saved.format(preview=preview),
            parse_mode=ParseMode.HTML,
            reply_markup=await admin_shop_product_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.price_per_gb, F.text, AdminFilter(settings, db))
    async def save_price(m: Message, state: FSMContext) -> None:
        try:
            v = float((m.text or "").strip().replace(",", "."))
        except ValueError:
            await m.answer(T.err_price_invalid, **_plain())
            return
        if v <= 0:
            await m.answer(T.err_price_positive, **_plain())
            return
        await db.set_setting("price_per_gb", str(int(v) if v == int(v) else v))
        await state.clear()
        await m.answer(
            T.msg_price_saved.format(v=v),
            parse_mode=ParseMode.HTML,
            reply_markup=await admin_shop_product_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.reset_test_user, AdminFilter(settings, db))
    async def save_reset_test_user(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if tid is None:
            await m.answer(
                T.err_credit_tid,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )
            return
        n = await db.reset_user_test_eligibility(tid)
        await state.clear()
        await m.answer(
            T.msg_admin_reset_test_done.format(tid=tid, n=n),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_test_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.test_service_gb, F.text, AdminFilter(settings, db))
    async def save_test_gb(m: Message, state: FSMContext) -> None:
        try:
            gb = float((m.text or "").strip().replace(",", "."))
        except ValueError:
            await m.answer(T.err_buy_gb_number, **_plain())
            return
        if gb < 0.1 or gb > 50:
            await m.answer(T.err_test_gb_range, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        await db.set_setting("test_service_gb", str(gb if gb != int(gb) else int(gb)))
        await state.clear()
        await m.answer(
            T.msg_test_gb_saved.format(gb=gb),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_test_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.payment_card, F.text, AdminFilter(settings, db))
    async def save_payment_card(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        if raw == "-":
            await db.set_setting("payment_card_text", "")
        elif len(raw) < 5:
            await m.answer(T.err_card_short, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        else:
            await db.set_setting("payment_card_text", raw)
        await state.clear()
        await m.answer(
            T.msg_card_saved,
            parse_mode=ParseMode.HTML,
            reply_markup=await admin_shop_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.channel_join_id, F.text, AdminFilter(settings, db))
    async def save_chan_join_id(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        if raw == "-":
            await db.set_mandatory_channel_ids([])
            await state.clear()
            await m.answer(
                T.msg_chan_id_saved.format(n=0),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_channel_kb(),
            )
            return
        ids = _parse_channel_ids_text(raw)
        if not ids:
            await m.answer(T.err_chan_id_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        for tid in ids:
            if not _validate_chan_id(tid):
                await m.answer(T.err_chan_id_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
                return
        await db.set_mandatory_channel_ids(ids)
        await state.clear()
        await m.answer(
            T.msg_chan_id_saved.format(n=len(ids)),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_channel_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.trust_wallet, F.text, AdminFilter(settings, db))
    async def save_trust(m: Message, state: FSMContext) -> None:
        txt = (m.text or "").strip()
        if len(txt) < 5:
            await m.answer(T.err_trust_short, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        await db.set_setting("trust_wallet_text", txt)
        await state.clear()
        await m.answer(
            T.msg_trust_saved,
            parse_mode=ParseMode.HTML,
            reply_markup=await admin_shop_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.maintenance_message, F.text, AdminFilter(settings, db))
    async def save_maint_msg(m: Message, state: FSMContext) -> None:
        txt = (m.text or "").strip()
        await db.set_setting("maintenance_message", txt)
        await state.clear()
        await m.answer(
            T.msg_maint_saved,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_bot_settings_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.welcome_message, AdminFilter(settings, db))
    async def save_welcome_msg(m: Message, state: FSMContext) -> None:
        txt = (m.text or m.caption or "").strip()
        if not txt:
            html_raw = getattr(m, "html_text", None) or getattr(m, "md_text", None)
            if html_raw:
                txt = str(html_raw).strip()
        if not txt:
            await m.answer(
                "⚠️ فقط متن بفرستید (می‌توانید چند خط و HTML داشته باشد).",
                reply_markup=admin_input_cancel_kb(),
                **_plain(),
            )
            return
        if txt == "-":
            await db.set_setting("welcome_message", "")
        else:
            await db.set_setting("welcome_message", txt)
        await state.clear()
        await m.answer(
            T.msg_welcome_saved,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_texts_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.receipt_channel_id, F.text, AdminFilter(settings, db))
    async def save_receipt_channel(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        if raw == "-":
            await db.set_setting("receipt_channel_id", "")
        elif not _validate_chan_id(raw):
            await m.answer(T.err_receipt_channel_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        else:
            await db.set_setting("receipt_channel_id", raw)
        await state.clear()
        await m.answer(
            T.msg_receipt_channel_saved,
            parse_mode=ParseMode.HTML,
            reply_markup=admin_bot_settings_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.receipt_admin_add, F.text, AdminFilter(settings, db))
    async def save_receipt_admin_add(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if not tid:
            await m.answer(T.err_credit_tid, parse_mode=ParseMode.HTML, reply_markup=admin_input_cancel_kb())
            return
        await state.clear()
        added = await db.add_receipt_admin(tid)
        if added:
            await m.answer(
                T.msg_receipt_admin_added.format(tid=tid),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_receipt_admins_kb(),
            )
        else:
            await m.answer(
                T.msg_receipt_admin_already,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_receipt_admins_kb(),
            )

    @admin_fsm.message(AdminBotInputStates.receipt_admin_rm, F.text, AdminFilter(settings, db))
    async def save_receipt_admin_rm(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if not tid:
            await m.answer(T.err_credit_tid, parse_mode=ParseMode.HTML, reply_markup=admin_input_cancel_kb())
            return
        await state.clear()
        removed = await db.remove_receipt_admin(tid)
        if removed:
            await m.answer(
                T.msg_receipt_admin_removed.format(tid=tid),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_receipt_admins_kb(),
            )
        else:
            await m.answer(
                T.msg_receipt_admin_not_found,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_receipt_admins_kb(),
            )

    @admin_fsm.message(AdminBotInputStates.panel_base_url, F.text, AdminFilter(settings, db))
    async def save_panel_url(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        data = await state.get_data()
        wizard = bool(data.get("panel_setup"))
        if wizard:
            if not _valid_panel_url(raw):
                await m.answer(T.err_panel_url_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
                return
            await db.set_setting("pasarguard_base_url", raw.rstrip("/"))
            await state.set_state(AdminBotInputStates.panel_username)
            await m.answer(
                T.msg_panel_add_step_user,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )
            return
        if raw == "-":
            await db.set_setting("pasarguard_base_url", "")
            await db.set_setting("pasarguard_username", "")
            await db.set_setting("pasarguard_password", "")
        elif not _valid_panel_url(raw):
            await m.answer(T.err_panel_url_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        else:
            await db.set_setting("pasarguard_base_url", raw.rstrip("/"))
        await state.clear()
        extra = ""
        cfg = await load_effective_panel_config(db)
        if panel_is_configured(cfg):
            err = await _try_reconnect_panel(pg, db)
            if err:
                extra = "\n" + T.msg_panel_connect_fail.format(err=html.escape(err))
            else:
                extra = "\n" + T.msg_panel_connect_ok
        await m.answer(
            T.msg_panel_saved + extra,
            parse_mode=ParseMode.HTML,
            reply_markup=await _admin_panel_reply_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.panel_username, F.text, AdminFilter(settings, db))
    async def save_panel_user(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        data = await state.get_data()
        wizard = bool(data.get("panel_setup"))
        if wizard:
            if len(raw) < 2:
                await m.answer(T.err_panel_url_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
                return
            await db.set_setting("pasarguard_username", raw)
            await state.set_state(AdminBotInputStates.panel_password)
            await m.answer(
                T.msg_panel_add_step_pass,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_input_cancel_kb(),
            )
            return
        if raw == "-":
            await db.set_setting("pasarguard_username", "")
        elif len(raw) < 2:
            await m.answer(T.err_panel_url_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        else:
            await db.set_setting("pasarguard_username", raw)
        await state.clear()
        extra = ""
        cfg = await load_effective_panel_config(db)
        if panel_is_configured(cfg):
            err = await _try_reconnect_panel(pg, db)
            if err:
                extra = "\n" + T.msg_panel_connect_fail.format(err=html.escape(err))
            else:
                extra = "\n" + T.msg_panel_connect_ok
        await m.answer(
            T.msg_panel_saved + extra,
            parse_mode=ParseMode.HTML,
            reply_markup=await _admin_panel_reply_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.panel_password, F.text, AdminFilter(settings, db))
    async def save_panel_pass(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        data = await state.get_data()
        wizard = bool(data.get("panel_setup"))
        if wizard:
            if len(raw) < 1:
                await m.answer(T.err_panel_url_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
                return
            await db.set_setting("pasarguard_password", raw)
            await state.clear()
            err = await _try_reconnect_panel(pg, db)
            lines = [T.msg_panel_add_done]
            if err:
                lines.append(T.msg_panel_connect_fail.format(err=html.escape(err)))
            else:
                lines.append(T.msg_panel_connect_ok)
            await m.answer(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=await _admin_panel_reply_kb(db),
            )
            return
        if raw == "-":
            await db.set_setting("pasarguard_password", "")
        elif len(raw) < 1:
            await m.answer(T.err_panel_url_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        else:
            await db.set_setting("pasarguard_password", raw)
        await state.clear()
        extra = ""
        cfg = await load_effective_panel_config(db)
        if panel_is_configured(cfg):
            err = await _try_reconnect_panel(pg, db)
            if err:
                extra = "\n" + T.msg_panel_connect_fail.format(err=html.escape(err))
            else:
                extra = "\n" + T.msg_panel_connect_ok
        await m.answer(
            T.msg_panel_saved + extra,
            parse_mode=ParseMode.HTML,
            reply_markup=await _admin_panel_reply_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.panel_username_prefix, F.text, AdminFilter(settings, db))
    async def save_panel_prefix(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        if raw == "-":
            await db.set_setting("panel_username_prefix", "")
        else:
            prefix = re.sub(r"[^a-zA-Z0-9_]", "", raw).lower()
            if not prefix:
                await m.answer(T.err_panel_prefix_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
                return
            await db.set_setting("panel_username_prefix", prefix[:20])
        await state.clear()
        await m.answer(
            T.msg_panel_saved,
            parse_mode=ParseMode.HTML,
            reply_markup=await _admin_panel_reply_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.panel_username_start, F.text, AdminFilter(settings, db))
    async def save_panel_start(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        if raw == "-":
            await db.set_setting("panel_username_start", "")
        else:
            try:
                n = int(float(raw))
            except ValueError:
                await m.answer(T.err_panel_start_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
                return
            if n < 1:
                await m.answer(T.err_panel_start_invalid, reply_markup=admin_input_cancel_kb(), **_plain())
                return
            await db.set_setting("panel_username_start", str(n))
        await state.clear()
        await m.answer(
            T.msg_panel_saved,
            parse_mode=ParseMode.HTML,
            reply_markup=await _admin_panel_reply_kb(db),
        )

    @admin_fsm.message(AdminBotInputStates.support_text, F.text, AdminFilter(settings, db))
    async def save_support_text(m: Message, state: FSMContext) -> None:
        txt = (m.text or "").strip()
        if txt == "-":
            await db.set_setting("support_text", "")
        else:
            await db.set_setting("support_text", txt)
        await state.clear()
        await m.answer(T.msg_support_saved, parse_mode=ParseMode.HTML, reply_markup=admin_texts_kb())

    @admin_fsm.message(AdminBotInputStates.connection_guide_text, F.text, AdminFilter(settings, db))
    async def save_guide_text(m: Message, state: FSMContext) -> None:
        txt = (m.text or "").strip()
        if txt == "-":
            await db.set_setting("connection_guide_text", "")
        else:
            await db.set_setting("connection_guide_text", txt)
        await state.clear()
        await m.answer(T.msg_guide_saved, parse_mode=ParseMode.HTML, reply_markup=admin_texts_kb())

    @admin_fsm.message(AdminBotInputStates.nowpayments_api_key, F.text, AdminFilter(settings, db))
    async def save_nowpay_key(m: Message, state: FSMContext) -> None:
        raw = (m.text or "").strip()
        if raw == "-":
            await db.set_setting("nowpayments_api_key", "")
        else:
            await db.set_setting("nowpayments_api_key", raw)
        await state.clear()
        await m.answer(T.msg_nowpayments_saved, parse_mode=ParseMode.HTML, reply_markup=await admin_shop_kb(db))

    @admin_fsm.message(AdminBotInputStates.main_button_rename, F.text, AdminFilter(settings, db))
    async def save_main_button_rename(m: Message, state: FSMContext) -> None:
        data = await state.get_data()
        bid = str(data.get("main_button_id") or "")
        label = (m.text or "").strip()
        if bid not in MAIN_MENU_BUTTON_DEFS or not label:
            await m.answer(T.msg_ask_main_button_rename, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        cfg = await load_main_menu_config(db)
        entry = dict(cfg["buttons"].get(bid) or default_main_menu_entry(bid))
        entry["label"] = label[:64]
        cfg["buttons"][bid] = entry
        await save_main_menu_config(db, cfg)
        await state.clear()
        await m.answer(T.msg_main_button_renamed, parse_mode=ParseMode.HTML, reply_markup=admin_main_buttons_kb(cfg))

    @admin_fsm.message(AdminBotInputStates.broadcast_message, F.text, AdminFilter(settings, db))
    async def save_broadcast(m: Message, state: FSMContext) -> None:
        text = (m.text or "").strip()
        if not text:
            await m.answer(T.msg_ask_broadcast, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        await state.clear()
        user_ids = await db.list_all_user_telegram_ids()
        ok = 0
        fail = 0
        for tid in user_ids:
            try:
                await m.bot.send_message(tid, text, parse_mode=ParseMode.HTML)
                ok += 1
            except Exception:
                fail += 1
            await asyncio.sleep(0.05)
        await m.answer(
            T.msg_broadcast_done.format(ok=ok, fail=fail),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_messaging_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.message_user_id, AdminFilter(settings, db))
    async def save_message_user_id(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if tid is None or tid <= 0:
            await m.answer(T.err_credit_tid, parse_mode=ParseMode.HTML, reply_markup=admin_input_cancel_kb())
            return
        await state.update_data(message_target_id=tid)
        await state.set_state(AdminBotInputStates.message_user_text)
        await m.answer(
            T.msg_ask_message_user_text.format(tid=tid),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_input_cancel_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.message_user_text, F.text, AdminFilter(settings, db))
    async def save_message_user_text(m: Message, state: FSMContext) -> None:
        data = await state.get_data()
        tid = int(data.get("message_target_id") or 0)
        text = (m.text or "").strip()
        if tid <= 0 or not text:
            await m.answer(T.err_credit_tid_bad, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        await state.clear()
        try:
            await m.bot.send_message(tid, text, parse_mode=ParseMode.HTML)
            await m.answer(
                T.msg_message_user_done.format(tid=tid),
                parse_mode=ParseMode.HTML,
                reply_markup=admin_messaging_kb(),
            )
        except Exception:
            await m.answer(T.msg_credit_notify_fail, reply_markup=admin_messaging_kb(), **_plain())

    @admin_fsm.message(AdminBotInputStates.add_admin_id, AdminFilter(settings, db))
    async def save_add_admin(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if tid is None or tid <= 0:
            await m.answer(T.err_credit_tid, parse_mode=ParseMode.HTML, reply_markup=admin_input_cancel_kb())
            return
        await state.clear()
        if await db.is_bot_admin(tid, settings.bot_admin_ids):
            await m.answer(T.msg_admin_already, parse_mode=ParseMode.HTML, reply_markup=admin_admins_kb())
            return
        added = await db.add_db_admin(tid)
        if not added:
            await m.answer(T.msg_admin_already, parse_mode=ParseMode.HTML, reply_markup=admin_admins_kb())
            return
        await m.answer(T.msg_admin_added.format(tid=tid), parse_mode=ParseMode.HTML, reply_markup=admin_admins_kb())

    @admin_fsm.message(AdminBotInputStates.remove_admin_id, AdminFilter(settings, db))
    async def save_remove_admin(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if tid is None or tid <= 0:
            await m.answer(T.err_credit_tid, parse_mode=ParseMode.HTML, reply_markup=admin_input_cancel_kb())
            return
        await state.clear()
        if await db.remove_db_admin(tid, settings.bot_admin_ids):
            await m.answer(T.msg_admin_removed.format(tid=tid), parse_mode=ParseMode.HTML, reply_markup=admin_admins_kb())
        else:
            await m.answer(T.msg_admin_remove_fail, parse_mode=ParseMode.HTML, reply_markup=admin_admins_kb())

    @admin_fsm.message(AdminBotInputStates.create_discount_code, F.text, AdminFilter(settings, db))
    async def save_create_discount(m: Message, state: FSMContext) -> None:
        parts = [p.strip() for p in (m.text or "").replace("،", ",").split(",") if p.strip()]
        if len(parts) < 2:
            await m.answer(T.err_discount_format, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        code = parts[0].upper()
        try:
            pct = float(parts[1].replace(",", "."))
        except ValueError:
            await m.answer(T.err_discount_format, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        max_uses = 0
        if len(parts) >= 3:
            try:
                max_uses = int(float(parts[2]))
            except ValueError:
                await m.answer(T.err_discount_format, reply_markup=admin_input_cancel_kb(), **_plain())
                return
        if pct <= 0 or pct > 100:
            await m.answer(T.err_discount_format, reply_markup=admin_input_cancel_kb(), **_plain())
            return
        ok = await db.add_discount_code(code, pct, max_uses=max_uses)
        await state.clear()
        if not ok:
            await m.answer(T.msg_discount_exists, parse_mode=ParseMode.HTML, reply_markup=admin_discount_kb())
            return
        await m.answer(
            T.msg_discount_created.format(code=html.escape(code), pct=pct),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_discount_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.remove_discount_code, F.text, AdminFilter(settings, db))
    async def save_remove_discount(m: Message, state: FSMContext) -> None:
        code = (m.text or "").strip().upper()
        await state.clear()
        if not code or not await db.remove_discount_code(code):
            await m.answer(T.msg_discount_not_found, parse_mode=ParseMode.HTML, reply_markup=admin_discount_kb())
            return
        await m.answer(
            T.msg_discount_removed.format(code=html.escape(code)),
            parse_mode=ParseMode.HTML,
            reply_markup=admin_discount_kb(),
        )

    @admin_fsm.message(AdminBotInputStates.user_stats_lookup, AdminFilter(settings, db))
    async def save_user_stats_lookup(m: Message, state: FSMContext) -> None:
        tid = _parse_credit_target_user_id(m)
        if tid is None or tid <= 0:
            await m.answer(T.err_credit_tid, parse_mode=ParseMode.HTML, reply_markup=admin_input_cancel_kb())
            return
        await state.clear()
        text = await _format_user_stats_html(db, tid)
        await m.answer(text, parse_mode=ParseMode.HTML, reply_markup=admin_root_kb())

# -*- coding: utf-8 -*-
"""رنگ دکمه‌های شیشه‌ای تلگرام — رجیستری یکپارچهٔ همهٔ دکمه‌های ربات."""

from __future__ import annotations

import json
import re
from typing import Any

from aiogram.types import InlineKeyboardButton

from database import Database

VALID_BUTTON_STYLES: tuple[str, ...] = ("", "primary", "success", "danger")

STYLE_LABELS_FA: dict[str, str] = {
    "": "⚪ پیش‌فرض",
    "primary": "🔵 آبی",
    "success": "🟢 سبز",
    "danger": "🔴 قرمز",
}

# (token, برچسب دکمه, style تلگرام)
COLOR_PICK_OPTIONS: tuple[tuple[str, str, str | None], ...] = (
    ("danger", "قرمز", "danger"),
    ("primary", "آبی", "primary"),
    ("success", "سبز", "success"),
)

COLOR_PICK_TOKENS: frozenset[str] = frozenset(t[0] for t in COLOR_PICK_OPTIONS)

# ——— دسته‌بندی برای پنل ادمین ———
STYLE_CATEGORIES: dict[str, tuple[str, list[str]]] = {
    "main": (
        "🏠 منوی اصلی",
        [
            "mm_buy",
            "mm_services",
            "mm_account",
            "mm_topup",
            "mm_support",
            "mm_guide",
            "mm_test",
            "mm_partner",
            "mm_admin",
        ],
    ),
    "payment": (
        "💳 پرداخت و شارژ",
        [
            "pay_wallet",
            "pay_card",
            "pay_crypto",
            "pay_nowpay",
            "apply_discount",
            "check_nowpay",
        ],
    ),
    "service": (
        "📦 سرویس‌های من",
        [
            "svc_open",
            "svc_extra",
            "svc_link",
            "svc_qr",
            "svc_disable",
            "svc_enable",
            "svc_delete",
            "svc_revoke",
            "page_prev",
            "page_next",
        ],
    ),
    "actions": (
        "🔘 عمومی",
        [
            "home",
            "cancel",
            "confirm_yes",
            "confirm_no",
            "delete",
            "admin_back",
        ],
    ),
    "channel": (
        "📢 جوین کانال",
        ["channel_join", "check_join"],
    ),
    "partner": (
        "👥 همکاری",
        ["partner_settle"],
    ),
    "orders": (
        "📋 سفارش‌ها",
        ["order_approve", "order_reject"],
    ),
    "test": (
        "🧪 سرویس تست",
        ["test_claim"],
    ),
    "admin_root": (
        "🛠 ادمین — منوی اصلی",
        [
            "adm_fin",
            "adm_shop",
            "adm_chan",
            "adm_admins",
            "adm_disc",
            "adm_msg",
            "adm_btns",
            "adm_texts",
            "adm_ustats",
            "adm_panel_menu",
            "adm_bot",
            "adm_test_menu",
            "adm_colors",
            "adm_home",
        ],
    ),
    "admin_fin": (
        "💰 ادمین — مالی",
        [
            "adm_b_ballist",
            "adm_b_addbal",
            "adm_b_dedbal",
            "adm_b_orders",
            "adm_pmenu",
        ],
    ),
    "admin_shop": (
        "🛒 ادمین — فروشگاه",
        [
            "adm_shop_product",
            "adm_b_card",
            "adm_b_trust",
            "adm_b_nowpaykey",
            "adm_b_togglebuymode",
            "adm_b_price",
            "adm_b_voldisc",
            "adm_b_packages",
        ],
    ),
    "admin_chan": (
        "📢 ادمین — کانال",
        ["adm_b_chanid", "adm_b_chanurl", "adm_b_togglechan"],
    ),
    "admin_admins": (
        "👮 ادمین — ادمین‌ها",
        ["adm_adm_list", "adm_adm_add", "adm_adm_rm"],
    ),
    "admin_disc": (
        "🏷 ادمین — تخفیف",
        ["adm_disc_add", "adm_disc_rm", "adm_disc_list"],
    ),
    "admin_msg": (
        "📣 ادمین — پیام",
        ["adm_msg_bcast", "adm_msg_user"],
    ),
    "admin_texts": (
        "✏️ ادمین — متن‌ها",
        ["adm_b_welcome", "adm_b_support", "adm_b_guide"],
    ),
    "admin_bot": (
        "⚙️ ادمین — تنظیمات ربات",
        [
            "adm_b_togglemaint",
            "adm_b_mtext",
            "adm_b_togglecard",
            "adm_b_togglecrypto",
            "adm_b_togglebuy",
            "adm_b_togglenowpay",
            "adm_b_toggledisc",
            "adm_b_receiptchan",
            "adm_export_run",
        ],
    ),
    "admin_test": (
        "🧪 ادمین — سرویس تست",
        ["adm_b_testgb", "adm_b_resettest"],
    ),
    "admin_panel": (
        "🖥 ادمین — پنل VPN",
        [
            "adm_panel_add",
            "adm_panel_remove",
            "adm_panel_url",
            "adm_panel_user",
            "adm_panel_pass",
            "adm_panel_groups",
            "adm_panel_prefix",
            "adm_panel_start",
        ],
    ),
    "admin_partner": (
        "👥 ادمین — همکار",
        [
            "adm_p_price",
            "adm_p_add",
            "adm_p_list",
            "adm_p_usage",
            "adm_p_voldisc",
            "adm_p_packages",
            "adm_p_rm",
        ],
    ),
    "admin_ui": (
        "🎨 ادمین — دکمه‌های تنظیمات",
        ["admin_nav"],
    ),
}

# دسته‌های مشتری / ادمین برای منوی تنظیم رنگ
CUSTOMER_COLOR_CATEGORY_IDS: tuple[str, ...] = (
    "main",
    "payment",
    "service",
    "actions",
    "channel",
    "partner",
    "orders",
    "test",
)

# فقط دکمه‌های قابل‌فهم برای کاربر عادی در جدول تنظیم رنگ
USER_COLOR_TABLE_KEYS_ORDERED: list[str] = [
    "mm_buy",
    "mm_services",
    "mm_account",
    "mm_topup",
    "mm_test",
    "mm_guide",
    "mm_support",
    "pay_wallet",
    "pay_card",
    "pay_crypto",
    "pay_nowpay",
    "apply_discount",
    "check_nowpay",
    "channel_join",
    "check_join",
    "svc_extra",
    "svc_link",
    "svc_qr",
    "svc_delete",
    "home",
    "cancel",
    "test_claim",
]

ADMIN_COLOR_CATEGORY_IDS: tuple[str, ...] = (
    "admin_root",
    "admin_fin",
    "admin_shop",
    "admin_chan",
    "admin_admins",
    "admin_disc",
    "admin_msg",
    "admin_texts",
    "admin_bot",
    "admin_test",
    "admin_panel",
    "admin_partner",
    "admin_ui",
)

BUTTON_STYLE_LABELS: dict[str, str] = {
    "mm_buy": "🛒 خرید سرویس",
    "mm_services": "📦 سرویس های من",
    "mm_account": "👤 حساب کاربری",
    "mm_topup": "💰 افزایش موجودی",
    "mm_support": "💬 پشتیبانی",
    "mm_guide": "📖 راهنمای اتصال",
    "mm_test": "🧪 اکانت تست",
    "mm_partner": "👥 پنل همکاری",
    "mm_admin": "🛠 پنل ادمین",
    "pay_wallet": "💳 پرداخت از کیف پول",
    "pay_card": "🏦 کارت به کارت",
    "pay_crypto": "💎 ارز دیجیتال",
    "pay_nowpay": "🌐 پرداخت آنلاین",
    "apply_discount": "🏷 کد تخفیف",
    "check_nowpay": "🔄 بررسی پرداخت",
    "svc_open": "📦 باز کردن سرویس",
    "svc_extra": "📈 خرید حجم اضافه",
    "svc_link": "🔗 لینک اشتراک",
    "svc_qr": "📲 QR اشتراک",
    "svc_disable": "⛔ خاموش کردن اکانت",
    "svc_enable": "✅ روشن کردن اکانت",
    "svc_delete": "🗑 حذف سرویس",
    "svc_revoke": "🔁 تغییر لینک ساب",
    "page_prev": "◀️ قبلی",
    "page_next": "بعدی ▶️",
    "home": "🏠 منوی اصلی",
    "cancel": "⬅️ لغو / انصراف",
    "confirm_yes": "✅ بله / تأیید",
    "confirm_no": "❌ خیر / رد",
    "delete": "🗑 حذف",
    "admin_back": "⬅️ بازگشت (ادمین)",
    "channel_join": "📢 ورود به کانال",
    "check_join": "✅ عضویت انجام شد",
    "partner_settle": "💰 تسویه همکار",
    "order_approve": "✅ تأیید سفارش",
    "order_reject": "❌ رد سفارش",
    "test_claim": "🧪 دریافت سرویس تست",
    "admin_nav": "دکمه‌های پنل تنظیمات",
    "adm_fin": "مدیریت مالی",
    "adm_shop": "فروشگاه",
    "adm_chan": "تنظیمات کانال",
    "adm_admins": "ادمین‌ها",
    "adm_disc": "کد تخفیف",
    "adm_msg": "ارسال پیام",
    "adm_btns": "دکمه‌های صفحه اصلی",
    "adm_texts": "تنظیم متن‌ها",
    "adm_ustats": "آمار کاربر",
    "adm_panel_menu": "تنظیمات پنل",
    "adm_bot": "تنظیمات ربات",
    "adm_test_menu": "سرویس تست",
    "adm_colors": "تنظیمات رنگ",
    "adm_home": "برگشت به منوی اصلی (ادمین)",
    "adm_b_ballist": "لیست موجودی‌ها",
    "adm_b_addbal": "افزایش موجودی",
    "adm_b_dedbal": "کسر موجودی",
    "adm_b_orders": "سفارش‌ها",
    "adm_pmenu": "مدیریت همکار (مالی)",
    "adm_shop_product": "تنظیم محصول",
    "adm_b_card": "متن کارت",
    "adm_b_trust": "متن ارز دیجیتال",
    "adm_b_nowpaykey": "کلید NOWPayments",
    "adm_b_togglebuymode": "نوع فروش",
    "adm_b_price": "قیمت هر گیگ",
    "adm_b_voldisc": "تخفیف حجمی",
    "adm_b_packages": "بسته‌های فروش",
    "adm_b_chanid": "آیدی کانال",
    "adm_b_chanurl": "لینک جوین",
    "adm_b_togglechan": "جوین اجباری",
    "adm_adm_list": "لیست ادمین‌ها",
    "adm_adm_add": "افزودن ادمین",
    "adm_adm_rm": "حذف ادمین",
    "adm_disc_add": "ساخت کد تخفیف",
    "adm_disc_rm": "حذف کد تخفیف",
    "adm_disc_list": "لیست کدهای تخفیف",
    "adm_msg_bcast": "پیام همگانی",
    "adm_msg_user": "پیام به کاربر",
    "adm_b_welcome": "متن خوش‌آمدگویی",
    "adm_b_support": "متن پشتیبانی",
    "adm_b_guide": "متن راهنما",
    "adm_b_togglemaint": "حالت به‌روزرسانی",
    "adm_b_mtext": "متن به‌روزرسانی",
    "adm_b_togglecard": "کارت به کارت",
    "adm_b_togglecrypto": "ارز دیجیتال",
    "adm_b_togglebuy": "قطع/وصل خرید",
    "adm_b_togglenowpay": "NOWPayments",
    "adm_b_toggledisc": "کد تخفیف (تگل)",
    "adm_b_receiptchan": "کانال رسیدها",
    "adm_export_run": "خروجی کانفیگ‌ها",
    "adm_b_testgb": "حجم سرویس تست",
    "adm_b_resettest": "ریست سرویس تست",
    "adm_panel_add": "افزودن پنل",
    "adm_panel_remove": "حذف پنل",
    "adm_panel_url": "آدرس پنل",
    "adm_panel_user": "نام کاربری پنل",
    "adm_panel_pass": "رمز پنل",
    "adm_panel_groups": "گروه‌های پنل",
    "adm_panel_prefix": "پیشوند پنل",
    "adm_panel_start": "شماره شروع پنل",
    "adm_p_price": "قیمت همکار",
    "adm_p_add": "افزودن همکار",
    "adm_p_list": "لیست همکاران",
    "adm_p_usage": "گیگ خریداری‌شده",
    "adm_p_voldisc": "تخفیف حجمی همکار",
    "adm_p_packages": "بسته‌های همکار",
    "adm_p_rm": "حذف همکار",
}

DEFAULT_BUTTON_STYLES: dict[str, str] = {
    "mm_buy": "primary",
    "mm_services": "primary",
    "mm_account": "success",
    "mm_topup": "success",
    "mm_support": "primary",
    "mm_guide": "primary",
    "mm_test": "primary",
    "mm_partner": "success",
    "mm_admin": "danger",
    "pay_wallet": "success",
    "pay_card": "primary",
    "pay_crypto": "primary",
    "pay_nowpay": "primary",
    "apply_discount": "primary",
    "check_nowpay": "primary",
    "svc_open": "primary",
    "svc_extra": "success",
    "svc_link": "primary",
    "svc_qr": "primary",
    "svc_disable": "danger",
    "svc_enable": "success",
    "svc_delete": "danger",
    "svc_revoke": "primary",
    "page_prev": "primary",
    "page_next": "primary",
    "home": "primary",
    "cancel": "danger",
    "confirm_yes": "success",
    "confirm_no": "danger",
    "delete": "danger",
    "admin_back": "primary",
    "channel_join": "primary",
    "check_join": "success",
    "partner_settle": "success",
    "order_approve": "success",
    "order_reject": "danger",
    "test_claim": "success",
    "admin_nav": "primary",
    "adm_fin": "success",
    "adm_shop": "primary",
    "adm_chan": "primary",
    "adm_admins": "primary",
    "adm_disc": "success",
    "adm_msg": "primary",
    "adm_btns": "primary",
    "adm_texts": "primary",
    "adm_ustats": "success",
    "adm_panel_menu": "primary",
    "adm_bot": "primary",
    "adm_test_menu": "primary",
    "adm_colors": "primary",
    "adm_home": "primary",
    "adm_b_addbal": "success",
    "adm_b_dedbal": "danger",
    "adm_b_orders": "primary",
    "adm_pmenu": "success",
    "adm_b_togglechan": "primary",
    "adm_disc_add": "success",
    "adm_disc_rm": "danger",
    "adm_adm_add": "success",
    "adm_adm_rm": "danger",
    "adm_p_add": "success",
    "adm_p_rm": "danger",
    "adm_panel_add": "success",
    "adm_panel_remove": "danger",
    "adm_export_run": "primary",
    "adm_b_resettest": "danger",
    "adm_b_ballist": "primary",
    "adm_b_orders": "primary",
    "adm_b_card": "primary",
    "adm_b_trust": "primary",
    "adm_b_nowpaykey": "primary",
    "adm_b_togglebuymode": "primary",
    "adm_b_price": "primary",
    "adm_b_voldisc": "primary",
    "adm_b_packages": "primary",
    "adm_b_chanid": "primary",
    "adm_b_chanurl": "primary",
    "adm_b_welcome": "primary",
    "adm_b_support": "primary",
    "adm_b_guide": "primary",
    "adm_b_togglemaint": "primary",
    "adm_b_mtext": "primary",
    "adm_b_togglecard": "primary",
    "adm_b_togglecrypto": "primary",
    "adm_b_togglebuy": "primary",
    "adm_b_togglenowpay": "primary",
    "adm_b_toggledisc": "primary",
    "adm_b_receiptchan": "primary",
    "adm_b_testgb": "primary",
    "adm_adm_list": "primary",
    "adm_disc_list": "primary",
    "adm_msg_bcast": "primary",
    "adm_msg_user": "primary",
    "adm_panel_url": "primary",
    "adm_panel_user": "primary",
    "adm_panel_pass": "primary",
    "adm_panel_groups": "primary",
    "adm_panel_prefix": "primary",
    "adm_panel_start": "primary",
    "adm_p_price": "primary",
    "adm_p_list": "primary",
    "adm_p_usage": "primary",
    "adm_p_voldisc": "primary",
    "adm_p_packages": "primary",
    "adm_chan": "primary",
    "adm_admins": "primary",
    "adm_msg": "primary",
    "adm_btns": "primary",
    "adm_texts": "primary",
    "adm_ustats": "success",
    "adm_panel_menu": "primary",
    "adm_bot": "primary",
    "adm_test_menu": "primary",
    "adm_colors": "primary",
}

ALL_STYLE_KEYS: frozenset[str] = frozenset(BUTTON_STYLE_LABELS.keys())

# سازگاری با کد قدیمی
GLOBAL_STYLE_KEYS = BUTTON_STYLE_LABELS
DEFAULT_GLOBAL_STYLES = DEFAULT_BUTTON_STYLES
DEFAULT_MAIN_MENU_STYLES = {
    bid: DEFAULT_BUTTON_STYLES.get(f"mm_{bid}", "")
    for bid in ("buy", "services", "account", "topup", "support", "guide", "test", "partner", "admin")
}

_CALLBACK_TO_STYLE_KEY: dict[str, str] = {
    "adm:fin": "adm_fin",
    "adm:shop": "adm_shop",
    "adm:chan": "adm_chan",
    "adm:admins": "adm_admins",
    "adm:disc": "adm_disc",
    "adm:msg": "adm_msg",
    "adm:btns": "adm_btns",
    "adm:texts": "adm_texts",
    "adm:ustats": "adm_ustats",
    "adm:panel:menu": "adm_panel_menu",
    "adm:bot": "adm_bot",
    "adm:test:menu": "adm_test_menu",
    "adm:colors": "adm_colors",
    "adm:pmenu": "adm_pmenu",
    "adm:shop:product": "adm_shop_product",
    "adm:b:ballist": "adm_b_ballist",
    "adm:b:addbal": "adm_b_addbal",
    "adm:b:dedbal": "adm_b_dedbal",
    "adm:b:orders": "adm_b_orders",
    "adm:b:card": "adm_b_card",
    "adm:b:trust": "adm_b_trust",
    "adm:b:nowpaykey": "adm_b_nowpaykey",
    "adm:b:togglebuymode": "adm_b_togglebuymode",
    "adm:b:price": "adm_b_price",
    "adm:b:voldisc": "adm_b_voldisc",
    "adm:b:packages": "adm_b_packages",
    "adm:b:chanid": "adm_b_chanid",
    "adm:b:chanurl": "adm_b_chanurl",
    "adm:b:togglechan": "adm_b_togglechan",
    "adm:adm:list": "adm_adm_list",
    "adm:adm:add": "adm_adm_add",
    "adm:adm:rm": "adm_adm_rm",
    "adm:disc:add": "adm_disc_add",
    "adm:disc:rm": "adm_disc_rm",
    "adm:disc:list": "adm_disc_list",
    "adm:msg:bcast": "adm_msg_bcast",
    "adm:msg:user": "adm_msg_user",
    "adm:b:welcome": "adm_b_welcome",
    "adm:b:support": "adm_b_support",
    "adm:b:guide": "adm_b_guide",
    "adm:b:togglemaint": "adm_b_togglemaint",
    "adm:b:mtext": "adm_b_mtext",
    "adm:b:togglecard": "adm_b_togglecard",
    "adm:b:togglecrypto": "adm_b_togglecrypto",
    "adm:b:togglebuy": "adm_b_togglebuy",
    "adm:b:togglenowpay": "adm_b_togglenowpay",
    "adm:b:toggledisc": "adm_b_toggledisc",
    "adm:b:receiptchan": "adm_b_receiptchan",
    "adm:export:run": "adm_export_run",
    "adm:b:testgb": "adm_b_testgb",
    "adm:b:resettest": "adm_b_resettest",
    "adm:panel:add": "adm_panel_add",
    "adm:panel:remove": "adm_panel_remove",
    "adm:panel:url": "adm_panel_url",
    "adm:panel:user": "adm_panel_user",
    "adm:panel:pass": "adm_panel_pass",
    "adm:panel:groups": "adm_panel_groups",
    "adm:panel:prefix": "adm_panel_prefix",
    "adm:panel:start": "adm_panel_start",
    "adm:p:price": "adm_p_price",
    "adm:p:add": "adm_p_add",
    "adm:p:list": "adm_p_list",
    "adm:p:usage": "adm_p_usage",
    "adm:p:voldisc": "adm_p_voldisc",
    "adm:p:packages": "adm_p_packages",
    "adm:root": "admin_back",
    "adm:cancel": "cancel",
    "app:home": "home",
    "app:checkjoin": "check_join",
    "app:partner:settle": "partner_settle",
    "app:buy": "mm_buy",
    "app:services": "mm_services",
    "app:account": "mm_account",
    "app:topup": "mm_topup",
    "app:support": "mm_support",
    "app:guide": "mm_guide",
    "app:test": "mm_test",
    "app:partner": "mm_partner",
}

_MAIN_MENU_IDS = frozenset(
    {"buy", "services", "account", "topup", "support", "guide", "test", "partner", "admin"}
)

_cached_styles: dict[str, str] = dict(DEFAULT_BUTTON_STYLES)


def normalize_button_style(style: str | None) -> str | None:
    if not style:
        return None
    s = str(style).strip().lower()
    if s in ("primary", "success", "danger"):
        return s
    return None


def style_label_fa(style: str | None) -> str:
    return STYLE_LABELS_FA.get(str(style or "").strip().lower(), STYLE_LABELS_FA[""])


def button_style_label(key: str) -> str:
    return BUTTON_STYLE_LABELS.get(key, key)


def _build_user_color_table_keys() -> list[str]:
    """کلیدهای قابل تنظیم در جدول رنگ — فقط دکمه‌های کاربر عادی."""
    return list(USER_COLOR_TABLE_KEYS_ORDERED)


USER_COLOR_TABLE_KEYS: frozenset[str] = frozenset(_build_user_color_table_keys())


def all_color_table_keys() -> list[str]:
    """ترتیب ثابت کلیدهای جدول تنظیم رنگ (فقط دکمه‌های کاربر عادی)."""
    return list(_build_user_color_table_keys())


def is_user_colorable_key(key: str) -> bool:
    return key in USER_COLOR_TABLE_KEYS


COLORS_TABLE_PAGE_SIZE = 8


def colors_table_page_count() -> int:
    n = len(all_color_table_keys())
    return max(1, (n + COLORS_TABLE_PAGE_SIZE - 1) // COLORS_TABLE_PAGE_SIZE)


def clamp_colors_page(page: int) -> int:
    return max(0, min(page, colors_table_page_count() - 1))


def all_style_keys_flat() -> list[str]:
    return list(all_color_table_keys())


def all_admin_style_keys() -> list[str]:
    keys: list[str] = []
    for cat_id in ADMIN_COLOR_CATEGORY_IDS:
        cat = STYLE_CATEGORIES.get(cat_id)
        if not cat:
            continue
        for key in cat[1]:
            if key not in keys:
                keys.append(key)
    return keys


def category_title_and_keys(cat_id: str) -> tuple[str, list[str]] | None:
    if cat_id == "admin_panel_all":
        return "🛠 پنل ادمین — همه دکمه‌ها", all_admin_style_keys()
    cat = STYLE_CATEGORIES.get(cat_id)
    if not cat:
        return None
    return cat[0], list(cat[1])


def iter_style_categories() -> list[tuple[str, str, list[str]]]:
    out: list[tuple[str, str, list[str]]] = []
    for cat_id, (title, keys) in STYLE_CATEGORIES.items():
        out.append((cat_id, title, keys))
    return out


def iter_customer_color_categories() -> list[tuple[str, str, list[str]]]:
    out: list[tuple[str, str, list[str]]] = []
    for cat_id in CUSTOMER_COLOR_CATEGORY_IDS:
        cat = STYLE_CATEGORIES.get(cat_id)
        if cat:
            out.append((cat_id, cat[0], list(cat[1])))
    return out


def iter_admin_color_categories() -> list[tuple[str, str, list[str]]]:
    out: list[tuple[str, str, list[str]]] = []
    for cat_id in ADMIN_COLOR_CATEGORY_IDS:
        cat = STYLE_CATEGORIES.get(cat_id)
        if cat:
            out.append((cat_id, cat[0], list(cat[1])))
    return out


def _parse_styles_json(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, val in data.items():
        if key not in USER_COLOR_TABLE_KEYS:
            continue
        norm = normalize_button_style(str(val))
        if norm:
            out[key] = norm
        elif str(val).strip() in ("", "default", "none"):
            out[key] = ""
    return out


def get_global_button_styles() -> dict[str, str]:
    return _cached_styles


def get_effective_style(style_key: str) -> str | None:
    if style_key not in USER_COLOR_TABLE_KEYS:
        return "primary"
    norm = normalize_button_style(_cached_styles.get(style_key))
    return norm or "primary"


async def _migrate_main_menu_styles(db: Database, overrides: dict[str, str]) -> dict[str, str]:
    """رنگ‌های ذخیره‌شده در main_menu_buttons_json را به رجیستری یکپارچه منتقل می‌کند."""
    raw = await db.get_setting("main_menu_buttons_json", "")
    if not raw.strip():
        return overrides
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return overrides
    buttons = data.get("buttons")
    if not isinstance(buttons, dict):
        return overrides
    changed = False
    for bid, entry in buttons.items():
        if bid not in _MAIN_MENU_IDS or not isinstance(entry, dict):
            continue
        mm_key = f"mm_{bid}"
        if mm_key in overrides:
            continue
        style = normalize_button_style(entry.get("style"))
        if style:
            overrides[mm_key] = style
            entry["style"] = ""
            changed = True
    if changed:
        data["buttons"] = buttons
        await db.set_setting("main_menu_buttons_json", json.dumps(data, ensure_ascii=False))
    return overrides


async def refresh_global_button_styles(db: Database) -> dict[str, str]:
    global _cached_styles
    overrides = _parse_styles_json(await db.get_setting("global_button_styles_json", ""))
    overrides = await _migrate_main_menu_styles(db, overrides)
    merged = dict(DEFAULT_BUTTON_STYLES)
    for key in ALL_STYLE_KEYS:
        if key not in USER_COLOR_TABLE_KEYS:
            merged[key] = "primary"
    for key in USER_COLOR_TABLE_KEYS:
        val = normalize_button_style(overrides.get(key))
        merged[key] = val or "primary"
    _cached_styles = merged
    return _cached_styles


async def save_global_button_styles(db: Database, overrides: dict[str, str]) -> None:
    clean: dict[str, str] = {}
    for key in USER_COLOR_TABLE_KEYS:
        if key not in overrides:
            continue
        norm = normalize_button_style(overrides[key])
        clean[key] = norm or ""
    await db.set_setting("global_button_styles_json", json.dumps(clean, ensure_ascii=False))
    await refresh_global_button_styles(db)


async def set_global_button_style(db: Database, key: str, style: str | None) -> None:
    if key not in USER_COLOR_TABLE_KEYS:
        return
    overrides = _parse_styles_json(await db.get_setting("global_button_styles_json", ""))
    overrides[key] = normalize_button_style(style) or ""
    await save_global_button_styles(db, overrides)


def resolve_style_key(callback_data: str | None, *, url: str | None = None) -> str | None:
    if url:
        return "channel_join"
    if not callback_data:
        return None
    cd = callback_data
    if cd in _CALLBACK_TO_STYLE_KEY:
        return _CALLBACK_TO_STYLE_KEY[cd]
    if cd.startswith("adm:o:") and cd.endswith(":a"):
        return "order_approve"
    if cd.startswith("adm:o:") and cd.endswith(":r"):
        return "order_reject"
    if cd.endswith(":cancel") or cd == "adm:cancel":
        return "cancel"
    if cd == "app:checkjoin":
        return "check_join"
    if cd == "app:home" or cd.endswith(":home"):
        return "home"
    if cd == "app:partner:settle":
        return "partner_settle"
    if cd == "app:testgo":
        return "test_claim"
    if ":promo" in cd:
        return "apply_discount"
    if cd.startswith("app:nowcheck:"):
        return "check_nowpay"
    if ":wallet" in cd and any(x in cd for x in ("buypay", "topay", "extrapay")):
        return "pay_wallet"
    if ":card" in cd and any(x in cd for x in ("buypay", "topay", "extrapay")):
        return "pay_card"
    if ":crypto" in cd and any(x in cd for x in ("buypay", "topay", "extrapay")):
        return "pay_crypto"
    if ":nowpay" in cd:
        return "pay_nowpay"
    if cd.endswith(":xy") or cd.endswith(":dy") or cd.endswith(":ey"):
        return "confirm_yes"
    if cd.endswith(":xn") or cd.endswith(":dn") or cd.endswith(":ex"):
        return "confirm_no"
    if re.search(r":svcpg:\d+$", cd):
        if "prev" in cd or cd.endswith(":0"):
            return "page_prev"
        return "page_next"
    if cd.startswith("app:svcpg:"):
        parts = cd.split(":")
        if len(parts) >= 3:
            try:
                pg = int(parts[-1])
                return "page_prev" if pg > 0 else "page_next"
            except ValueError:
                pass
    if cd.startswith("app:svcopen:"):
        return "svc_open"
    if re.search(r":v$", cd):
        return "svc_extra"
    if re.search(r":l$", cd):
        return "svc_link"
    if re.search(r":q$", cd):
        return "svc_qr"
    if re.search(r":d$", cd):
        return "svc_disable"
    if re.search(r":e$", cd):
        return "svc_enable"
    if re.search(r":x$", cd):
        return "svc_delete"
    if re.search(r":s$", cd):
        return "svc_revoke"
    if cd.startswith("adm:p:rm:"):
        return "adm_p_rm"
    if cd.startswith("adm:panel:grptgl:"):
        return "adm_panel_groups"
    if cd.startswith("adm:") and not cd.startswith(
        ("adm:colors", "adm:mbtn:", "adm:gstyle:")
    ):
        return "admin_nav"
    return None


def resolve_button_style(
    *,
    callback_data: str | None = None,
    url: str | None = None,
    style_key: str | None = None,
    style: str | None = None,
    main_menu_button_id: str | None = None,
    main_menu_styles: dict[str, str] | None = None,
) -> str | None:
    if style is not None:
        return normalize_button_style(style)
    if style_key and style_key in ALL_STYLE_KEYS:
        return get_effective_style(style_key)
    if main_menu_button_id:
        mm_key = f"mm_{main_menu_button_id}"
        if main_menu_styles:
            mm = normalize_button_style(main_menu_styles.get(main_menu_button_id))
            if mm:
                return mm
        return get_effective_style(mm_key)
    key = resolve_style_key(callback_data, url=url)
    if key:
        return get_effective_style(key)
    return None


def make_button(
    text: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
    style_key: str | None = None,
    style: str | None = None,
    main_menu_button_id: str | None = None,
    main_menu_styles: dict[str, str] | None = None,
) -> InlineKeyboardButton:
    resolved = resolve_button_style(
        callback_data=callback_data,
        url=url,
        style_key=style_key,
        style=style,
        main_menu_button_id=main_menu_button_id,
        main_menu_styles=main_menu_styles,
    )
    kw: dict[str, Any] = {"text": text}
    if url:
        kw["url"] = url
    elif callback_data is not None:
        kw["callback_data"] = callback_data
    if resolved:
        kw["style"] = resolved
    return InlineKeyboardButton(**kw)


def next_style_in_cycle(current: str | None) -> str:
    order = ["", "primary", "success", "danger"]
    cur = (current or "").strip().lower()
    if cur not in order:
        cur = ""
    idx = order.index(cur)
    return order[(idx + 1) % len(order)]

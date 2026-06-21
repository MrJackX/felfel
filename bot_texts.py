# -*- coding: utf-8 -*-
"""
متن‌ها و برچسب دکمه‌های ربات — برای تغییر ظاهر و پیام‌ها فقط همین فایل را ویرایش کنید.
می‌توانید از تگ‌های HTML تلگرام (<b>، <i>، <code>) استفاده کنید؛ جاهایی که {متغیر} دارند را دست نخورده بگذارید.
"""

from __future__ import annotations

import html


class TEXTS:
    """همهٔ رشته‌های ثابت؛ توابعِ قالب در انتهای فایل هستند."""

    # ——— دکمه‌های منوی اصلی و عمومی ———
    btn_partner_panel = "👥 پنل همکاری"
    btn_partner_settle = "✅ تسویه حساب"
    btn_buy = "🛒 خرید سرویس"
    btn_test_service = "🧪 اکانت تست"
    btn_services = "📦 سرویس های من"
    btn_account = "👤 حساب کاربری"
    btn_topup = "💰 افزایش موجودی"
    btn_support = "💬 پشتیبانی"
    btn_connection_guide = "📖 راهنمای اتصال"
    btn_main_home = "🏠 منوی اصلی"
    btn_admin_panel = "🛠 پنل ادمین"
    btn_cancel_fsm = "⬅️ لغو و برگشت"
    btn_cancel_admin_input = "⬅️ لغو"
    btn_pay_wallet = "💳 پرداخت از کیف پول"
    btn_pay_card = "🏦 کارت به کارت"
    btn_pay_crypto = "💎 ارز دیجیتال"
    btn_pay_nowpayments = "🌐 پرداخت آنلاین (NOWPayments)"
    btn_check_nowpay = "🔄 بررسی پرداخت"
    btn_apply_discount = "🏷 کد تخفیف"
    btn_admin_financial = "💰 مدیریت مالی"
    btn_admin_shop = "🛒 فروشگاه"
    btn_admin_channel = "📢 تنظیمات کانال"
    btn_admin_admins = "👮 ادمین‌ها"
    btn_admin_discount_codes = "🏷 کد تخفیف"
    btn_admin_messaging = "📣 ارسال پیام"
    btn_admin_main_buttons = "🔘 چیدمان منوی اصلی"
    btn_admin_texts = "✏️ تنظیم متن‌ها"
    btn_admin_user_stats = "📊 جستجو و آمار کاربران"
    btn_admin_panel_section = "🖥 تنظیمات پنل"
    btn_admin_bot_settings = "⚙️ تنظیمات ربات"
    btn_admin_test_section = "🧪 تنظیمات سرویس تست"
    btn_admin_colors = "🎨 رنگ دکمه‌ها"
    btn_admin_backup = "🗄 پشتیبان‌گیری و بازیابی"
    btn_admin_settings = "⚙️ تنظیمات ربات"
    btn_admin_partner_manage = "👥 مدیریت همکار"
    btn_admin_nowpayments_key = "🔑 کلید NOWPayments"
    btn_admin_nowpayments_toggle = "🔑 NOWPayments"
    btn_admin_discount_toggle = "کد تخفیف"
    btn_admin_support_text = "💬 متن پشتیبانی"
    btn_admin_guide_text = "📖 متن راهنمای اتصال"
    btn_admin_broadcast = "📢 پیام همگانی"
    btn_admin_message_user = "✉️ پیام به کاربر"
    btn_admin_add_admin = "➕ افزودن ادمین"
    btn_admin_list_admins = "📋 لیست ادمین‌ها"
    btn_admin_remove_admin = "❌ حذف ادمین"
    btn_admin_create_discount = "➕ ساخت کد تخفیف"
    btn_admin_remove_discount = "❌ حذف کد تخفیف"
    btn_admin_find_user = "🔍 جستجوی کاربر"
    btn_admin_panel_remove = "🗑 حذف پنل"
    btn_admin_partner_financial = "👥 مدیریت همکار"
    btn_admin_balance_list = "📋 لیست موجودی‌ها"
    btn_admin_partner_price = "💵 قیمت هر گیگ (همکار)"
    btn_admin_partner_add = "➕ افزودن همکار"
    btn_admin_partner_list = "📋 لیست همکاران"
    btn_admin_partner_usage = "📊 لیست گیگ خریداری‌شده"
    btn_admin_partner_volume_discount = "📉 تخفیف حجمی همکار"
    btn_admin_partner_packages = "📦 بسته‌های همکار"
    btn_admin_partner_remove = "❌ حذف"
    btn_admin_home = "⬅️ برگشت به منوی اصلی"
    btn_admin_back = "⬅️ بازگشت"
    btn_admin_add_balance = "💰 افزایش موجودی کاربر"
    btn_admin_deduct_balance = "➖ کسر موجودی کاربر"
    btn_admin_price_gb = "💵 قیمت هر گیگ"
    btn_admin_volume_discount = "📉 تخفیف حجمی (درصد)"
    btn_admin_card_edit = "🏦 متن کارت"
    btn_admin_card_toggle = "کارت به کارت"
    btn_admin_crypto_edit = "💎 متن ارز دیجیتال"
    btn_admin_crypto_toggle = "ارز دیجیتال"
    btn_admin_buy_packages = "📦 بسته‌های فروش"
    btn_admin_product_settings = "📦 تنظیمات فروش"
    btn_admin_list_discount = "📋 لیست کدهای تخفیف"
    btn_admin_toggle_buy_mode = "🔄 نوع فروش: {mode}"
    btn_buy_custom_gb = "✏️ حجم دلخواه"
    label_buy_mode_packages = "بسته‌ای"
    label_buy_mode_volume = "حجمی"
    btn_admin_chan_id = "📢 آیدی کانال"
    btn_admin_chan_url = "🔗 لینک جوین"
    btn_admin_chan_toggle = "📢 جوین اجباری"
    btn_admin_toggle_buy = "🛒 قطع/وصل خرید کانفیگ"
    btn_admin_export_configs = "📤 خروجی کانفیگ‌ها (انتقال پنل)"
    btn_admin_welcome_text = "✏️ متن خوش‌آمدگویی"
    btn_admin_panel_settings = "🖥 تنظیمات پنل"
    btn_admin_receipt_channel = "📢 کانال رسیدها"
    btn_admin_receipt_admins = "👥 ادمین رسیدها"
    btn_admin_receipt_admin_add = "➕ افزودن ادمین رسید"
    btn_admin_receipt_admin_rm = "➖ حذف ادمین رسید"
    btn_admin_receipt_admin_list = "📋 لیست ادمین رسیدها"
    btn_admin_panel_url = "🔗 آدرس پنل"
    btn_admin_panel_user = "👤 نام کاربری پنل"
    btn_admin_panel_pass = "🔑 رمز پنل"
    btn_admin_panel_groups = "👥 گروه‌های پیش‌فرض"
    btn_admin_panel_prefix = "🏷 پیشوند نام کاربری"
    btn_admin_panel_start = "🔢 شماره شروع نام"
    btn_admin_panel_add = "➕ افزودن پنل"
    btn_admin_toggle_test = "🧪 سرویس تست"
    btn_admin_test_gb = "📊 حجم سرویس تست"
    btn_admin_reset_test = "🔄 ریست سرویس تست کاربر"
    btn_admin_maint = "🚧 حالت تعمیر و نگهداری"
    btn_admin_maint_text = "✏️ متن به‌روزرسانی"
    btn_admin_orders = "📋 سفارشات ({n})"
    btn_order_approve = "✅ تایید"
    btn_order_reject = "❌ رد"
    btn_svc_link = "🔗 لینک اشتراک"
    btn_svc_qr = "📲 بارکد اشتراک"
    btn_svc_extra = "📈 خرید حجم اضافه"
    btn_svc_disable = "⛔ خاموش کردن اکانت"
    btn_svc_enable = "✅ روشن کردن اکانت"
    btn_svc_revoke = "🔁 تعویض لینک اشتراک"
    btn_svc_disable_yes = "✅ بله، خاموش شود"
    btn_svc_disable_no = "❌ خیر"
    btn_svc_enable_yes = "✅ بله، روشن شود"
    btn_svc_enable_no = "❌ خیر"
    btn_svc_delete = "🗑 حذف سرویس"
    btn_svc_delete_yes = "✅ بله، حذف شود"
    btn_svc_delete_no = "❌ خیر"
    btn_page_prev = "◀️ قبلی"
    btn_page_next = "بعدی ▶️"
    btn_page_indicator = "📄 {page}/{pages}"

    # ——— /start و خانه ———
    msg_cmd_start = (
        "🐉 سلام به ربات Mr.jack خوش آمدید 👋\n\n"
        "📌 جهت خرید سرویس لطفا یکی از موارد زیر را انتخاب کنید"
    )
    msg_cmd_start_admin_suffix = "\n\n🛠 <b>پنل ادمین</b> برای شما فعال است."

    msg_home = (
        "🐉 سلام به ربات Mr.jack خوش آمدید 👋\n\n"
        "📌 جهت خرید سرویس لطفا یکی از موارد زیر را انتخاب کنید"
    )
    msg_home_admin_suffix = "\n🛠 <b>پنل ادمین</b> فقط برای شما نمایش داده می‌شود."
    alert_no_message = "پیام یافت نشد."
    alert_please_wait = "لطفاً صبر کنید. (اسپم نکنید)"

    msg_cancel_done = "✅ عملیات لغو شد.\nاز منوی زیر ادامه دهید:"
    cq_cancelled = "لغو شد."

    # ——— خرید / شارژ ———
    msg_buy_blocked = "🚫 خرید موقتاً غیرفعال است. بعداً مراجعه کنید."
    msg_test_disabled = "🧪 سرویس تست الان فعال نیست."
    err_test_already_used = "⚠️ هر کاربر فقط یک‌بار می‌تواند سرویس تست بگیرد."
    err_test_no_extra = "⚠️ روی سرویس تست امکان خرید حجم اضافه نیست."
    msg_test_intro = (
        "🧪 <b>سرویس تست رایگان</b>\n\n"
        "حجم: <b>{gb}</b> گیگ — فقط <b>یک‌بار</b> برای هر حساب.\n"
        "با زدن دکمهٔ زیر، کانفیگ بلافاصله ساخته می‌شود."
    )
    btn_test_claim = "✅ دریافت سرویس تست"
    msg_test_done = (
        "✅ <b>سرویس تست</b> فعال شد.\n"
        "📊 حجم: <code>{gb}</code> GB"
        
    )
    msg_test_fail = "⛔ ساخت سرویس تست ناموفق بود. بعداً دوباره امتحان کنید یا با پشتیبانی تماس بگیرید."
    msg_buy_intro = (
        "🛒 <b>خرید کانفیگ</b>\n\n"
        "حجم مورد نیاز را به <b>گیگابایت</b> بفرستید (مثال: <code>20</code> یا <code>5.5</code>).\n"
        "پس از محاسبهٔ مبلغ، می‌توانید با <b>کیف پول داخلی</b> یا <b>رسید واریز</b> پرداخت کنید."
    )
    msg_buy_packages_intro = (
        "🛒 <b>خرید کانفیگ</b>\n\n"
        "یک <b>بسته</b> را از لیست زیر انتخاب کنید."
    )
    msg_ask_buy_packages = (
        "📦 <b>بسته‌های فروش</b>\n\n"
        "برای هر بسته این قالب را بفرستید (چند بسته را با یک خط خالی جدا کنید):\n\n"
        "<code>اسم بسته: بسته ۱۰ گیگی\n"
        "حجم: 10\n"
        "قیمت: 1000000\n"
        "روز: 30</code>\n\n"
        "روز = مدت اعتبار کانفیگ. برای نامحدود: <code>0</code>\n"
        "حذف همه بسته‌ها: <code>-</code>\n\n"
        "بسته‌های فعلی:\n<pre>{current}</pre>"
    )
    err_buy_packages_parse = (
        "⚠️ فرمت نامعتبر. هر بسته باید شامل "
        "<code>اسم بسته</code>، <code>حجم</code>، <code>قیمت</code> و <code>روز</code> باشد."
    )
    msg_buy_packages_saved = "✅ بسته‌های فروش ذخیره شد:\n{preview}"
    msg_ask_partner_buy_packages = (
        "📦 <b>بسته‌های همکار</b>\n\n"
        "برای هر بسته این قالب را بفرستید (چند بسته را با یک خط خالی جدا کنید):\n\n"
        "<code>اسم بسته: بسته ۱۰ گیگی\n"
        "حجم: 10\n"
        "قیمت: 1000000\n"
        "روز: 30</code>\n\n"
        "روز = مدت اعتبار کانفیگ. برای نامحدود: <code>0</code>\n"
        "حذف همه بسته‌ها: <code>-</code>\n\n"
        "بسته‌های فعلی:\n<pre>{current}</pre>"
    )
    msg_partner_buy_packages_saved = "✅ بسته‌های همکار ذخیره شد:\n{preview}"
    err_buy_gb_number = "⚠️ فقط عدد (گیگ) بفرستید."
    err_buy_gb_range = "⚠️ حجم باید بین ۰.۱ تا ۵۰۰۰ گیگ باشد."
    msg_buy_payment_choice = (
        "💰 <b>مبلغ سفارش:</b> <code>{amount:,.0f}</code> تومان\n"
        "{discount_line}"
        "{package_line}"
        "{rate_line}"
        "📊 حجم: <code>{gb}</code> GB\n"
        "💳 موجودی فعلی کیف شما: <b>{bal:,.0f}</b> تومان\n\n"
        "نحوهٔ پرداخت را انتخاب کنید:"
    )
    msg_buy_package_line = "📦 بسته: <b>{title}</b> — مدت: <b>{days_label}</b>\n"
    msg_buy_rate_line = "📊 نرخ: <code>{ppg:,.0f}</code> تومان/گیگ\n"
    msg_buy_discount_line = (
        "🎁 تخفیف حجم: <b>{pct:g}٪</b> — قبل از تخفیف: <code>{subtotal:,.0f}</code> تومان\n"
    )
    alert_wallet_insufficient = (
        "موجودی کیف کافی نیست. یکی از روش‌های «کارت به کارت» یا «ارز دیجیتال» را بزنید یا موجودی را شارژ کنید."
    )
    alert_wallet_busy = "⏳ پرداخت قبلی هنوز در حال پردازش است. لطفاً صبر کنید."
    alert_wallet_cooldown = "⏳ لطفاً ۱۵ ثانیه صبر کنید و دوباره تلاش کنید."
    msg_wallet_processing = (
        "⏳ <b>در حال پردازش پرداخت...</b>\n\n"
        "لطفاً تا ۱۵ ثانیه دیگر صبر کنید و دکمه را دوباره نزنید."
    )
    msg_buy_wallet_done = (
        "✅ پرداخت از <b>کیف پول</b> انجام شد؛ سرویس فعال است.\n"
        "💳 موجودی فعلی: <b>{new_bal:,.0f}</b> تومان —"
    )
    msg_buy_receipt_step = (
        "💰 <b>مبلغ قابل پرداخت:</b> <code>{amount:,.0f}</code> تومان\n"
        "📊 حجم: <code>{gb}</code> GB\n"
        "{instructions}"
        "📸 لطفاً <b>اسکرین‌شات رسید</b> را ارسال کنید (عکس)."
    )
    msg_buy_payment_reminder = "لطفاً یکی از دکمه‌های زیر را بزنید."
    msg_buy_order_done = (
        "✅ سفارش <b>#{oid}</b> ثبت شد.\n"
        "⏳ پس از بررسی ادمین، کانفیگ برایتان ساخته می‌شود."
    )
    msg_buy_order_done_short = "✅ سفارش <b>#{oid}</b> ثبت شد.\n⏳ در انتظار تایید ادمین."
    err_image_only = "⚠️ فقط تصویر (عکس یا فایل تصویری) بفرستید."
    err_image_only_short = "⚠️ فقط تصویر بفرستید."

    msg_topup_intro = (
        "💰 <b>افزایش موجودی</b>\n\n"
        "مبلغ را به <b>تومان</b> بفرستید (فقط عدد، مثال: <code>500000</code>).\n"
        "سپس رسید واریز را ارسال می‌کنید."
    )
    err_topup_amount = "⚠️ فقط عدد مبلغ (تومان)."
    err_topup_range = "⚠️ مبلغ معقول وارد کنید (۱۰ هزار تا ۵۰۰ میلیون)."
    msg_topup_payment_choice = (
        "💰 مبلغ شارژ: {amt:,.0f} تومان\n\n"
        "روش ارسال رسید را انتخاب کنید:"
    )
    msg_topup_amount_ack = "✅ مبلغ ثبت شد؛ روش پرداخت را از همان پیام بالا انتخاب کنید."
    err_topup_no_payment_method = (
        "⚠️ الان هیچ روش پرداخت با رسید (کارت یا ارز دیجیتال) فعال نیست.\n"
        "از ادمین بخواهید یکی را روشن کند، یا بعداً دوباره امتحان کنید."
    )
    err_pay_card_unavailable = "پرداخت کارت به کارت الان در دسترس نیست."
    err_pay_crypto_unavailable = "پرداخت با ارز دیجیتال الان در دسترس نیست."
    msg_topup_receipt_step = (
        "💰 مبلغ شارژ: <b>{amt:,.0f}</b> تومان\n"
        "{instructions}"
        "📸 رسید (عکس) را بفرستید."
    )
    msg_topup_pending = "✅ درخواست شارژ <b>#{oid}</b> ثبت شد.\n⏳ پس از تایید، به موجودی شما اضافه می‌شود."
    msg_topup_pending_short = "✅ درخواست شارژ <b>#{oid}</b> ثبت شد.\n⏳ در انتظار تایید."

    msg_channel_join_start = (
        "📢 برای استفاده از ربات ابتدا باید در کانال ما عضو شوید.\n\n"
        "روی دکمهٔ زیر بزنید، عضو شوید و سپس دوباره <b>/start</b> را بزنید."
    )
    msg_channel_join_required = (
        "📢 برای ادامه ابتدا باید عضو کانال ما شوید.\n\n"
        "پس از عضویت، دوباره همان گزینه را از منو بزنید."
    )
    btn_join_channel = "📢 عضویت در کانال"
    btn_check_channel_join = "✅ عضو شدم"
    msg_account = (
        "👤 <b>حساب کاربری</b>\n\n"
        "🆔 شناسه تلگرام: <code>{uid}</code>\n"
        "💳 موجودی کیف پول داخلی: <b>{bal:,.0f}</b> تومان\n\n"
        "با تایید رسید «افزایش موجودی» شارژ می‌شود؛ می‌توانید از همین موجودی هم خرید کانفیگ بکنید."
    )
    msg_support_default = "💬 برای پشتیبانی با ادمین تماس بگیرید."
    msg_guide_default = (
        "📖 <b>راهنمای اتصال</b>\n\n"
        "۱) لینک اشتراک را از «سرویس های من» کپی کنید.\n"
        "۲) در اپ v2rayNG / Streisand / Hiddify وارد کنید.\n"
        "۳) اتصال را روشن کنید."
    )

    # ——— سرویس‌ها ———
    msg_services_empty = (
        "📦 هنوز سرویس فعالی ندارید.\n"
        "پس از خرید با کیف پول بلافاصله فعال می‌شود؛ با پرداخت رسید پس از تایید ادمین اینجا ظاهر می‌شود."
    )
    msg_services_error = "⚠️ سفارش <code>#{oid}</code> — <code>{un}</code>\nخطا: {err}"
    msg_services_page = "📄 صفحه <b>{page}</b> از <b>{pages}</b> — مجموع <b>{n}</b> سرویس"
    msg_services_pick_hint = "🔹 یکی از سرویس‌ها را انتخاب کنید؛ سپس از دکمه‌های کارت برای مدیریت استفاده کنید."
    msg_services_open_fail = "⛔ نمایش سرویس انجام نشد. دوباره از «📦 سرویس‌های من» تلاش کنید."

    # ——— فاکتور / اعلان کانال (خرید کیف پول) ———
    invoice_hashtag = "#سفارش_جدید"
    invoice_balance = "• 🛍 موجودی جدید کاربر : {bal}"
    invoice_paid = "✅  فاکتور با موفقیت پرداخت گردید و سرویس شما فعال گردید"
    invoice_svc_title = "🔑 اطلاعات سرویس شما :"
    invoice_cost = "• 💰 هزینه سرویس : {amt} تومان"
    invoice_code = "• 🔑 نام کانفیگ : <code>{code}</code>"
    invoice_period = "• 🗓 دوره پرداخت : {period}"
    invoice_traffic = "• 🚘 ترافیک : {traffic}"
    invoice_link_intro = "🔗لینک سرویس شما :"
    invoice_footer_id = "id : {uid}"
    invoice_footer_username = "username : {uname}"
    msg_buy_wallet_fail = (
        "⛔ ساخت سرویس در پنل ناموفق بود؛ مبلغ به کیف شما برگشت داده شد.\n"
        "لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.\n<code>{err}</code>"
    )

    # کپشن رسید برای ادمین (متن ساده؛ روی عکس رسید)
    admin_receipt_buy_caption = (
        "💠 یک پیام جدید - ارسال رسید\n\n"
        "🔢 ایدی عددی : {uid}\n"
        "👥 تعداد زیرمجموعه ها : {referrals} نفر\n"
        "🛍 تعداد سرویس ها : {svc_count} عدد\n\n"
        " - مبلغ مد نظر : {amount}\n\n"
        " {clock} | {jdate}"
    )

    alert_order_invalid = "این سفارش متعلق به شما نیست یا نامعتبر است."
    msg_sub_link_title = "🔗 <b>لینک اشتراک شما</b>\n\n"
    dash = "—"
    msg_extra_gb_intro = (
        "📈 <b>خرید حجم اضافه</b>\n\n"
        "حجم اضافه را به <b>گیگابایت</b> بفرستید (مثال: <code>5</code> یا <code>2.5</code>).\n"
        "سپس <b>کیف پول</b> یا <b>رسید واریز</b> (کارت / ارز دیجیتال) را انتخاب کنید.\n"
        "فقط برای سرویس‌هایی با <b>سقف حجم مشخص</b> در پنل قابل انجام است."
    )
    msg_extra_receipt_step = (
        "📈 <b>حجم اضافه — ارسال رسید</b>\n\n"
        "💰 مبلغ: <code>{amount:,.0f}</code> تومان\n"
        "📊 حجم: <code>{gb}</code> GB\n"
        "🔑 اکانت: <code>{panel_user}</code>\n\n"
        "{instructions}\n"
        "عکس رسید را در همین چت بفرستید."
    )
    msg_extra_order_done = "✅ درخواست حجم اضافه ثبت شد. شماره سفارش: <b>#{oid}</b>\nپس از بررسی رسید، حجم به سرویس اضافه می‌شود."
    msg_extra_wallet_done = (
        "✅ <b>{gb}</b> گیگ به سقف حجم اکانت اضافه شد.\n"
        "💳 موجودی جدید کیف: <b>{bal:,.0f}</b> تومان"
    )
    err_extra_gb_number = "⚠️ فقط عدد (گیگ) بفرستید."
    err_extra_gb_range = "⚠️ حجم باید بین ۰.۱ تا ۵۰۰۰ گیگ باشد."
    err_extra_gb_wallet = "⚠️ موجودی کیف برای این حجم کافی نیست. از «💰 افزایش موجودی» شارژ کنید."
    err_extra_panel = "⛔ به‌روزرسانی حجم در پنل ناموفق بود؛ مبلغ به کیف برگشت."
    msg_extra_ok = (
        "✅ <b>{gb}</b> گیگ به سقف حجم اکانت اضافه شد.\n"
        "💳 موجودی جدید کیف: <b>{bal:,.0f}</b> تومان"
    )
    msg_extra_unlimited = (
        "ℹ️ این اکانت در پنل <b>نامحدود</b> است؛ افزودن حجم از ربات برایش تعریف نشده است."
    )
    msg_revoke_ok = "✅ لینک اشتراک عوض شد."
    msg_disable_confirm = (
        "⛔ <b>خاموش کردن اکانت</b>\n\n"
        "در پنل، وضعیت کاربر روی <b>غیرفعال</b> می‌شود. ادامه می‌دهید؟"
    )
    cq_disable_cancel = "لغو شد."
    msg_disabled_ok = "⛔ اکانت <code>{un}</code> غیرفعال شد."
    msg_enable_confirm = (
        "✅ <b>روشن کردن اکانت</b>\n\n"
        "در پنل، وضعیت کاربر روی <b>فعال</b> می‌شود. ادامه می‌دهید؟"
    )
    cq_enable_cancel = "لغو شد."
    msg_enabled_ok = "✅ اکانت <code>{un}</code> دوباره فعال شد."
    msg_delete_confirm = (
        "🗑 <b>حذف سرویس</b>\n\n"
        "اکانت از پنل حذف می‌شود و دیگر در «سرویس‌های من» نمایش داده نمی‌شود.\n"
        "این کار <b>برگشت‌پذیر نیست</b>. ادامه می‌دهید؟"
    )
    cq_delete_cancel = "لغو شد."
    msg_deleted_ok = (
        "✅ سرویس <code>{un}</code> حذف شد.\n"
        "از منوی زیر می‌توانید سرویس‌های دیگر را ببینید یا خرید جدید انجام دهید."
    )
    msg_svc_auto_deleted_volume = (
        "⏱ سرویس <code>{un}</code> به‌دلیل <b>اتمام حجم</b> و عدم شارژ (خرید حجم اضافه) "
        "ظرف <b>{hours}</b> ساعت از پنل و لیست «سرویس‌های من» حذف شد."
    )

    # ——— کارت سرویس (برچسب‌ها؛ مقادیر داینامیک در کد ساخته می‌شوند) ———
    svc_exp_unlimited = "📅 <b>تاریخ اتمام :</b> نامحدود"
    svc_exp_fmt = "📅 <b>تاریخ اتمام :</b> {jalali} ({countdown})"
    svc_online_none = "📶 <b>آخرین زمان اتصال :</b> —"
    svc_online_fmt = "📶 <b>آخرین زمان اتصال :</b> {jalali}"
    svc_sub_none = "🔄 <b>آخرین زمان آپدیت لینک اشتراک :</b> —"
    svc_sub_fmt = "🔄 <b>آخرین زمان آپدیت لینک اشتراک :</b> {jalali}"
    svc_client_none = "#️⃣ <b>کلاینت متصل شده :</b> —"
    svc_client_fmt = "#️⃣ <b>کلاینت متصل شده :</b> {ua}"
    svc_tip = "💡 برای قطع دسترسی دیگران کافیست روی گزینه «تغییر لینک ساب» کلیک کنید."
    svc_status_line = "📊 <b>وضعیت سرویس :</b> {icon} {status}"
    svc_name_line = "👤 <b>نام سرویس :</b> <code>{un}</code>"
    svc_loc_line = "🌍 <b>موقعیت سرویس :</b> {loc}"
    svc_product_line = "🗂 <b>نام محصول :</b> {product}"
    svc_traffic_line = "🔋 <b>ترافیک :</b> {total}"
    svc_used_line = "📥 <b>حجم مصرفی :</b> {used}"
    svc_remain_line = "💢 <b>حجم باقی مانده :</b> {rem} ({pct})"
    svc_default_location = "VPN"
    countdown_expired = "منقضی شده"
    countdown_suffix = " دیگر"
    unit_day = "روز"
    unit_hour = "ساعت"
    unit_minute = "دقیقه"
    unit_gb = "گیگابایت"
    traffic_unlimited = "نامحدود"
    svc_product_fmt = "{gb} گیگ - {amt} تومان"

    # ——— ادمین ———
    msg_admin_input_cancelled = "✅ ورودی لغو شد."
    msg_admin_addbal_intro = (
        "💰 <b>افزایش موجودی کاربر</b>\n\n"
        "۱) شناسهٔ تلگرام <b>کاربر مقصد</b> را بفرستید (فقط عدد)، یا <b>همان پیام کاربر را فوروارد</b> کنید.\n"
        "۲) در پیام بعد مبلغ را به <b>تومان</b> می‌فرستید؛ همان لحظه به کیف پول داخلی او اضافه می‌شود.\n\n"
        "مثال شناسه: <code>123456789</code>"
    )
    msg_admin_root = "🛠 <b>پنل ادمین</b>\n\nبخش مورد نظر را انتخاب کنید:"
    msg_admin_financial_menu = (
        "💰 <b>مدیریت مالی</b>\n\n"
        "👛 کاربران با موجودی: <b>{wallet_users}</b> نفر\n"
        "📋 سفارش در انتظار: <b>{pending}</b>"
    )
    msg_admin_shop_menu = (
        "🛒 <b>فروشگاه</b>\n\n"
        "🔄 نوع فروش: <b>{buy_mode}</b>\n"
        "💵 قیمت هر گیگ: <code>{ppg:,.0f}</code> تومان\n"
        "🏦 کارت به کارت: <b>{card}</b>\n"
        "💎 ارز دیجیتال: <b>{crypto}</b>\n"
        "🔑 NOWPayments: <b>{nowpay}</b>\n"
        "📦 بسته‌ها: {packages}"
    )
    msg_admin_channel_menu = (
        "📢 <b>تنظیمات کانال (جوین اجباری)</b>\n\n"
        "وضعیت: <b>{chan_req}</b>\n"
        "تعداد کانال: <b>{chan_count}</b>\n"
        "آیدی کانال‌ها:\n<code>{chan_preview}</code>"
    )
    msg_admin_shop_product_menu = (
        "📦 <b>تنظیم محصول</b>\n\n"
        "🔄 نوع فروش: <b>{buy_mode}</b>\n"
        "💵 قیمت هر گیگ: <code>{ppg:,.0f}</code> تومان\n"
        "📉 تخفیف حجمی: {volume_discount}\n"
        "📦 بسته‌ها: {packages}"
    )
    msg_admin_admins_menu = (
        "👮 <b>ادمین‌ها</b>\n\n"
        "ادمین‌های env: <code>{env_count}</code>\n"
        "ادمین‌های ربات: <b>{db_count}</b> نفر"
    )
    msg_admin_discount_menu = "🏷 <b>کدهای تخفیف</b>\n\nتعداد: <b>{count}</b>"
    msg_admin_messaging_menu = "📣 <b>ارسال پیام</b>\n\nنوع پیام را انتخاب کنید."
    msg_admin_buttons_menu = (
        "🔘 <b>تنظیم دکمه‌های صفحه اصلی</b>\n\n"
        "دکمه‌ها <b>دو تا دو تا</b> (دو دکمه در هر ردیف) نمایش داده می‌شوند.\n"
        "روی هر دکمه بزنید تا نام یا وضعیت روشن/خاموش را تغییر دهید.\n"
        "برای تغییر رنگ دکمه‌ها از بخش «🎨 تنظیمات رنگ دکمه‌ها» در پنل ادمین استفاده کنید."
    )
    msg_admin_colors_menu = (
        "🎨 <b>جدول رنگ دکمه‌ها</b>\n\n"
        "فقط دکمه‌هایی که کاربران عادی می‌بینند در این لیست هستند.\n"
        "دکمه‌های پنل ادمین و بقیهٔ موارد همیشه <b>آبی</b> هستند.\n\n"
        "هر ردیف: <b>نام دکمه</b> + قرمز / آبی / سبز\n"
        "روی رنگ مورد نظر بزنید — دکمهٔ • همان رنگ فعال است.\n\n"
        "📄 صفحه <b>{page}</b> از <b>{pages}</b> — مجموع <b>{total}</b> دکمه"
    )
    cq_color_cycled = "رنگ: {style}"
    cq_color_same = "همین رنگ از قبل فعال است."
    msg_admin_texts_menu = "✏️ <b>تنظیم متن‌ها</b>\n\nمتن مورد نظر را انتخاب کنید."
    msg_admin_user_stats_menu = (
        "📊 <b>آمار کاربر</b>\n\n"
        "شناسه عددی تلگرام کاربر را بفرستید (یا پیام را فوروارد کنید)."
    )
    msg_admin_bot_menu = (
        "⚙️ <b>تنظیمات ربات</b>\n\n"
        "⏳ حالت به‌روزرسانی: <b>{maint}</b>\n"
        "🏦 کارت به کارت: <b>{card}</b>\n"
        "💎 ارز دیجیتال: <b>{crypto}</b>\n"
        "🛒 خرید سرویس: <b>{buy}</b>\n"
        "🔑 NOWPayments: <b>{nowpay}</b>\n"
        "🏷 کد تخفیف: <b>{disc}</b>\n"
        "📢 کانال رسید: <code>{receipt_preview}</code>"
    )
    msg_admin_test_menu = (
        "🧪 <b>سرویس تست</b>\n\n"
        "📊 حجم سرویس تست: <code>{test_gb}</code> گیگ\n\n"
        "روشن/خاموش دکمهٔ «اکانت تست» در منوی اصلی از "
        "«تنظیم دکمه‌های صفحه اصلی» انجام می‌شود."
    )
    msg_buy_packages_mode_empty = (
        "📦 فروش <b>بسته‌ای</b> فعال است اما هنوز بسته‌ای ثبت نشده.\n"
        "لطفاً بعداً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
    )
    cq_buy_mode_toggled = "نوع فروش تغییر کرد."
    msg_admin_settings_menu = (
        "⚙️ <b>تنظیمات ربات</b>\n\n"
        "⏳ حالت به‌روزرسانی: <b>{maint}</b>\n"
        "🛒 خرید کانفیگ برای مشتری: <b>{buy}</b>\n"
        "📢 جوین اجباری کانال: <b>{chan_req}</b>\n"
        "　آیدی کانال: <code>{chan_preview}</code>\n"
        "📢 کانال رسیدها: <code>{receipt_preview}</code>\n"
        "🖥 پنل: <code>{panel_preview}</code>\n"
        "🏷 پیشوند نام: <code>{prefix}</code> — شروع: <code>{start_num}</code>"
    )
    msg_admin_export_intro = (
        "📤 <b>خروجی انتقال پنل</b>\n\n"
        "با زدن دکمه زیر، فایل JSON شامل همهٔ کاربران پنل "
        "(نام کاربری، حجم، انقضا، لینک ساب و اطلاعات سفارش ربات) "
        "برای شما ارسال می‌شود."
    )
    msg_admin_export_busy = "⏳ خروجی قبلی هنوز در حال آماده‌سازی است."
    msg_admin_export_start = "⏳ در حال دریافت اطلاعات از پنل… لطفاً صبر کنید."
    msg_admin_export_done = (
        "✅ فایل خروجی آماده شد.\n"
        "👤 کاربران پنل: <b>{panel_count}</b>\n"
        "🔗 متصل به سفارش ربات: <b>{linked_count}</b>"
    )
    msg_admin_export_fail = "⛔ خطا در تهیهٔ خروجی: {err}"
    msg_admin_panel_not_configured = (
        "🖥 <b>تنظیمات پنل</b>\n\n"
        "هنوز پنلی متصل نشده.\n"
        "با دکمهٔ زیر آدرس، نام کاربری و رمز پنل PasarGuard را وارد کنید."
    )
    msg_admin_panel_menu = (
        "🖥 <b>تنظیمات پنل PasarGuard</b>\n\n"
        "🔗 آدرس: <code>{url}</code>\n"
        "👤 کاربر: <code>{user}</code>\n"
        "🔑 رمز: <code>{pass_mask}</code>\n"
        "👥 گروه‌ها: <code>{groups}</code>\n"
        "🏷 پیشوند نام: <code>{prefix}</code>\n"
        "🔢 شماره شروع: <code>{start_num}</code>"
    )
    msg_panel_add_step_url = (
        "➕ <b>افزودن پنل — مرحله ۱ از ۳</b>\n\n"
        "🔗 آدرس پنل را بفرستید.\n"
        "مثال: <code>https://panel.example.com:2096</code>"
    )
    msg_panel_add_step_user = (
        "➕ <b>افزودن پنل — مرحله ۲ از ۳</b>\n\n"
        "👤 نام کاربری ادمین پنل را بفرستید."
    )
    msg_panel_add_step_pass = (
        "➕ <b>افزودن پنل — مرحله ۳ از ۳</b>\n\n"
        "🔑 رمز عبور پنل را بفرستید."
    )
    msg_panel_add_done = (
        "✅ پنل با موفقیت متصل شد.\n"
        "گروه‌ها، پیشوند نام و شماره شروع را از همین منو تنظیم کنید."
    )
    err_panel_not_configured = "⚠️ ابتدا پنل را از تنظیمات ربات اضافه کنید."
    msg_ask_welcome = (
        "✏️ <b>متن خوش‌آمدگویی</b> (/start و منوی اصلی) را بفرستید.\n"
        "می‌توانید از تگ‌های HTML (&lt;b&gt;، &lt;i&gt;، &lt;code&gt;) استفاده کنید.\n"
        "برای بازگشت به پیش‌فرض فقط <code>-</code> بفرستید."
    )
    msg_welcome_saved = "✅ متن خوش‌آمدگویی ذخیره شد."
    msg_ask_panel_url = (
        "🔗 <b>آدرس پنل</b> را بفرستید (مثال: <code>https://panel.example.com:2096</code>).\n"
        "برای پاک کردن اتصال پنل فقط <code>-</code> بفرستید."
    )
    msg_ask_panel_user = (
        "👤 <b>نام کاربری ادمین پنل</b> را بفرستید.\n"
        "برای پاک کردن فقط <code>-</code> بفرستید."
    )
    msg_ask_panel_pass = (
        "🔑 <b>رمز عبور پنل</b> را بفرستید.\n"
        "برای پاک کردن فقط <code>-</code> بفرستید."
    )
    msg_admin_panel_groups_pick = (
        "👥 <b>گروه‌های پیش‌فرض</b>\n\n"
        "از لیست زیر گروه‌هایی را که برای کاربران جدید اعمال می‌شوند انتخاب کنید:"
    )
    msg_admin_panel_groups_empty = "⚠️ گروهی در پنل پیدا نشد. ابتدا اتصال پنل را بررسی کنید."
    msg_admin_panel_groups_fail = "⛔ دریافت گروه‌ها از پنل ناموفق: {err}"
    msg_panel_groups_saved = "✅ گروه‌های پیش‌فرض به‌روز شد."
    cq_panel_group_toggled = "✓"
    err_panel_groups_need_one = "⚠️ حداقل یک گروه باید انتخاب شود."
    msg_ask_panel_prefix = (
        "🏷 <b>پیشوند نام کاربری</b> جدید در پنل را بفرستید.\n"
        "مثال: <code>mrjack_</code>\n"
        "برای پیش‌فرض (<code>mr</code>) فقط <code>-</code> بفرستید."
    )
    msg_ask_panel_start = (
        "🔢 <b>شماره شروع</b> برای ساخت نام کاربری را بفرستید (فقط عدد).\n"
        "مثال: <code>1001</code>\n"
        "برای پیش‌فرض (<code>100</code>) فقط <code>-</code> بفرستید."
    )
    msg_ask_receipt_channel = (
        "📢 <b>آیدی کانال رسیدها</b> را بفرستید.\n"
        "مثال: <code>-1002519779909</code>\n"
        "ربات باید در کانال ادمین باشد.\n"
        "برای غیرفعال کردن فقط <code>-</code> بفرستید."
    )
    err_panel_url_invalid = "⚠️ آدرس باید با http:// یا https:// شروع شود."
    err_panel_groups_invalid = "⚠️ فرمت گروه‌ها نامعتبر است. مثال: 1 یا 1,2"
    err_panel_prefix_invalid = "⚠️ پیشوند نامعتبر است (فقط حروف، عدد و _)."
    err_panel_start_invalid = "⚠️ فقط عدد صحیح مثبت بفرستید."
    err_receipt_channel_invalid = "⚠️ آیدی کانال نامعتبر است (عدد منفی سوپرگروه)."
    msg_panel_saved = "✅ تنظیمات پنل ذخیره شد."
    msg_panel_connect_ok = "✅ اتصال به پنل برقرار شد."
    msg_panel_connect_fail = "⛔ اتصال به پنل ناموفق: {err}"
    msg_receipt_channel_saved = "✅ آیدی کانال رسیدها ذخیره شد."
    msg_admin_deduct_intro = (
        "➖ <b>کاهش موجودی کاربر</b>\n\n"
        "۱) شناسهٔ تلگرام کاربر را بفرستید (عدد) یا پیام را <b>فوروارد</b> کنید.\n"
        "۲) مبلغ کسر را به <b>تومان</b> بفرستید (فقط از موجودی فعلی کم می‌شود)."
    )
    msg_deduct_done_admin = (
        "✅ <b>{amt:,.0f}</b> تومان از کیف کاربر <code>{tid}</code> کسر شد.\n"
        "💳 موجودی جدید: <b>{bal:,.0f}</b> تومان"
    )
    msg_deduct_done_user = (
        "➖ از موجودی کیف شما <b>{amt:,.0f}</b> تومان توسط ادمین کسر شد.\n"
        "موجودی فعلی: <b>{bal:,.0f}</b> تومان"
    )
    err_deduct_insufficient = "⚠️ موجودی کاربر برای این مبلغ کافی نیست."
    msg_balance_list_empty = "📭 کاربری با موجودی کیف پیدا نشد."
    msg_balance_list_header = "📋 <b>لیست موجودی کیف پول</b> (تا {n} نفر)\n\n"
    msg_balance_list_line = "• <code>{tid}</code> — <b>{bal:,.0f}</b> تومان\n"
    msg_admin_partner_menu = (
        "👥 <b>مدیریت همکار</b>\n\n"
        "💵 قیمت هر گیگ برای همکاران: <code>{ppg:,.0f}</code> تومان\n"
        "📉 تخفیف حجمی همکار: {partner_volume_discount}\n"
        "📦 بسته‌های همکار: {partner_packages}\n"
        "📊 تعداد همکاران ثبت‌شده: <b>{count}</b>"
    )
    msg_ask_partner_volume_discount = (
        "📉 <b>تخفیف حجمی همکار</b>\n\n"
        "هر خط: <code>حداقل_گیگ,درصد</code>\n"
        "مثال:\n<code>5,5</code>\n<code>10,10</code>\n\n"
        "برای حذف همه پله‌ها فقط <code>-</code> بفرستید.\n\n"
        "پله‌های فعلی:\n<code>{current}</code>"
    )
    err_partner_volume_discount_parse = "⚠️ فرمت نامعتبر. هر خط: حداقل_گیگ,درصد"
    msg_partner_volume_discount_saved = "✅ تخفیف حجمی همکار ذخیره شد:\n{preview}"
    msg_ask_partner_price = "💵 قیمت هر گیگ را برای <b>همکاران</b> به تومان بفرستید (فقط عدد)."
    msg_partner_price_saved = "✅ قیمت هر گیگ همکار ذخیره شد: <b>{v:,.0f}</b> تومان"
    msg_admin_partner_add_intro = (
        "➕ <b>افزودن همکار</b>\n\n"
        "شناسهٔ تلگرام را بفرستید (فقط عدد) یا پیام کاربر را <b>فوروارد</b> کنید.\n"
        "اختیاری: در خط بعد نام/یادداشت (مثال: <code>علی فروشگاه</code>)."
    )
    msg_partner_added = "✅ همکار <code>{tid}</code> اضافه شد."
    msg_partner_already = "ℹ️ این کاربر از قبل در لیست همکاران است."
    err_partner_tid = "⚠️ شناسهٔ تلگرام نامعتبر است."
    msg_partners_list_empty = "📭 هنوز همکاری ثبت نشده است."
    msg_partners_list_header = "📋 <b>لیست همکاران</b> ({n} نفر)\n\n"
    msg_partners_list_line = "• <code>{tid}</code>{label}\n"
    msg_partner_usage_empty = (
        "📭 از آخرین تسویه، هیچ همکاری گیگ ثبت‌شده‌ای ندارد.\n"
        "پس از خرید یا حجم اضافه، اینجا نمایش داده می‌شود."
    )
    msg_partner_usage_header = (
        "📊 <b>گیگ خریداری‌شده همکاران</b> (از آخرین تسویه — {n} نفر)\n"
        "<i>با تسویه حساب همکار، مقدار او صفر می‌شود.</i>\n\n"
    )
    msg_partner_usage_line = (
        "• <code>{tid}</code>{label}\n"
        "　📊 <b>{gb}</b> گیگ — 💰 <b>{amount:,.0f}</b> تومان\n"
    )
    msg_partner_removed = "✅ همکار <code>{tid}</code> از لیست حذف شد."
    msg_partner_remove_fail = "⚠️ همکار یافت نشد."
    msg_buy_partner_rate = "👥 نرخ <b>همکار</b> اعمال شد.\n"
    msg_partner_panel = (
        "👥 <b>پنل همکاری</b>\n\n"
        "📊 گیگ خریداری‌شده (از آخرین تسویه): <b>{gb}</b> گیگ\n"
        "💰 مبلغ قابل تسویه: <b>{amount:,.0f}</b> تومان\n"
        "💳 موجودی کیف پول: <b>{bal:,.0f}</b> تومان\n"
        "💵 نرخ هر گیگ (همکار): <code>{ppg:,.0f}</code> تومان"
    )
    msg_partner_settle_ok = (
        "✅ <b>تسویه حساب</b> ثبت شد.\n"
        "مبلغ تسویه‌شده: <b>{amount:,.0f}</b> تومان — <b>{gb}</b> گیگ\n"
        "از این لحظه خریدهای جدید دوباره در حساب شما جمع می‌شود."
    )
    msg_partner_settle_empty = "ℹ️ در حال حاضر مبلغی برای تسویه ثبت نشده است."
    notif_partner_settlement_fmt = (
        "✅ <b>تسویه حساب همکار</b>\n\n"
        "👤 نام: <b>{name}</b>\n"
        "🔢 شناسه: <code>{uid}</code>\n"
        "📊 گیگ تسویه‌شده: <b>{gb}</b>\n"
        "💰 مبلغ: <b>{amount:,.0f}</b> تومان"
    )
    msg_admin_manage = (
        "🤖 <b>مدیریت ربات</b>\n\n"
        "💵 قیمت هر گیگ: <code>{ppg:,.0f}</code> تومان\n"
        "🛒 خرید برای مشتری: <b>{buy}</b>\n"
        "⏳ حالت به‌روزرسانی: <b>{maint}</b>\n\n"
        "🏦 نمایش شماره کارت در رسید: <b>{card}</b>\n"
        "💎 نمایش ارز دیجیتال در رسید: <b>{crypto}</b>\n"
        "📢 جوین اجباری کانال برای خرید/شارژ: <b>{chan_req}</b>\n"
        "　آیدی کانال: <code>{chan_preview}</code>\n\n"
        "🧪 سرویس تست برای مشتری: <b>{test}</b>\n"
        "📊 حجم سرویس تست: <code>{test_gb}</code> گیگ\n"
        "📉 تخفیف حجمی: {volume_discount}\n"
    )
    label_buy_on = "🟢 فعال"
    label_buy_off = "🔴 غیرفعال"
    label_maint_on = "🟢 روشن"
    label_maint_off = "⚪ خاموش"
    label_tgl_on = "🟢 روشن"
    label_tgl_off = "⚪ خاموش"
    cq_buy_toggled = "✅ وضعیت خرید به‌روز شد."
    cq_test_toggled = "✅ وضعیت سرویس تست به‌روز شد."
    msg_ask_test_gb = "📊 حجم سرویس تست را به <b>گیگابایت</b> بفرستید (مثال: <code>1</code> یا <code>0.5</code>)."
    err_test_gb_range = "⚠️ حجم تست باید بین ۰.۱ تا ۵۰ گیگ باشد."
    msg_test_gb_saved = "✅ حجم سرویس تست ذخیره شد: <b>{gb}</b> گیگ"
    notif_channel_test_service = (
        "🧪 <b>سرویس تست</b>\n"
        "👤 آیدی: <code>{uid}</code>\n"
        "📛 تلگرام: {tg_user}\n"
        "🔑 اکانت پنل: <code>{panel_user}</code>\n"
        "📊 حجم: <code>{gb}</code> GB\n"
        "✅ اوکی"
    )
    notif_channel_service_deleted = (
        "🗑 <b>حذف سرویس توسط کاربر</b>\n"
        "👤 آیدی: <code>{uid}</code>\n"
        "📛 تلگرام: {tg_user}\n"
        "🔑 اکانت پنل: <code>{panel_user}</code>\n"
        "📊 حجم سفارش: <code>{gb}</code> GB"
    )
    msg_admin_reset_test_intro = (
        "🔄 <b>ریست سرویس تست</b>\n\n"
        "شناسهٔ تلگرام کاربر را بفرستید (فقط عدد) یا پیام او را <b>فوروارد</b> کنید.\n"
        "پس از ریست، می‌تواند دوباره یک‌بار سرویس تست بگیرد."
    )
    msg_admin_reset_test_done = "✅ سرویس تست برای کاربر <code>{tid}</code> ریست شد ({n} رکورد پاک شد)."
    cq_maint_toggled = "✅ وضعیت به‌روزرسانی تغییر کرد."
    cq_toggle_card = "✅ وضعیت نمایش کارت به‌روز شد."
    cq_toggle_crypto = "✅ وضعیت نمایش ارز دیجیتال به‌روز شد."
    cq_toggle_chan = "✅ وضعیت جوین اجباری به‌روز شد."
    cq_channel_join_ok = "✅ عضویت تأیید شد. به ربات خوش آمدید!"
    err_channel_join_pending = "هنوز عضو کانال نشده‌اید. ابتدا روی «ورود به کانال» بزنید."
    err_chan_required_fields = "ابتدا آیدی کانال را ثبت کنید. برای کانال خصوصی در صورت نیاز لینک جوین را هم وارد کنید."
    msg_ask_price = "💵 قیمت هر گیگ را به <b>تومان</b> بفرستید (فقط عدد، مثال: 120000)."
    msg_ask_volume_discount = (
        "📉 <b>تخفیف حجمی (درصد)</b>\n\n"
        "هر خط یک پله: <code>حداقل_گیگ,درصد</code>\n"
        "برای حجم <b>بزرگ‌تر یا مساوی</b> هر پله، همان درصد (یا پلهٔ بالاتر) اعمال می‌شود.\n\n"
        "مثال (قیمت هر گیگ ۳۰۰ هزار):\n"
        "<code>3,5</code>  → از ۳ گیگ به بالا، ۵٪ تخفیف\n"
        "<code>5,10</code> → از ۵ گیگ به بالا، ۱۰٪ تخفیف\n\n"
        "برای غیرفعال کردن فقط <code>-</code> بفرستید.\n\n"
        "پله‌های فعلی:\n<code>{current}</code>"
    )
    err_volume_discount_parse = "⚠️ فرمت نامعتبر. هر خط: حداقل_گیگ,درصد (مثال: 3,5)"
    msg_volume_discount_saved = "✅ پله‌های تخفیف حجمی ذخیره شد:\n{preview}"
    msg_ask_card = (
        "🏦 <b>متن شماره کارت / واریز بانکی</b> را بفرستید (چند خط مجاز است).\n"
        "برای خالی کردن فقط <code>-</code> بفرستید."
    )
    err_card_short = "⚠️ برای حذف متن کارت فقط <code>-</code> بفرستید؛ در غیر این صورت حداقل ۵ نویسه لازم است."
    msg_ask_trust = "💎 متن راهنمای <b>ارز دیجیتال</b> / شبکه را بفرستید (می‌تواند چند خط باشد)."
    msg_ask_chan_id = (
        "📢 <b>آیدی کانال‌ها</b> را بفرستید (هر کانال در یک خط):\n"
        "مثال:\n"
        "<code>@mychannel</code>\n"
        "<code>-1001234567890</code>\n\n"
        "ربات باید در همهٔ کانال‌ها <b>ادمین</b> باشد تا عضویت کاربر چک شود.\n"
        "برای پاک کردن همه فقط <code>-</code> بفرستید."
    )
    err_chan_id_invalid = "⚠️ آیدی نامعتبر است. مثال: @channel یا عدد منفی سوپرگروه."
    msg_ask_chan_url = (
        "🔗 <b>لینک عضویت</b> (برای دکمهٔ شیشه‌ای) را بفرستید.\n"
        "باید با <code>https://</code> شروع شود، مثال:\n<code>https://t.me/+invite</code> یا <code>https://t.me/mychannel</code>"
    )
    err_chan_url_invalid = "⚠️ لینک باید با http:// یا https:// شروع شود (ترجیحاً https://t.me/...)."
    msg_ask_maint = "✏️ متنی که در حالت «به‌روزرسانی» به مشتری نشان داده می‌شود را بفرستید."
    msg_orders_empty = "📭 سفارش در انتظاری نیست."
    msg_order_cap = (
        "📋 <b>سفارش #{oid}</b> — <code>{kind}</code>\n"
        "👤 <code>{user_id}</code> — 💰 <code>{amount:,.0f}</code> تومان\n"
        "📊 GB: <code>{gb}</code>"
    )
    err_panel_html = "⛔ خطای پنل: {err}"
    msg_order_wallet_note = "\n\n💳 <i>پرداخت از کیف پول داخلی</i>"

    alert_order_stale = "این سفارش دیگر قابل عمل نیست."
    msg_user_reject_plain = "❌ سفارش #{oid} رد شد."
    msg_user_reject_wallet = "❌ سفارش #{oid} رد شد.\n💳 مبلغ به کیف پول شما برگشت داده شد."
    msg_user_topup_ok = "✅ شارژ سفارش #{oid} تایید شد.\n💳 موجودی جدید: <b>{bal:,.0f}</b> تومان"
    msg_user_buy_ok = (
        "✅ سفارش #{oid} تایید شد!\n\n"
        "👤 نام کاربری: <code>{username}</code>\n"
        "🔗 سابسکریپشن:\n<code>{sub}</code>"
    )
    err_panel = "⛔ خطای پنل: {err}"
    msg_user_buy_fail = "⛔ سفارش #{oid}: مشکل فنی در ساخت."
    msg_user_buy_fail_wallet_suffix = " مبلغ به کیف پول شما برگشت داده شد."
    msg_user_buy_fail_support_suffix = " با پشتیبانی تماس بگیرید."

    err_credit_tid = (
        "⚠️ شناسهٔ عددی تلگرام را بفرستید (مثال: <code>123456789</code>)، "
        "یا همان پیام کاربر را <b>فوروارد</b> کنید.\n"
        "اگر فوروارد «ناشناس» باشد، شناسه دیده نمی‌شود — باید عدد را دستی بفرستید."
    )
    err_credit_tid_bad = "⚠️ شناسه نامعتبر است."
    msg_credit_ask_amount = (
        "کاربر مقصد: <code>{tid}</code>\n\n"
        "مبلغ شارژ را به <b>تومان</b> بفرستید (فقط عدد، مثال: <code>500000</code>)."
    )
    msg_deduct_ask_amount = (
        "کاربر مقصد: <code>{tid}</code>\n\n"
        "مبلغ کاهش موجودی را به <b>تومان</b> بفرستید (فقط عدد، مثال: <code>500000</code>)."
    )
    err_credit_amt = "⚠️ فقط عدد مبلغ (تومان)."
    err_credit_range = "⚠️ مبلغ بین ۱ هزار تا ۵۰۰ میلیون تومان باشد."
    msg_credit_done_admin = (
        "✅ <b>{amt:,.0f}</b> تومان به کیف کاربر <code>{tid}</code> اضافه شد.\n"
        "💳 موجودی جدید او: <b>{bal:,.0f}</b> تومان"
    )
    msg_credit_done_user = (
        "💳 به موجودی کیف شما <b>{amt:,.0f}</b> تومان توسط ادمین اضافه شد.\n"
        "موجودی فعلی: <b>{bal:,.0f}</b> تومان"
    )
    msg_credit_notify_fail = "⚠️ پیام به کاربر ارسال نشد (شاید ربات را استارت نکرده). شارژ در دیتابیس ثبت شد."

    err_price_invalid = "⚠️ عدد نامعتبر."
    err_price_positive = "⚠️ باید بزرگ‌تر از صفر باشد."
    msg_price_saved = "✅ قیمت هر گیگ ذخیره شد: <b>{v:,.0f}</b> تومان"
    err_trust_short = "⚠️ متن خیلی کوتاه است."
    msg_card_saved = "✅ متن شماره کارت ذخیره شد."
    msg_trust_saved = "✅ متن ارز دیجیتال ذخیره شد."
    msg_chan_id_saved = "✅ آیدی کانال‌ها ذخیره شد ({n} کانال)."
    msg_chan_url_saved = "✅ لینک جوین ذخیره شد."
    msg_maint_saved = "✅ متن حالت به‌روزرسانی ذخیره شد."
    msg_ask_support_text = (
        "💬 <b>متن دکمه پشتیبانی</b> را بفرستید.\n"
        "می‌توانید از HTML استفاده کنید.\n"
        "برای پیش‌فرض فقط <code>-</code> بفرستید."
    )
    msg_ask_guide_text = (
        "📖 <b>متن راهنمای اتصال</b> را بفرستید.\n"
        "می‌توانید از HTML استفاده کنید.\n"
        "برای پیش‌فرض فقط <code>-</code> بفرستید."
    )
    msg_support_saved = "✅ متن پشتیبانی ذخیره شد."
    msg_guide_saved = "✅ متن راهنمای اتصال ذخیره شد."
    msg_ask_nowpayments_key = (
        "🔑 <b>کلید API درگاه NOWPayments</b> را بفرستید.\n"
        "برای پاک کردن فقط <code>-</code> بفرستید."
    )
    msg_nowpayments_saved = "✅ کلید NOWPayments ذخیره شد."
    msg_ask_main_button_rename = "✏️ نام جدید دکمه را بفرستید (حداکثر ۶۴ نویسه)."
    msg_main_button_renamed = "✅ نام دکمه به‌روز شد."
    msg_main_button_toggled = "✅ وضعیت دکمه تغییر کرد."
    msg_main_button_style_saved = "✅ رنگ دکمه: {style}"
    msg_global_style_saved = "✅ رنگ ذخیره شد: {style}"
    msg_ask_broadcast = "📢 متن <b>پیام همگانی</b> را بفرستید (HTML مجاز)."
    msg_broadcast_done = "✅ پیام همگانی ارسال شد.\nموفق: <b>{ok}</b> — ناموفق: <b>{fail}</b>"
    msg_ask_message_user_id = (
        "✉️ شناسه عددی کاربر مقصد را بفرستید (یا پیام را فوروارد کنید)."
    )
    msg_ask_message_user_text = "متن پیام را برای کاربر <code>{tid}</code> بفرستید."
    msg_message_user_done = "✅ پیام به کاربر <code>{tid}</code> ارسال شد."
    msg_ask_add_admin = (
        "➕ شناسه عددی ادمین جدید را بفرستید (یا پیام را فوروارد کنید).\n"
        "ادمین‌های env قابل حذف از ربات نیستند."
    )
    msg_receipt_admin_added = "✅ ادمین رسید <code>{tid}</code> اضافه شد."
    msg_receipt_admin_already = "ℹ️ این کاربر از قبل در لیست ادمین رسیدها است."
    msg_receipt_admin_removed = "✅ ادمین رسید <code>{tid}</code> حذف شد."
    msg_receipt_admin_not_found = "⚠️ این شناسه در لیست ادمین رسیدها نیست."
    msg_receipt_admins_list_empty = "📭 لیست ادمین رسیدها خالی است — رسیدها به همه ادمین‌ها می‌رود."
    msg_receipt_admins_list_header = "📋 <b>ادمین رسیدها</b>\n\nرسیدهای کاربران فقط برای این افراد ارسال می‌شود:\n\n"
    msg_receipt_admin_list_line = "• <code>{tid}</code>\n"
    msg_ask_receipt_admin_add = "➕ شناسه تلگرام ادمین رسید را بفرستید:"
    msg_ask_receipt_admin_rm = "➖ شناسه تلگرام ادمین رسید برای حذف را بفرستید:"
    msg_admin_added = "✅ ادمین <code>{tid}</code> اضافه شد."
    msg_admin_already = "ℹ️ این کاربر از قبل ادمین است."
    msg_admin_removed = "✅ ادمین <code>{tid}</code> حذف شد."
    msg_admin_remove_fail = "⚠️ حذف نشد (شاید ادمین env باشد یا در لیست نباشد)."
    msg_admins_list_empty = "📭 ادمین اضافه‌شده‌ای در ربات نیست (فقط env)."
    msg_admins_list_header = "📋 <b>ادمین‌های ربات</b>\n\n"
    msg_admins_list_line = "• <code>{tid}</code>{tag}\n"
    msg_ask_remove_admin = "❌ شناسه ادمین برای حذف را بفرستید."
    msg_ask_create_discount = (
        "➕ کد تخفیف را بفرستید:\n"
        "<code>کد,درصد</code> یا <code>کد,درصد,حداکثر_استفاده</code>\n"
        "مثال: <code>SALE10,10,100</code>"
    )
    err_discount_format = "⚠️ فرمت: کد,درصد[,حداکثر_استفاده]"
    msg_discount_created = "✅ کد <code>{code}</code> با {pct:g}٪ تخفیف ساخته شد."
    msg_discount_exists = "⚠️ این کد از قبل وجود دارد."
    msg_ask_remove_discount = "❌ کد تخفیف برای حذف را بفرستید."
    msg_discount_removed = "✅ کد <code>{code}</code> حذف شد."
    msg_discount_not_found = "⚠️ کد یافت نشد."
    msg_discount_list_empty = "📭 کد تخفیفی ثبت نشده."
    msg_discount_list_header = "🏷 <b>کدهای تخفیف</b>\n\n"
    msg_discount_list_line = (
        "• <code>{code}</code> — {pct:g}٪ — استفاده: {used}{max_part}\n"
    )
    msg_user_stats_result = (
        "📊 <b>آمار کاربر</b> <code>{tid}</code>\n\n"
        "💳 موجودی: <b>{bal:,.0f}</b> تومان\n"
        "📦 سرویس‌های فعال: <b>{svc_count}</b>\n\n"
        "<b>تاریخچه پرداخت (آخرین {n}):</b>\n{orders_block}\n\n"
        "<b>کانفیگ‌ها:</b>\n{configs_block}"
    )
    msg_user_stats_no_orders = "— سفارشی نیست —"
    msg_user_stats_order_line = (
        "• #{oid} {kind} — {status} — {amount:,.0f} ت — {gb_part}\n"
    )
    msg_user_stats_config_line = "• <code>{un}</code> — {gb} GB\n"
    msg_panel_removed = "✅ اتصال پنل حذف شد."
    cq_nowpay_toggled = "✅ وضعیت NOWPayments به‌روز شد."
    msg_buy_discount_code_line = "🏷 کد تخفیف: <b>{code}</b> — <b>{pct:g}٪</b>\n"
    msg_ask_promo_code = (
        "🏷 کد تخفیف را بفرستید.\n"
        "برای لغو فقط - را بفرستید."
    )
    err_promo_invalid = "⚠️ کد تخفیف نامعتبر یا منقضی است."
    msg_promo_applied = "✅ کد <code>{code}</code> اعمال شد — {pct:g}٪ تخفیف."
    err_nowpay_unavailable = "پرداخت NOWPayments الان در دسترس نیست."
    msg_nowpay_invoice = (
        "🌐 <b>پرداخت آنلاین NOWPayments</b>\n\n"
        "💰 مبلغ: <code>{amount:,.0f}</code> تومان\n"
        "📊 حجم: <code>{gb}</code> GB\n"
        "🧾 سفارش: <b>#{oid}</b>\n\n"
        "روی دکمهٔ زیر بزنید و پس از پرداخت، «بررسی پرداخت» را بزنید."
    )
    msg_nowpay_paid_ok = "✅ پرداخت NOWPayments تایید شد؛ سرویس فعال می‌شود."
    msg_nowpay_pending = "⏳ هنوز پرداخت تایید نشده. چند دقیقه بعد دوباره «بررسی پرداخت» را بزنید."
    msg_nowpay_fail = "⛔ خطا در ساخت فاکتور NOWPayments:\n<code>{err}</code>"
    cq_disc_toggled = "✅ وضعیت کد تخفیف به‌روز شد."

    # ——— اعلان ادمین / کانال ———
    notif_photo_fail_suffix = "\n\n(ارسال عکس ناموفق — شناسه فایل را از سفارش ببینید)"
    notif_channel_order_copy = "\n\n<i>کپی سفارش — تایید/رد فقط از پیام ادمین‌ها.</i>"
    notif_channel_receipt_copy = "\n\n<i>کپی رسید — دکمه تایید فقط برای ادمین‌ها در چت خصوصی است.</i>"

    notif_caption_buy_fmt = (
        "🆕 <b>سفارش خرید کانفیگ</b> #{oid}\n"
        "👤 کاربر: <code>{uid}</code>\n"
        "📊 حجم: <code>{gb}</code> GB\n"
        "💰 مبلغ: <code>{amount:,.0f}</code> تومان"
    )
    notif_caption_buy_doc_suffix = "\n📎 رسید به‌صورت فایل"
    notif_caption_buy_wallet_fmt = (
        "🆕 <b>سفارش خرید کانفیگ (کیف پول)</b> #{oid}\n"
        "👤 کاربر: <code>{uid}</code>\n"
        "📊 حجم: <code>{gb}</code> GB\n"
        "💰 مبلغ کسرشده: <code>{amount:,.0f}</code> تومان\n"
        "💳 موجودی جدید کاربر: <code>{new_bal:,.0f}</code> تومان"
    )
    notif_caption_topup_fmt = (
        "💎 <b>درخواست افزایش موجودی</b> #{oid}\n"
        "👤 کاربر: <code>{uid}</code>\n"
        "💰 مبلغ: <code>{amt:,.0f}</code> تومان"
    )
    notif_caption_topup_short_fmt = (
        "💎 <b>شارژ موجودی</b> #{oid}\n"
        "👤 کاربر: <code>{uid}</code>\n"
        "💰 مبلغ: <code>{amt:,.0f}</code> تومان"
    )
    notif_caption_extra_receipt_fmt = (
        "📈 <b>خرید حجم اضافه (رسید)</b> #{oid}\n"
        "👤 کاربر: <code>{uid}</code>\n"
        "🆔 سرویس #{parent_oid} — اکانت: <code>{panel_user}</code>\n"
        "📊 حجم: <code>{gb}</code> GB\n"
        "💰 مبلغ: <code>{amount:,.0f}</code> تومان"
    )
    notif_caption_extra_wallet_fmt = (
        "📈 <b>حجم اضافه (کیف پول)</b>\n"
        "👤 کاربر: <code>{uid}</code>\n"
        "🔑 اکانت: <code>{panel_user}</code>\n"
        "📊 +<code>{gb}</code> GB\n"
        "💰 مبلغ: <code>{amount:,.0f}</code> تومان\n"
        "💳 موجودی جدید: <code>{new_bal:,.0f}</code> تومان"
    )
    admin_receipt_extra_caption = (
        "📈 رسید — حجم اضافه\n\n"
        "🔢 ایدی عددی : {uid}\n"
        "🔑 اکانت پنل : {panel_user}\n"
        "🆔 سرویس : {parent_oid}\n"
        "👥 تعداد زیرمجموعه ها : {referrals} نفر\n"
        "🛍 تعداد سرویس ها : {svc_count} عدد\n\n"
        " - مبلغ : {amount}\n"
        " - حجم (گیگ) : {gb}\n\n"
        " {clock} | {jdate}"
    )
    msg_user_extra_ok = (
        "✅ سفارش حجم اضافه #{oid} تایید شد.\n"
        "📊 <b>{gb}</b> گیگ به سقف حجم سرویس شما اضافه شد."
    )

    # ——— وضعیت کاربر در پنل (فارسی) ———
    status_active = "فعال"
    status_disabled = "غیرفعال"
    status_limited = "محدود"
    status_expired = "منقضی"
    status_on_hold = "تعلیق"

    icon_status_ok = "✅"
    icon_status_warn = "⚠️"

    # ——— پیش‌فرض نگهداری (اگر در دیتابیس خالی باشد) ———
    default_maintenance = "⏳ ربات در حال به‌روزرسانی است."


# نمونهٔ واحد برای import
T = TEXTS()


def buy_payment_choice_text(
    *,
    amount: float,
    gb: float,
    ppg: float,
    bal: float,
    discount_percent: float,
    subtotal: float,
    is_partner: bool = False,
    package_title: str = "",
    config_days: int | None = None,
    promo_code: str = "",
    promo_percent: float = 0.0,
) -> str:
    disc_line = ""
    if discount_percent > 0:
        disc_line = T.msg_buy_discount_line.format(pct=discount_percent, subtotal=subtotal)
    if promo_code and promo_percent > 0:
        disc_line += T.msg_buy_discount_code_line.format(
            code=html.escape(promo_code, quote=False),
            pct=promo_percent,
        )
    partner_line = T.msg_buy_partner_rate if is_partner else ""
    package_line = ""
    if package_title:
        days_label = "نامحدود" if config_days is not None and config_days <= 0 else f"{config_days} روز"
        package_line = T.msg_buy_package_line.format(
            title=html.escape(package_title, quote=False),
            days_label=days_label,
        )
    rate_line = T.msg_buy_rate_line.format(ppg=ppg) if not package_title else ""
    return T.msg_buy_payment_choice.format(
        amount=amount,
        discount_line=partner_line + disc_line,
        package_line=package_line,
        rate_line=rate_line,
        gb=gb,
        bal=bal,
    )


def fmt_admin_manage(
    ppg: float,
    buy_on: bool,
    maint_on: bool,
    *,
    card_on: bool,
    crypto_on: bool,
    chan_on: bool,
    chan_preview: str,
    test_on: bool,
    test_gb: float,
    volume_discount: str,
) -> str:
    buy = T.label_buy_on if buy_on else T.label_buy_off
    maint = T.label_maint_on if maint_on else T.label_maint_off
    card = T.label_tgl_on if card_on else T.label_tgl_off
    crypto = T.label_tgl_on if crypto_on else T.label_tgl_off
    chan_req = T.label_tgl_on if chan_on else T.label_tgl_off
    test = T.label_tgl_on if test_on else T.label_tgl_off
    return T.msg_admin_manage.format(
        ppg=ppg,
        buy=buy,
        maint=maint,
        card=card,
        crypto=crypto,
        chan_req=chan_req,
        chan_preview=chan_preview,
        test=test,
        test_gb=test_gb,
        volume_discount=volume_discount,
    )


def fmt_admin_financial(
    pending: int,
    wallet_users: int,
) -> str:
    return T.msg_admin_financial_menu.format(
        pending=pending,
        wallet_users=wallet_users,
    )


def fmt_admin_colors_table(*, page: int, pages: int, total: int) -> str:
    return T.msg_admin_colors_menu.format(page=page, pages=pages, total=total)


def fmt_admin_shop(
    *,
    card_on: bool,
    crypto_on: bool,
    nowpay_on: bool,
    packages: str,
    buy_mode: str,
    ppg: float,
) -> str:
    card = T.label_tgl_on if card_on else T.label_tgl_off
    crypto = T.label_tgl_on if crypto_on else T.label_tgl_off
    nowpay = T.label_tgl_on if nowpay_on else T.label_tgl_off
    return T.msg_admin_shop_menu.format(
        card=card,
        crypto=crypto,
        nowpay=nowpay,
        packages=packages,
        buy_mode=buy_mode,
        ppg=ppg,
    )


def fmt_admin_test(*, test_gb: float) -> str:
    return T.msg_admin_test_menu.format(test_gb=test_gb)


def fmt_admin_bot_settings(
    *,
    maint_on: bool,
    card_on: bool,
    crypto_on: bool,
    nowpay_on: bool,
    buy_on: bool,
    disc_on: bool,
    receipt_preview: str,
) -> str:
    maint = T.label_maint_on if maint_on else T.label_maint_off
    card = T.label_tgl_on if card_on else T.label_tgl_off
    crypto = T.label_tgl_on if crypto_on else T.label_tgl_off
    nowpay = T.label_tgl_on if nowpay_on else T.label_tgl_off
    buy = T.label_buy_on if buy_on else T.label_buy_off
    disc = T.label_tgl_on if disc_on else T.label_tgl_off
    return T.msg_admin_bot_menu.format(
        maint=maint,
        card=card,
        crypto=crypto,
        nowpay=nowpay,
        buy=buy,
        disc=disc,
        receipt_preview=receipt_preview,
    )


def fmt_admin_channel(*, chan_on: bool, chan_preview: str, chan_count: int = 0) -> str:
    chan_req = T.label_tgl_on if chan_on else T.label_tgl_off
    return T.msg_admin_channel_menu.format(
        chan_req=chan_req,
        chan_preview=chan_preview,
        chan_count=chan_count,
    )


def fmt_admin_panel_menu(
    *,
    url: str,
    user: str,
    pass_mask: str,
    groups: str,
    prefix: str,
    start_num: int,
) -> str:
    return T.msg_admin_panel_menu.format(
        url=html.escape(url),
        user=html.escape(user),
        pass_mask=pass_mask,
        groups=html.escape(groups),
        prefix=html.escape(prefix),
        start_num=start_num,
    )


def notif_caption_buy(oid: int, uid: int, gb: float, amount: float) -> str:
    return T.notif_caption_buy_fmt.format(oid=oid, uid=uid, gb=gb, amount=amount)


def notif_caption_buy_doc(oid: int, uid: int, gb: float, amount: float) -> str:
    return notif_caption_buy(oid, uid, gb, amount) + T.notif_caption_buy_doc_suffix


def notif_caption_buy_wallet(oid: int, uid: int, gb: float, amount: float, new_bal: float) -> str:
    return T.notif_caption_buy_wallet_fmt.format(oid=oid, uid=uid, gb=gb, amount=amount, new_bal=new_bal)


def notif_caption_topup(oid: int, uid: int, amt: float) -> str:
    return T.notif_caption_topup_fmt.format(oid=oid, uid=uid, amt=amt)


def notif_caption_topup_short(oid: int, uid: int, amt: float) -> str:
    return T.notif_caption_topup_short_fmt.format(oid=oid, uid=uid, amt=amt)


def notif_caption_extra_receipt(
    oid: int,
    uid: int,
    *,
    parent_oid: int,
    panel_user: str,
    gb: float,
    amount: float,
) -> str:
    return T.notif_caption_extra_receipt_fmt.format(
        oid=oid,
        uid=uid,
        parent_oid=parent_oid,
        panel_user=panel_user,
        gb=gb,
        amount=amount,
    )


def notif_caption_extra_wallet(
    uid: int,
    *,
    panel_user: str,
    gb: float,
    amount: float,
    new_bal: float,
) -> str:
    return T.notif_caption_extra_wallet_fmt.format(
        uid=uid,
        panel_user=panel_user,
        gb=gb,
        amount=amount,
        new_bal=new_bal,
    )


def status_label_fa(code: str | None) -> str:
    key = str(code or "").strip().lower()
    return {
        "active": T.status_active,
        "disabled": T.status_disabled,
        "limited": T.status_limited,
        "expired": T.status_expired,
        "on_hold": T.status_on_hold,
    }.get(key, html.escape(key or "—"))

<div align="center">

# 🌶  فلفل

**ربات تلگرامی مدیریت و فروش خودکار VPN**

مدیریت کامل از داخل تلگرام و ترمینال سرور — بدون نیاز به دانش فنی

<br>

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0?logo=telegram&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux-FCC624?logo=linux&logoColor=black)
![Status](https://img.shields.io/badge/Status-Active-success)

</div>

---

## ✨ امکانات

| | |
|---|---|
| 🛒 **فروش خودکار** | سرویس حجمی و بسته‌ای |
| 💰 **کیف پول** | شارژ و پرداخت داخلی |
| 💳 **پرداخت چندروشه** | کارت‌به‌کارت، ارز دیجیتال، درگاه آنلاین |
| 🏷 **کد تخفیف** | با محدودیت تعداد استفاده |
| 🧪 **سرویس تست** | اکانت تست رایگان برای کاربران |
| 👥 **پنل همکاری** | نمایندگی با قیمت‌گذاری اختصاصی |
| 📢 **عضویت اجباری** | الزام عضویت در کانال |
| 🗄 **پشتیبان‌گیری** | بکاپ/بازیابی کامل و بازگشت به تنظیمات کارخانه |
| ♻️ **مدیریت خودکار** | حذف خودکار سرویس‌های منقضی |
| 🎨 **شخصی‌سازی** | تغییر دکمه‌ها، متن‌ها و رنگ‌ها از داخل ربات |

---

## 🚀 نصب

```bash
git clone https://github.com/MrJackX/felfel.git
cd felfel
sudo bash install.sh
```

اسکریپت نصب به‌صورت **کاملاً خودکار**:

1. پایتون و وابستگی‌ها را نصب می‌کند
2. هنگام نصب **توکن ربات** و **شناسه ادمین** را می‌پرسد
3. ربات را به‌عنوان سرویس راه‌اندازی می‌کند تا همیشه روشن بماند (auto-restart + اجرای خودکار بعد از ریبوت)
4. دستور `felfel` را برای مدیریت آسان می‌سازد

---

## 🖥 مدیریت

کافی است در ترمینال سرور تایپ کنید:

```bash
felfel
```

<div align="center">

| گزینه | عملکرد |
|:---:|:---|
| ▶️ ⏹ 🔄 | شروع / توقف / ری‌استارت |
| 📊 📜 | وضعیت و لاگ زنده |
| 🔑 👮 | تغییر توکن و ادمین‌ها |
| ⬆️ | به‌روزرسانی از گیت‌هاب |
| 🗑 | حذف کامل ربات |

</div>

> سایر تنظیمات (قیمت، متن‌ها، بسته‌ها و ...) از **پنل ادمین داخل تلگرام** انجام می‌شود.

---

## ⚙️ پیکربندی

متغیرهای فایل `.env` (در نصب خودکار به‌صورت خودکار ساخته می‌شود):

| متغیر | توضیح | پیش‌فرض |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | توکن ربات از [@BotFather](https://t.me/BotFather) | الزامی |
| `BOT_ADMIN_IDS` | شناسه ادمین‌ها (جداشده با کاما) | الزامی |
| `VERIFY_SSL` | بررسی گواهی SSL | `true` |
| `BOT_DB_PATH` | مسیر فایل دیتابیس | `felfel.sqlite` |

<details>
<summary>🔧 نصب دستی (بدون اسکریپت)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate        # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # سپس .env را ویرایش کنید
python bot.py
```

</details>

---

## 🔐 امنیت

فایل‌های `.env` و دیتابیس به‌صورت پیش‌فرض در `.gitignore` قرار دارند و منتشر نمی‌شوند. در صورت لو رفتن توکن، از طریق `/revoke` در [@BotFather](https://t.me/BotFather) توکن جدید بگیرید.

<div align="center">
<sub>ساخته‌شده با ❤️ توسط <a href="https://github.com/MrJackX">MrJackX</a></sub>
</div>

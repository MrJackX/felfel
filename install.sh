#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  اسکریپت نصب خودکار ربات فلفل (felfel)
#  پشتیبانی: Ubuntu / Debian
#
#  نصب تک‌خطی:
#    bash <(curl -sL https://raw.githubusercontent.com/MrJackX/felfel/main/install.sh)
#
#  یا اگر از قبل clone کرده‌اید:
#    sudo bash install.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[x]${NC} $1" >&2; }

REPO_URL="https://github.com/MrJackX/felfel.git"
INSTALL_DIR="${FELFEL_DIR:-/opt/felfel}"
SERVICE_NAME="felfel"
PYTHON_BIN="python3"
CLI_PATH="/usr/local/bin/felfel"
RUN_USER="${SUDO_USER:-root}"

# باید با دسترسی root اجرا شود
if [[ $EUID -ne 0 ]]; then
    err "لطفاً اسکریپت را با دسترسی root اجرا کنید."
    err "نصب تک‌خطی:  sudo bash <(curl -sL ${REPO_URL%.git}/raw/main/install.sh)"
    exit 1
fi

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║        نصب ربات فلفل (felfel)        ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${NC}"

# ─── git را زود نصب می‌کنیم (برای حالت تک‌خطی لازم است) ───
if ! command -v git >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update -qq && apt-get install -y git >/dev/null
    fi
fi

# ─── تشخیص محل پروژه؛ اگر پیدا نشد، خودش clone می‌کند ───
if [[ -f "./bot.py" && -f "./requirements.txt" ]]; then
    PROJECT_DIR="$(pwd)"
elif SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" && [[ -f "$SD/bot.py" ]]; then
    PROJECT_DIR="$SD"
else
    # حالت تک‌خطی: پروژه را clone یا به‌روزرسانی می‌کنیم
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "به‌روزرسانی پروژه در $INSTALL_DIR ..."
        git -C "$INSTALL_DIR" pull --quiet
    else
        info "دریافت پروژه از گیت‌هاب در $INSTALL_DIR ..."
        git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    fi
    PROJECT_DIR="$INSTALL_DIR"
fi

VENV_DIR="$PROJECT_DIR/.venv"
cd "$PROJECT_DIR"

# ─── ۱) پیش‌نیازهای سیستمی ───
info "نصب پیش‌نیازهای سیستمی..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y python3 python3-venv python3-pip git >/dev/null
else
    warn "apt-get پیدا نشد — مطمئن شوید python3 و python3-venv نصب است."
fi

# ─── ۲) محیط مجازی و وابستگی‌ها ───
info "ساخت محیط مجازی پایتون..."
$PYTHON_BIN -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
info "نصب وابستگی‌های ربات..."
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q

# ─── ۳) دریافت تنظیمات از کاربر و ساخت .env ───
if [[ -f "$PROJECT_DIR/.env" ]]; then
    warn "فایل .env از قبل وجود دارد — از تنظیمات فعلی استفاده می‌شود."
else
    echo
    echo -e "${CYAN}── پیکربندی ربات ──${NC}"
    while [[ -z "${BOT_TOKEN:-}" ]]; do
        read -rp "🔑 توکن ربات تلگرام (از @BotFather): " BOT_TOKEN
    done
    while [[ -z "${ADMIN_IDS:-}" ]]; do
        read -rp "👮 شناسه عددی ادمین (از @userinfobot): " ADMIN_IDS
    done

    cat > "$PROJECT_DIR/.env" <<EOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
BOT_ADMIN_IDS=$ADMIN_IDS
VERIFY_SSL=true
BOT_DB_PATH=felfel.sqlite
EOF
    chmod 600 "$PROJECT_DIR/.env"
    info "فایل تنظیمات ساخته شد."
fi

# ─── ۴) سرویس systemd ───
info "راه‌اندازی سرویس..."
cat > "/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=Felfel Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python $PROJECT_DIR/bot.py
Restart=always
RestartSec=5
StandardOutput=append:$PROJECT_DIR/felfel.log
StandardError=append:$PROJECT_DIR/felfel.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1
systemctl restart "$SERVICE_NAME"

# ─── ۵) ساخت دستور مدیریت felfel ───
info "ساخت دستور مدیریت «felfel»..."
cat > "$CLI_PATH" <<EOF
#!/usr/bin/env bash
# منوی مدیریت ربات فلفل
PROJECT_DIR="$PROJECT_DIR"
SERVICE="$SERVICE_NAME"
VENV="$VENV_DIR"
ENV_FILE="$PROJECT_DIR/.env"
EOF
cat >> "$CLI_PATH" <<'FELFEL_CLI'

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'

need_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${R}این کار به دسترسی root نیاز دارد. با sudo اجرا کنید.${N}"
        exit 1
    fi
}

status_line() {
    if systemctl is-active --quiet "$SERVICE"; then
        echo -e "وضعیت ربات: ${G}● روشن${N}"
    else
        echo -e "وضعیت ربات: ${R}● خاموش${N}"
    fi
}

set_env() {  # set_env KEY VALUE
    local key="$1" val="$2"
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}

while true; do
    clear
    echo -e "${C}"
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║         مدیریت ربات فلفل             ║"
    echo "  ╚══════════════════════════════════════╝"
    echo -e "${N}"
    status_line
    echo
    echo "  1) ▶️  شروع ربات"
    echo "  2) ⏹  توقف ربات"
    echo "  3) 🔄 ری‌استارت ربات"
    echo "  4) 📊 وضعیت کامل"
    echo "  5) 📜 مشاهده لاگ زنده"
    echo "  6) 🔑 تغییر توکن ربات"
    echo "  7) 👮 تغییر شناسه ادمین‌ها"
    echo "  8) ⬆️  به‌روزرسانی از گیت‌هاب"
    echo "  9) 🗑  حذف کامل ربات"
    echo "  0) 🚪 خروج"
    echo
    read -rp "  انتخاب شما: " ch
    case "$ch" in
        1) need_root; systemctl start "$SERVICE";   echo -e "${G}ربات شروع شد.${N}"; read -rp "Enter..." _ ;;
        2) need_root; systemctl stop "$SERVICE";    echo -e "${Y}ربات متوقف شد.${N}"; read -rp "Enter..." _ ;;
        3) need_root; systemctl restart "$SERVICE"; echo -e "${G}ربات ری‌استارت شد.${N}"; read -rp "Enter..." _ ;;
        4) systemctl status "$SERVICE" --no-pager; read -rp "Enter..." _ ;;
        5) echo -e "${Y}برای خروج Ctrl+C بزنید${N}"; sleep 1; journalctl -u "$SERVICE" -f ;;
        6) need_root
           read -rp "توکن جدید ربات: " NT
           if [[ -n "$NT" ]]; then set_env "TELEGRAM_BOT_TOKEN" "$NT"; systemctl restart "$SERVICE"; echo -e "${G}توکن به‌روزرسانی و ربات ری‌استارت شد.${N}"; fi
           read -rp "Enter..." _ ;;
        7) need_root
           read -rp "شناسه ادمین‌ها (با کاما جدا کنید): " NA
           if [[ -n "$NA" ]]; then set_env "BOT_ADMIN_IDS" "$NA"; systemctl restart "$SERVICE"; echo -e "${G}ادمین‌ها به‌روزرسانی و ربات ری‌استارت شد.${N}"; fi
           read -rp "Enter..." _ ;;
        8) need_root
           cd "$PROJECT_DIR" && git pull && "$VENV/bin/pip" install -r requirements.txt -q && systemctl restart "$SERVICE"
           echo -e "${G}به‌روزرسانی انجام شد.${N}"; read -rp "Enter..." _ ;;
        9) need_root
           read -rp "مطمئنید؟ برای حذف کامل ربات «yes» تایپ کنید: " CONF
           if [[ "$CONF" == "yes" ]]; then
               systemctl stop "$SERVICE"; systemctl disable "$SERVICE" 2>/dev/null
               rm -f "/etc/systemd/system/$SERVICE.service"; systemctl daemon-reload
               rm -f /usr/local/bin/felfel
               echo -e "${Y}ربات حذف شد. (پوشه پروژه و دیتابیس دست‌نخورده باقی ماند)${N}"
               exit 0
           fi ;;
        0) exit 0 ;;
        *) echo -e "${R}گزینه نامعتبر${N}"; sleep 1 ;;
    esac
done
FELFEL_CLI
chmod +x "$CLI_PATH"

echo
info "نصب کامل شد! 🌶"
echo -e "${CYAN}برای مدیریت ربات، کافی است تایپ کنید:${NC}  ${GREEN}felfel${NC}"
echo
status_line() { :; }
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "وضعیت فعلی ربات: ${GREEN}● روشن${NC}"
else
    echo -e "وضعیت فعلی ربات: ${RED}● خاموش — لاگ را بررسی کنید: felfel → گزینه ۵${NC}"
fi

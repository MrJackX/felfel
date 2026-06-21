#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  Felfel Telegram Bot - automatic installer
#  Supported: Ubuntu / Debian
#
#  One-line install:
#    sudo bash <(curl -sL https://raw.githubusercontent.com/MrJackX/felfel/main/install.sh)
#
#  Or if already cloned:
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

# Must run as root
if [[ $EUID -ne 0 ]]; then
    err "Please run this script as root."
    err "One-line install:  sudo bash <(curl -sL ${REPO_URL%.git}/raw/main/install.sh)"
    exit 1
fi

echo -e "${CYAN}"
echo "  +======================================+"
echo "  |        Felfel Bot  -  Installer      |"
echo "  +======================================+"
echo -e "${NC}"

# Install git early (needed for one-line mode)
if ! command -v git >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update -qq && apt-get install -y git >/dev/null
    fi
fi

# Detect project location; if not found, clone it
if [[ -f "./bot.py" && -f "./requirements.txt" ]]; then
    PROJECT_DIR="$(pwd)"
elif SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" && [[ -f "$SD/bot.py" ]]; then
    PROJECT_DIR="$SD"
else
    # One-line mode: clone or update the project
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Updating project in $INSTALL_DIR ..."
        git -C "$INSTALL_DIR" pull --quiet
    else
        info "Downloading project into $INSTALL_DIR ..."
        git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    fi
    PROJECT_DIR="$INSTALL_DIR"
fi

VENV_DIR="$PROJECT_DIR/.venv"
cd "$PROJECT_DIR"

# 1) System dependencies
info "Installing system dependencies..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y python3 python3-venv python3-pip git >/dev/null
else
    warn "apt-get not found - make sure python3 and python3-venv are installed."
fi

# 2) Virtualenv and dependencies
info "Creating Python virtual environment..."
$PYTHON_BIN -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
info "Installing bot dependencies..."
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q

# 3) Ask for settings and create .env
if [[ -f "$PROJECT_DIR/.env" ]]; then
    warn ".env already exists - using current settings."
else
    echo
    echo -e "${CYAN}-- Bot configuration --${NC}"
    while [[ -z "${BOT_TOKEN:-}" ]]; do
        read -rp "Telegram bot token (from @BotFather): " BOT_TOKEN
    done
    while [[ -z "${ADMIN_IDS:-}" ]]; do
        read -rp "Admin numeric id (from @userinfobot): " ADMIN_IDS
    done

    cat > "$PROJECT_DIR/.env" <<EOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
BOT_ADMIN_IDS=$ADMIN_IDS
VERIFY_SSL=true
BOT_DB_PATH=felfel.sqlite
EOF
    chmod 600 "$PROJECT_DIR/.env"
    info "Config file created."
fi

# 4) systemd service
info "Setting up service..."
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

# 5) Create the felfel management command
info "Creating 'felfel' management command..."
cat > "$CLI_PATH" <<EOF
#!/usr/bin/env bash
# Felfel bot management menu
PROJECT_DIR="$PROJECT_DIR"
SERVICE="$SERVICE_NAME"
VENV="$VENV_DIR"
ENV_FILE="$PROJECT_DIR/.env"
EOF
cat >> "$CLI_PATH" <<'FELFEL_CLI'

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'

need_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${R}This action needs root. Run with sudo.${N}"
        exit 1
    fi
}

status_line() {
    if systemctl is-active --quiet "$SERVICE"; then
        echo -e "Bot status: ${G}* running${N}"
    else
        echo -e "Bot status: ${R}* stopped${N}"
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
    echo "  +======================================+"
    echo "  |          Felfel  -  Manager          |"
    echo "  +======================================+"
    echo -e "${N}"
    status_line
    echo
    echo "  1) Start bot"
    echo "  2) Stop bot"
    echo "  3) Restart bot"
    echo "  4) Full status"
    echo "  5) Live logs"
    echo "  6) Change bot token"
    echo "  7) Change admin ids"
    echo "  8) Update from GitHub"
    echo "  9) Uninstall bot"
    echo "  0) Exit"
    echo
    read -rp "  Your choice: " ch
    case "$ch" in
        1) need_root; systemctl start "$SERVICE";   echo -e "${G}Bot started.${N}"; read -rp "Press Enter..." _ ;;
        2) need_root; systemctl stop "$SERVICE";    echo -e "${Y}Bot stopped.${N}"; read -rp "Press Enter..." _ ;;
        3) need_root; systemctl restart "$SERVICE"; echo -e "${G}Bot restarted.${N}"; read -rp "Press Enter..." _ ;;
        4) systemctl status "$SERVICE" --no-pager; read -rp "Press Enter..." _ ;;
        5) echo -e "${Y}Press Ctrl+C to exit${N}"; sleep 1; journalctl -u "$SERVICE" -f ;;
        6) need_root
           read -rp "New bot token: " NT
           if [[ -n "$NT" ]]; then set_env "TELEGRAM_BOT_TOKEN" "$NT"; systemctl restart "$SERVICE"; echo -e "${G}Token updated and bot restarted.${N}"; fi
           read -rp "Press Enter..." _ ;;
        7) need_root
           read -rp "Admin ids (comma separated): " NA
           if [[ -n "$NA" ]]; then set_env "BOT_ADMIN_IDS" "$NA"; systemctl restart "$SERVICE"; echo -e "${G}Admins updated and bot restarted.${N}"; fi
           read -rp "Press Enter..." _ ;;
        8) need_root
           cd "$PROJECT_DIR" && git pull && "$VENV/bin/pip" install -r requirements.txt -q && systemctl restart "$SERVICE"
           echo -e "${G}Update done.${N}"; read -rp "Press Enter..." _ ;;
        9) need_root
           read -rp "Are you sure? type 'yes' to fully uninstall: " CONF
           if [[ "$CONF" == "yes" ]]; then
               systemctl stop "$SERVICE"; systemctl disable "$SERVICE" 2>/dev/null
               rm -f "/etc/systemd/system/$SERVICE.service"; systemctl daemon-reload
               rm -f /usr/local/bin/felfel
               echo -e "${Y}Bot removed. (project folder and database kept intact)${N}"
               exit 0
           fi ;;
        0) exit 0 ;;
        *) echo -e "${R}Invalid choice${N}"; sleep 1 ;;
    esac
done
FELFEL_CLI
chmod +x "$CLI_PATH"

echo
info "Installation complete!"
echo -e "${CYAN}To manage the bot, just type:${NC}  ${GREEN}felfel${NC}"
echo
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "Current bot status: ${GREEN}* running${NC}"
else
    echo -e "Current bot status: ${RED}* stopped - check logs: felfel -> option 5${NC}"
fi

#!/usr/bin/env bash
# One-line installer for the ShopOn mart demo bot.
#   curl -fsSL https://raw.githubusercontent.com/kimsungyong1117-jpg/shopon-mart-demo/main/install.sh | bash -s <BOT_TOKEN>
# Installs into /root/shopon-demo, keeps an existing .env/database, and runs the bot as a
# systemd service so it survives logout and reboots. Safe to run again to update.
set -euo pipefail

REPO_TARBALL="https://github.com/kimsungyong1117-jpg/shopon-mart-demo/archive/refs/heads/main.tar.gz"
APP_DIR="/root/shopon-demo"
SERVICE="shopon-demo"
TOKEN="${1:-}"

echo "==> [1/5] 시스템 패키지 확인 중"
if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq python3-venv >/dev/null || apt-get install -y -qq "python3.$(python3 -c 'import sys;print(sys.version_info.minor)')-venv" >/dev/null
fi

echo "==> [2/5] 데모 봇 내려받는 중"
mkdir -p "$APP_DIR"
TMP="$(mktemp -d)"
curl -fsSL "$REPO_TARBALL" | tar -xz -C "$TMP" --strip-components=1
# Keep the owner's settings and demo data across updates.
cp -a "$TMP"/. "$APP_DIR"/
rm -rf "$TMP"
cd "$APP_DIR"

echo "==> [3/5] 파이썬 패키지 설치 중"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

echo "==> [4/5] 설정 저장 중"
if [ ! -f .env ]; then
  cp .env.example .env
fi
if [ -n "$TOKEN" ]; then
  sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=$TOKEN|" .env
fi
chmod 600 .env
if grep -q "^BOT_TOKEN=paste-" .env; then
  echo "!! 봇 토큰이 아직 없어요. 명령어 끝에 토큰을 붙여서 다시 실행하세요:  ... | bash -s <봇토큰>"
  exit 1
fi

echo "==> [5/5] 데모 봇 시작 중"
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=ShopOn mart demo bot
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/mart_demo_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1
systemctl restart "$SERVICE"
sleep 6

if systemctl is-active --quiet "$SERVICE"; then
  echo
  echo "✅ 데모 봇이 실행 중이에요. 텔레그램에서 데모 봇에 /start 를 보내보세요"
  echo "   로그 보기: journalctl -u $SERVICE -n 50    끄기: systemctl stop $SERVICE"
else
  echo
  echo "❌ 데모 봇이 시작되지 않았어요. 아래 내용을 복사해서 Claude에게 보내주세요:"
  journalctl -u "$SERVICE" -n 30 --no-pager
  exit 1
fi

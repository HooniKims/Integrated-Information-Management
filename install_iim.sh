#!/bin/bash

set -e

APP_NAME="iim"
PORT="8765"
ALLOWED_NETWORK="10.73.78.0/24"
CURRENT_USER="$(whoami)"
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "======================================"
echo "Integrated Information Management 설치 시작"
echo "======================================"
echo ""
echo "현재 사용자: $CURRENT_USER"
echo "설치 위치: $INSTALL_DIR"
echo "사용 포트: $PORT"
echo "허용 내부망: $ALLOWED_NETWORK"
echo ""

echo "[1/10] apt 패키지 목록 업데이트"
sudo apt update

echo ""
echo "[2/10] 기본 패키지 업그레이드"
sudo apt upgrade -y

echo ""
echo "[3/10] 필수 시스템 패키지 설치"
sudo apt install -y git python3 python3-pip python3-venv ufw curl iputils-ping

echo ""
echo "[4/10] 프로젝트 파일 확인"
cd "$INSTALL_DIR"

if [ ! -f "$INSTALL_DIR/server.py" ]; then
    echo "오류: server.py 파일을 찾을 수 없습니다."
    echo "install_iim.sh 파일은 server.py와 같은 폴더에 있어야 합니다."
    exit 1
fi

if [ ! -f "$INSTALL_DIR/requirements.txt" ]; then
    echo "주의: requirements.txt 파일이 없습니다."
    echo "필요한 파이썬 패키지 설치를 건너뜁니다."
fi

echo ""
echo "[5/10] Python 가상환경 생성"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
else
    echo "기존 venv 가상환경을 사용합니다."
fi

echo ""
echo "[6/10] Python 패키지 설치"
source "$INSTALL_DIR/venv/bin/activate"

python -m pip install --upgrade pip setuptools wheel

if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    pip install -r "$INSTALL_DIR/requirements.txt"
else
    echo "requirements.txt가 없어 pip 패키지 설치를 건너뜁니다."
fi

deactivate

echo ""
echo "[7/10] UFW 방화벽 설정"
sudo ufw allow ssh
sudo ufw allow from "$ALLOWED_NETWORK" to any port "$PORT" proto tcp
sudo ufw --force enable

echo ""
echo "[8/10] systemd 서비스 파일 생성"
sudo tee /etc/systemd/system/${APP_NAME}.service > /dev/null <<EOF
[Unit]
Description=Integrated Information Management Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "[9/10] 서비스 등록 및 시작"
sudo systemctl daemon-reload
sudo systemctl enable "$APP_NAME"
sudo systemctl restart "$APP_NAME"

echo ""
echo "[10/10] 설치 상태 확인"
sleep 2

echo ""
echo "서비스 상태:"
sudo systemctl status "$APP_NAME" --no-pager || true

echo ""
echo "포트 확인:"
ss -tulnp | grep "$PORT" || true

echo ""
echo "방화벽 상태:"
sudo ufw status numbered || true

echo ""
echo "======================================"
echo "설치 완료"
echo "======================================"
echo ""
echo "프로젝트 위치:"
echo "$INSTALL_DIR"
echo ""
echo "메인 실행 파일:"
echo "$INSTALL_DIR/server.py"
echo ""
echo "서비스 이름:"
echo "$APP_NAME"
echo ""
echo "허용된 내부망:"
echo "$ALLOWED_NETWORK"
echo ""
echo "허용된 포트:"
echo "$PORT"
echo ""
echo "접속 주소 예시:"
echo "http://라즈베리파이IP:$PORT"
echo ""
echo "상태 확인:"
echo "sudo systemctl status $APP_NAME"
echo ""
echo "서버 재시작:"
echo "sudo systemctl restart $APP_NAME"
echo ""
echo "실시간 로그 확인:"
echo "journalctl -u $APP_NAME -f"
echo ""
echo "포트 확인:"
echo "ss -tulnp | grep $PORT"
echo ""
echo "재부팅 테스트:"
echo "sudo reboot"
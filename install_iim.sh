#!/bin/bash

set -e

APP_NAME="iim"
PORT="8765"
ALLOWED_NETWORK="10.73.78.0/24"
DEFAULT_LOGIN_ID="dcms"
DEFAULT_LOGIN_PASSWORD="dcms04935!"
STATIC_IP="10.73.78.15"
STATIC_PREFIX="24"
STATIC_IP_CIDR="${STATIC_IP}/${STATIC_PREFIX}"
GATEWAY="10.73.78.254"
DNS_SERVER="8.8.8.8"
CURRENT_USER="$(whoami)"
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"

detect_network_interface() {
    ip route | awk '/^default/ {print $5; exit}'
}

configure_static_ip() {
    local interface_name="$1"

    if [ -z "$interface_name" ]; then
        interface_name="$(ip -o link show | awk -F': ' '$2 != "lo" {print $2; exit}')"
    fi

    if [ -z "$interface_name" ]; then
        echo "경고: 네트워크 인터페이스를 찾지 못했습니다. 고정 IP 설정을 건너뜁니다."
        return 0
    fi

    echo "네트워크 인터페이스: $interface_name"
    echo "고정 IP: $STATIC_IP_CIDR"
    echo "기본 게이트웨이: $GATEWAY"
    echo "DNS: $DNS_SERVER"

    if command -v nmcli >/dev/null 2>&1; then
        local connection_name
        connection_name="$(nmcli -t -f NAME,DEVICE connection show --active | awk -F: -v dev="$interface_name" '$2 == dev {print $1; exit}')"

        if [ -z "$connection_name" ]; then
            connection_name="$(nmcli -t -f NAME,DEVICE connection show | awk -F: -v dev="$interface_name" '$2 == dev {print $1; exit}')"
        fi

        if [ -z "$connection_name" ]; then
            echo "경고: NetworkManager 연결 이름을 찾지 못했습니다. 고정 IP 설정을 건너뜁니다."
            return 0
        fi

        sudo nmcli connection modify "$connection_name" \
            ipv4.method manual \
            ipv4.addresses "$STATIC_IP_CIDR" \
            ipv4.gateway "$GATEWAY" \
            ipv4.dns "$DNS_SERVER" \
            connection.autoconnect yes

        sudo nmcli connection up "$connection_name" || {
            echo "경고: 네트워크 연결을 즉시 다시 올리지 못했습니다. 재부팅 후 적용될 수 있습니다."
        }
        return 0
    fi

    if [ -f /etc/dhcpcd.conf ]; then
        sudo cp /etc/dhcpcd.conf "/etc/dhcpcd.conf.bak.$(date +%Y%m%d%H%M%S)"
        sudo sed -i "/^interface ${interface_name}$/,/^$/d" /etc/dhcpcd.conf
        sudo tee -a /etc/dhcpcd.conf >/dev/null <<EOF

interface ${interface_name}
static ip_address=${STATIC_IP_CIDR}
static routers=${GATEWAY}
static domain_name_servers=${DNS_SERVER}
EOF

        if systemctl list-unit-files | grep -q '^dhcpcd\.service'; then
            sudo systemctl restart dhcpcd || {
                echo "경고: dhcpcd 재시작에 실패했습니다. 재부팅 후 적용될 수 있습니다."
            }
        fi
        return 0
    fi

    echo "경고: nmcli와 dhcpcd.conf를 모두 찾지 못했습니다. 고정 IP는 수동 확인이 필요합니다."
}

configure_env_file() {
    local env_file="$INSTALL_DIR/.env"

    if [ ! -f "$env_file" ]; then
        cat > "$env_file" <<EOF
DCMS_LOGIN_ID=${DEFAULT_LOGIN_ID}
DCMS_LOGIN_PASSWORD=${DEFAULT_LOGIN_PASSWORD}
EOF
        chmod 600 "$env_file"
        echo ".env 파일을 기본 로그인 정보로 생성했습니다."
        return 0
    fi

    if ! grep -q '^DCMS_LOGIN_ID=' "$env_file"; then
        printf '\nDCMS_LOGIN_ID=%s\n' "$DEFAULT_LOGIN_ID" >> "$env_file"
        echo ".env 파일에 기본 로그인 ID를 추가했습니다."
    fi

    if ! grep -q '^DCMS_LOGIN_PASSWORD=' "$env_file"; then
        printf 'DCMS_LOGIN_PASSWORD=%s\n' "$DEFAULT_LOGIN_PASSWORD" >> "$env_file"
        echo ".env 파일에 기본 로그인 비밀번호를 추가했습니다."
    fi

    chmod 600 "$env_file"
}

echo "======================================"
echo "Integrated Information Management 설치 시작"
echo "======================================"
echo ""
echo "현재 사용자: $CURRENT_USER"
echo "설치 위치: $INSTALL_DIR"
echo "사용 포트: $PORT"
echo "허용 내부망: $ALLOWED_NETWORK"
echo "기본 로그인 ID: $DEFAULT_LOGIN_ID"
echo "설정할 고정 IP: $STATIC_IP_CIDR"
echo "기본 게이트웨이: $GATEWAY"
echo "DNS: $DNS_SERVER"
echo ""

echo "[1/13] apt 패키지 목록 업데이트"
sudo apt update

echo ""
echo "[2/13] 기본 패키지 업그레이드"
sudo apt upgrade -y

echo ""
echo "[3/13] 필수 시스템 패키지 설치"
sudo apt install -y git python3 python3-pip python3-venv ufw curl iputils-ping arping libcap2-bin openssh-server samba-common-bin

if command -v arping >/dev/null 2>&1 && command -v setcap >/dev/null 2>&1; then
    sudo setcap cap_net_raw+ep "$(command -v arping)" || {
        echo "경고: arping 권한 설정에 실패했습니다. IP 충돌 감지가 제한될 수 있습니다."
    }
fi

echo ""
echo "[4/13] SSH 서버 자동 실행 설정"
sudo systemctl enable ssh
sudo systemctl start ssh

echo ""
echo "[5/13] 프로젝트 파일 확인"
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
echo "[6/13] 로그인 환경설정 파일 생성"
configure_env_file

echo ""
echo "[7/13] Python 가상환경 생성"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
else
    echo "기존 venv 가상환경을 사용합니다."
fi

echo ""
echo "[8/13] Python 패키지 설치"
source "$INSTALL_DIR/venv/bin/activate"

python -m pip install --upgrade pip setuptools wheel

if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    pip install -r "$INSTALL_DIR/requirements.txt"
else
    echo "requirements.txt가 없어 pip 패키지 설치를 건너뜁니다."
fi

deactivate

echo ""
echo "[9/13] UFW 방화벽 설정"
sudo ufw allow from "$ALLOWED_NETWORK" to any port 22 proto tcp
sudo ufw allow from "$ALLOWED_NETWORK" to any port "$PORT" proto tcp
sudo ufw --force enable

echo ""
echo "[10/13] systemd 서비스 파일 생성"
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
echo "[11/13] 서비스 등록 및 시작"
sudo systemctl daemon-reload
sudo systemctl enable "$APP_NAME"
sudo systemctl restart "$APP_NAME"

echo ""
echo "[12/13] 고정 IP 설정"
DEFAULT_INTERFACE="$(detect_network_interface)"
configure_static_ip "$DEFAULT_INTERFACE"

echo ""
echo "[13/13] 설치 상태 확인"
sleep 2

echo ""
echo "SSH 서비스 상태:"
sudo systemctl status ssh --no-pager || true

echo ""
echo "웹앱 서비스 상태:"
sudo systemctl status "$APP_NAME" --no-pager || true

echo ""
echo "IP 주소 확인:"
ip -4 addr show | grep -E "inet (${STATIC_IP}|127\.0\.0\.1)" || true

echo ""
echo "라우팅 확인:"
ip route || true

echo ""
echo "포트 확인:"
ss -tulnp | grep -E "(:22|:${PORT})" || true

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
echo "기본 로그인 정보:"
echo "ID: $DEFAULT_LOGIN_ID"
echo "PW: $DEFAULT_LOGIN_PASSWORD"
echo ""
echo "SSH 접속 허용:"
echo "$ALLOWED_NETWORK -> TCP 22"
echo ""
echo "웹앱 접속 허용:"
echo "$ALLOWED_NETWORK -> TCP $PORT"
echo ""
echo "고정 IP 설정:"
echo "$STATIC_IP_CIDR"
echo ""
echo "접속 주소:"
echo "http://$STATIC_IP:$PORT"
echo ""
echo "상태 확인:"
echo "sudo systemctl status $APP_NAME"
echo "sudo systemctl status ssh"
echo ""
echo "서버 재시작:"
echo "sudo systemctl restart $APP_NAME"
echo ""
echo "실시간 로그 확인:"
echo "journalctl -u $APP_NAME -f"
echo ""
echo "포트 확인:"
echo "ss -tulnp | grep -E '(:22|:$PORT)'"
echo ""
echo "방화벽 확인:"
echo "sudo ufw status numbered"
echo ""
echo "네트워크 설정 적용이 불완전하면 재부팅하세요:"
echo "sudo reboot"

# 정보부 업무 웹앱

학교 내부망에서 사용하는 통합 정보 관리 웹앱입니다. `IP 스캔`, `사이트 계정 관리`, `기기관리대장`을 한 화면에서 관리할 수 있도록 구성되어 있으며, 서버 진입점은 `server.py`입니다.

기본 실행 포트는 `8765`이고, 내부망 다른 PC에서도 접속할 수 있도록 `0.0.0.0:8765`로 바인딩됩니다.

## 주요 기능

### IP 스캔

- 기본 범위 `10.73.78.1 ~ 10.73.78.254` 스캔
- 사용자 지정 시작/끝 IP 스캔
- IP 오름차순 정렬, 검색, 필터, 상세 확인
- 장치명, MAC 주소, 응답 여부 확인
- Linux/Raspberry Pi 환경에서 `nbtscan` 기반 Windows PC명 조회 지원
- `nbtscan`으로 이름이 안 잡히면 `nmblookup -A` fallback으로 NetBIOS 이름 추가 조회
- 같은 IP에서 여러 MAC이 응답하면 `IP 충돌 의심`으로 표시
- IP별 저장 장치명을 수정해 `data/scan_device_names.json`에 유지
- IP 스캔 결과 CSV 전체 다운로드
- IP별 저장 장치명 CSV 양식 다운로드 및 업로드

### 사이트 계정 관리

- 사이트, 설명, URL, ID, PW, 비고 관리
- 검색, 추가, 수정, 삭제
- 체크박스 기반 단일 선택 및 전체 선택
- 선택 항목 일괄 삭제
- CSV 양식 다운로드
- 현재 저장된 전체 목록 CSV 다운로드
- CSV 업로드
- 업로드 시 기존 항목과 중복되는 `사이트 + ID`는 제외하고 신규 항목만 추가
- 대시보드 목록은 최신 수정순으로 정렬

### 기기관리대장

- 관리번호, 분류, 모델명, 제조사, 구입시기, 상태, 제품 이미지 URL 등 관리
- 검색, 분류 필터, 추가, 수정, 삭제
- 체크박스 기반 단일 선택 및 전체 선택
- 선택 항목 일괄 삭제
- CSV 양식 다운로드
- 현재 저장된 전체 목록 CSV 다운로드
- CSV 업로드
- 업로드 시 기존 `관리번호`와 중복되는 항목은 제외하고 신규 항목만 추가
- 구입시기 오름차순으로 정렬
- 기기관리대장 보고서 `xlsx` 다운로드
- 상태 옵션에 `불용 예정`, `불용 완료` 포함

### 화면과 폰트

- 프런트엔드는 `web/index.html`, `web/app.js`, `web/styles.css`로 구성됩니다.
- Paperlogy 폰트는 외부 CDN이 아니라 `web/assets/fonts/`의 로컬 파일을 사용합니다.
- 외부 폰트 CDN 차단 경고가 발생하지 않도록 구성되어 있습니다.

## Windows 실행 방법

### 실행 전 준비

Windows에 Python 3를 설치한 뒤, 프로젝트 폴더에서 필요한 패키지를 설치합니다.

```powershell
py -3 -m pip install -r requirements.txt
```

`python` 명령이 바로 동작하지 않는 PC에서는 `py -3`를 사용하면 됩니다.

### 바로 실행

`run-ip-scan-webapp.bat`를 실행합니다. 서버가 준비된 뒤 브라우저가 열립니다.

### 직접 실행

```powershell
py -3 server.py
```

실행 후 접속 주소는 다음과 같습니다.

- 로컬 PC: `http://127.0.0.1:8765`
- 같은 내부망 PC: `http://서버PC내부IP:8765`

필요하면 `add-firewall-rule-for-webapp.bat`로 Windows 방화벽 인바운드 규칙을 추가할 수 있습니다.

## Raspberry Pi/Linux 자동 설치

라즈베리파이 또는 Linux 서버에서는 `install_iim.sh`로 설치와 서비스 등록을 한 번에 처리할 수 있습니다.

```bash
chmod +x install_iim.sh
./install_iim.sh
```

`install_iim.sh`는 다음 작업을 수행합니다.

- `apt update`, `apt upgrade`
- `git`, `python3`, `python3-pip`, `python3-venv`, `ufw`, `curl`, `iputils-ping`, `arping`, `libcap2-bin`, `openssh-server`, `samba-common-bin`, `nbtscan` 설치
- `arping`에 IP 충돌 감지용 raw socket 권한 설정
- 기본 로그인용 `.env` 생성
- SSH 서버 자동 실행 등록 및 시작
- `server.py`와 `requirements.txt` 존재 여부 확인
- 프로젝트 폴더 안에 `venv` 가상환경 생성
- `requirements.txt` 기반 Python 패키지 설치
- UFW 방화벽에서 내부망 SSH 접속 허용
- 내부망 `10.73.78.0/24`에서 `8765` 포트 접속 허용
- 고정 IP `10.73.78.15/24`, 기본 게이트웨이 `10.73.78.254`, 기본 DNS `219.250.36.130`, 보조 DNS `8.8.8.8` 설정
- `iim.service` systemd 서비스 생성
- 부팅 시 자동 실행 등록
- 서비스 시작 및 상태 확인

설치 스크립트의 기본값은 다음과 같습니다.

```bash
APP_NAME="iim"
PORT="8765"
ALLOWED_NETWORK="10.73.78.0/24"
DEFAULT_LOGIN_ID="dcms"
DEFAULT_LOGIN_PASSWORD="dcms04935!"
STATIC_IP="10.73.78.15"
GATEWAY="10.73.78.254"
PRIMARY_DNS_SERVER="219.250.36.130"
SECONDARY_DNS_SERVER="8.8.8.8"
```

설치 후 접속 주소 예시는 다음과 같습니다.

```text
http://10.73.78.15:8765
```

운영 중 자주 쓰는 명령은 다음과 같습니다.

```bash
sudo systemctl status iim
sudo systemctl status ssh
sudo systemctl restart iim
journalctl -u iim -f
ss -tulnp | grep -E '(:22|:8765)'
sudo ufw status numbered
```

## 데이터 파일

앱 데이터는 런타임에 아래 JSON 파일로 저장됩니다.

- `data/site_accounts.json`
- `data/scan_device_names.json`
- `data/device_inventory.json`
- `data/device_inventory_events.json`

이 파일들은 실제 사이트 계정, 비밀번호, 자산 정보가 들어갈 수 있으므로 GitHub에 올리지 않습니다. 현재 저장소는 `.gitignore`에서 `data/*.json`을 제외하도록 구성되어 있습니다.

운영 데이터는 웹앱에서 직접 입력하거나 CSV 업로드로 채울 수 있습니다. 서버를 옮기거나 재설치할 때는 `data/` 폴더를 별도로 백업해야 합니다.

## CSV 사용 방식

사이트 계정 관리, 기기관리대장, IP 스캔 저장 장치명은 비슷한 흐름으로 사용할 수 있습니다.

1. `전체 다운`으로 현재 저장된 내용을 CSV로 내려받습니다.
2. 내려받은 CSV를 엑셀 등에서 수정하거나 새 행을 추가합니다.
3. `CSV 업로드`로 다시 올립니다.
4. 이미 존재하는 항목은 중복으로 보고 제외하며, 새 항목만 추가됩니다.

중복 판단 기준은 다음과 같습니다.

- 사이트 계정 관리: `사이트 + ID`
- 기기관리대장: `관리번호`
- IP 스캔 저장 장치명: `IP`

## 폴더 구조

- `server.py`: HTTP 서버 진입점
- `scanner.py`: 네트워크 스캔 로직
- `site_accounts.py`: 사이트 계정 저장소와 CSV 처리
- `device_inventory.py`: 기기관리대장 저장소, CSV 처리, 보고서 생성
- `web/`: 프런트엔드 정적 파일
- `web/assets/fonts/`: 로컬 Paperlogy 폰트
- `data/`: 런타임 데이터 저장 폴더
- `tests/`: 백엔드와 API 테스트
- `docs/`: 설계, 운영, 참고 문서
- `install_iim.sh`: Raspberry Pi/Linux 자동 설치 스크립트

## 검증 명령

코드 변경 후에는 아래 명령으로 기본 검증을 수행합니다.

```powershell
python -m py_compile server.py site_accounts.py device_inventory.py scanner.py
node --check .\web\app.js
python -m unittest discover -s tests -p "test_*.py"
```

## 운영 주의사항

- 학교 내부망 사용을 전제로 합니다.
- 사이트 계정과 기기관리대장 데이터는 민감 정보로 취급해야 합니다.
- 운영 데이터가 저장되는 `data/` 폴더는 별도로 백업해야 합니다.
- 실제 장치명, MAC, 응답 여부는 네트워크 환경과 방화벽 정책에 따라 다르게 보일 수 있습니다.
- 현재 저장 방식은 로컬 JSON 기반이므로, 서버 PC와 라즈베리파이 접근 권한을 제한해야 합니다.

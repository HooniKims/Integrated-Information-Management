# 정보부 업무 웹앱

학교 내부망에서 사용하는 통합 관리 웹앱입니다. 현재 구성은 `IP 스캔`, `사이트 계정 관리`, `기기관리대장` 세 화면으로 이루어져 있습니다.

## 주요 기능

- 기본 범위 `10.73.78.2 ~ 10.73.78.254` IP 스캔
- 사용자 지정 시작/끝 IP 스캔
- 스캔 결과 IP 오름차순 정렬, 필터, 검색, 상세 확인
- 사이트, 설명, URL, ID, PW, 비고 관리
- 기기관리대장 검색, 필터, 추가, 수정, 삭제
- 기기관리대장 보고서 `xlsx` 다운로드
- 내부망 다른 PC에서 접속 가능하도록 `0.0.0.0:8765` 바인딩

## 실행 방법

### Windows 바로 실행

`run-ip-scan-webapp.bat` 를 실행합니다.

### 직접 실행

```powershell
python server.py
```

실행 후 브라우저 접속 주소:

- 로컬 PC: `http://127.0.0.1:8765`
- 같은 내부망 PC: `http://서버PC내부IP:8765`

필요하면 `add-firewall-rule-for-webapp.bat` 로 Windows 방화벽 인바운드 규칙을 추가할 수 있습니다.

## 데이터 파일

앱 데이터는 아래 JSON 파일에 저장됩니다.

- `data/site_accounts.json`
- `data/device_inventory.json`
- `data/device_inventory_events.json`

초기 업로드 상태는 빈 데이터 파일 기준입니다. 운영 데이터는 웹앱에서 직접 입력하거나 CSV 가져오기로 채우면 됩니다.

## 폴더 구조

- `web/`: 프런트엔드 정적 파일
- `data/`: 런타임 데이터 저장 파일
- `server.py`: HTTP 서버 진입점
- `scanner.py`: 네트워크 스캔 로직
- `site_accounts.py`: 사이트 계정 저장소
- `device_inventory.py`: 기기관리대장 저장소 및 보고서 생성
- `docs/research/`: 참고용 조사 문서

## 비고

- 학교 내부망 사용을 전제로 합니다.
- 실제 장치명, MAC, 응답 여부는 네트워크 환경과 방화벽 정책에 따라 다르게 보일 수 있습니다.
- 현재 저장 방식은 로컬 JSON 기반이므로, 서버 PC 접근 권한 관리가 필요합니다.

# 정보화기기대장 비교 분석 메모

작성일: 2026-04-19

## 목적

학교 내부 정보화기기대장을 웹앱으로 옮길 때, 실제 학교 운영과 유지보수 흐름에 맞으면서도 지나치게 복잡하지 않은 공통 구조를 선택하기 위한 비교 메모다.

## 국내 기준에서 반복된 요소

### 전북특별자치도교육청 학교정보화지원시스템

- 공식 소개 자료에서 학교 정보화업무 지원, 학생 스마트기기 현황 관리, 원클릭 AS, 정보화기기 관리 기능을 함께 제공한다고 설명한다.
- 관리 대상 예시는 `데스크톱, 노트북, 스마트패드, 네트워크장비, 무선 AP`까지 포함한다.
- 학교관리자 역할에도 `학교 AS처리 현황 모니터링`, `학교 스마트기기 현황(보유, 전출·입, 수리/교체 등) 관리`가 포함된다.

참고:

- https://it.jbe.go.kr/upload_data/board_data/TEMP/171152847878822.pdf
- https://it.jbe.go.kr/index.jbe?menuCd=DOM_000000105005000000

### 전북특별자치도교육청 예산·교체주기 자료

- 학교 정보화기기는 `컴퓨터, 노트북, 무선 AP, 온라인 수업 기자재` 등으로 잡고 있다.
- 교원용 컴퓨터는 `교체주기 6년`, 교육용 컴퓨터는 `내용연수 6년, 교체주기 7년` 기준이 제시된다.

참고:

- https://it.jbe.go.kr/upload_data/board_data/TEMP/168128649450497.pdf

### 경기도교육청 통합 유지관리 방향

- 경기도교육청은 보도자료와 매뉴얼 게시를 통해 `통합 유지관리 시스템`, `통합 콜센터`, `지역거점센터`, `스마트기기 관리 방안 및 유지관리 서비스 매뉴얼`을 운영한다.
- 즉, 현장 요구는 단순 대장 보관이 아니라 `보유 현황 + 장애 대응 + 유지관리 이력`까지 한 흐름으로 보는 쪽에 가깝다.

참고:

- https://www.goe.go.kr/goe/na/ntt/selectNttInfo.do?mi=10102&nttSn=1041915&searchAt1=&searchValue1=
- https://www.goe.go.kr/goe/na/ntt/selectNttInfo.do?mi=10961&nttSn=1049464

## 글로벌 ITAM 제품에서 반복된 요소

### Microsoft Intune

- 장치 상세 화면에서 `serial number`, `primary user`, `device category`, `ownership`, 하드웨어 세부정보를 본다.
- 별도 문서에서 `primary user`를 장치와 연결된 핵심 사용자 속성으로 정의한다.

참고:

- https://learn.microsoft.com/en-us/intune/device-management/inventory-and-status/device-details
- https://learn.microsoft.com/en-us/intune/device-management/inventory-and-status/find-primary-user

### ServiceNow Hardware Asset Management

- 자산 레코드에서 `Serial number`, `Location`, `Department`, `Assigned`, `Installed`, `Substate` 같은 운영 필드를 핵심으로 다룬다.
- 특히 상태는 단순 정상/고장보다 `state + substate` 조합으로 관리하는 방향이 보인다.

참고:

- https://www.servicenow.com/docs/r/washingtondc/it-asset-management/hardware-asset-management/asset-record-fields.html

### Atlassian Assets

- ITAM 속성 예시로 `Asset tag`, `Serial number`, `Maintenance contract`, `Purchase date`, `Refresh date`, `Ownership type`, `Device type`, `Operational status`를 제시한다.
- 즉, 자산 식별자와 구매·계약·교체주기 필드가 반복된다.

참고:

- https://support.atlassian.com/assets/docs/creating-attributes-for-it-asset-management-itam/

### Snipe-IT

- 자산이 누구에게 배정되었는지, 물리적 위치가 어디인지, 현재 배치·대기·수리·보관 상태인지, 전체 이력이 어떤지 빠르게 보는 구조를 강조한다.
- 가져오기/내보내기, 감사, 유지보수 이력도 핵심 기능으로 잡고 있다.

참고:

- https://snipeitapp.com/product

## 비교 결과

국내 학교 운영과 글로벌 ITAM 도구를 함께 보면 공통 핵심은 다음이다.

- 고유 식별자: 관리번호 또는 자산 태그
- 장비 식별 정보: 기기구분, 기기명, 제조사, 모델명, 시리얼번호
- 배정 정보: 사용자, 부서
- 위치 정보: 설치위치
- 네트워크 정보: IP, MAC
- 수명주기 정보: 상태, 도입일자, 보증만료일, 최근점검일
- 운영 메모: 유지보수업체, 비고
- 이력: 등록, 수정, 가져오기, 삭제 같은 이벤트 로그

## 이 프로젝트에 적용한 최종 구조

이번 웹앱에는 `단일 자산 테이블 + 이벤트 로그`를 최종 선택했다.

선택 이유:

- 학교 현장에서 기존 엑셀 대장과 바로 매핑하기 쉽다.
- 관리번호 기준으로 CSV 가져오기와 갱신이 단순하다.
- 사용자, 위치, 상태, 점검 여부를 한 화면에서 바로 찾을 수 있다.
- 향후 IP 스캔 결과와 `IP`, `MAC`, `장치명`을 연결하기 쉽다.
- 복잡한 자산 마스터/계약/발주 구조를 초기부터 넣지 않아도 유지가 쉽다.

## 현재 구현된 핵심 필드

- 관리번호
- 기기구분
- 기기명
- 제조사
- 모델명
- 시리얼번호
- 사용자
- 부서
- 설치위치
- 상태
- 도입일자
- IP
- MAC
- 최근점검일
- 유지보수업체
- 보증만료일
- 비고

## 자동 계산 필드

- 사용연수
- 점검 필요 여부
- 위치 미확인 여부
- 사용자 미지정 여부

## 이번 버전에서 일부러 뺀 것

- 구매금액, 감가상각, 회계 처리
- 모델 마스터와 자산 인스턴스 분리
- 복수 창고/대여 반납 워크플로우
- 자산 승인 프로세스

이 항목들은 학교 실무의 첫 운영 부담을 높일 가능성이 커서 1차 버전에서는 제외했다.

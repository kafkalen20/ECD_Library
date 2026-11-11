---
owner: park-jihee
created: 2026-11-11
updated: 2026-11-11
---
# 프로젝트 개요 — ECD_Library

## 무슨 시스템
에코두비즈 **내부 서드파티 Odoo 모듈 저장소**. 고객사 프로젝트 자체가 아니라, Odoo 프로젝트에 **공통 적용**하거나 **필요한 고객사에만 골라 설치**해 바로 쓰는 모듈 모음이다. (근거: 담당자 설명 2026-11-11, 루트 `README.md`)

- 쓰는 방식 예: 문자 서비스를 쓰려는 고객사에만 `barobill` + `barobill_sms` 설치.
- **Odoo 버전별 폴더**: 지금은 `19.0/`만. 앞으로 Odoo 버전에 맞춰 `20.0/` 등 폴더가 늘어난다. 각 버전 폴더가 그 버전의 `addons_path` 단위.
- 현재 대상: **19.0 Enterprise** (`edb_*` 라이선스 `OEEL-1`, `edb_helpdesk`가 EE 전용 `helpdesk`에 의존)
- 모듈 지도 → [modules.md](modules.md)
- 기능 영역: 바로빌 전자문서·메시징(`barobill_*`) · 회사 공통/보안(`edb_*`) · 고객사 공통 고객센터 커스터마이징(`edb_helpdesk`) · 전역 검색(`global_search`)
- 예정: 소셜 로그인 `edb_auth` + `edb_auth_<provider>` (README 「인증·로그인」)

## 핵심 요구사항 (코드·README에서 확인되는 것)
- 각 기능 영역은 독립 모듈 — `depends` 로 선언하지 않는 한 서로 독립. 필요한 것만 골라 설치할 수 있어야 한다.
- 특정 고객사에 묶이지 않는다 — 고객사별 값은 코드가 아니라 설치 후 설정 화면에서.
- 어느 프로젝트에나 얹을 수 있게 표준 Odoo(`base`, `web`) 위주 의존.
- 바로빌 5개 채널(SMS·FAX·알림톡·세금계산서·현금영수증)은 **하나의 바로빌 계정**을 공유.
- 비밀값은 소스에 커밋하지 않고 설치 후 설정 화면에서 입력.

## 외부 의존성
- Python: `zeep`(바로빌 전체 — SOAP), `pytz`(fax·tax_invoice·cash_receipt). 각 `__manifest__.py` `external_dependencies`에 선언.
- 외부 서비스: 바로빌 SOAP API(테스트/운영 엔드포인트), 바로빌 FTP(FAX).

## 고객사 적용·유지보수
- 적용: 필요한 **모듈 폴더만 고객사 프로젝트 레포로 복사** (submodule·공용 addons_path 아님) → [적용 절차](../guides/deploy.md)
- 고객사별 설치 현황은 별도로 관리하지 않음 (2026-11-11 기준).
- 이전 Odoo 버전 폴더는 **쓰는 고객사가 있으면 유지보수, 없으면 중단**.

## 설계 방침
- 폴더 중첩 대신 **접두어 네이밍**으로 그룹, **베이스 + 채널** 패턴 → [conventions.md](conventions.md)
- 바로빌: 모델 = 업무 로직, `controllers/` 일반 클래스 = SOAP 호출만 → 루트 `README.md` 「바로빌 아키텍처」

## 아직 모르는 것
- 없음 (2026-11-11 기준). 사내 운영 인스턴스 없음 — 모든 모듈은 고객사 프로젝트에 복사해서만 쓰인다.

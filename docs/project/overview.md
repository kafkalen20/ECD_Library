---
owner: parkbohee
created: 2026-11-11
updated: 2026-11-11
---
# 프로젝트 개요 — ECD_Library

## 무슨 시스템
에코두비즈 **사내 공용 Odoo 19 애드온 저장소**. 고객사 프로젝트가 아니라, 여러 프로젝트에서 공통으로 가져다 쓰는 내부 모듈 모음이다. (근거: 루트 `README.md`)

- 대상 Odoo: **19.0 Enterprise** (`edb_*` 라이선스 `OEEL-1`, `edb_helpdesk`가 EE 전용 `helpdesk`에 의존)
- 모듈 위치: `19.0/` 아래 평평하게 — 모듈 지도 → [modules.md](modules.md)
- 기능 영역: 바로빌 전자문서·메시징(`barobill_*`) · 회사 공통/보안(`edb_*`) · 고객센터(`edb_helpdesk`) · 전역 검색(`global_search`)
- 예정: 소셜 로그인 `edb_auth` + `edb_auth_<provider>` (README 「인증·로그인」)

## 핵심 요구사항 (코드·README에서 확인되는 것)
- 각 기능 영역은 독립 모듈 — `depends` 로 선언하지 않는 한 서로 독립.
- 어느 프로젝트에나 얹을 수 있게 표준 Odoo(`base`, `web`) 위주 의존.
- 바로빌 5개 채널(SMS·FAX·알림톡·세금계산서·현금영수증)은 **하나의 바로빌 계정**을 공유.
- 비밀값은 소스에 커밋하지 않고 설치 후 설정 화면에서 입력.

## 외부 의존성
- Python: `zeep`(바로빌 전체 — SOAP), `pytz`(fax·tax_invoice·cash_receipt). 각 `__manifest__.py` `external_dependencies`에 선언.
- 외부 서비스: 바로빌 SOAP API(테스트/운영 엔드포인트), 바로빌 FTP(FAX).

## 설계 방침
- 폴더 중첩 대신 **접두어 네이밍**으로 그룹, **베이스 + 채널** 패턴 → [conventions.md](conventions.md)
- 바로빌: 모델 = 업무 로직, `controllers/` 일반 클래스 = SOAP 호출만 → 루트 `README.md` 「바로빌 아키텍처」

## 아직 모르는 것
- [❓확인 필요: 이 모듈들을 실제로 쓰는 프로젝트(고객사 레포) 목록과 반영 방식 — submodule? 복사? addons_path 추가?]
- [❓확인 필요: 사내 운영 인스턴스(예: 고객센터·보안 모듈을 실제로 돌리는 서버)가 있는지]

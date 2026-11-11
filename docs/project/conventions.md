---
owner: parkbohee
created: 2026-11-11
updated: 2026-11-11
---
# 코딩·네이밍·커밋 규칙 (코드에서 관찰된 것)

> 모듈 배치·네이밍·베이스+채널 패턴의 **원본은 루트 `README.md` 「모듈 네이밍·그룹 규칙」** — 여기선 요점과 코드에서 관찰한 것만.

## 배치·네이밍
- 모든 모듈은 `19.0/` 바로 아래 평평하게. 그룹 폴더 금지 (addons_path 비재귀).
- 접두어로 그룹: `barobill_<채널>`, `edb_<기능>`, `edb_auth_<provider>`. 범용 유틸은 접두어 없이(`global_search`).
- 베이스 + 채널: 공통은 베이스 모듈, 변형은 베이스에 `depends`. 베이스만 `application: True`.
- 모듈 버전 형식: `19.0.x.y.z`.

## 모델·뷰
- 모델 `_name`: 모듈 접두어 기반 점 표기 (`barobill.fax`, `barobill.fax.result`, `edb.device.access`, `global.search.config`).
- 로그 모델은 `<모델>.result` — append-only, `base.group_user`에 읽기/생성만 (`security/ir.model.access.csv`).
- 뷰 ID: Odoo 표준 `<model>_view_<type>` (예: `barobill_alimtalk_result_view_list`), 설정 뷰는 `res_config_settings_view_form[_<모듈>]`.
- 메뉴 ID: `<모듈>_menu_root` / `<모듈>_<이름>_menu` / `<모듈>_category` 혼재. [❓확인 필요: 메뉴 ID 규칙을 하나로 통일할지]
- cron 이름: `[<영역>] <설명>` (예: `[Barobill FAX] 진행 중 발송 상태 폴링`).
- UI 문자열·필드 라벨·docstring·오류 메시지는 **한국어**.

## 바로빌 전용
- SOAP 호출은 `controllers/` 일반 클래스(`BarobillController` 상속)의 `_메서드`로만. 모델은 `_get_barobill_api()`로 받아 씀.
- 설정 키: 공통 `barobill.mode|certkey|corpnum|id`, 채널별 `barobill_<채널>.<mode>.server`.
- 오류: 음수 5자리 문자열 → `_get_err_string()`로 메시지 조회 후 `error_message` 저장.

## 커밋
- 관찰된 형식: `[MOD] <모듈>: <요약>` (예: `[MOD] edb_security: 보안 모니터링 통합 ...`). 이력이 짧아 다른 태그는 미확인.
- 브랜치·커밋 규약 → [gitflow](../guides/gitflow.md), PR 본문 → [pr-rules](../guides/pr-rules.md).

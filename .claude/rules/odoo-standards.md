---
paths:
  - "*.0/**/*.py"
---
# Odoo 모델 코딩 규칙

- 모델: `_inherit`(코어 확장) 또는 `_name = '<module>.xxx'`
- 모델 이름은 단수형. wizard(transient) `<기준모델>.<action>`, 리포트 모델 `<기준모델>.report.<action>`
- 메서드 이름: `_compute_<필드>` · `_inverse_<필드>` · `_search_<필드>` · `_default_<필드>` · `_selection_<필드>` · `_onchange_<필드>` · `_check_<제약>` · 버튼 액션 `action_<무엇>` (`self.ensure_one()`로 시작)
- 속성·메서드 순서: private 속성(`_name` 등) → default 메서드 → 필드 → SQL 제약·인덱스 → compute·inverse·search(필드 순서대로) → selection → constraint·onchange → CRUD 오버라이드 → action → 기타 business
- public 메서드는 docstring 필수
- 핵심 비즈니스 로직(가격·세금·재고평가)은 코어를 바꾸지 않는다 (Method B: Core Extension)
- 뷰 arch에 이모지(non-BMP) 넣지 않는다 (모듈 업데이트 시 xml_translate 파싱 오류)

## XML ID·파일 네이밍 (Odoo 공식 코딩 가이드라인 — 새 코드부터 적용)
> 출처: https://www.odoo.com/documentation/19.0/contributing/development/coding_guidelines.html
> **이미 올라간 모듈의 기존 XML ID는 바꾸지 않는다** — 설치된 DB에서 레코드가 삭제·재생성되어 참조가 깨진다.
> `<model_name>` = 모델 이름의 `.`을 `_`로 바꾼 것 (예: `barobill.fax.result` → `barobill_fax_result`).

| 대상 | 규칙 | 예 |
|---|---|---|
| 메뉴 | `<model_name>_menu`, 하위 메뉴 `<model_name>_menu_<do_stuff>` | `barobill_fax_menu` |
| 뷰 | `<model_name>_view_<view_type>` (`form`·`list`·`kanban`·`search` …) | `barobill_fax_view_form` |
| 액션 | 대표 액션 `<model_name>_action`, 여러 개면 `<model_name>_action_<detail>` | `barobill_fax_action` |
| 특정 뷰 window action | `<model_name>_action_view_<view_type>` | |
| 그룹 | `<module_name>_group_<group_name>` (`user`·`manager` 등) | `barobill_group_manager` |
| 레코드 규칙 | `<model_name>_rule_<concerned_group>` (`user`·`public`·`company` 등) | |
| 상속 뷰 | **원본과 같은 XML ID** 사용(모듈 접두가 달라 충돌 없음), `name`에 `.inherit.<details>` 접미. 새 primary 뷰는 접미 불필요 | `edb_helpdesk.helpdesk_ticket_view_form` |
- 레코드 `name`은 XML ID의 `_`를 `.`으로 바꾼 것과 같게.

| 파일 | 규칙 |
|---|---|
| 모델 | 주 모델 이름으로 1파일, 상속 모델도 각자 1파일 |
| 뷰 | `<model>_views.xml`, 포털/웹 템플릿 `<model>_templates.xml` |
| 보안 | `ir.model.access.csv`, 그룹 `<module>_groups.xml`, 레코드 규칙 `<model>_security.xml` |
| 데이터 | `<main_model>_data.xml` / `_demo.xml` |
| 컨트롤러 | `controllers/<module_name>.py` (`main.py`는 옛 방식) |
| wizard | `wizard/<transient>.py` + `wizard/<transient>_views.xml` |
| 리포트 | 인쇄용 `<report>_reports.xml` + `<report>_templates.xml` |
- 파일명 문자는 `[a-z0-9_]`만.

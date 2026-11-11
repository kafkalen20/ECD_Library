---
paths:
  - "19.0/**/*.py"
---
# Odoo 모델 코딩 규칙

- 모델: `_inherit`(코어 확장) 또는 `_name = '<module>.xxx'`
- 메서드 순서: default → compute → constraint → CRUD → action → business
- public 메서드는 docstring 필수
- 핵심 비즈니스 로직(가격·세금·재고평가)은 코어를 바꾸지 않는다 (Method B: Core Extension)
- 뷰 arch에 이모지(non-BMP) 넣지 않는다 (모듈 업데이트 시 xml_translate 파싱 오류)

## 뷰/XML 네이밍
- 뷰 ID: `<model>_view_<type>` (Odoo 표준 — 기존 코드 기준, 예: `barobill_fax_result_view_list`)
- 메뉴 XML ID: 기존 코드 혼재(`<module>_menu_root`·`<module>_<name>_menu`) — 새 메뉴는 같은 모듈 기존 패턴을 따른다

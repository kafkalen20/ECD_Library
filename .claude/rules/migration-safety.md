---
paths:
  - "scripts/**/*.py"
  - "migration/**/*.py"
---
# 데이터 정정 · 마이그레이션 안전 규칙

- 실행 전 반드시 **DRY-RUN** 결과를 확인한다.
- 운영 DB는 **백업 후에만** 적용한다.
- **데이터 삭제/덮어쓰기 금지** — 되돌릴 SQL(롤백셋)과 세트로만.
- 변경은 진실원(source of truth)을 건드리지 말고 파생값만; 진실원 수정이 불가피하면 별도 ADR/issue 기록.
- 정정 후 즉시 재조회로 검증한다(AFTER 탐지 0 확인).

## 함정
- odoo-bin shell 파이프 실행은 **종료 시 커밋**된다 → 스크립트 내부 `cr.rollback()`도 운영에 반영될 수 있음.
  운영 DRY는 psql `BEGIN..ROLLBACK`/savepoint를 쓰거나, DRY 직후 재조회로 검증할 것.

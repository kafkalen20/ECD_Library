---
owner: park-jihee
created: 2026-11-11
updated: 2026-11-11
---
# Git 브랜치·커밋 가이드

> 이 프로젝트의 **브랜치·커밋 규칙**(프로젝트마다 다름 — 자유롭게 고친다).
> **PR 본문·티켓 표기 등 회사 공통 규칙은 `docs/guides/pr-rules.md`**(kit 동기화 파일, 직접 수정 금지).

## 브랜치
- 기본 브랜치 `main`은 **PR-only** — 직접 커밋·push·force push 금지.
- 작업은 `feature/…`·`fix/…` 브랜치에서 → PR → 리뷰 → 머지.

## 커밋 메시지 — Odoo 공식 규약
> 출처: https://www.odoo.com/documentation/19.0/contributing/development/git_guidelines.html

```
[TAG] <모듈 기술명>: <짧은 요약 — 50자 안팎, 변경 이유가 드러나게>

<본문 — 무엇보다 **왜** 바꿨는지. 고른 방식·영향 범위>

#<GitHub issue 번호>
```
- 모듈은 **기술명**(`barobill_fax`, 표시 이름 X). 여러 모듈이면 나열하거나 `various`. 가능하면 한 커밋 = 한 모듈.
- `bugfix` 같은 한 단어 요약 금지.

| 태그 | 언제 |
|---|---|
| `[ADD]` | 새 모듈 추가 |
| `[IMP]` | 기능 개선·추가 (문서만 바꿀 때도 이것) |
| `[FIX]` | 버그 수정 |
| `[REF]` | 기능을 크게 다시 작성 |
| `[REM]` | 죽은 코드·뷰·모듈 삭제 |
| `[REV]` | 커밋 되돌리기 |
| `[MOV]` | 내용 변경 없이 파일·코드 이동 |
| `[MERGE]` | 여러 커밋에 걸친 기능의 병합 커밋 |
| `[I18N]` | 번역 파일 |
| `[PERF]` | 성능 개선 |
| `[CLN]` | 코드 정리 |
| `[LINT]` | 린트 |
| `[REL]` | 릴리스 커밋 |
- 기존 `[MOD]` 커밋은 그대로 둔다(새 커밋부터 적용).
- GitHub issue는 `#N`, 헬프데스크 티켓은 `#` 없이 `티켓 00124` → `docs/guides/pr-rules.md`.

## PR
- 본문 작성법·CI 강제 규칙 → **`docs/guides/pr-rules.md`**
- 관련 issue는 `## 관련`에 `Closes #N`.

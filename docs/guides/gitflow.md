---
owner: parkbohee
created: 2026-11-11
updated: 2026-11-11
---
# Git 브랜치·커밋 가이드

> 이 프로젝트의 **브랜치·커밋 규칙**(프로젝트마다 다름 — 자유롭게 고친다).
> **PR 본문·티켓 표기 등 회사 공통 규칙은 `docs/guides/pr-rules.md`**(kit 동기화 파일, 직접 수정 금지).

## 브랜치
- 기본 브랜치 `main`은 **PR-only** — 직접 커밋·push·force push 금지.
- 작업은 `feature/…`·`fix/…` 브랜치에서 → PR → 리뷰 → 머지.

## 커밋 메시지
- 관찰된 형식: `[MOD] <모듈>: <요약>` (한국어 요약). 문서만 바꿀 때 `[DOCS] ...`.
- [❓확인 필요: `[ADD]`·`[FIX]` 등 다른 태그 목록]
- 헬프데스크 티켓 표기는 `docs/guides/pr-rules.md` 를 따른다(`#` 금지).

## PR
- 본문 작성법·CI 강제 규칙 → **`docs/guides/pr-rules.md`**

# 팀 자료실 목차 (docs)

> 문서를 추가하면 여기에 `[제목](경로) — 한 줄 요약` 한 줄을 등록한다.
> AI/사람이 자료실 전체를 뒤지지 않고 이 목차만 보고 바로 찾아가게 하는 핵심.

**먼저 볼 것:** [현황 — 지금 할 일](status.md) · [일정·범위·담당](project/schedule-scope.md) · [요구사항 추적표](requirements/trace.md)

## 폴더 안내 (필요하면 나중에 세분화)
- `decisions/` — 설계 결정 이유 (ADR, 쌓임 — 고치지 말고 추가)
- `issues/` — 장애·운영 정정 기록 (쌓임)
- `guides/` — 방법·절차 (배포·접속 등, 살아있는 문서)
- `project/` — 프로젝트 구조·규칙 · 모듈 개요(compass) · 고객사 특이사항 (살아있는 문서, 민감정보 X)
- `design/` — 큰 기능 설계 스펙 + 목업 (구현 전 "앞으로 이렇게 만들자")
- `handoff/` — 다른 세션/사람이 이어받을 미완 작업 인계 (끝나면 삭제)
- `requirements/` — 요구사항 추적표 `trace.md` (번호 | 요구 | 근거 | 만든 것 | 시험 | PR | 상태) + 긴 요구의 상세
- `delivery/` — 사람·외부에 보내는 전달 문서·메일 초안·수정 요청 (`## 가정한 것` 필수)
- `_templates/` — 빈 서식
> standards·domain·analysis 등은 폴더로 안 만들고 project/ 안 파일로 시작. 파일이 4~5개 넘게 쌓이면 그때 폴더로 승격.

## 결정 (decisions)
- [0001. 설계 결정을 ADR로 기록한다](decisions/0001-record-architecture-decisions.md) — 왜/기각한 대안을 남기는 규칙
<!-- [0002. 제목](decisions/0002-xxx.md) — 한 줄 -->

## 장애·정정 (issues)
<!-- [yyyy-mm-dd 제목](issues/yyyy-mm-dd-xxx.md) — 한 줄 -->

## 설계 (design)
<!-- [기능명 설계](design/기능명.md) — 한 줄 (status) -->

## 가이드 (guides)
- [PR 작성 규칙](guides/pr-rules.md) — PR 5섹션(한글 헤더)·티켓 표기, CI 강제 (kit 동기화 — 직접 수정 금지)
- [Git 브랜치·커밋 가이드](guides/gitflow.md) — 이 프로젝트의 브랜치 전략·커밋 규약
- [문서 작성 절차](guides/write-doc.md) — 유형 판단→폴더·파일명→템플릿→목차→검증 (kit 동기화 — 직접 수정 금지)
- [고객사 적용 절차](guides/deploy.md) — 필요한 모듈만 고객사 레포로 복사 → 고객사 배포 절차로 반영 (사람이 실행)
- [로컬 개발 환경](guides/dev-setup.md) — `.odoorc`·addons_path(`19.0`)·실행/테스트 명령
- [요구 추적표 다시 맞추기](guides/req-trace.md) — 요구 번호로 커밋·PR·시험 검색 → 표 갱신 (kit 동기화 — 직접 수정 금지)
- [완료 처리 절차](guides/task-done.md) — "끝났어" → 갱신할 곳 목록·빠진 곳 보고 (kit 동기화 — 직접 수정 금지)

## 요구사항 (requirements)
- [요구사항 추적표](requirements/trace.md) — 요구 번호별 근거·만든 것·시험·PR·상태
<!-- [<번호> 제목](requirements/<번호>-제목.md) — 한 줄 -->

## 프로젝트/모듈 지식
- [일정·범위·담당](project/schedule-scope.md) — 자주 바뀌는 사실의 유일한 원본 (다른 문서는 링크만)
- [프로젝트 개요](project/overview.md) — 사내 공용 Odoo 19 EE 애드온 저장소, 의존성·설계 방침
- [모듈 지도](project/modules.md) — 10개 모듈 역할·depends·의존 관계
- [코딩·네이밍·커밋 규칙](project/conventions.md) — 플랫 배치·접두어·바로빌 컨트롤러 규칙 (원본은 루트 README)

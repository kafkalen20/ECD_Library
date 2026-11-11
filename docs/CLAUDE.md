# docs 작성 규칙

> 이 폴더의 파일을 만질 때 자동으로 읽힌다(nested CLAUDE.md). 문서를 규칙대로 쓰게 유도.
> **언제/어디에 남길지는 `ROUTING.md`가 유일 기준.** 헷갈리면 거기부터 본다.

## 어디에 무엇을
- 장애·운영 정정·작업 사고 → `issues/`, `_templates/issue.md` 복사
- 설계 결정 → `decisions/`, `_templates/decision.md` 복사, **번호는 마지막+1**
- 방법·절차 → `guides/`, `_templates/guide.md` 복사
- 프로젝트/모듈/고객사 지식 → `project/` (모듈 개요는 `_templates/project.md` 복사, 25~35줄)
- 큰 기능 설계(구현 전) → `design/`, `_templates/design.md` 복사
- 다른 세션 인계 → `handoff/`, `_templates/handoff.md` 복사 (끝나면 삭제)
- 사람·외부에 보내는 문서 → `delivery/`, `_templates/delivery.md` 복사 (`## 가정한 것` 필수)
- 요구사항 → `requirements/trace.md` 한 줄 (번호 형식은 `id-format:`, 길면 `_templates/requirement.md` 로 상세) — 커밋·PR 제목·시험 이름에 번호
- 지금 할 일 → `status.md` 한 파일 (20줄 권장·40줄 차단, 경과 X) / 일정·범위·담당 → `project/schedule-scope.md` 한 파일 (다른 문서는 링크만)

## 파일명·꼬리표
- 파일명: `날짜-무엇-어디.md` (decisions는 `번호-제목.md`) — grep 되게 키워드 포함
- 맨 위 꼬리표: 살아있는 문서 = `owner·created·updated`, 쌓이는 문서 = `date·keywords·status`
- **모든 날짜는 년월일 `YYYY-MM-DD`** (꼬리표·변경 이력·파일명 전부). 월일만 쓰지 않는다.

## 추가하면
- `docs/README.md` 목차에 `[제목](경로) — 한 줄` 등록

## 성격별 수정 규칙
- 살아있는 문서(project·guides·design): 코드/상태 바뀌면 같이 갱신, `updated` 날짜·변경이력 한 줄
- 쌓이는 문서(decisions·issues): **고치지 말고 새로 추가** (supersede)
- 임시 문서(handoff): 작업 끝나면 삭제/보관
- 일이 끝나면 `guides/task-done.md` 목록대로 여러 곳을 같이 갱신

## 금지
- 비번·키·서버IP를 문서에 넣지 않는다 (방법만, 값은 비밀번호 관리자)

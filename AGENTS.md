# AGENTS.md

> **팀 규칙의 원본.** 모든 AI 코딩 에이전트(Claude / Codex / Gemini / Cursor 등)와 사람이 같은 내용을 읽는다.
> `CLAUDE.md` 등 도구별 진입 파일은 이 파일을 불러오고, 그 도구 전용 내용만 덧붙인다(복붙 금지).
> **얇게** 유지한다(목표 80줄 이내). 실제 지식은 `docs/`에 있고, 여기서는 위치만 가리킨다.

Respond in Korean.

## What this is
에코두비즈 **사내 공용 Odoo 19 (EE) 애드온 저장소**. 바로빌 전자문서·메시징, 회사 공통 UX, 보안 감사, 고객센터, 전역 검색 모듈을 모아 여러 프로젝트에서 가져다 쓴다. (개요 → `docs/project/overview.md`)

## 먼저 읽을 것 (작업 시작 전)
1. 이 파일 전체 — 특히 `숨은 결정 ★`·`사람 확인이 필요한 곳`
2. `docs/status.md` — 지금 할 일 (일정·범위·담당은 `docs/project/schedule-scope.md`)
3. `docs/README.md` — 자료실 목차 (여기서 필요한 문서로 찾아간다)
4. `docs/handoff/` — 이어받을 미완 작업이 있는지
5. 바꾸려는 영역의 `docs/decisions/` (아키텍처·모듈구조·배포를 건드릴 때는 필수)
6. 바꾸려는 모듈의 `19.0/<모듈>/README.md`

## Repository Layout
- `19.0/` — 커스텀 모듈, **평평하게(flat)** 배치 (모듈 지도 → `docs/project/modules.md`)
- `README.md` — 저장소 개요·모듈 네이밍 규칙·바로빌 아키텍처 (사람용 원본)
- `docs/` — 팀 자료실 (목차 → `docs/README.md`)
- `scripts/` — 문서 검사(`check_docs.py`)·데이터 정정 스크립트 (문서와 섞지 않음)

## Running & Testing
- 실행: `odoo-bin -c .odoorc -d <db> -u <module>` (`.odoorc`는 개인 로컬 — 커밋 안 함)
- 테스트: `odoo-bin -c .odoorc -d <db> --test-enable --test-tags /<module> --stop-after-init`
- 자세히 → `docs/guides/dev-setup.md`

## 숨은 결정 ★ (버그 같은데 일부러 둔 것 · 고치면 조용히 깨지는 것)
- `addons_path`에 넣을 경로는 저장소 루트가 아니라 **`19.0/`**. 그룹 하위 폴더 금지(addons_path 비재귀) → `README.md` 「모듈 네이밍·그룹 규칙」
- 바로빌 SOAP 호출은 모델이 아니라 `controllers/`의 **일반 파이썬 클래스**(`http.Controller` 아님). 모델에 `client.service.X` 금지 → `README.md` 「바로빌 아키텍처」
- 바로빌 인증값은 `barobill/models/common.py` 헬퍼로만 읽는다. 비밀값은 소스가 아니라 설정 화면에서 입력.
- `barobill.*.result` 로그 모델은 append-only — 일반 사용자 권한은 읽기/생성만.
- FAX FTP는 CP949 — 인코딩 불가 파일명은 UUID로 치환. 결과 이력은 상태 *전이*만 기록.
- [❓확인 필요: 위 외에 코드만 봐선 모를 결정(예: edb_security 유휴 1시간 기준, helpdesk `ticket_no` 정수화 이유)을 ADR로 남길지]

## 규칙·절차가 있는 곳
| 무엇 | 위치 |
|---|---|
| 문서를 언제·어디에 남기나 | `docs/ROUTING.md` (유일 기준) |
| PR·커밋 메시지 | `docs/guides/pr-rules.md` (회사 공통·CI 강제) · `docs/guides/gitflow.md` (브랜치·커밋 규약) |
| 문서 작성 절차 · 파일명·꼬리표·날짜 규칙 | `docs/guides/write-doc.md` · `docs/CLAUDE.md` (이름은 Claude용이지만 내용은 공통) |
| 코딩·네이밍 규칙 | `docs/project/conventions.md` · `.claude/rules/odoo-standards.md` |
| 요구사항 추적 | `docs/requirements/trace.md` · 다시 맞추기 `docs/guides/req-trace.md` |
| 일 끝났을 때 갱신할 곳 | `docs/guides/task-done.md` ("○○ 끝났어" → 목록을 돌고 빠진 곳 보고) |
| 배포(모듈을 쓰는 프로젝트로 반영) | `docs/guides/deploy.md` (실행은 사람만) — [❓확인 필요: 배포 방식] |
| 보안·마이그레이션·코딩 규칙 | `.claude/rules/*.md` (평문 — 어느 AI든 그대로 읽고 따른다) |

## Knowledge rules
- 아키텍처/모듈구조/배포를 바꾸기 전에 **관련 `docs/decisions/`를 먼저 읽는다.**
- 이미 채택된 결정은 재논쟁하지 말고 **새 ADR로 supersede**한다.
- **팀 규칙은 AI 개인 메모리에 저장하지 않는다.** 이 파일이나 `docs/`에 쓴다 — 메모리는 그 PC의 그 AI만 읽는다.
- **한 사실은 한 곳에.** 일정·범위·담당은 `docs/project/schedule-scope.md`에만, 모듈 목록·네이밍 규칙은 루트 `README.md`에만 — 다른 문서는 링크.
- 새 모듈을 추가하면 ① 모듈 폴더 `README.md` ② 루트 `README.md` 카테고리 ③ `docs/project/modules.md` 에 한 줄.
- **요구 번호를 커밋·PR 제목·시험 이름에 남긴다** (형식은 `trace.md` 의 `id-format:`).
- 절차의 본문은 `docs/guides/`에 평문으로 둔다. 도구별 스킬·명령은 그 문서를 부르기만 한다.

## 문서 기록 규칙 (언제/어디에는 docs/ROUTING.md가 유일 기준)
- 모든 개발은 **PR 설명**(What/Why/How/Gotchas)으로 맥락을 남긴다 → 대부분 별도 파일 X.
  - **PR·커밋 메시지를 쓰기 전에 `docs/guides/pr-rules.md` 를 반드시 읽는다** (한글 헤더 5섹션·티켓 `#` 금지 등 — CI가 강제, 어기면 PR 실패).
- **작업 종료 시 스스로 판단해 자동 초안을 만든다(누락 방지):**
  - 운영 장애·데이터 정정·배포 실패·30분+ 대응·**작업 사고** → `docs/issues/`
  - 비자명한 설계/아키텍처/코어 변경 → `docs/decisions/` (자동 초안, **기각한 대안 포함**)
  - 그 외 일상 개발 → PR 설명으로 끝.
- **저장 위치는 `docs/ROUTING.md` 표를 그대로 따른다. 임의 폴더에 넣지 않는다.**
- 문서 작성은 `docs/guides/write-doc.md` 절차대로 (저장 후 `python3 scripts/check_docs.py`로 검증).
- 세션을 넘길 때는 `docs/handoff/`에 인계 문서 (`docs/_templates/handoff.md`).

## 사람 확인이 필요한 곳 (AI가 혼자 끝내지 않는다)
- 외부로 나가는 문서·메일 → **초안까지만.** 끝에 `## 가정한 것`을 붙여 사람에게 넘긴다 (`docs/delivery/`, 양식 `docs/_templates/delivery.md`).
- 범위·일정이 들어간 문장 → 기억·옛 문서로 쓰지 말고 **일정·범위 파일**(`docs/project/schedule-scope.md`)과 대조한다.
- 남의 담당 영역 → 직접 고치지 말고 **요청 문서**(같은 `delivery.md` 양식)를 만든다.
- 운영 반영(배포·운영 DB)·비밀값(바로빌 CERTKEY·FTP 비번 등) → **사람만** 한다.

## 금지
- 비밀번호·API 키·SSH 키·서버 IP를 **어떤 문서/코드에도 적지 않는다.** (비밀번호 관리자에 두고 위치만 참조)
- 운영 DB 직접 수정은 백업·DRY-RUN·롤백셋 없이 하지 않는다. (`.claude/rules/migration-safety.md`)
- `main`에 직접 커밋·push 하지 않는다 — 작업 브랜치 → PR.

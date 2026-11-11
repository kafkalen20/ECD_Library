# CLAUDE.md

> Claude Code 전용 진입점. **팀 규칙의 원본은 `AGENTS.md`** — 아래 `@AGENTS.md` 로 그대로 불러온다.
> 여기에는 **Claude Code에만 해당하는 것**만 쓴다(목표 30줄 이내). 공통 규칙을 여기 복붙하지 않는다.

@AGENTS.md

## Claude Code 전용
- 스킬은 절차 문서를 부르기만 한다 (본문은 `docs/guides/` — 다른 AI도 같은 절차를 따르게):
  - `/write-doc` → `docs/guides/write-doc.md`
  - `/task-done` → `docs/guides/task-done.md` ("○○ 끝났어" 할 때)
  - `/req-trace [번호]` → `docs/guides/req-trace.md` (요구 추적표 다시 맞추기)
  - `/deploy` → `docs/guides/deploy.md` (사람만 호출 — `disable-model-invocation`)
- `.claude/rules/*.md` 는 `paths:` 에 맞는 파일을 만질 때 자동으로 읽힌다. `docs/CLAUDE.md` 는 `docs/` 작업 시 자동으로 읽힌다.
- `.claude/settings.json` 의 hook·권한이 규칙을 강제한다 (문서 저장 시 `check_docs.py` 등).

## 자동 메모리 (auto memory)
- **팀 규칙·프로젝트 사실은 자동 메모리에 저장하지 않는다.** `AGENTS.md`·`docs/`에 쓴다 (메모리는 이 PC의 Claude만 읽는다).
- 메모리에는 개인 취향(답변 스타일 등)만. 세션 중 메모리로 간 팀 규칙이 있으면 인계 전에 `AGENTS.md`·`docs/`로 옮긴다.

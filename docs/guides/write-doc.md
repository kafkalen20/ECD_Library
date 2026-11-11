---
owner: claude-brain
created: 2026-10-29
updated: 2026-10-30
---
# 문서 작성 절차 (회사 공통)

> ⚠️ **kit 엔진 파일** — `claude-brain`에서 동기화된다. **이 프로젝트에서 직접 고치지 말 것.** (고칠 게 있으면 `/claude-brain` 역반영)
>
> 어느 AI든 사람이든 이 순서대로 한다. Claude Code는 `/write-doc` 스킬이 이 문서를 불러 실행한다.
> 목적: "어디에 저장할지" 헤매거나 엉뚱한 폴더에 넣는 것을 막고, 개발자가 까먹어도 누락되지 않게.
> 기준은 항상 `docs/ROUTING.md`. 이 절차는 그 판단을 결정적으로 실행한다.

## 실행 순서

1. **유형 판단** — `docs/ROUTING.md`의 라우팅 표로 트리거를 매칭한다.
   - 트리거 없음(일상 개발) → **문서 만들지 말고 PR 설명으로** 안내하고 종료.
2. **폴더 확정** — 표의 "저장 위치"를 그대로 쓴다. 절대 임의 폴더에 넣지 않는다.
   - issues / decisions / guides / project / design / handoff / delivery / requirements 중 하나 (현황은 `status.md`, 일정·범위는 `project/schedule-scope.md` 고정) (+ AI 반복절차는 `docs/guides/` 본문 + 도구별 스킬).
3. **파일명 생성** — 표의 파일명 규칙대로.
   - issues: `YYYY-MM-DD-무엇-어디.md` (검색 키워드 포함)
   - delivery: `YYYY-MM-DD-받는곳-주제.md`
   - requirements: 표 `trace.md` 에 한 줄 (번호 = `id-format:` 형식으로 마지막 번호 + 1) / 상세는 `<번호>-제목.md`
   - decisions: `NNNN-제목.md` → **기존 decisions/ 의 마지막 번호 확인 후 +1**
4. **템플릿 복사·작성** — `docs/_templates/`의 해당 서식을 채운다.
   - issue(장애기록): 증상→영향→타임라인→**5 Whys**→해결→**재발방지(우선순위·소유자·마감일)**
   - decision: 맥락→결정→**기각한 대안(이유로)**→결과
   - delivery(전달 문서): `to:`·`scope:` → 요점→본문→요청→**가정한 것**(비우지 않음, 없으면 "없음")
   - 살아있는 문서면 `owner:` 지정.
5. **저장** — 확정한 폴더에 저장한다.
6. **목차 등록** — `docs/README.md` 해당 섹션에 `[제목](경로) — 한 줄 요약` 추가.
7. **검증** — `python3 scripts/check_docs.py` 를 돌려 배치/파일명/표식 위반이 없는지 확인.
8. **사람 확인** — 초안임을 알리고 확인/수정을 요청한다. (자동 저장하되, 커밋은 사람 승인 후)

## 금지
- ROUTING 표에 없는 임의 폴더 생성/저장.
- 비번·키·서버IP를 문서에 기입 (방법·위치만).

---
owner: parkbohee
created: 2026-11-16
updated: 2026-11-17
status: 종결
---
# SEC-5 설정 스위치 연결 검토

> 작업목록: `공통보안모듈_작업목록_261105.xlsx` → `기존 모듈 보완` 시트 SEC-5 (P2)
> 기준 코드: `feature/edb-security-merge` 커밋 `5ecd47f` (PR #1). 줄 번호는 이 커밋 기준이다.
> **결론 먼저: 코드를 다시 확인해 보니 사용자에게 보이는 문제는 이미 해결돼 있다. 이 항목은 2026-11-17 종결했다.** 이 문서는 나중에 해당 기능을 만들 개발자가 알아야 할 연결 방법을 남긴다.

## 배경 / 목표 (무엇을 왜)

설정 스위치 10개(`core/guards.py:11` `TOGGLES`)와 "이벤트 보관 개월" 중 실제 코드가 읽는 것은 3개뿐이다.

| 설정 | 코드 | 읽는 곳 | 화면 |
|---|---|---|---|
| 로그인 이벤트 수집 | `hook_login` | `res_users.py`, `collector.record` | 보임 |
| 탐지 엔진 | `detect_engine` | `security_rule.py` `_cron_evaluate` | 보임 |
| 치명 즉시 알림 | `notify_critical` | `security_rule_hit.py` `_notify_hit` | 보임 |
| 사용자 변경 수집 | `hook_user_write` | 없음 (H-2 미구현) | **숨김** |
| API 키 수집 | `hook_apikey` | 없음 (H-3 미구현) | **숨김** |
| 권한 구조 변경 수집 | `hook_acl` | 없음 (H-4 미구현) | **숨김** |
| 설정 변경 수집 | `hook_config` | 없음 (H-7 미구현) | **숨김** |
| 일일 다이제스트 | `notify_digest` | 없음 (Phase 2) | **숨김** |
| 보관 기간 파기 | `gc_enabled` | 없음 (Phase 2) | **숨김** |
| 자가 점검 | `selfcheck_enabled` | 없음 | **숨김** |
| 이벤트 보관(개월) | `retention_months` | 없음 (Phase 2) | **숨김** |

화면 근거: `views/res_config_settings_views.xml`. 숨긴 이유와 되살리는 방법이 XML 주석에 이미 적혀 있다 ("설정이 거짓말을 하면 안 된다 … 소비자가 생기면 이 `<setting>` 블록만 되살리면 된다").

작업목록을 쓸 때는 "화면에서 켜고 끌 수 있는데 아무 일도 안 한다"고 보았는데, **사실과 달랐다.** 남은 것은 화면 밖의 작은 부작용 하나뿐이다.

- 프리셋 버튼(`최소`/`표준`, `res_config_settings.py` `_apply_preset`)은 숨긴 스위치까지 함께 켜고 끈다. 값이 바뀌면 그 스위치마다 `config_changed` 이벤트가 생긴다(`_log_toggle_change`). 그래서 이벤트 목록에 사용자가 본 적 없는 설정의 변경 기록이 섞인다. 동작에는 영향이 없다.

## 요구사항 (해당 기능을 만들 때 지킬 것)

- R1. 숨긴 스위치에 해당하는 기능(H-2·H-3·H-4·H-7, 다이제스트, 파기, 자가 점검)을 만드는 작업은, **그 기능의 첫 줄에서 `guards.is_active(env, '<코드>')`로 스위치를 확인하고, 같은 PR에서 설정 화면의 `<setting>` 블록을 되살린다.**
- R2. 파기 cron을 만들 때는 `retention_months`(기본 12)를 읽고, 보관 개월 설정 블록을 함께 되살린다.
- R3. 설정 변경 기록(`_log_toggle_change`)은 `hook_config` 스위치와 상관없이 항상 남긴다. 공격자가 먼저 스위치를 끄는 것을 막기 위해서다 (`res_config_settings.py:87` docstring). `hook_config`는 **다른** 설정 변경(H-7)에만 쓴다.

## 설계 (채택 안 함: 프리셋 기록 잡음 줄이기)

나중에 위 부작용을 고치기로 하면 다음 한 가지만 하면 된다.

- `_apply_preset`에서 `config_changed` 이벤트를 남기는 대상을 "화면에 보이는 스위치"로 한정한다. 보이는 스위치 목록은 상수로 둔다(`VISIBLE_TOGGLES = {'hook_login', 'detect_engine', 'notify_critical'}`). 기능을 추가할 때 이 상수에도 더한다.
- 시험: `tests/test_settings.py`에 "`표준` 프리셋 적용 시 `config_changed` 이벤트는 보이는 스위치 수 이하"를 추가한다.

## 대안 검토 (택하지 않은 방향)

- **숨긴 스위치·필드를 코드에서 지우기**: 기능을 만들 때 다시 만들어야 하고, 이미 설치된 DB의 `ir.config_parameter` 값이 고아로 남는다. 지금처럼 숨겨 두는 편이 싸다.
- **숨긴 스위치를 회색(읽기 전용)으로 보여 주기**: 사용자가 "왜 못 켜나"를 묻게 된다. 준비되지 않은 기능은 안 보이는 편이 낫다.

## 영향 범위 / 리스크

- 종결해서 코드 변경이 없다.
- 위 설계를 하게 되면 `models/res_config_settings.py`, `tests/test_settings.py`만 바뀐다.

## 미결 / 열린 질문

- [x] 종결 (2026-11-17). "선택" 설계는 하지 않는다. R1~R3은 LOG-9·RPT-2 등 해당 기능 작업에서 지킨다.
- [x] 작업목록 SEC-5 문구를 실제 상태에 맞게 고쳤다 (2026-11-17).

## 관련

- 작업목록: SEC-5, LOG-9(권한 변경 이력), RPT-2(이상 징후 알림)
- 코드: `19.0/edb_security/core/guards.py`, `models/res_config_settings.py`, `views/res_config_settings_views.xml`

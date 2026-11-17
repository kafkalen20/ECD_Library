---
owner: parkbohee
created: 2026-11-16
updated: 2026-11-16
status: 초안
---
# SEC-4 탐지 중복 검사 정리 설계

> 작업목록: `공통보안모듈_작업목록_261105.xlsx` → `기존 모듈 보완` 시트 SEC-4 (P2)
> 기준 코드: `feature/edb-security-merge` 커밋 `5ecd47f` (PR #1). 줄 번호는 이 커밋 기준이다. **PR #1이 머지된 뒤 `main`에서 브랜치를 따서 작업한다.**

## 배경 / 목표 (무엇을 왜)

탐지 cron(`_cron_evaluate`, 1분 주기)은 룰마다 "검사 구간"을 정해 이벤트를 본다 (`security_rule.py:85` `_window_start`).

- 구간 시작 = `지금 - window_minutes` (기본 룰은 10분). cron이 멈췄다 돌아온 경우에만 `last_eval`까지 거슬러 간다(최대 24시간).
- 구간이 1분씩 밀리며 10분 폭으로 겹치므로, **같은 이벤트를 10번 검사한다.**

룰 종류별로 영향이 다르다.

| 종류 | 겹쳐 검사하는 이유 | 지금 같은 알림을 막는 장치 | 문제 |
|---|---|---|---|
| 임계 집계(`threshold`, R-01·R-01B) | "최근 10분 안에 N건"을 매분 다시 세는 **슬라이딩 구간**이라 겹치는 것이 맞다 | 중복 억제(`cooldown_minutes`, `_in_cooldown` `:171`) | 중복 억제를 0으로 두면 조건이 유지되는 동안 매분 히트가 생긴다 |
| 새 IP(`new_ip`, R-02) | 이벤트 1건마다 판단하므로 1번만 보면 된다 | 중복 억제 | 0이면 같은 이벤트로 최대 10번 히트. 이벤트마다 `search_count`를 1번씩 실행한다(`:140`) |
| 업무시간 외(`offhours`, R-03) | 이벤트 1건마다 판단 | 중복 억제 | 0이면 같은 이벤트로 최대 10번 히트 |

기본 룰은 중복 억제가 30~60분이라 지금 당장 알림이 반복되지는 않는다. 하지만 룰 화면에서 감사자가 0으로 바꿀 수 있고, 그러면 같은 사건으로 치명 알림 메일이 10통 간다.

**왜 그냥 "지난 평가 이후 이벤트만" 보지 않는가**: 로그인 성공 이벤트는 요청 트랜잭션 안에서 ORM으로 만들어진다. `create_date`는 트랜잭션 **시작** 시각인데 DB에 보이는 것은 **커밋** 시각이다. 요청이 길면 `create_date`가 이미 지난 구간에 속한 채로 늦게 나타난다. 구간을 겹치지 않게 자르면 이런 이벤트를 놓친다. 지금 구간이 겹치는 것은 이것을 막는 안전장치이므로 유지한다.

## 요구사항

- R1. 새 IP·업무시간 외 룰은 **이벤트 1건당 최대 1번만** 히트를 만든다. 중복 억제 값과 상관없다.
- R2. 임계 집계 룰은 같은 그룹 키에 대해 **같은 이벤트 묶음으로 히트를 거듭 만들지 않는다.** 중복 억제가 0이어도 최소한 검사 구간(`window_minutes`) 동안은 다시 발동하지 않는다.
- R3. 늦게 커밋된 이벤트를 놓치지 않는다 (검사 구간은 지금처럼 겹친다).
- R4. 새 IP 룰의 DB 조회 수를 이벤트 수에 비례하지 않게 줄인다.
- R5. 기존 `tests/test_rules.py`가 그대로 통과한다.

## 설계 (구조 · 데이터 · 흐름)

### 1. 이벤트 단위 룰: 이미 이 룰의 히트에 붙은 이벤트 빼기 (R1, R3)

`_evaluate_new_ip`(`:134`)와 `_evaluate_offhours`(`:151`)에서 검사 대상을 찾을 때 조건을 하나 더한다.

```python
domain = self._base_domain(window_start) + [('hit_ids.rule_id', 'not in', [self.id])]
```

- `edb.security.event.hit_ids`는 이미 있는 역방향 관계다 (`security_event.py:67`). 새 필드가 필요 없다.
- 히트를 만들 때 `_fire(..., events=event)`가 그 이벤트를 히트에 연결하므로(`:182` 이하), 다음 분부터 그 이벤트는 대상에서 빠진다.
- 구간은 지금처럼 겹치므로 늦게 커밋된 이벤트도 다음 검사 때 잡힌다.
- **확인 필요**: Odoo 19에서 x2many 경로에 `not in`을 쓰면 "해당하는 관련 레코드가 하나도 없다"는 뜻으로 해석되는지 개발자가 테스트로 확인한다. 기대와 다르면 `('id', 'not in', 이 룰 히트의 event_ids)`로 바꾼다 (히트 수가 적어 비용이 작다).

### 2. 임계 집계: 중복 억제 하한을 구간 길이로 (R2)

`_in_cooldown`(`:171`)에서 실제로 쓰는 억제 시간을 다음처럼 바꾼다.

```python
minutes = self.cooldown_minutes
if self.rule_kind == 'threshold':
    minutes = max(minutes, self.window_minutes or 1)
if not minutes:
    return False
```

- 뜻: 임계 집계는 "같은 10분 안의 같은 이벤트 묶음"으로 한 번만 알린다. 그 뒤에도 조건이 계속되면 다음 구간에서 다시 알린다.
- 룰 폼의 `cooldown_minutes` 도움말에 "임계 집계 룰은 검사 구간보다 짧게 잡아도 검사 구간만큼은 억제한다"를 적는다.

### 3. 새 IP 룰 조회 수 줄이기 (R4)

지금은 대상 이벤트마다 "이 사용자가 이 IP로 전에 로그인한 적 있나"를 `search_count`로 한 번씩 조회한다(`:140`). 한 번의 집계로 바꾼다.

```python
recent = Event.search(domain)            # 1번
pairs = {(e.user_id.id, e.client_ip) for e in recent if e.user_id and e.client_ip}
seen = set()
if pairs:
    rows = Event._read_group(
        [('event_type', 'in', ...),       # SEC-1 이 먼저 끝났으면 self._event_types(), 아니면 [self.event_type]
         ('user_id', 'in', [u for u, _ in pairs]),
         ('client_ip', 'in', [ip for _, ip in pairs]),
         ('create_date', '<', window_start)],
        ['user_id', 'client_ip'], ['__count'])   # 2번
    seen = {(u.id, ip) for u, ip, _cnt in rows}
for event in recent:
    if (event.user_id.id, event.client_ip) not in seen:
        self._fire(...)
```

- `user_id IN`과 `client_ip IN`을 따로 거르므로 짝이 맞지 않는 행도 일부 나오지만, 마지막에 짝으로 비교하므로 결과는 같다.
- 같은 구간에 같은 사용자·IP 이벤트가 여럿이면 첫 번째로 히트를 만들고, 나머지는 중복 억제나 1번 조건으로 빠진다. 지금과 같다.

## 시험 (개발자가 추가할 테스트)

`tests/test_rules.py`에 추가한다. 기존 `_backdate`·`_recent_kst_naive_utc` 도우미를 쓴다.

| 테스트 | 확인할 것 |
|---|---|
| `test_offhours_same_event_fires_once_with_zero_cooldown` | 중복 억제 0, 업무시간 외 이벤트 1건, `_evaluate()` 3번 → 히트 1건 |
| `test_new_ip_same_event_fires_once_with_zero_cooldown` | 같은 조건으로 새 IP 룰 → 히트 1건 |
| `test_late_committed_event_still_detected` | 이벤트 `create_date`를 지난 평가 시각보다 앞으로 돌린 뒤 평가 → 히트 생김 (R3) |
| `test_threshold_zero_cooldown_suppressed_within_window` | 임계 룰 중복 억제 0, 같은 실패 묶음으로 2번 평가 → 히트 1건 |
| `test_new_ip_query_count_constant` | 이벤트 1건과 20건에서 쿼리 수가 같다 (`self.assertQueryCount` 사용) |

## 대안 검토 (택하지 않은 방향)

- **검사 구간을 겹치지 않게(`last_eval` 이후만)**: 늦게 커밋된 이벤트를 놓친다 (배경 참고).
- **이벤트에 "검사 완료" 표시 필드 추가**: 룰이 여럿이라 룰별로 표시해야 하고, 그러면 결국 지금의 `hit_ids` 관계와 같은 것이 된다.
- **중복 억제 0을 입력 단계에서 막기**: 임계 집계에서는 "구간마다 다시 알림"이 의미가 있을 수 있다. 막기보다 하한을 두는 편이 낫다.

## 영향 범위 / 리스크

- 파일: `19.0/edb_security/models/security_rule.py`, `views/security_rule_views.xml`(도움말), `tests/test_rules.py`.
- 1번 조건은 이벤트 단위 룰의 히트 수를 줄이기만 한다. 기본 룰(중복 억제 30분)에서는 지금과 결과가 같다.
- SEC-1과 같은 파일을 고친다. **SEC-1을 먼저 하면** 3번 코드의 유형 조건을 `self._event_types()`로 쓴다.

## 미결 / 열린 질문

- [ ] 탐지 이벤트가 매우 많은 고객사(분당 수천 건)에서 1번 조건이 느린지. 그런 고객사가 생기면 실측한다.

## 관련

- 작업목록: SEC-4
- 모듈 README: `19.0/edb_security/README.md` B1(탐지 cron), B2(기본 룰)
- 관련 설계: SEC-1(R-02·R-03 유형 확장)

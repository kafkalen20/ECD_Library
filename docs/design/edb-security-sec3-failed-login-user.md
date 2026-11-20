---
owner: parkbohee
created: 2026-11-16
updated: 2026-11-19
status: 구현
---
# SEC-3 로그인 실패 기록에 계정 연결 설계

> 작업목록: `공통보안모듈_작업목록_261105.xlsx` → `기존 모듈 보완` 시트 SEC-3 (P1)
> 기준 코드: `feature/edb-security-merge` 커밋 `5ecd47f` (PR #1). 줄 번호는 이 커밋 기준이다. **PR #1이 머지된 뒤 `main`에서 브랜치를 따서 작업한다.**

> **구현: 2026-11-19, 브랜치 `feature/edb-security-sec3-failed-login-user` (`main` 기준, PR #1·#3 머지 후).** 설계와 달라진 점은 맨 아래 「구현 메모」.

## 배경 / 목표 (무엇을 왜)

로그인 실패 이벤트(`login_failed`)는 `res_users.py:46`에서 기록한다. 이때 `login` 칸만 채우고 **`user_id`는 비워 둔다.**

- `_secmon_failed_login_value()`(`res_users.py:14`)는 이미 "입력한 문자열이 실제 계정인가"를 조회한다 (`search_count`). 실제 계정이면 평문을, 아니면 `unknown:<HMAC>`을 돌려준다. 그런데 **찾은 계정의 id는 버린다.**
- 그 결과:
  - 이벤트 화면의 "이 계정 추적"(`security_event.py:113` `action_trace_user`)은 `user_id`가 있으면 `user_id`로 찾는다. 성공 이벤트에서 누르면 `user_id` 기준이라 **실패 이벤트가 목록에서 빠진다.**
  - 이벤트 목록을 사용자별로 묶거나 거르면 실패가 "사용자 없음"으로 따로 모인다.
  - 계정 로그인 ID가 나중에 바뀌면 옛 실패 기록과 계정을 이을 방법이 없다.

## 요구사항

- R1. 입력한 로그인 문자열이 실제 계정이면 `login_failed` 이벤트의 `user_id`에 그 계정을 넣는다. 보관(비활성) 계정도 포함한다.
- R2. 없는 계정이면 지금처럼 `user_id`는 비우고 `login`은 `unknown:<HMAC>`으로 남긴다.
- R3. 계정을 찾는 기준은 **코어 `_login`과 같아야** 한다. 같은 로그인 ID를 가진 계정이 여럿일 수 있는 구성(웹사이트별 사용자 등)에서 코어가 고르는 계정과 같은 계정을 넣는다.
- R4. 조회 횟수를 늘리지 않는다. 지금 하는 조회 1회로 해결한다.
- R5. 이 처리가 실패해도 원래의 `AccessDenied`를 가리지 않는다 (기존 원칙, `res_users.py:34-36`).

## 설계 (구조 · 데이터 · 흐름)

### 1. `_secmon_failed_login_value` → 계정도 함께 돌려주기

이름과 반환값을 바꾼다: `_secmon_failed_login_info(login)` → `(login_value, user_id)`.

```python
def _secmon_failed_login_info(self, login):
    if not login or not isinstance(login, str):
        return login, None
    if not guards.is_active(self.env, 'hook_login'):
        return None, None
    try:
        user = self.sudo().with_context(active_test=False).search(
            self._get_login_domain(login),
            order=self._get_login_order(),   # 코어 _login 과 같은 정렬 (R3)
            limit=1)
        if user:
            return login, user.id
        secret = ...  # 기존 HMAC 처리 그대로
        return 'unknown:' + digest[:12], None
    except Exception:
        return None, None
```

- `search_count` → `search(..., limit=1)`로 바꿔 id를 얻는다. 조회 횟수는 1회 그대로다 (R4).
- 정렬 `_get_login_order()`는 코어 `_login`(`odoo/addons/base/models/res_users.py:765`)과 같은 것을 써서, 같은 로그인 ID가 여럿일 때 코어와 같은 계정을 고른다 (R3).
- `active_test=False`는 그대로 둔다. 보관 계정으로 로그인을 시도한 것도 그 계정에 묶어야 조사에 쓸 수 있다 (R1).

### 2. 호출부 (`res_users.py:46`)

```python
login_value, user_id = self._secmon_failed_login_info(login)
collector.record(self.env, 'hook_login', 'login_failed',
                 severity='high', detached=True,
                 login=login_value, user_id=user_id, ...)
```

`detached` 경로는 raw SQL INSERT라 `user_id`에 정수 id만 넣으면 된다 (`collector._ALLOWED_FIELDS`에 이미 `user_id`가 있음).

### 3. 영향받는 화면·룰

- "이 계정 추적": 코드 변경 없이 실패 이벤트가 함께 나온다.
- R-01(`group_by=login`)·R-01B(`group_by=client_ip`): 그룹 기준이 `user_id`가 아니므로 결과가 같다.
- R-02(`new_ip`): `login_success`만 대상이므로 영향 없다.

### 4. 이미 쌓인 데이터

옛 `login_failed` 이벤트의 `user_id`는 채우지 않는다. 평문 `login`이 남아 있는 행(실제 계정)은 SQL로 이을 수 있지만, 로그인 ID가 그새 바뀌었을 수 있어 틀린 계정에 묶일 위험이 있다. 필요하면 미결 1로 따로 정한다.

## 시험 (개발자가 추가할 테스트)

`tests/test_login_hook.py`에 추가한다. 기존 `test_failed_login_of_existing_login_is_stored_in_plaintext`(`:60`)와 같은 방식으로 실패를 만든다.

| 테스트 | 확인할 것 |
|---|---|
| `test_failed_login_of_existing_login_links_user` | 실제 계정, 틀린 비밀번호 → `user_id` = 그 계정 |
| `test_failed_login_of_archived_user_links_user` | 보관 계정 → `user_id` = 그 계정 |
| `test_failed_login_of_unknown_login_has_no_user` | 없는 계정 → `user_id` 비어 있음, `login`은 `unknown:` |
| `test_trace_user_includes_failed_logins` | 성공 이벤트에서 "이 계정 추적" → 같은 계정의 실패 이벤트도 결과에 포함 |

## 대안 검토 (택하지 않은 방향)

- **탐지 cron이나 화면에서 `login` 문자열로 계정을 나중에 찾기**: 로그인 ID가 바뀌면 틀린 계정에 묶인다. 기록 시점에 이미 조회하고 있으므로 그때 넣는 것이 맞다.
- **"이 계정 추적"만 `user_id OR login`으로 고치기**: 화면 하나는 고쳐지지만 목록 그룹·필터·보고서는 그대로 빠진다.

## 영향 범위 / 리스크

- 파일: `19.0/edb_security/models/res_users.py`, `19.0/edb_security/tests/test_login_hook.py`.
- 실패 경로에서 `search_count`가 `search(limit=1)`로 바뀐다. 같은 UNIQUE 인덱스를 타므로 비용 차이는 거의 없다.
- 기존 테스트 중 `_secmon_failed_login_value`를 직접 부르는 것이 있으면 새 이름·반환값에 맞춘다 (`grep -rn _secmon_failed_login_value 19.0/edb_security`).

## 미결 / 열린 질문

- [ ] 1. 이미 쌓인 실패 이벤트에 `user_id`를 채울지 (위 4번). 채운다면 마이그레이션 스크립트로 한다.

## 구현 메모 (2026-11-19)

- 코드는 설계 1·2번 그대로다. `_secmon_failed_login_value` → `_secmon_failed_login_info` 가 `(login, user_id)` 를 돌려주고, `_login` 실패 경로가 `user_id` 를 같이 넘긴다. 정렬은 코어 `_login`(`odoo/addons/base/models/res_users.py:765`)과 같은 `_get_login_order()` 를 쓴다 (`website` 가 `website_id` 를 앞에 붙임).
- **시험에서 FK 함정이 있었다.** 실패 기록은 분리 커넥션의 raw INSERT 라 `user_id` FK 가 **COMMIT 된** `res_users` 행만 본다. 테스트 트랜잭션 안에서 만든 사용자를 넣으면 `edb_security_event_user_id_fkey` 위반으로 그 행이 통째로 버려진다 (기존 `test_failed_login_of_existing_login_is_stored_in_plaintext` 가 이렇게 깨졌다). 그래서 계정 연결 시험은 사용자 생성과 실패 로그인을 별도 커서에서 COMMIT 해서 만들고 끝나면 직접 지운다 (`_committed_user`·`_fail_login_committed`). 기존 시험은 `test_failed_login_of_existing_login_links_user` 로 바꿨다.
- 운영에서는 로그인 대상 계정이 이미 COMMIT 돼 있어 같은 문제가 없다. 다만 실패 행이 큐에 머무는 사이 그 계정이 **삭제**되면 FK 위반으로 그 실패 기록이 버려진다 (`dropped()` 에 집계). 드문 경우라 이번 범위에서는 막지 않았다.
- 시험 `test_failed_login_info_matches_core_login_lookup` 을 하나 더 넣었다 (R3 — 코어와 같은 domain·정렬로 고른 계정과 같은지).
- `user_id` 를 빼고 돌리면 계정 연결·보관 계정·계정 추적 시험 3개가 실패하는 것을 확인했다. `edb_security` 시험 68개 모두 통과.

## 관련

- 작업목록: SEC-3
- 같이 보면 좋은 문서: SEC-7(계정 추적 빈 로그인), SEC-1(2FA 실패 이벤트는 처음부터 `user_id`를 넣도록 설계함)

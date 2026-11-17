---
owner: parkbohee
created: 2026-11-16
updated: 2026-11-16
status: 초안
---
# SEC-7 계정 추적 빈 로그인 처리 설계

> 작업목록: `공통보안모듈_작업목록_261105.xlsx` → `기존 모듈 보완` 시트 SEC-7 (P2)
> 기준 코드: `feature/edb-security-merge` 커밋 `5ecd47f` (PR #1). 줄 번호는 이 커밋 기준이다. **PR #1이 머지된 뒤 `main`에서 브랜치를 따서 작업한다.**

## 배경 / 목표 (무엇을 왜)

보안 이벤트 폼의 "이 계정 추적" 버튼(`views/security_event_views.xml:28`)은 `action_trace_user`(`models/security_event.py:113`)를 부른다.

```python
domain = [('user_id', '=', self.user_id.id)] if self.user_id \
    else [('login', '=', self.login)]
```

- `user_id`도 없고 `login`도 비어 있으면 도메인이 `[('login', '=', False)]`가 된다. Odoo는 이것을 "login이 비어 있는 모든 이벤트"로 해석한다. 그래서 **서로 관계없는 이벤트가 한꺼번에 "계정 추적: -" 화면에 뜬다.**
- 이런 이벤트가 생기는 경우:
  - 로그인 실패 시 `_secmon_failed_login_value()`가 판정에 실패해 `None`을 돌려준 경우 (`res_users.py:34-36`)
  - 요청 없이 시스템이 만든 이벤트 (앞으로 생길 파기·자가 점검 등)
- "이 IP 추적" 버튼은 IP가 없으면 이미 숨긴다 (`views/security_event_views.xml:32` `invisible="not client_ip"`). 계정 버튼에만 이 처리가 빠졌다.

## 요구사항

- R1. 이벤트에 계정(`user_id`)도 로그인 문자열(`login`)도 없으면 "이 계정 추적" 버튼을 보이지 않는다.
- R2. 버튼을 거치지 않고 메서드를 직접 부르는 경우(RPC 등)에도 엉뚱한 목록을 열지 않는다.

## 설계 (구조 · 데이터 · 흐름)

1. 화면 (`views/security_event_views.xml:28`): 버튼에 조건을 더한다.

   ```xml
   <button name="action_trace_user" type="object"
           string="이 계정 추적" class="btn-primary"
           invisible="not user_id and not login"/>
   ```

   조건에 쓰는 필드는 폼에 있어야 한다. 지금 폼에는 `user_id`는 있고 `login`은 없다(`login_display`만 있음). 폼 안에 `<field name="login" invisible="1"/>`을 추가한다.

2. 메서드 (`models/security_event.py:113`): 둘 다 없으면 오류를 낸다.

   ```python
   if not self.user_id and not self.login:
       raise UserError("이 이벤트에는 추적할 계정 정보가 없습니다.")
   ```

   `odoo.exceptions`에서 `UserError`를 import한다.

3. SEC-3을 먼저 하면 실제 계정의 실패 이벤트에는 `user_id`가 들어가므로, 이 경우는 더 드물어진다. 순서는 상관없다.

## 시험 (개발자가 추가할 테스트)

`tests/test_event_model.py`에 추가한다.

| 테스트 | 확인할 것 |
|---|---|
| `test_trace_user_without_user_and_login_raises` | `user_id`·`login`이 없는 이벤트에서 `action_trace_user()` → `UserError` |
| `test_trace_user_with_login_only` | `login`만 있는 이벤트 → 도메인이 `[('login', '=', 그 값)]` |

## 대안 검토 (택하지 않은 방향)

- **빈 목록을 여는 도메인(`[('id', '=', 0)]`)을 돌려주기**: 사용자는 왜 비었는지 모른다. 버튼을 숨기고 메서드는 오류로 막는 편이 분명하다.
- **IP로 대신 추적하기**: 버튼 이름과 동작이 달라진다. IP 추적은 따로 버튼이 있다.

## 영향 범위 / 리스크

- 파일: `19.0/edb_security/models/security_event.py`, `views/security_event_views.xml`, `tests/test_event_model.py`.
- 화면 하나와 메서드 하나라 다른 동작에는 영향이 없다.

## 미결 / 열린 질문

- 없음

## 관련

- 작업목록: SEC-7
- 관련 설계: SEC-3(실패 이벤트에 계정 연결)

---
owner: parkbohee
created: 2026-11-16
updated: 2026-11-16
status: 초안
---
# SEC-1 2단계 인증 단계별 로그인 기록 설계

> 작업목록: `공통보안모듈_작업목록_261105.xlsx` → `기존 모듈 보완` 시트 SEC-1 (P1)
> 기준 코드: `feature/edb-security-merge` 커밋 `5ecd47f` (PR #1). 아래 줄 번호는 이 커밋 기준이다. **PR #1이 머지된 뒤 `main`에서 브랜치를 따서 작업한다.**
> 선행: 없음 / 후행: AUTH-1(2단계 인증 강제)은 이 작업이 끝난 뒤에 한다.

## 배경 / 목표 (무엇을 왜)

`edb_security`는 `res.users._login`에서 로그인 성공·실패를 기록한다 (`19.0/edb_security/models/res_users.py:39`). 그런데 Odoo 19에서 2단계 인증(2FA)을 쓰는 사용자는 **비밀번호 단계와 2FA 단계를 따로** 지난다. `_login`은 비밀번호 단계만 본다.

현재 동작 (코드 추적으로 확인, 실행으로는 아직 확인하지 않음):

| 단계 | Odoo 코어 동작 | 근거 | 지금 기록 |
|---|---|---|---|
| ① `/web/login`에서 ID·비밀번호 입력 | `Session.authenticate` → `res.users.authenticate` → `_login` | `odoo/http.py:1199` | `login_success` (`res_users.py:56`) |
| ② 2FA가 필요한지 판단 | `auth_info['mfa'] != 'skip'`이고 `user._mfa_url()`이 있으면 `finalize()`를 하지 않는다. 세션에는 `pre_uid`만 있고 `uid`는 없다 = **아직 로그인 아님** | `odoo/http.py:1207-1209` | — |
| ③ `/web/login/totp`에서 코드 틀림 | `user._check_credentials({'type': 'totp' 또는 'totp_mail', ...})`가 `AccessDenied`를 낸다. 컨트롤러가 받아서 화면에 오류만 보인다 | `auth_totp/controllers/home.py:50-52` | **없음** |
| ③' 코드 검사 한도 초과 (1시간 5회) | `_totp_rate_limit('code_check')`가 `AccessDenied`를 낸다 | `auth_totp/models/res_users.py:26, 120-138` | **없음** |
| ④ 코드 맞음 | `session.finalize()` → 진짜 로그인 | `auth_totp/controllers/home.py:56` | 없음 (①에서 이미 성공으로 기록) |
| ④' 신뢰 기기 쿠키로 통과 | `auth_totp.device._check_credentials_for_uid(scope='browser')` → `finalize()` | `auth_totp/controllers/home.py:34-38` | 없음 |

문제점:
1. 비밀번호만 맞히고 2FA에서 막힌 사람도 `login_success`로 남는다. 사고를 조사할 때 실제로 들어왔는지 구분할 수 없다.
2. 2FA 실패와 한도 초과가 남지 않는다. 비밀번호가 이미 새어 나갔다는 가장 강한 신호를 놓친다.
3. R-02(관리자 새 IP)와 R-03(관리자 업무시간 외)은 ①에서 발동하는데, 알림에는 "로그인"이라고만 나와 담당자가 상황을 잘못 판단한다.

`auth_totp`와 `auth_totp_mail`은 `auto_install`이라 거의 모든 DB에 깔려 있으므로 모든 고객사에 해당한다.

## 요구사항

- R1. 비밀번호를 통과했고 2FA가 남은 경우에는 `login_success` 대신 **`login_mfa_pending`(2단계 인증 대기)** 으로 기록한다.
- R2. 2FA 코드가 틀리거나 검사 한도를 넘으면 **`login_mfa_failed`(2단계 인증 실패)** 로 기록한다. 요청이 롤백돼도 남아야 한다.
- R3. 2FA를 통과하거나 신뢰 기기로 통과하면 그때 `login_success`로 기록한다. `auth_method`에는 `totp` / `totp_mail` / `trusted_device` 중 하나가 들어간다.
- R4. 2FA를 쓰지 않는 사용자, RPC(API 키)·패스키 로그인은 지금과 같이 ①에서 `login_success`로 기록한다.
- R5. R-02·R-03은 **비밀번호 통과 단계(`login_mfa_pending`)부터 발동한다** (2026-11-16 결정). 알림과 발동 이력에는 어느 단계였는지 보인다.
- R6. 같은 로그인 한 번에 R-02·R-03 알림이 두 번(대기 1번 + 성공 1번) 가지 않는다.
- R7. 이 작업이 로그인 자체를 막거나 늦추지 않는다. 기록이 실패해도 로그인 흐름은 그대로 간다 (기존 `collector.record`의 예외 흡수 원칙).

## 설계 (구조 · 데이터 · 흐름)

### 1. 의존성

`__manifest__.py`의 `depends`에 `auth_totp_mail`을 추가한다 (`auth_totp`는 이것이 끌고 온다).

- 이유: `auth_totp`·`auth_totp_mail`의 `_check_credentials`는 자기 유형(`totp`/`totp_mail`)이면 **`super()`를 부르지 않고** 끝낸다 (`auth_totp/models/res_users.py:74-96`, `auth_totp_mail/models/res_users.py:137-155`). 우리 오버라이드가 MRO에서 그보다 위에 있어야 실패를 볼 수 있다. 의존성을 걸어야 순서가 보장된다.
- 영향: 둘 다 `auto_install`이고 `edb_security`는 이미 `mail`에 의존하므로 실제로 더 설치되는 것은 없다.
- 버전: `19.0.2.0.0` → `19.0.2.1.0`.

### 2. 이벤트 유형 추가

`models/security_event.py`의 `EVENT_TYPES`에 두 줄을 추가한다.

```python
('login_mfa_pending', '2단계 인증 대기'),
('login_mfa_failed', '2단계 인증 실패'),
```

심각도: 대기 `info`, 실패 `high` (`login_failed`와 같게).

### 3. ① 비밀번호 단계: `res_users.py` `_login`

성공 분기(`res_users.py:56`)에서 2FA가 남았는지 판단해 유형을 나눈다. 판단 조건은 **코어 `http.py:1208`과 똑같이** 맞춘다.

```python
uid = (auth_info or {}).get('uid')
user = self.env['res.users'].sudo().browse(uid)
mfa_pending = bool(
    (user_agent_env or {}).get('interactive')      # RPC 는 False (odoo/service/common.py:31)
    and (auth_info or {}).get('mfa') != 'skip'     # 패스키는 'skip'
    and user._mfa_url()
)
event_type = 'login_mfa_pending' if mfa_pending else 'login_success'
```

- 코어 조건이 바뀌면 같이 바꿔야 하므로 주석에 `odoo/http.py` `Session.authenticate`를 근거로 적는다.
- `interactive` 조건이 필요한 이유: RPC 인증(`common.authenticate`)은 2FA 단계 없이 바로 끝나기 때문이다. 2FA 사용자는 RPC에서 API 키로만 들어올 수 있다 (`_rpc_api_keys_only`).

### 4. ③ 2FA 코드 검사: `_check_credentials` 오버라이드 (`res_users.py`)

```python
_MFA_TYPES = ('totp', 'totp_mail')

def _check_credentials(self, credential, env):
    if credential.get('type') not in _MFA_TYPES or not self._secmon_is_login_mfa():
        return super()._check_credentials(credential, env)
    try:
        auth_info = super()._check_credentials(credential, env)
    except AccessDenied as exc:
        collector.record(self.env, 'hook_login', 'login_mfa_failed',
                         severity='high', detached=True,
                         user_id=self.id, login=self.sudo().login,
                         auth_method=credential['type'],
                         detail={'reason': str(exc) or 'AccessDenied'})
        raise
    collector.record(self.env, 'hook_login', 'login_success',
                     user_id=self.id, login=self.sudo().login,
                     auth_method=credential['type'])
    return auth_info
```

`_secmon_is_login_mfa()`: **로그인 중인 2FA 검사일 때만** 기록한다. `_check_credentials`는 다른 곳에서도 불리기 때문이다 (예: 비밀번호 재확인 `res.users.identitycheck`, `base/models/res_users.py:1426`).

```python
def _secmon_is_login_mfa(self):
    return bool(request and request.session.get('pre_uid') == self.id
                and not request.session.uid)
```

- `detached=True`인 이유: `login_failed`와 같은 방식이다. 지금 컨트롤러는 예외를 받아서 처리하므로 롤백되지 않지만, 다른 호출 경로를 생각해 롤백돼도 남게 한다.
- 한도 초과도 같은 `AccessDenied`라 같은 유형으로 남는다. 구분은 `detail.reason` 문구로 한다 (번역 문구라 집계 키로 쓰지 않는다).

### 5. ④' 신뢰 기기: `auth_totp.device` 상속 (새 파일 `models/auth_totp_device.py`)

```python
class AuthTotpDevice(models.Model):
    _inherit = 'auth_totp.device'

    def _check_credentials_for_uid(self, *, scope, key, uid):
        ok = super()._check_credentials_for_uid(scope=scope, key=key, uid=uid)
        if ok and scope == 'browser' and request \
                and request.session.get('pre_uid') == uid and not request.session.uid:
            user = self.env['res.users'].sudo().browse(uid)
            collector.record(self.env, 'hook_login', 'login_success',
                             user_id=uid, login=user.login,
                             auth_method='trusted_device')
        return ok
```

### 6. 탐지 룰: R-02·R-03이 대기 단계도 보게 하기

`edb.security.rule`(`models/security_rule.py`)에 필드를 하나 추가한다.

```python
include_mfa_pending = fields.Boolean(
    string='2단계 인증 대기 포함',
    help='대상 이벤트가 로그인 성공일 때, 비밀번호만 통과하고 2단계 인증을 기다리는 시점도 함께 본다.')
```

- 룰 폼에서 `event_type == 'login_success'`일 때만 보이게 한다.
- 대상 유형 목록을 돌려주는 메서드 하나를 두고, 유형을 비교하는 두 곳에서 쓴다.

```python
def _event_types(self):
    self.ensure_one()
    types = [self.event_type]
    if self.include_mfa_pending and self.event_type == 'login_success':
        types.append('login_mfa_pending')
    return types
```

  - `_base_domain` (`security_rule.py:98`): `('event_type', '=', self.event_type)` → `('event_type', 'in', self._event_types())`
  - `_evaluate_new_ip`의 "본 적 있는 IP" 조회 (`security_rule.py:140`): 같은 식으로 바꾼다. 그래야 대기 단계에서 본 IP도 "본 적 있음"으로 친다.
- 기본 룰 데이터 `data/security_rule_data.xml`의 R-02·R-03에 `<field name="include_mfa_pending" eval="True"/>`를 추가한다.
- **이미 설치된 DB**: 이 파일은 `noupdate="1"`이라 업그레이드해도 반영되지 않는다. `migrations/19.0.2.1.0/post-migrate.py`에서 `edb_security.rule_r02`·`rule_r03`의 `include_mfa_pending`을 True로 바꾼다. 단 고객사가 지운 룰이면 건너뛴다(`env.ref(..., raise_if_not_found=False)`).
- R6(알림 중복 방지): R-02의 그룹 키는 `login@IP`, R-03은 `login`이다. 대기 → 성공이 같은 키로 이어지므로 기존 중복 억제(30분, `_in_cooldown`)가 두 번째 히트를 막는다. 따로 코드를 넣지 않는다. 단 중복 억제를 0으로 바꾼 룰은 두 번 발동한다 (SEC-4에서 다룸).

### 7. 알림에 단계 표시 (R5)

`security_rule_hit.py` `_notify_hit`의 `note`에, 히트에 연결된 이벤트가 전부 `login_mfa_pending`이면 `단계: 비밀번호 통과, 2단계 인증 대기`를 한 줄 덧붙인다. 개인정보가 아니므로 메일로 나가도 된다.

### 8. 화면

- 이벤트 목록·검색 필터: 새 유형이 selection에 들어가므로 따로 손댈 것은 없다. 검색 뷰에 "로그인 관련"(성공·실패·대기·2FA 실패) 필터가 있으면 새 유형을 더한다.
- 대시보드 로그인 실패 KPI는 `login_failed`만 센다. **이번 작업에서는 바꾸지 않는다** (미결 1).

## 시험 (개발자가 추가할 테스트)

`tests/test_login_hook.py`에 추가한다. 2FA 사용자는 `totp_secret`을 sudo로 직접 써서 만든다. TOTP 토큰을 만드는 방법은 코어 `odoo/addons/auth_totp/tests/test_totp.py`의 `TestTOTPMixin.install_totphook`을 참고한다.

| 테스트 | 확인할 것 |
|---|---|
| `test_mfa_user_password_step_records_pending` | 2FA 사용자로 `/web/session/authenticate` → `login_mfa_pending` 1건, `login_success` 0건 |
| `test_mfa_wrong_code_records_mfa_failed` | `/web/login/totp`에 틀린 코드 POST → `login_mfa_failed` 1건(`user_id` 채워짐) |
| `test_mfa_right_code_records_success` | 맞는 코드 → `login_success` 1건, `auth_method='totp'` |
| `test_trusted_device_records_success` | 신뢰 기기 쿠키로 GET → `login_success`, `auth_method='trusted_device'` |
| `test_non_mfa_user_unchanged` | 2FA 없는 사용자 → 지금처럼 ①에서 `login_success` |
| `test_identitycheck_totp_not_recorded` | 로그인 중이 아닐 때(`pre_uid` 없음) `_check_credentials(type='totp')` → 기록 없음 |
| `test_r02_fires_on_mfa_pending_once` | 관리자 새 IP 대기 → R-02 히트 1건. 이어서 같은 IP 성공 → 히트 추가 없음 |

HTTP 테스트(`HttpCase`)는 서버를 띄우므로, 로컬 서버(8170)가 떠 있으면 `--http-port`를 다른 값으로 준다.

## 대안 검토 (택하지 않은 방향)

- **`Session.finalize()`를 몽키패치해 진짜 로그인 시점 하나로 잡기**: 모델이 아니라 `odoo/http.py`의 클래스 메서드라 상속으로 덮을 수 없다. 몽키패치는 다른 모듈과 충돌하고 업그레이드 때 깨지기 쉬워서 택하지 않았다.
- **`login_success`는 두고 `detail`에 `mfa: pending`만 표시**: 유형이 같아서 룰·집계·화면이 계속 "성공"으로 센다. 문제 1을 해결하지 못한다.
- **R-02·R-03을 대기 단계용으로 복제(R-02P 등)**: 룰이 늘어나고, 대기 → 성공에서 알림이 두 번 간다 (룰이 다르면 중복 억제가 안 걸림).
- **모든 `login_success` 룰에 대기 단계를 자동 포함**: 고객사가 만든 룰의 의미가 몰래 바뀐다. 룰마다 켜는 필드로 드러냈다.

## 영향 범위 / 리스크

- 건드리는 파일: `__manifest__.py`, `models/security_event.py`, `models/res_users.py`, `models/auth_totp_device.py`(새 파일), `models/__init__.py`, `models/security_rule.py`, `models/security_rule_hit.py`, `views/security_rule_views.xml`, `data/security_rule_data.xml`, `migrations/19.0.2.1.0/post-migrate.py`(새 파일), `tests/test_login_hook.py`, `tests/test_rules.py`, `README.md` (B1·B2의 로그인 기록 설명).
- 로그인 경로에 코드가 늘어난다. 2FA 검사 경로는 원래 1시간 5회 한도가 있어 호출 수가 적다.
- 코어 `Session.authenticate`의 2FA 판단 조건이 바뀌면 3번 판단이 어긋난다. Odoo 버전을 올릴 때 다시 확인한다.
- 17·18 백포트(README B5): 17·18의 `_login`은 classmethod라 3번을 다시 짜야 한다. 이 문서는 19 기준이다.

## 미결 / 열린 질문

- [ ] 1. 대시보드 "로그인 실패" KPI에 `login_mfa_failed`를 합칠지 (지금은 비밀번호 실패만 셈)
- [ ] 2. 2FA 실패 반복을 잡는 기본 룰(예: 계정별 1시간 3회)을 추가할지. 코어 한도가 1시간 5회라 그 아래로 잡아야 의미가 있다
- [ ] 3. 대기 상태로 끝난 로그인(2FA를 끝내지 않고 떠난 경우)을 따로 보여 줄지

## 관련

- 작업목록: `~/Downloads/공통보안모듈_작업목록_261105.xlsx` SEC-1 (원본은 담당자 PC)
- 모듈 README: `19.0/edb_security/README.md` B1·B2·B5
- 관련 항목: AUTH-1(2단계 인증 강제), LOG-2(로그인 기록), SEC-4(중복 억제 0일 때 반복)

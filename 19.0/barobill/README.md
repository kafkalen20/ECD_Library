# 바로빌 (Barobill) — 공통 베이스

바로빌(전자문서·메시징 서비스)의 **SOAP API 연동 공통 기반** 모듈. SMS·FAX·알림톡·
세금계산서·현금영수증 등 채널 모듈들이 공유하는 **계정 설정, 인증정보, 오류 조회,
포인트 잔액 조회**를 담당한다. 이 모듈은 직접 발송 기능이 없고, 채널 모듈이 `depends`로
얹혀서 동작한다.

> 이 저장소(`ECD_Library`)에서 유일하게 `application: True`인 바로빌 "앱"이며,
> 채널 모듈(`barobill_*`)은 모두 `application: False`로 이 앱 아래 메뉴에 붙는다.

---

## 핵심 개념: 계정은 하나, 엔드포인트는 채널별

모든 채널이 **하나의 바로빌 계정**을 쓴다. 그래서 인증정보는 공통 키 한 벌로 관리하고,
서버 주소(SOAP 엔드포인트)만 채널·환경별로 따로 둔다.

### 공통 설정 키 (`barobill.*`)
| 키 | 설명 |
|----|------|
| `barobill.mode` | 활성 환경 `'test'` \| `'prod'` (각 채널이 어느 서버를 쓸지 결정) |
| `barobill.certkey` | 연동인증키(CERTKEY) |
| `barobill.corpnum` | 사업자등록번호(10자리) |
| `barobill.id` | 바로빌 ID |
| `barobill.test.server` / `barobill.prod.server` | 공통 API(오류·포인트 조회)용 서버 URL |
| `barobill.point.balance` / `barobill.point.checked_at` | 최근 조회한 포인트 잔액(현재값만) |

> **인증정보·비밀번호는 소스에 커밋하지 않는다.** 설치 후 **설정 > 바로빌** 화면에서
> 직접 입력한다. 소스에는 공개 엔드포인트 기본값(`common.py`의 `DEFAULT_SERVER`)만 둔다.

---

## 아키텍처 (채널 모듈이 따르는 하우스 규칙)

### 1. config 헬퍼 — `models/common.py`
인증정보를 여기저기서 직접 읽지 않고 반드시 헬퍼를 거친다.
- `get_shared_mode(env)` → `'test'` \| `'prod'`
- `get_shared_auth(env)` → `(certkey, corpnum, id)`
- `get_base_server(env)` → 공통 API(오류·포인트 조회)용 서버 URL

### 2. SOAP 호출은 컨트롤러로 분리 — `controllers/barobill.py`
실제 SOAP 호출(`client.service.*`)은 모델이 아니라 **컨트롤러**의 평범한 파이썬 클래스에
둔다(이 저장소 관례이며 `odoo.http.Controller`가 아님).

```python
class BarobillController:
    def __init__(self, server, certkey): ...
    @property
    def client(self):          # zeep.Client — 최초 사용 시점에 lazy 생성
    def _get_err_string(self, err_code):          # 오류코드 → 사람이 읽는 메시지
    def _get_balance_cost_amount(self, corpnum):  # 포인트 잔액 조회
```
채널 모듈은 이 클래스를 상속해 채널 API 메서드만 덧붙인다.

### 3. 오류 규약
바로빌은 실패 시 **음수 5자리 문자열**(`^-[0-9]{5}$`, 또는 `int(result) < 0`)을 돌려준다.
이때 `_get_err_string()`로 메시지를 조회해 사용자에게 안내한다.

### 4. 포인트 잔액
`res_config_settings.py`의 **시간당 cron**(`_cron_check_barobill_point_balance`)과
설정 화면의 "지금 조회" 버튼이 `GetBalanceCostAmountEx`를 호출한다. 이력 없이 현재값만 저장.

---

## 구조

```
barobill/
├── __manifest__.py                 # depends: base / python: zeep / application: True
├── controllers/barobill.py         # BarobillController (SOAP 베이스, lazy zeep client)
├── models/
│   ├── common.py                   # 공통 config 헬퍼 (get_shared_*)
│   └── res_config_settings.py      # 공통 인증/모드 설정 + 포인트 조회 cron·버튼
├── data/
│   ├── ir_config_parameter.xml     # 공통 키 빈 값으로 생성
│   └── ir_cron_data.xml            # 포인트 잔액 시간당 조회 cron
└── views/
    ├── res_config_settings_views.xml   # 설정 > 바로빌 (앱 루트 폼)
    └── menu.xml                        # barobill_menu_root (채널 메뉴가 붙는 루트)
```

---

## 설정 방법

1. `barobill`과 필요한 채널 모듈을 설치한다.
2. **설정 > 바로빌**에서 모드(test/prod), 연동인증키, 사업자번호, 바로빌 ID,
   환경별 서버 URL을 입력한다.
3. "지금 조회"로 포인트 잔액이 조회되면 연동 정상.

---

## 의존성

- Odoo: `base`
- Python: `zeep` (SOAP 클라이언트)

## 라이선스

LGPL-3

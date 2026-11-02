# ECD_Library

에코두비즈(Ecodoobiz) **사내 공용 Odoo 19 애드온 저장소**. 바로빌 메시징·전자문서,
회사 공통 UX, 보안 감사, 전역 검색 등 내부 모듈을 모아둔다. 각 기능 영역은 독립 모듈
(또는 베이스 모듈 + 의존 채널 모듈)이며, `depends`로 선언하지 않는 한 서로 독립적이다.

> **모듈은 `19.0/` 아래에 있다.** `.odoorc`의 addons_path에 등록할 실제 경로는
> 저장소 루트가 아니라 **`ECD_Library/19.0`** 이다.

모듈은 폴더로 묶지 않고 `19.0/` 아래에 **평평하게(flat)** 두고, **접두어 네이밍**으로
논리적 그룹을 표현한다(Odoo `addons_path`는 하위 폴더를 재귀 탐색하지 않으므로 그룹
폴더는 쓰지 않는다 — 자세한 규칙은 아래 [모듈 네이밍·그룹 규칙](#모듈-네이밍그룹-규칙) 참고).

### 바로빌 — 전자문서·메시징 (`barobill_*`)
| 모듈 | 설명 |
|------|------|
| `barobill` | **[베이스]** 공통 계정 설정·오류 조회·포인트 잔액 |
| `barobill_sms` | SMS/LMS (`SendMessage`) |
| `barobill_fax` | FAX (FTP 업로드 → `SendFaxFromFTP` → 상태 폴링) |
| `barobill_alimtalk` | 카카오 알림톡 (`SendATKakaotalksEx`) |
| `barobill_tax_invoice` | 전자세금계산서 (저장/발급/취소) |
| `barobill_cash_receipt` | 현금영수증 (저장/발급/삭제) |

### 회사 공통·보안 (`edb_*`)
| 모듈 | 설명 |
|------|------|
| `edb_common` | **[베이스]** 회사 공통 — 상태 색상·리스트 UX·설정 카테고리 |
| `edb_security` | 보안 — 접속 이력 감사·대시보드 |

### 업무
| 모듈 | 설명 |
|------|------|
| `edb_helpdesk` | 고객센터 (표준 Helpdesk 커스터마이징) |

### 검색
| 모듈 | 설명 |
|------|------|
| `global_search` | 전역 통합검색 (상단 검색창) |

### 인증·로그인 (`edb_auth_*`, 예정)
네이버·구글·카카오 소셜 로그인 등을 **베이스 + provider 채널** 패턴으로 추가 예정
(예: `edb_auth` + `edb_auth_naver` / `edb_auth_google` / `edb_auth_kakao`).

각 모듈 폴더에 **모듈별 README.md**가 있다. 이 문서는 저장소 전체 개요와 바로빌 하우스
규칙을 담는다.

---

## 모듈 네이밍·그룹 규칙

모듈이 늘어도 복잡해지지 않도록, **폴더 중첩 대신 네이밍 규칙**으로 그룹을 표현한다.

1. **평평한 배치** — 모든 모듈은 `19.0/` 바로 아래에 둔다. 기능별 상위 폴더로 묶지 않는다.
   - 이유: Odoo `addons_path`는 등록한 경로의 **바로 아래 한 단계만** 모듈로 스캔한다
     (재귀 안 함). 그룹 폴더를 쓰면 그 폴더마다 `addons_path`에 따로 등록해야 해서
     설정·배포가 오히려 복잡해진다.
2. **접두어로 그룹** — 같은 기능 영역은 **공통 접두어**를 쓴다. 파일 정렬상 자동으로 묶여
   보인다.
   - 바로빌: `barobill`, `barobill_<채널>`
   - 회사 공통/사내 기능: `edb_<기능>` (예: `edb_common`, `edb_security`, `edb_helpdesk`)
   - 인증: `edb_auth`, `edb_auth_<provider>`
   - 범용·독립 유틸은 예외적으로 접두어 없이 기능명을 쓸 수 있다(예: `global_search`).
3. **베이스 + 채널 패턴** — 한 영역에 공통 로직 + 여러 변형이 있으면, 공통은 **베이스
   모듈**로 빼고 변형은 베이스에 `depends`한다(바로빌이 기준 예시).
   - 베이스만 `application: True`, 채널/변형은 `application: False`.
4. **새 기능 영역** — 관련 없는 모듈을 확장하지 말고 **새 최상위 모듈**을 만든다
   (`/addons-init`로 스캐폴드).
5. **문서 동기화** — 새 모듈을 추가하면 ① 모듈 폴더에 `README.md`, ② 이 문서의 위
   카테고리 목록에 한 줄 추가한다.

> 참고: 플랫 + 접두어는 Odoo 생태계의 표준 방식이다(OCA 등 대형 저장소도 모듈 수백 개를
> 전부 플랫으로 둔다). 목록 파악은 폴더가 아니라 이 README의 카테고리 인덱스가 담당한다.

---

## 바로빌 아키텍처

바로빌(한국 전자문서·메시징 서비스)은 SMS/LMS·팩스·알림톡·세금계산서·현금영수증을
SOAP API(`zeep`)로 처리한다. 채널 모듈은 모두 `barobill`에 `depends`하며
`application: False`이고, `barobill`만 `application: True`다.

### 계정은 하나, 엔드포인트는 채널별
모든 채널이 **하나의 바로빌 계정**을 쓴다. 인증값은 공통 키 한 벌로 두고
`barobill/models/common.py`의 헬퍼로만 읽는다(여기저기서 직접 읽지 않는다).

- `barobill.mode` — 활성 환경 `'test'` | `'prod'` (각 채널이 어느 **서버 엔드포인트**를
  쓸지 결정. 인증값은 공통 유지)
- `barobill.certkey` / `barobill.corpnum` / `barobill.id` — CERTKEY, 사업자번호(10자리), 바로빌 ID
- 헬퍼(설정 조회 전용): `get_shared_mode(env)`, `get_shared_auth(env)` → `(certkey, corpnum, id)`,
  `get_base_server(env)`

**채널별** 서버 URL 등은 각 채널 모듈의 `res_config_settings.py`에 `barobill_<채널>.<mode>.server`
키로 둔다(예: `barobill_fax.test.server`, `barobill_fax.test.ftp_host`). 일부는 레거시
단일 키 fallback(`barobill_sms.server`)을 유지한다.

**비밀값(certkey/corpnum/id, FTP 비밀번호)은 소스에 커밋하지 않는다** — 설치 후
설정 > 바로빌 화면에서 직접 입력한다.

### SOAP 호출은 컨트롤러로 분리
원시 SOAP 호출(`client.service.*`)은 모델이 아니라 `controllers/`의 **평범한 파이썬 클래스**에
둔다(하우스 규칙; `odoo.http.Controller` 아님). 베이스 `barobill/controllers/barobill.py` →
`BarobillController(server, certkey)` : lazy `client`(`zeep.Client`), `_get_err_string(err_code)`,
`_get_balance_cost_amount(corpnum)`. 각 채널이 이를 상속해 채널 API 메서드를 더한다:
`BarobillSmsController._send_message(...)`, `BarobillFaxController._send_fax_from_ftp(...)` /
`_get_fax_message(...)`, `BarobillAlimtalkController._send_at_kakaotalks(...)`,
세금계산서·현금영수증 컨트롤러는 `ns0:` 복합타입을 내부에서 조립한다.

모델은 설정을 해석한 뒤 `self._get_barobill_api()`를 호출한다 →
`(controller, corpnum, barobill_id[, yellowid])` 반환. 모델은 업무 로직(검증·상태·결과 로깅),
컨트롤러는 SOAP 호출만. **새 바로빌 API를 추가할 때는 모델에 `client.service.X`를 쓰지 말고
해당 컨트롤러에 `_메서드`를 추가한다.**

### 채널별 모델 패턴
각 채널은 발송(문서) 모델 + 결과 로그 모델로 같은 모양을 따른다.

- `barobill.<채널>` — `_get_barobill_config()`(설정 검증, 누락 시 `UserError`로 빠진 항목 안내),
  `_get_barobill_api()`(채널 컨트롤러 생성), 액션 메서드들, `state` 상태머신.
- `barobill.<채널>.result` — 발송/처리마다 `.sudo().create(...)`로 남기는 append-only 로그.

### 오류 규약
바로빌은 실패 시 **음수 5자리 문자열**(`^-[0-9]{5}$`, 또는 `int(result) < 0`)을 돌려준다.
오류면 컨트롤러의 `_get_err_string()`로 메시지를 조회해 `error_message`에 저장하고 상태를
유지/실패 처리한다. 성공 시 전송키/관리번호 등을 반환한다.

### 채널 특이사항
- **FAX** (`barobill_fax`): 2단계 — 파일을 바로빌 FTP에 업로드 후 `SendFaxFromFTP`. FTP는
  CP949/MS949(한국 윈도우); CP949 불가 파일명은 UUID로 치환. 바로빌 일시는 KST
  `YYYYMMDDHHMMSS`, `_parse_barobill_dt()`로 UTC-naive 변환. **2분 cron**
  (`_cron_check_pending_status`)이 진행 중 팩스를 폴링. 결과 이력은 상태 *전이*만 기록.
  `FAX_SEND_STATES` / `FAX_SEND_RESULTS` / `ALLOWED_EXTENSIONS` 참고.
- **알림톡** (`barobill_alimtalk`): `YellowId`(발신프로필)와 사전 승인 `TemplateName` 필요.
  본문이 템플릿과 다르면 발송 거부. SOAP 복합타입은 `_send_at_kakaotalks` 내부에서 조립.
- **세금계산서** (`barobill_tax_invoice`): 공급자/공급받는자 + 품목 라인. 정발행이라 공급받는자
  MgtNum은 비움. 국세청 발행에는 바로빌 계정에 공동인증서 등록 필요.
- **현금영수증** (`barobill_cash_receipt`): 라인 없는 단일 문서(가맹점+거래정보+금액).
- **포인트 잔액** (`barobill/res_config_settings.py`): 시간당 cron
  (`_cron_check_barobill_point_balance`) + "지금 조회" 버튼이 `GetBalanceCostAmountEx` 호출.
  이력 없이 현재값만 `barobill.point.balance` / `barobill.point.checked_at`에 저장.

---

## 공통 규칙

- UI 문자열·필드 라벨·docstring·오류 메시지는 **한국어**. 수정 시 맞춘다.
- Python 의존성: `zeep`(전 바로빌), `pytz`(fax·tax_invoice·cash_receipt). 각
  `__manifest__.py`의 `external_dependencies`에 선언.
- 결과(로그) 모델은 `base.group_user`에 읽기/생성만 부여(수정·삭제 불가) —
  `security/ir.model.access.csv` 참고.
- 이 디렉토리는 **git 저장소가 아니다.** 별도 Odoo 서버 인스턴스가 로드하는 애드온 경로다.

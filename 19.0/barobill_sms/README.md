# 바로빌 SMS

바로빌 API로 **SMS/LMS 문자를 발송**하는 채널 모듈. `barobill` 베이스에 얹혀 동작하며,
화면에서 직접 작성해 보내거나(발송 화면), 다른 모듈이 모델을 호출해 발송할 수 있다.

> 같은 패턴의 형제 모듈: `barobill_fax`, `barobill_alimtalk`, `barobill_tax_invoice`,
> `barobill_cash_receipt`. 공통 계정·인증·오류 규약은 `barobill` README 참고.

---

## 주요 기능

- **SMS/LMS 발송** — 내용 길이에 따라 자동 선택(`SendMessage`).
- **발송 화면** — 발신/수신번호, 수신자명, 내용을 입력해 바로 발송.
- **발송 결과 로그** — 발송할 때마다 결과(성공/실패)를 이력 모델에 기록(append-only).
- **환경 전환** — 공통 `barobill.mode`(test/prod)에 따라 SMS 서버 엔드포인트가 전환된다.

---

## 모델

- **`barobill.sms`** — 발송 레코드(초안). 상태머신 `state`: `draft`(대기) → `sent`(전송성공)
  \| `failed`(전송실패).
  - `_get_barobill_config()` : 설정 검증(누락 시 `UserError`로 빠진 항목 안내)
  - `_get_barobill_api()` : SMS 컨트롤러 + `(corpnum, barobill_id)` 생성
  - `action_send_sms()` : 발송 → 결과 로그 생성 → 상태 갱신
  - `action_reset()` : 상태 초기화
- **`barobill.sms.result`** — 발송 결과 로그(읽기/생성만, 수정·삭제 불가).

---

## 설정

채널 서버 URL만 이 모듈에서 관리하고, 인증정보는 공통(`barobill.*`)을 쓴다.

| 설정 키 | 설명 |
|---------|------|
| `barobill_sms.test.server` / `barobill_sms.prod.server` | 환경별 SMS SOAP 서버 URL |
| `barobill_sms.server` | (하위호환) 단일 키 fallback |
| `barobill_sms.default_from` | 기본 발신번호 |

**설정 > 바로빌 > SMS** 블록에서 입력한다. 테스트 서버 예: `https://testws.baroservice.com/SMS.asmx?WSDL`

---

## 사용법

1. 메뉴 **바로빌 > SMS > 전송**에서 새 레코드 작성.
2. 수신번호·내용 입력 후 **메시지 발송**.
3. 성공 시 전송키 저장, 실패 시 오류메시지 표시. 이력은 **결과** 메뉴에서 확인.

---

## 구조

```
barobill_sms/
├── __manifest__.py                         # depends: barobill / python: zeep
├── controllers/barobill_sms.py             # BarobillSmsController._send_message (SendMessage)
├── models/
│   ├── barobill_sms.py                      # barobill.sms (발송 + 상태머신)
│   ├── barobill_sms_result.py               # barobill.sms.result (결과 로그)
│   └── res_config_settings.py               # 채널 서버 URL·기본 발신번호
├── data/ir_config_parameter.xml            # 채널 설정 키 빈 값 생성
├── security/ir.model.access.csv            # 결과 모델은 읽기/생성만
└── views/                                   # 발송·결과·설정·메뉴
```

---

## 의존성 / 라이선스

- Odoo: `barobill` · Python: `zeep`
- LGPL-3

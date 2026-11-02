# 바로빌 알림톡 (카카오톡)

바로빌 API로 **카카오톡 알림톡을 발송**하는 채널 모듈. 사전 승인된 템플릿으로만
보낼 수 있으며, `barobill` 베이스에 얹혀 동작한다.

> 같은 패턴의 형제 모듈: `barobill_sms`, `barobill_fax`, `barobill_tax_invoice`,
> `barobill_cash_receipt`. 공통 계정·인증·오류 규약은 `barobill` README 참고.

---

## 주요 기능

- **알림톡 발송** — `SendATKakaotalksEx` 사용. 여러 수신자 동시 발송 지원.
- **발송 화면** — 발신프로필(YellowId)·템플릿·수신자·내용을 넣어 발송.
- **발송 결과 로그** — 발송 결과(성공/실패)를 이력 모델에 기록.
- **환경 전환** — 공통 `barobill.mode`(test/prod)에 따라 알림톡 서버 엔드포인트가 전환된다.

---

## 알림톡 필수 조건

- **YellowId(발신프로필)** — 카카오 비즈니스 채널 식별자.
- **TemplateName(템플릿명)** — 카카오에서 사전 승인된 템플릿. 본문이 템플릿과 다르면 발송 거부.
- SOAP 복합타입(`client.get_type('ns0:...')`)은 컨트롤러
  `BarobillAlimtalkController._send_at_kakaotalks` 안에서 조립.

---

## 모델

- **`barobill.alimtalk`** — 발송 레코드. 상태머신 `state`: `draft` → `sent` \| `failed`.
  - `_get_barobill_config()` / `_get_barobill_api()` : 설정 검증 + 컨트롤러 생성
    (알림톡은 `(controller, corpnum, barobill_id, yellowid)` 반환)
  - `action_send_*()` : 발송 → 결과 로그 → 상태 갱신
  - `action_reset()` : 상태 초기화
- **`barobill.alimtalk.result`** — 발송 결과 로그.

---

## 설정

| 설정 키 | 설명 |
|---------|------|
| `barobill_alimtalk.test.server` / `barobill_alimtalk.prod.server` | 환경별 알림톡 SOAP 서버 URL |
| `barobill_alimtalk.yellowid` | 발신프로필(YellowId) |

**설정 > 바로빌 > 알림톡** 블록에서 입력.
테스트 서버 예: `https://testws.baroservice.com/KAKAOTALK.asmx?wsdl`

---

## 사용법

1. 메뉴 **바로빌 > 알림톡 > 전송**에서 레코드 작성.
2. 템플릿·수신자·본문(템플릿과 일치) 입력 후 발송.
3. 결과는 **결과** 메뉴에서 확인.

---

## 구조

```
barobill_alimtalk/
├── __manifest__.py                         # depends: barobill / python: zeep
├── controllers/barobill_alimtalk.py        # _send_at_kakaotalks (ns0 복합타입 조립)
├── models/
│   ├── barobill_alimtalk.py                 # barobill.alimtalk (발송·상태)
│   ├── barobill_alimtalk_result.py          # barobill.alimtalk.result (결과 로그)
│   └── res_config_settings.py               # 서버 URL·YellowId
├── data/ir_config_parameter.xml
├── security/ir.model.access.csv
└── views/                                   # 발송·결과·설정·메뉴
```

---

## 의존성 / 라이선스

- Odoo: `barobill` · Python: `zeep`
- LGPL-3

# 바로빌 현금영수증

바로빌 API로 **현금영수증을 발행**하는 채널 모듈. 화면에서 직접 작성해
**저장 → 발급 → (삭제)** 전 과정을 수행한다. `barobill` 베이스에 얹혀 동작하며,
특정 프로젝트 전용 필드에 의존하지 않는 **독립 모듈**이다.

> 같은 패턴의 형제 모듈: `barobill_sms`, `barobill_fax`, `barobill_alimtalk`,
> `barobill_tax_invoice`. 공통 계정·인증·오류 규약은 `barobill` README 참고.

---

## 주요 기능

- **현금영수증 API** — 저장(`RegistCashBillEx`), 수정(`UpdateCashBillEx`),
  발급(`IssueCashBill`), 상태조회(`GetCashBillState` → 국세청 승인번호),
  삭제(`DeleteCashBill`), 조회URL(`GetCashBillPopUpURL`).
- **직접 작성 화면** — 가맹점(발행자) 정보 + 거래정보(거래구분/용도/방법·신분확인번호·
  품목·공급가액·부가세)를 입력해 발행. 고객 선택 시 연락처/이메일 자동 채움.
- **처리 이력 로그** — 저장/발급/삭제 결과를 기록(성공/실패).

---

## 거래 구분값

- **거래구분**: `N` 승인거래 / `D` 취소거래
- **거래용도**: `1` 소득공제 / `2` 지출증빙
- **거래방법(신분확인수단)**: `5` 휴대폰(자진발급 포함) / `1` 카드번호 / `3` 주민등록번호 /
  `4` 사업자번호

---

## 상태머신

```
draft(작성) → save(저장) → issued(발급)
                 └─ delete ─→ draft
draft → cancel(로컬 취소)
```
> **취소(action_cancel)는 작성(draft) 상태의 로컬 취소**다(바로빌 호출 없음).
> 발급된 현금영수증의 국세청 취소(취소거래 `D`)는 포함하지 않는다.

---

## 모델

- **`barobill.cash_receipt`** — 현금영수증(라인 없는 단일 문서).
  - 가맹점(발행자) 정보, 거래정보, `amount`/`tax`/`amount_total`,
    `management_number`(관리번호), `confirm_number`(국세청 승인번호)
  - `_get_barobill_config()` / `_get_barobill_api()` : 설정 검증 + 컨트롤러 생성
  - `action_regist()` / `action_update()` / `action_issue()` / `action_delete()` /
    `action_cancel()` / `action_popup_url()`
  - 관리번호 규칙: `YYMMDDHHMM-문서번호`(KST)
  - 가맹점 사업자번호·바로빌ID 기본값은 공통 계정(`barobill.corpnum`/`barobill.id`)에서 채움
- **`barobill.cash_receipt.result`** — 처리 이력 로그.

---

## 설정

| 설정 키 | 설명 |
|---------|------|
| `barobill_cash_receipt.test.server` / `barobill_cash_receipt.prod.server` | 환경별 현금영수증 SOAP 서버 URL |

**설정 > 바로빌 > 현금영수증** 블록에서 입력.
- 운영: `https://ws.baroservice.com/CashBill.asmx?WSDL`
- 테스트: `https://testws.baroservice.com/CashBill.asmx?WSDL`

> 현금영수증 발급은 세금계산서와 달리 공동인증서 없이 테스트 서버에서 발급·승인번호
> 수신까지 확인된다.

---

## 사용법

1. 메뉴 **바로빌 > 현금영수증 > 작성**에서 레코드 작성(가맹점/거래정보/금액).
2. **저장** → 바로빌 임시저장(관리번호 발급) → **발급** → 국세청 승인번호 수신.
3. 필요 시 **수정/삭제**, **바로빌 조회**로 원본 확인.
4. 처리 이력은 폼의 이력 탭 또는 **결과** 메뉴에서 확인.

---

## 구조

```
barobill_cash_receipt/
├── __manifest__.py                             # depends: barobill / python: zeep, pytz
├── controllers/barobill_cash_receipt.py        # 현금영수증 SOAP API + ns0:CashBillEx 조립
├── models/
│   ├── barobill_cash_receipt.py                 # 단일 문서 + 상태머신 + 액션
│   ├── barobill_cash_receipt_result.py          # 처리 이력
│   └── res_config_settings.py                   # 채널 서버 URL
├── data/
│   ├── ir_config_parameter.xml
│   └── ir_sequence_data.xml                     # 문서번호 시퀀스(CR00001)
├── security/ir.model.access.csv
└── views/                                       # 작성·결과·설정·메뉴
```

---

## 의존성 / 라이선스

- Odoo: `barobill` · Python: `zeep`, `pytz`
- LGPL-3

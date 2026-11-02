# 바로빌 세금계산서

바로빌 API로 **전자세금계산서를 발행**하는 채널 모듈. 화면에서 직접 작성해
**저장 → 발급 → (취소/삭제)** 전 과정을 수행한다. `barobill` 베이스에 얹혀 동작하며,
특정 프로젝트 전용 필드에 의존하지 않는 **독립 모듈**이다.

> 같은 패턴의 형제 모듈: `barobill_sms`, `barobill_fax`, `barobill_alimtalk`,
> `barobill_cash_receipt`. 공통 계정·인증·오류 규약은 `barobill` README 참고.

---

## 주요 기능

- **세금계산서 API** — 저장(`RegistTaxInvoiceEX`), 수정(`UpdateTaxInvoiceEX`),
  발급(`IssueTaxInvoice`), 상태조회(`GetTaxInvoiceStateEX` → 국세청 승인번호),
  삭제(`DeleteTaxInvoice`), 발행취소(`ProcTaxInvoice`), 조회URL(`GetTaxInvoicePopUpURL`).
- **직접 작성 화면** — 공급자·공급받는자 정보와 품목(라인)을 입력해 발행.
  공급받는자는 파트너 선택 시 자동 채움.
- **처리 이력 로그** — 저장/발급/삭제/취소 결과를 기록(성공/실패).

---

## 상태머신

```
draft(작성) → save(저장) → issued(발급)
                 │             │
                 └─ delete ────┘→ draft
         save/cancel → delete → draft
         issued → 발행취소 → cancel
```

---

## 모델

- **`barobill.tax_invoice`** — 세금계산서 헤더.
  - 공급자(invoicer)/공급받는자(invoicee) 정보 필드, `tax_date`, 과세형태·계산서형태·
    영수/청구 구분, `management_number`(관리번호), `approval_number`(국세청 승인번호)
  - `_get_barobill_config()` / `_get_barobill_api()` : 설정 검증 + 컨트롤러 생성
  - `action_regist()` / `action_update()` / `action_issue()` / `action_delete()` /
    `action_cancel()` / `action_popup_url()`
  - 관리번호 규칙: `YYMMDDHHMM-문서번호`(KST). **정발행이므로 공급받는자 MgtNum은 비움**
    (공급자와 동일 시 바로빌 -11028 오류).
- **`barobill.tax_invoice.line`** — 품목 라인(수량·단가로 공급가액/세액 자동계산).
- **`barobill.tax_invoice.result`** — 처리 이력 로그.

---

## 설정

| 설정 키 | 설명 |
|---------|------|
| `barobill_tax_invoice.test.server` / `barobill_tax_invoice.prod.server` | 환경별 세금계산서 SOAP 서버 URL |

**설정 > 바로빌 > 세금계산서** 블록에서 입력.
- 운영: `https://ws.baroservice.com/TI.asmx?WSDL`
- 테스트: `https://testws.baroservice.com/TI.asmx?WSDL`

> ⚠ **발급(국세청 발행)에는 바로빌 계정에 공동인증서 등록이 필요**하다. 미등록 시
> 저장까지는 되지만 발급에서 `-26001` 오류가 난다.

---

## 사용법

1. 메뉴 **바로빌 > 세금계산서 > 작성**에서 레코드 작성(공급자/공급받는자/품목).
2. **저장** → 바로빌 임시저장(관리번호 발급) → **발급** → 국세청 승인번호 수신.
3. 필요 시 **수정/삭제/발행취소**, **바로빌 조회**로 원본 확인.
4. 처리 이력은 폼의 이력 탭 또는 **결과** 메뉴에서 확인.

---

## 구조

```
barobill_tax_invoice/
├── __manifest__.py                             # depends: barobill / python: zeep, pytz
├── controllers/barobill_tax_invoice.py         # 세금계산서 SOAP API + ns0 복합타입 조립
├── models/
│   ├── barobill_tax_invoice.py                  # 헤더 + 상태머신 + 액션
│   ├── barobill_tax_invoice_line.py             # 품목 라인
│   ├── barobill_tax_invoice_result.py           # 처리 이력
│   └── res_config_settings.py                   # 채널 서버 URL
├── data/
│   ├── ir_config_parameter.xml
│   └── ir_sequence_data.xml                     # 문서번호 시퀀스(TI00001)
├── security/ir.model.access.csv
└── views/                                       # 작성·결과·설정·메뉴
```

---

## 의존성 / 라이선스

- Odoo: `barobill` · Python: `zeep`, `pytz`
- LGPL-3

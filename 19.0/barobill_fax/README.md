# 바로빌 FAX

바로빌 API로 **팩스를 발송**하는 채널 모듈. 파일을 바로빌 FTP에 올린 뒤 전송하고,
전송 상태를 주기적으로 조회(폴링)한다. `barobill` 베이스에 얹혀 동작한다.

> 같은 패턴의 형제 모듈: `barobill_sms`, `barobill_alimtalk`, `barobill_tax_invoice`,
> `barobill_cash_receipt`. 공통 계정·인증·오류 규약은 `barobill` README 참고.

---

## 주요 기능

- **2단계 발송** — ① 파일을 바로빌 **FTP에 업로드** → ② `SendFaxFromFTP`로 전송.
- **상태 폴링** — `GetFaxMessageEx2`로 전송 상태 조회. **2분 주기 cron**이 진행 중
  팩스를 자동 갱신(`_cron_check_pending_status`).
- **발송 화면** — 발신/수신번호, 수신자 정보, 첨부파일을 넣어 발송·재전송·상태조회.
- **결과 이력** — 상태가 바뀔 때마다 기록(동일 상태 연속 폴링은 중복 제거).
- **환경 전환** — 공통 `barobill.mode`(test/prod)에 따라 FAX 서버·FTP 엔드포인트가 전환된다.

---

## 동작 특이점 (중요)

- **FTP 인코딩**: 바로빌 FTP 서버는 CP949/MS949(한국 윈도우). CP949로 인코딩 불가한
  파일명은 UUID로 치환해 업로드.
- **시각 변환**: 바로빌 API 일시는 KST `YYYYMMDDHHMMSS`. `_parse_barobill_dt()`가
  Odoo용 UTC-naive로 변환.
- **폴링 대상**: `send_key`가 있고 `send_state`가 0/1/2이며 생성 12시간 이내인 건.
- 상태·결과 코드/허용 확장자는 `FAX_SEND_STATES` / `FAX_SEND_RESULTS` /
  `ALLOWED_EXTENSIONS` 상수로 정의.

---

## 모델

- **`barobill.fax`** — 발송 레코드. 상태머신 `state`: `draft` → `sent`(전송접수) →
  `success`(전송완료) \| `failed`(전송실패).
  - `_get_barobill_config()` / `_get_barobill_api()` : 설정 검증 + 컨트롤러 생성
  - `action_send_fax()` : FTP 업로드 → 전송
  - `action_check_status()` : 상태 조회
  - `_cron_check_pending_status()` : 진행 중 팩스 일괄 폴링(cron)
- **`barobill.fax.result`** — 전송 상태 이력 로그.

---

## 설정

| 설정 키 | 설명 |
|---------|------|
| `barobill_fax.test.server` / `barobill_fax.prod.server` | 환경별 FAX SOAP 서버 URL |
| `barobill_fax.test.ftp_host` / `barobill_fax.prod.ftp_host` | 환경별 FTP 호스트 |
| `barobill_fax.test.ftp_port` / `barobill_fax.prod.ftp_port` | 환경별 FTP 포트 |
| `barobill_fax.ftp_password` | FTP 비밀번호(비밀) |
| `barobill_fax.default_from` | 기본 발신번호 |

**설정 > 바로빌 > FAX** 블록에서 입력. 테스트 서버 예: `https://testws.baroservice.com/FAX.asmx?WSDL`

---

## 사용법

1. 메뉴 **바로빌 > FAX > 전송**에서 레코드 작성, 파일 첨부.
2. **전송** → 상태 `전송접수`. cron 또는 **상태 조회**로 `전송완료`/`전송실패` 갱신.
3. 결과 이력은 폼의 이력 탭 또는 **결과** 메뉴에서 확인.

---

## 구조

```
barobill_fax/
├── __manifest__.py                     # depends: barobill / python: zeep, pytz
├── controllers/barobill_fax.py         # SendFaxFromFTP, GetFaxMessageEx2
├── models/
│   ├── barobill_fax.py                  # barobill.fax (FTP 업로드·전송·폴링·상수)
│   ├── barobill_fax_result.py           # barobill.fax.result (상태 이력)
│   └── res_config_settings.py           # 서버/FTP 설정
├── data/
│   ├── ir_config_parameter.xml         # 채널 설정 키
│   └── ir_cron_data.xml                # 2분 주기 상태 폴링 cron
├── security/ir.model.access.csv
└── views/                               # 발송·설정·메뉴
```

---

## 의존성 / 라이선스

- Odoo: `barobill` · Python: `zeep`, `pytz`
- LGPL-3

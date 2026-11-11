---
owner: parkbohee
created: 2026-11-11
updated: 2026-11-11
---
# 모듈 지도

> 모듈별 역할 한 줄. 상세는 각 `19.0/<모듈>/README.md`. 카테고리 설명의 원본은 루트 `README.md`.
> 모듈을 추가·삭제하면 이 표도 같이 고친다. (근거: 각 `__manifest__.py`, 2026-11-11 기준 전부 `19.0.1.0.0`)

| 모듈 | 역할 | depends | application | 라이선스 |
|---|---|---|---|---|
| `barobill` | **[베이스]** 바로빌 공통 계정 설정·오류 조회·포인트 잔액(시간당 cron) | base | ✅ | LGPL-3 |
| `barobill_sms` | SMS/LMS 발송 (`SendMessage`) | barobill | | LGPL-3 |
| `barobill_fax` | FAX — FTP 업로드 → `SendFaxFromFTP` → 2분 cron 상태 폴링 | barobill | | LGPL-3 |
| `barobill_alimtalk` | 카카오 알림톡 (`SendATKakaotalksEx`, 사전 승인 템플릿) | barobill | | LGPL-3 |
| `barobill_tax_invoice` | 전자세금계산서 저장/발급/취소 | barobill | | LGPL-3 |
| `barobill_cash_receipt` | 현금영수증 저장/발급/삭제 | barobill | | LGPL-3 |
| `edb_common` | **[베이스]** 회사 공통 — 상태 색상 토큰·리스트 UX·"Ecodoobiz" 설정 카테고리 | base, web | | OEEL-1 |
| `edb_security` | 접속 이력(디바이스 접속·로그인 실패) 영구 감사 로그·대시보드 | edb_common, base, web | | OEEL-1 |
| `edb_helpdesk` | 표준 Helpdesk 사내 고객센터 커스터마이징(요청자·일자·숫자 ID·단계 알림) | edb_common, helpdesk, helpdesk_timesheet | | OEEL-1 |
| `global_search` | 상단 시스트레이 검색창에서 여러 모델·필드 동시 검색(대상은 화면 설정) | base, web | | LGPL-3 |

## 의존 관계
```
barobill ─┬─ barobill_sms / _fax / _alimtalk / _tax_invoice / _cash_receipt
edb_common ─┬─ edb_security
            └─ edb_helpdesk (+ helpdesk, helpdesk_timesheet — EE)
global_search (독립)
```

## 시험
- 2026-11-11 `main` 기준 자동 테스트 파일 없음. [❓확인 필요: 테스트 작성 방침 — 모듈별 `tests/` 필수 여부]

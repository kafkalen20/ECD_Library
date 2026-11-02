# 에코두비즈 보안 (edb_security)

사용자 **접속 이력(디바이스 접속)을 영구 기록·시각화**하는 보안/감사 모듈. 프로젝트에
독립적이며 표준 Odoo(`base`, `web`) + `edb_common`에만 의존한다.

> Odoo 코어의 `res.device` / `res.device.log`는 세션·기기별 **마지막** 접속만 유지하고
> 주기적으로 정리한다. 이 모듈은 **접속마다 1행을 남기는 영구 감사 로그**(+ 로그인 실패
> 이벤트)를 추가한다.

---

## 추가되는 기능

1. **접속 감사 로그** — 새 세션/기기 접속, 또는 1시간 유휴 후 재접속마다 1행 기록.
   기기/OS·브라우저·시각·IP·사용자 저장. **로그인 실패**도 별도 기록.
2. **정교한 UA 파싱** — OS 계열·기기구분(PC/모바일)을 보정하고, 코어가 "chrome"으로
   뭉뚱그리는 브라우저(웨일/삼성인터넷/엣지/비발디/오페라/iOS 크롬·파이어폭스 등)를 구분.
3. **접속 현황 대시보드**(OWL) — KPI(오늘/WAU/MAU/로그인실패), 추이·기기·시간대·요일 차트,
   사용자별·미접속자 표, 최근 로그인 실패. 주/월/년 토글 + **엑셀 내보내기**.
4. **보관 기간 관리** — 오래된 로그 자동 삭제(autovacuum).

---

## 핵심 동작

### 기록 경로 2가지 (둘 다 별도 writable 커서 사용 → 트랜잭션 롤백에도 로그 보존)
- **성공 접속** : `res.device.log._update_device` 오버라이드. `_edb_should_log()`로 게이팅
  (최초 접속 또는 1시간 유휴 후 재접속), 로그인 사용자만. 동일 세션·기기·분(minute) 중복은
  부분 유니크 인덱스 + `ON CONFLICT DO NOTHING`으로 방지.
- **로그인 실패** : `res.users._login` 오버라이드가 `AccessDenied`를 잡아
  `event_type='login_failed'`로 기록(별도 커서라 인증 롤백에도 남음).

### 엑셀 내보내기
- 컨트롤러 `GET /edb_security/device_access/export?period=...` → `build_dashboard_xlsx`로
  5개 시트(요약/접속추이/사용자별/미접속/로그인실패) 생성.

---

## 모델

- **`edb.device.access`**(신규) — 접속 내역. `models/edb_device_access.py`
  - 필드: `user_id`, `session_identifier`, `access_datetime`, `device`, `browser`,
    `access_detail`(원본 UA), `os_family`, `device_type`(PC/모바일), `ip_address`,
    `event_type`(access/login_failed), `login`(실패 시 시도한 로그인값)
  - `init()` : 분단위 중복 제거 + 부분 유니크 인덱스 생성
  - `get_access_dashboard_data(period)` : 대시보드 집계(week/month/year)
  - `build_dashboard_xlsx(period)` : 엑셀 생성(xlsxwriter)
  - `_edb_log_access()` / `_edb_log_failed_login()` : 이벤트 insert(별도 커서)
  - `@api.autovacuum _gc_device_access()` : 보관기간 지난 로그 삭제
- **`res.users`**(상속) — `_login()` 오버라이드(로그인 실패 캡처)
- **`res.device.log`**(상속) — `_update_device()` 오버라이드(성공 접속 캡처)

---

## 설정 / 권한

- **보관 기간**: 시스템 파라미터 `edb_security.device_access_retention_days`(기본 365,
  `0`이면 삭제 안 함). 설정 > 기술 > 시스템 파라미터에서 조정. (별도 설정 화면 없음)
- **접근권한**(`security/ir.model.access.csv`): 일반 사용자 **읽기 전용**,
  시스템 관리자 **전체**. 리스트/폼도 생성·수정·삭제 비활성(열람용 이력).

---

## 메뉴

**설정 > 사용자 및 회사 > 접속 정보** → 대시보드(client action). 전체 목록은 대시보드의
"전체 보기"로 진입.

---

## 구조

```
edb_security/
├── __manifest__.py                         # depends: edb_common, base, web
├── models/edb_device_access.py             # edb.device.access + res.users/res.device.log 훅
├── controllers/device_access.py            # 엑셀 내보내기 라우트
├── security/ir.model.access.csv            # 사용자 읽기 / 관리자 전체
├── views/edb_device_access_views.xml       # 대시보드·리스트·폼·검색·메뉴·보관기간 파라미터
└── static/src/dashboard/                   # OWL 대시보드(js/xml/css, Chart.js)
```

---

## 의존성 / 라이선스

- Odoo: `edb_common`, `base`, `web` · Python: `xlsxwriter`(엑셀 내보내기)
- OEEL-1

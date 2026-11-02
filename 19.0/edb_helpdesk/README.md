# 에코두비즈 고객센터 (edb_helpdesk)

Odoo 표준 Helpdesk 위에 얹는 **에코두비즈 내부 고객센터 커스터마이징** 모듈. 표준 티켓
워크플로우를 사내 고객센터 프로세스에 맞게 바꾼다 — 내부 요청자(직원), 자유 입력 담당자,
요청/완료예정/완료 일자, 정렬용 숫자 ID, 단계 변경 시 지정 이메일 알림.

---

## 추가되는 기능

1. **고객센터형 티켓 필드** — 내부 직원 **요청자**, 자유 텍스트 **담당자**,
   **요청일자 / 완료예정일자 / 완료일자**. 검색·리스트·폼에 모두 노출.
2. **숫자 티켓 ID(`ticket_no`)** — 표준 `ticket_ref`(문자 시퀀스)를 정수로 변환·저장·인덱싱.
   리스트를 최신순(내림차순)으로 정렬.
3. **단계 변경 이메일 알림** — 티켓 단계가 바뀔 때, 단계 메일 템플릿의 수신자를
   설정된 **단일 주소**(`edb_helpdesk.notify_email`)로 바꿔 발송. 주소가 비면 표준 동작 유지.
4. **타임시트 연동** — 타임시트 라인(`account.analytic.line`)에 자유 텍스트 **담당자** 추가,
   표준 `user_id` 기본값 제거(담당자를 직접 입력하는 방식이라). 티켓의 타임시트 탭에 표시.
5. **UI 간소화** — 안 쓰는 표준 필드/필터/열(담당자 user, 파트너, SLA, 활동 등)을 숨기고
   단계를 statusbar로 표시.

---

## 모델

- **`helpdesk.ticket`**(상속) — `models/helpdesk_ticket.py`
  - 필드: `requester_id`(hr.employee, 요청자, 필수), `assignee`(Char, 담당자, 추적),
    `request_date`/`expected_completion_date`/`completion_date`(Date),
    `ticket_no`(Integer, 계산·저장·인덱스)
  - `_compute_ticket_no()` : `ticket_ref` → 정수 변환(실패 시 0)
  - `_track_template()` : 단계 변경 시 `edb_helpdesk.notify_email`로 메일 수신자 교체
- **`account.analytic.line`**(상속, 타임시트 라인) — `assignee`(Char) 추가, `user_id` 기본값 제거
- **`res.config.settings`**(상속) — `edb_helpdesk_notify_email`
  (`config_parameter='edb_helpdesk.notify_email'`)

---

## 설정

**설정 > Ecodoobiz > 고객센터**의 "담당자 이메일"에 알림 주소를 입력한다.
비워 두면 표준 Helpdesk 알림 동작을 그대로 쓴다.

---

## 뷰 변경 (`views/helpdesk_ticket_views.xml`)

표준 Helpdesk의 검색/리스트/폼/타임시트 탭 뷰를 상속해 위 필드를 추가하고
안 쓰는 항목을 숨긴다. 리스트 기본 정렬은 `ticket_no desc`, 단계는 statusbar.

---

## 구조

```
edb_helpdesk/
├── __manifest__.py                     # depends: edb_common, helpdesk, helpdesk_timesheet
├── models/
│   ├── helpdesk_ticket.py              # 요청자·담당자·일자·ticket_no·단계알림
│   ├── account_analytic_line.py        # 타임시트 라인 담당자
│   └── res_config_settings.py          # 알림 이메일 설정
└── views/
    ├── helpdesk_ticket_views.xml       # 검색/리스트/폼/타임시트 탭 커스터마이징
    └── res_config_settings_views.xml   # 고객센터 설정 블록
```

> 보안 파일(ir.model.access/record rule)은 없다 — 표준 Helpdesk 권한을 그대로 쓴다.

---

## 의존성 / 라이선스

- Odoo: `edb_common`, `helpdesk`, `helpdesk_timesheet`
- OEEL-1

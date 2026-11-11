---
tags: [edb_helpdesk, helpdesk, sort]
scope: 19.0/edb_helpdesk
date: 2026-11-11
status: accepted
---
# 0002. helpdesk 티켓은 정수 `ticket_no`로 정렬한다

## 맥락 (어떤 업무/요구사항)
Odoo 표준 helpdesk의 티켓 번호 `ticket_ref`는 문자(Char) 시퀀스다. Odoo 18까지 티켓 번호가 `99` → `100`처럼
자릿수 패딩 없이 만들어져, 문자열 정렬하면 `"100"`이 `"99"`보다 앞에 오는 문제가 있었다. (출처: 담당자 설명 2026-11-11)

## 결정
`edb_helpdesk`에서 `helpdesk.ticket`에 `ticket_no`(Integer, compute·store·index)를 추가하고
`_compute_ticket_no()`로 `ticket_ref`를 정수로 변환(실패 시 0)해 목록을 내림차순(최신순) 정렬한다.
코드: `19.0/edb_helpdesk/models/helpdesk_ticket.py`

## 기각한 대안 (결과가 아니라 이유로)
- `ticket_ref` 그대로 정렬: 위 문자열 정렬 오류가 그대로 남는다.
- [❓확인 필요: 시퀀스에 0 패딩을 주는 방식 등 다른 대안을 검토했는지]

## 결과
- 목록 정렬은 `ticket_no` 기준. `ticket_ref`가 숫자가 아니면 `ticket_no = 0`이 되어 맨 뒤로 간다.
- 이 필드를 "중복"으로 보고 지우면 정렬 오류가 조용히 되살아난다.

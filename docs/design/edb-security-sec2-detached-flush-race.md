---
owner: parkbohee
created: 2026-11-16
updated: 2026-11-16
status: 초안
---
# SEC-2 로그인 실패 기록 지연 해소 설계

> 작업목록: `공통보안모듈_작업목록_261105.xlsx` → `기존 모듈 보완` 시트 SEC-2 (P1)
> 기준 코드: `feature/edb-security-merge` 커밋 `5ecd47f` (PR #1). 줄 번호는 이 커밋 기준이다. **PR #1이 머지된 뒤 `main`에서 브랜치를 따서 작업한다.**

## 배경 / 목표 (무엇을 왜)

로그인 실패는 요청 트랜잭션이 롤백돼도 남아야 해서, 별도 커넥션으로 기록한다 (`core/conn.py`). 구조는 다음과 같다.

1. `enqueue()`(`conn.py:72`)가 행을 **프로세스 메모리 큐**(`_QUEUES[dbname]`, `deque`)에 넣고 바로 `flush()`를 부른다.
2. `flush()`(`conn.py:80`)는 전역 락 `_LOCK`을 **기다리지 않고** 잡아 본다 (`conn.py:100`, `acquire(blocking=False)`). 못 잡으면 "지금 비우는 스레드가 내 행도 가져가겠지" 하고 0을 돌려준다.
3. 락을 잡은 스레드는 큐가 빌 때까지 INSERT하고, 커밋한 뒤 락을 놓는다 (`conn.py:143`).

**빈틈 (코드로 확인, 실행 재현은 안 함)**: 스레드 A가 큐를 다 비우고 `while` 루프를 빠져나온 뒤, 커밋하고 락을 놓기 전 사이에 스레드 B가 행을 넣는 경우다.

```
A: while q 끝 (큐 비었음) ──── 커밋 ──── 락 해제 ──── 끝
B:                  enqueue → flush → 락 못 잡음 → return 0
                    (B의 행은 큐에 남음)
```

- B의 행은 **같은 프로세스에서 다음 `enqueue()`가 있을 때까지** DB에 들어가지 않는다.
- Odoo를 멀티 워커(prefork)로 띄우면 큐가 워커마다 따로 있다. 그 워커에 다음 로그인 실패가 한참 안 오면 그만큼 늦게 기록되고, 그 전에 워커가 재시작되면(`limit_memory_soft`·`limit_request` 등) **사라진다**.
- 탐지 cron은 1분마다 DB만 보므로, 큐에 남은 행은 R-01·R-01B 집계에서 빠진다.

`flush()` docstring(`conn.py:81-98`)은 "예산 초과로 남은 행"의 한계만 적어 두었고, 이 경합은 다루지 않는다.

## 요구사항

- R1. 락을 놓는 순간 사이에 들어온 행도, 락을 가진 스레드가 놓은 직후 다시 확인해 기록한다.
- R2. DB가 느리거나 죽은 상태(`_in_backoff`, 시간 예산 초과)에서는 지금처럼 무한히 다시 돌지 않는다.
- R3. 로그인 요청을 막거나 크게 늦추지 않는다 (기존 원칙: 한 번의 `flush()`는 `FLUSH_BUDGET_SEC` 2초 안).
- R4. 기존 테스트(`tests/test_conn.py`)가 그대로 통과한다.

## 설계 (구조 · 데이터 · 흐름)

`flush()`를 "락 잡기 → 비우기 → 락 놓기"를 **큐가 비어 있을 때까지 반복**하는 형태로 바꾼다. 실제 INSERT 부분(지금의 `try` 블록 본문)은 그대로 `_drain(dbname)` 같은 내부 함수로 옮긴다.

```python
def flush(dbname):
    written = 0
    while _queue(dbname) and not _in_backoff(dbname):
        if not _LOCK.acquire(blocking=False):
            # 다른 스레드가 비우는 중. 그 스레드가 놓은 뒤 다시 확인한다(아래).
            return written
        try:
            n, finished = _drain(dbname)   # finished: 시간 예산 안에 큐를 다 비웠는가
            written += n
        finally:
            _LOCK.release()
        if not finished:
            break   # 예산 초과·커넥션 실패: 기존처럼 다음 enqueue 에 맡긴다 (R2)
    return written
```

- 핵심: **락을 놓은 뒤 큐를 다시 본다.** B가 락을 못 잡고 돌아가도, 락을 가졌던 A가 놓은 직후 `while _queue(dbname)` 조건에서 B의 행을 보고 한 바퀴 더 돈다. B가 A의 해제 뒤에 들어왔다면 B가 스스로 락을 잡는다. 둘 중 하나는 반드시 기록한다.
- `_drain()`은 지금 `flush()`의 `try/except` 본문과 같다. 시간 예산 안에 큐를 다 비웠으면 `finished=True`, 예산 초과나 예외(백오프 진입)면 `False`를 돌려준다.
- 다시 도는 횟수는 "락을 놓는 동안 새로 들어온 행이 있을 때"만 늘어난다. 백오프 중이거나 예산을 넘기면 멈추므로 R2를 지킨다.
- `flush()` docstring의 한계 설명에 "락 해제 직후 재확인으로 경합 구간은 닫았다. 남는 한계는 시간 예산 초과분과 프로세스 재시작뿐"을 적는다.

## 시험 (개발자가 추가할 테스트)

`tests/test_conn.py`에 추가한다. 실제 스레드 경합은 재현이 불안정하므로, **락 해제 순간에 행이 들어오는 상황을 가짜 락으로 만든다.**

```python
def test_flush_picks_up_row_enqueued_during_release(self):
    """락을 놓는 사이에 들어온 행도 같은 flush() 호출에서 기록된다."""
    # 1) conn._LOCK 을 감싸, 처음 release() 할 때 큐에 행 하나를 직접 append 한다
    #    (다른 스레드의 enqueue 가 락을 못 잡고 돌아간 상황과 같다).
    # 2) 행 하나로 conn.enqueue() 호출.
    # 3) 두 행 모두 edb_security_event 에 있고 큐가 비었는지 확인.
```

- 가짜 락은 `unittest.mock.patch.object(conn, '_LOCK', wrapper)`로 바꿔 끼운다. 기존 `test_flush_writes_row_outside_transaction`이 별도 커넥션으로 확인하는 방식을 따라 DB를 조회한다.
- **고치기 전 코드에서 이 테스트가 실패하는지 먼저 확인한다** (두 번째 행이 큐에 남아야 함).

## 대안 검토 (택하지 않은 방향)

- **`acquire(blocking=True)`로 기다리기**: 로그인 폭주 때 모든 요청 스레드가 락 앞에 줄을 선다. 한 `flush()`가 최대 2초이므로 대기가 쌓여 로그인이 느려진다 (R3 위반).
- **탐지 cron에서 큐를 비우기**: 큐는 워커 프로세스 메모리에 있고 cron은 다른 프로세스에서 돈다. 멀티 워커에서는 남의 큐를 볼 수 없다.
- **백그라운드 스레드로 주기적으로 비우기**: 워커마다 스레드가 생기고, prefork 워커 재시작·종료와 수명을 맞추기 번거롭다. 위 방식이 코드가 더 적다.
- **큐 없이 매번 직접 INSERT**: `conn.py` 머리말의 원칙(커넥션당 여러 INSERT)과 백오프·드롭 집계를 다 버리게 된다.

## 영향 범위 / 리스크

- 파일: `19.0/edb_security/core/conn.py`, `19.0/edb_security/tests/test_conn.py`.
- 바뀌는 것은 `flush()` 안쪽뿐이다. 호출자(`collector.record`, `enqueue`)와 반환값 의미(이번 호출에서 쓴 행 수)는 같다.
- README B4.6의 측정 수치(실패 1건당 0.3~0.4ms)는 경합이 없을 때 그대로다. 경합이 있을 때만 한 바퀴가 더 돈다.

## 미결 / 열린 질문

- [ ] 프로세스 종료 시 큐에 남은 행을 비우는 처리(`atexit` 등)를 넣을지. prefork 워커가 신호로 죽을 때는 동작이 보장되지 않아 이번 범위에서는 뺐다.

## 관련

- 작업목록: SEC-2
- 모듈 README: `19.0/edb_security/README.md` B1, B4.6 (로그인 실패 폭주 측정)

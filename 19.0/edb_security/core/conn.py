# -*- coding: utf-8 -*-
"""롤백 위험 경로의 이벤트를 본 트랜잭션과 분리해 기록한다.

원칙: 커넥션당 수천 INSERT 를 태운다. INSERT 당 커넥션을 태우지 않는다.

호출 계약:
- `columns` 는 반드시 `event_type` 과 `severity` 를 포함해야 한다. 둘 다
  DB NOT NULL 이고, Odoo 는 `required=True` 필드에 SQL DEFAULT 를 걸지
  않으므로 (`odoo/orm/fields.py`) 빠뜨리면 INSERT 가 그대로 실패해 해당
  행이 조용히 드롭된다.
- `columns` 는 신뢰된 리터럴(코드에 박힌 컬럼명)이어야 한다. SQL 문자열로
  직접 조립되므로 외부 입력에서 파생된 값을 넘기면 안 된다.
- 이 모듈은 마스킹을 하지 않는다 — 여기로 넘어오는 값은 이미 마스킹된 것으로
  간주한다. 마스킹 책임은 호출자(collector.record())가 분기 이전에 진다.
"""
import logging
import threading
import time
from collections import deque

from odoo import sql_db

_logger = logging.getLogger(__name__)

TABLE = 'edb_security_event'
QUEUE_MAX = 1000
STATEMENT_TIMEOUT_MS = 1000
BACKOFF_BASE_SEC = 5
BACKOFF_MAX_SEC = 300
FLUSH_BUDGET_SEC = 2.0  # 저하된 DB 에서도 한 flush() 호출이 이 시간을 넘기지 않는다

_LOCK = threading.Lock()
_QUEUES = {}      # dbname -> deque
_DROPPED = {}     # dbname -> int
_BACKOFF = {}     # dbname -> (until_ts, failures)


def _queue(dbname):
    return _QUEUES.setdefault(dbname, deque(maxlen=QUEUE_MAX))


def _count_drop(dbname, n=1):
    _DROPPED[dbname] = _DROPPED.get(dbname, 0) + n


def dropped(dbname):
    return _DROPPED.get(dbname, 0)


def reset(dbname):
    _QUEUES.pop(dbname, None)
    _DROPPED.pop(dbname, None)
    _BACKOFF.pop(dbname, None)


def _in_backoff(dbname):
    until, _failures = _BACKOFF.get(dbname, (0, 0))
    return time.time() < until


def _note_failure(dbname):
    _until, failures = _BACKOFF.get(dbname, (0, 0))
    failures += 1
    delay = min(BACKOFF_BASE_SEC * (2 ** (failures - 1)), BACKOFF_MAX_SEC)
    _BACKOFF[dbname] = (time.time() + delay, failures)


def _note_success(dbname):
    _BACKOFF.pop(dbname, None)


def enqueue(dbname, columns, values):
    q = _queue(dbname)
    if len(q) == QUEUE_MAX:
        _count_drop(dbname)
    q.append((tuple(columns), tuple(values)))
    flush(dbname)


def flush(dbname):
    """큐를 비운다. 락을 못 잡으면 다음 호출자에게 맡기고 즉시 돌아간다.

    행마다 세이브포인트를 둬서 한 행의 INSERT 실패가 배치의 나머지를
    롤백시키지 않게 한다. 실패한 행은 dropped() 에 반영된다.

    `FLUSH_BUDGET_SEC` 시간 예산이 지나면 남은 행은 큐에 그대로 두고
    돌아간다 (statement_timeout 은 문장 하나만 보호하지 배치 전체를
    보호하지 않으므로, DB 가 느려지기만 한 저하 상태에서 이 락을 오래
    쥐고 있지 않기 위함이다). 남은 행은 다음 enqueue() 가 이어서 처리한다.

    락을 놓은 뒤 큐를 다시 확인해, 비어 있지 않으면 한 바퀴 더 돈다.
    다른 스레드가 이 락을 쥔 동안 행을 넣고 그냥 돌아갔더라도(락을 못
    잡았으므로), 락을 쥐고 있던 쪽이 놓은 직후 그 행을 가져간다. 놓은 뒤에
    들어온 행이면 넣은 스레드가 스스로 락을 잡는다 — 어느 쪽이든 기록된다.
    예산 초과·백오프 진입 시에는 다시 돌지 않는다 (무한 재시도 방지).

    한계 두 가지는 고칠 수 없어 문서화만 한다:
    - 시간 예산은 커넥션 획득 이후 구간에만 적용된다. 풀 고갈이나 네트워크
      지연으로 db_connect() 자체가 블로킹되면 그 대기는 예산 밖이다.
    - 예산 초과로 큐에 남은 행은 다음 enqueue() 호출이 있어야 기록된다.
      마지막 enqueue() 이후 호출이 없으면 그 행들은 프로세스가 사는 동안
      큐에 남고, 재시작 시 유실된다.
    """
    written = 0
    while _queue(dbname) and not _in_backoff(dbname):
        if not _LOCK.acquire(blocking=False):
            # 다른 스레드가 비우는 중. 그 스레드가 락을 놓은 뒤 다시 확인한다.
            return written
        try:
            n, finished = _drain(dbname)
            written += n
        finally:
            _LOCK.release()
        if not finished:
            # 예산 초과·커넥션 실패: 남은 행은 다음 enqueue() 에 맡긴다.
            break
    return written


def _drain(dbname):
    """락을 쥔 상태에서 호출한다. (기록한 행 수, 큐를 다 비웠는가) 를 돌려준다."""
    written = 0
    finished = False
    try:
        q = _queue(dbname)
        if not q:
            return 0, True
        deadline = time.monotonic() + FLUSH_BUDGET_SEC
        with sql_db.db_connect(dbname).cursor() as cr:
            cr.execute("SET LOCAL statement_timeout = %s", (STATEMENT_TIMEOUT_MS,))
            while q and time.monotonic() < deadline:
                columns, values = q.popleft()
                cols = ', '.join(columns)
                marks = ', '.join(['%s'] * len(columns))
                sql = (
                    "INSERT INTO %s (create_date, write_date, %s) "
                    "VALUES (now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC', %s)"
                    % (TABLE, cols, marks)
                )
                # 한 행의 오류가 배치 전체를 롤백시키지 않도록 행마다 세이브포인트를 둔다.
                cr.execute("SAVEPOINT secmon_row")
                try:
                    cr.execute(sql, values)
                except Exception:
                    # ROLLBACK/RELEASE 자체가 예외를 던질 수 있다(커넥션
                    # 단절). 그 경우에도 이 행의 드롭이 집계에서 누락되지
                    # 않도록 카운트를 가장 먼저 한다.
                    _count_drop(dbname)
                    cr.execute("ROLLBACK TO SAVEPOINT secmon_row")
                    cr.execute("RELEASE SAVEPOINT secmon_row")
                    _logger.debug("보안 이벤트 행 기록 실패", exc_info=True)
                else:
                    cr.execute("RELEASE SAVEPOINT secmon_row")
                    written += 1
            finished = not q
        _note_success(dbname)
    except Exception:
        # 커넥션·커밋 단위 실패. 개별 행 실패는 이미 안에서 카운트했으므로
        # 여기서는 "INSERT 는 성공했지만 커밋되지 못한 행" 만 유실로 센다.
        _count_drop(dbname, written)
        written = 0
        finished = False
        _note_failure(dbname)
        _logger.warning("보안 이벤트 분리 기록 실패", exc_info=True)
    return written, finished

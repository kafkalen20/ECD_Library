from odoo import sql_db
from odoo.tests.common import TransactionCase
from odoo.addons.edb_security.core import conn


class TestConn(TransactionCase):

    def test_enqueue_overflow_counts_drops(self):
        db = 'unit-test-fake-db'
        conn.reset(db)
        # 백오프를 걸어두면 flush() 가 즉시 반환하므로 DB 를 건드리지 않고
        # enqueue() 의 큐잉·드롭 카운팅 경로만 검증할 수 있다.
        conn._note_failure(db)
        try:
            for i in range(conn.QUEUE_MAX + 5):
                conn.enqueue(db, ['event_type', 'severity'], ['login_failed', 'high'])
            self.assertEqual(len(conn._queue(db)), conn.QUEUE_MAX)
            self.assertEqual(conn.dropped(db), 5)
        finally:
            conn.reset(db)

    def test_flush_writes_row_outside_transaction(self):
        db = self.env.cr.dbname
        conn.reset(db)

        def _cleanup():
            # 실제 COMMIT 으로 적재된 행이라 TransactionCase 의 롤백으로는
            # 지워지지 않는다. 별도 커넥션으로 직접 삭제하고 커밋해 정리한다.
            # assertEqual 이 실패해도 항상 실행되도록 addCleanup 을 쓴다.
            with sql_db.db_connect(db).cursor() as cr:
                cr.execute(
                    "DELETE FROM edb_security_event WHERE login = %s",
                    ('detached-probe',))
        self.addCleanup(_cleanup)

        # enqueue() 가 내부에서 이미 flush() 를 호출하므로 반환값이 아니라
        # 실제로 적재된 행을 기준으로 단언한다.
        conn.enqueue(db,
                     ['event_type', 'severity', 'login'],
                     ['login_failed', 'high', 'detached-probe'])

        # 조회도 self.env.cr 가 아니라 별도 커넥션으로 한다. Odoo 는 모든
        # 커서를 REPEATABLE READ 로 열므로 (odoo/sql_db.py), self.env.cr 의
        # 스냅샷은 그 트랜잭션의 첫 실제 데이터 문 시점에 고정되어 다른
        # 테스트의 실행 순서에 따라 이 검증이 우연히 통과하거나 깨질 수
        # 있다. 별도 커넥션으로 조회하면 그 격리수준 문제 자체가 사라진다.
        with sql_db.db_connect(db).cursor() as cr:
            cr.execute(
                "SELECT count(*) FROM edb_security_event WHERE login = %s",
                ('detached-probe',))
            count = cr.fetchone()[0]
        self.assertEqual(count, 1)

    def test_backoff_blocks_flush_and_resets_on_success(self):
        db = 'unit-test-fake-db2'
        conn.reset(db)
        try:
            conn._note_failure(db)
            self.assertTrue(conn._in_backoff(db))
            self.assertEqual(conn.flush(db), 0)
            conn._note_success(db)
            self.assertFalse(conn._in_backoff(db))
        finally:
            conn.reset(db)

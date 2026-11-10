from odoo import sql_db
from odoo.tools import mute_logger
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.edb_security.core import collector, guards


@tagged('post_install', '-at_install')
class TestCollector(TransactionCase):

    def setUp(self):
        super().setUp()
        guards.enable_db(self.env.cr.dbname)
        guards.invalidate(self.env.cr.dbname)

    def test_record_creates_event(self):
        collector.record(self.env, 'hook_login', 'login_failed',
                         severity='high', login='probe-1')
        found = self.env['edb.security.event'].search([('login', '=', 'probe-1')])
        self.assertEqual(len(found), 1)
        self.assertEqual(found.severity, 'high')

    def test_toggle_off_records_nothing(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'edb_security.hook_login', 'False')
        guards.invalidate(self.env.cr.dbname)
        try:
            collector.record(self.env, 'hook_login', 'login_failed', login='probe-2')
            found = self.env['edb.security.event'].search([('login', '=', 'probe-2')])
            self.assertEqual(len(found), 0)
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'edb_security.hook_login', 'True')
            guards.invalidate(self.env.cr.dbname)

    def test_internal_error_does_not_raise(self):
        # Selection 제약 위반은 ORM create() 에서 실제로 예외를 던진다.
        # record() 가 그것을 삼켜 본 흐름을 막지 않아야 하고,
        # 동시에 잘못된 이벤트를 저장해서도 안 된다.
        collector.record(self.env, 'hook_login', 'login_failed',
                         severity='not_a_real_severity', login='probe-err')
        found = self.env['edb.security.event'].search([('login', '=', 'probe-err')])
        self.assertEqual(len(found), 0)

    def test_db_level_error_does_not_abort_transaction(self):
        """FK 위반은 파이썬 레벨에서 걸러지지 않고 실제 SQL 까지 도달한다.

        user_id 는 res.users 로 향하는 진짜 FK 제약이다
        (odoo/orm/fields_relational.py:update_db_foreign_key, ondelete 값과
        무관하게 항상 걸린다). 존재하지 않는 id 를 주면 ORM 은 사전 검증 없이
        그대로 INSERT 문을 실행하고, PostgreSQL 이 문장 단계에서 그것을
        거부한다 — test_internal_error_does_not_raise 의 Selection 위반과
        달리 여기서는 파이썬이 절대 먼저 걸러내지 못한다. 세이브포인트가
        없으면 이 시점에 커서가 aborted 상태가 되어 같은 트랜잭션의 이후
        모든 문장이 실패한다(InFailedSqlTransaction). 로그인 성공 경로에서
        이 일이 나면 그 사용자는 로그인 자체를 못 하게 된다.
        """
        collector.record(self.env, 'hook_login', 'login_success',
                         login='probe-fk', user_id=999999999)
        found = self.env['edb.security.event'].search([('login', '=', 'probe-fk')])
        self.assertEqual(len(found), 0)

        # 같은 커서로 이어지는 정상 ORM 작업이 여전히 성공해야 한다.
        # 세이브포인트가 없다면 여기서 "current transaction is aborted"
        # 로 이 assert 이전에 예외가 난다.
        ok = self.env['edb.security.event'].create({
            'event_type': 'login_success', 'login': 'after-fk-error',
        })
        self.assertTrue(ok.id)

    def test_caller_pending_write_failure_is_not_swallowed(self):
        """호출자의 보류 쓰기가 DB 레벨에서 실패해도 record() 가 그것을 삼키면 안 된다.

        회사 FK 에 존재하지 않는 id 를 써 두고(flush 전까지는 캐시에만 있다)
        record() 를 지난 뒤, 그 실패가 호출자의 flush 에서 정상 전파되는지 본다.
        savepoint(flush=True) 였다면 record() 안에서 그 flush 가 먼저 터져
        except 에 삼켜지고 호출자는 실패를 영영 모르게 된다.
        """
        partner = self.env['res.partner'].create({'name': 'pending-write-probe'})
        self.env.flush_all()
        partner.write({'company_id': 999999999})  # 아직 flush 안 됨

        collector.record(self.env, 'hook_login', 'login_success', login='probe-pending')
        found = self.env['edb.security.event'].search([('login', '=', 'probe-pending')])
        self.assertEqual(len(found), 1, "우리 이벤트는 호출자 쓰기와 무관하게 기록된다")

        raised = False
        try:
            with mute_logger('odoo.sql_db'), self.env.cr.savepoint(flush=False):
                self.env.flush_all()  # 호출자의 실패가 여기서 드러나야 한다
        except Exception:
            raised = True
        self.assertTrue(raised, "record() 가 호출자의 보류 쓰기 실패를 삼켰다")
        self.env.invalidate_all(flush=False)

    def test_request_context_without_request(self):
        ctx = collector.request_context()
        self.assertIsNone(ctx['client_ip'])
        self.assertFalse(ctx['ip_trusted'])

    def test_detached_persists_masked_detail(self):
        db = self.env.cr.dbname

        def _cleanup():
            with sql_db.db_connect(db).cursor() as cr:
                cr.execute(
                    "DELETE FROM edb_security_event WHERE login = %s",
                    ('detached-detail-probe',))
        self.addCleanup(_cleanup)

        collector.record(self.env, 'hook_login', 'login_failed',
                         login='detached-detail-probe', detached=True,
                         detail={'note': 'contact me at test@example.com'})

        with sql_db.db_connect(db).cursor() as cr:
            cr.execute(
                "SELECT detail FROM edb_security_event WHERE login = %s",
                ('detached-detail-probe',))
            row = cr.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], {'note': 'contact me at [EMAIL]'})

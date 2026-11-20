# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, api, sql_db
from odoo.exceptions import AccessDenied
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.edb_security.core import conn, guards
from .common import create_user


@tagged('post_install', '-at_install')
class TestLoginHook(TransactionCase):
    """게이트가 registry.ready 를 보므로 post_install 에서만 유효하다."""

    def setUp(self):
        super().setUp()
        guards.enable_db(self.env.cr.dbname)
        guards.invalidate(self.env.cr.dbname)
        conn.reset(self.env.cr.dbname)

    def _failed_rows(self, login_values):
        """실패 기록은 분리 커넥션으로 COMMIT 되므로 검증도 별도 커넥션으로 한다
        (self.env.cr 는 REPEATABLE READ 스냅샷이라 그 COMMIT 을 못 본다)."""
        with sql_db.db_connect(self.env.cr.dbname).cursor() as cr:
            cr.execute(
                "SELECT login, severity, user_id FROM edb_security_event "
                "WHERE event_type = 'login_failed' AND login = ANY(%s)",
                (list(login_values),))
            return cr.fetchall()

    def _fail_login(self, login, times=1):
        # 분리 커넥션 기록은 롤백되지 않는다. 단언 실패에도 정리되게 미리 등록.
        db = self.env.cr.dbname
        stored = self.env['res.users']._secmon_failed_login_info(login)[0]

        def _cleanup():
            with sql_db.db_connect(db).cursor() as cr:
                cr.execute("DELETE FROM edb_security_event WHERE login = %s", (stored,))
        self.addCleanup(_cleanup)
        for _i in range(times):
            with self.assertRaises(AccessDenied):
                self.env['res.users']._login(
                    {'login': login, 'password': 'x', 'type': 'password'},
                    {'interactive': False})
        return stored

    def _committed_user(self, vals):
        """COMMIT 된 사용자를 만든다 → id.

        실패 기록은 분리 커넥션의 raw INSERT 라 user_id FK 가 COMMIT 된
        res_users 행만 본다. 테스트 트랜잭션 안에서 만든 사용자를 넣으면 FK
        위반으로 그 행이 통째로 버려진다. 그래서 사용자 생성과 실패 로그인을
        모두 별도 커서에서 하고, 끝나면 직접 지운다.
        """
        db = self.env.cr.dbname
        with sql_db.db_connect(db).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            user = create_user(env, vals)
            uid, pid = user.id, user.partner_id.id

        def _cleanup():
            with sql_db.db_connect(db).cursor() as cr:
                # user_id 가 빠진 채 기록된 행(회귀)도 남기지 않는다. 남으면
                # 다음 실행의 단언과 R-01 집계 시험이 깨진다.
                cr.execute("DELETE FROM edb_security_event WHERE user_id = %s OR login = %s",
                           (uid, vals['login']))
                env = api.Environment(cr, SUPERUSER_ID, {'active_test': False})
                env['res.users'].browse(uid).unlink()
                env['res.partner'].browse(pid).unlink()
        self.addCleanup(_cleanup)
        return uid

    def _fail_login_committed(self, login):
        """별도 커서에서 로그인 실패를 만든다 (COMMIT 된 사용자를 보도록)."""
        with sql_db.db_connect(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            with self.assertRaises(AccessDenied):
                env['res.users']._login(
                    {'login': login, 'password': 'x', 'type': 'password'},
                    {'interactive': False})

    def test_failed_login_of_unknown_login_is_not_stored_in_plaintext(self):
        """ID 칸에 잘못 친 비밀번호가 평문으로 남으면 안 된다. 같은 입력은
        같은 값으로 남아 R-01 의 login 집계는 유지된다."""
        typo = 'My-Typo-Password-9!'
        stored = self._fail_login(typo, times=2)
        self.assertRegex(stored, r'^unknown:[0-9a-f]{12}$')
        self.assertNotIn(typo, stored)
        self.assertFalse(self._failed_rows([typo]), "평문이 저장됐다")
        rows = self._failed_rows([stored])
        self.assertEqual(len(rows), 2)
        self.assertEqual({r[1] for r in rows}, {'high'})
        # 없는 계정은 user_id 를 비운다 (SEC-3 R2)
        self.assertEqual({r[2] for r in rows}, {None})
        # 다른 입력은 다른 값
        self.assertNotEqual(stored, self.env['res.users']._secmon_failed_login_info('other-typo')[0])

    def test_failed_login_of_existing_login_links_user(self):
        """실존 계정이면 login 평문과 함께 그 계정을 user_id 로 남긴다 (SEC-3 R1)."""
        uid = self._committed_user({
            'name': 'Secmon Existing', 'login': 'secmon-existing-login',
            'password': 'secmon-real-pw',
        })
        self._fail_login_committed('secmon-existing-login')
        self.assertEqual(self._failed_rows(['secmon-existing-login']),
                         [('secmon-existing-login', 'high', uid)])

    def test_failed_login_of_archived_user_links_user(self):
        """보관 계정으로의 시도도 그 계정에 묶는다 (SEC-3 R1)."""
        uid = self._committed_user({
            'name': 'Secmon Archived', 'login': 'secmon-archived-login',
            'password': 'secmon-real-pw', 'active': False,
        })
        self._fail_login_committed('secmon-archived-login')
        self.assertEqual(self._failed_rows(['secmon-archived-login']),
                         [('secmon-archived-login', 'high', uid)])

    def test_failed_login_info_matches_core_login_lookup(self):
        """계정 조회는 코어 _login 과 같은 domain·정렬을 쓴다 (SEC-3 R3).
        웹사이트별 사용자처럼 같은 login 이 여럿이면 _get_login_order() 가 고른다."""
        user = create_user(self.env, {
            'name': 'Secmon Lookup', 'login': 'secmon-lookup-login',
        })
        Users = self.env['res.users']
        core = Users.sudo().search(
            Users._get_login_domain(user.login), order=Users._get_login_order(), limit=1)
        self.assertEqual(Users._secmon_failed_login_info(user.login), (user.login, core.id))
        self.assertEqual(core, user)

    def test_trace_user_includes_failed_logins(self):
        """성공 이벤트에서 "이 계정 추적" 을 눌러도 같은 계정의 실패가 나온다."""
        uid = self._committed_user({
            'name': 'Secmon Trace', 'login': 'secmon-trace-login',
            'password': 'secmon-real-pw',
        })
        self._fail_login_committed('secmon-trace-login')
        # 그 사용자는 이 테스트 트랜잭션 스냅샷에서 안 보여 create 하면 FK 위반이다.
        # 버튼 동작만 보면 되므로 저장하지 않는 레코드로 만든다.
        success = self.env['edb.security.event'].new({
            'event_type': 'login_success', 'severity': 'info',
            'login': 'secmon-trace-login', 'user_id': uid,
        })
        domain = success.action_trace_user()['domain']
        # 실패 행은 분리 커넥션으로 COMMIT 돼 이 스냅샷에서 안 보인다. 같은
        # domain 이 user_id 기준임을 확인하고, 실패 행이 그 user_id 를 가졌는지 본다.
        self.assertEqual(domain, [('user_id', '=', uid)])
        self.assertEqual([r[2] for r in self._failed_rows(['secmon-trace-login'])], [uid])

    def test_login_success_is_recorded(self):
        # admin 비밀번호를 바꾸면 _update_last_login() 등 부수효과가 다른
        # 테스트를 오염시킬 수 있어, 이 테스트 전용 사용자를 새로 만든다.
        user = create_user(self.env, {
            'name': 'Secmon Login Hook Test User',
            'login': 'secmon-login-hook-test',
            'password': 'secmon-test-pw',
        })
        self.env['res.users']._login(
            {'login': user.login, 'password': 'secmon-test-pw', 'type': 'password'},
            {'interactive': False})
        found = self.env['edb.security.event'].search([
            ('event_type', '=', 'login_success'),
            ('login', '=', user.login),
        ])
        self.assertTrue(found)

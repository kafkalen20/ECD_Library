# -*- coding: utf-8 -*-
from odoo import sql_db
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
                "SELECT login, severity FROM edb_security_event "
                "WHERE event_type = 'login_failed' AND login = ANY(%s)",
                (list(login_values),))
            return cr.fetchall()

    def _fail_login(self, login, times=1):
        # 분리 커넥션 기록은 롤백되지 않는다. 단언 실패에도 정리되게 미리 등록.
        db = self.env.cr.dbname
        stored = self.env['res.users']._secmon_failed_login_value(login)

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
        # 다른 입력은 다른 값
        self.assertNotEqual(stored, self.env['res.users']._secmon_failed_login_value('other-typo'))

    def test_failed_login_of_existing_login_is_stored_in_plaintext(self):
        user = create_user(self.env, {
            'name': 'Secmon Existing', 'login': 'secmon-existing-login',
            'password': 'secmon-real-pw',
        })
        stored = self._fail_login(user.login)
        self.assertEqual(stored, user.login)
        self.assertEqual(len(self._failed_rows([user.login])), 1)

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

# -*- coding: utf-8 -*-
import base64
import json
import os
import re
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields, sql_db
from odoo.exceptions import AccessDenied
from odoo.tests import HttpCase, get_db_name, tagged
from odoo.tests.common import TransactionCase
from odoo.addons.auth_totp.models.totp import TIMESTEP, hotp
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


def _enable_totp(user):
    """2단계 인증을 켠 상태로 만든다. 토큰 생성용 원본 키를 돌려준다."""
    key = os.urandom(20)
    user.sudo().totp_secret = base64.b32encode(key).decode()
    return key


@tagged('post_install', '-at_install')
class TestMfaLoginStep(TransactionCase):
    """비밀번호 단계에서 2단계 인증이 남았는지 판단하는 부분 (SEC-1)."""

    def setUp(self):
        super().setUp()
        guards.enable_db(self.env.cr.dbname)
        guards.invalidate(self.env.cr.dbname)
        conn.reset(self.env.cr.dbname)
        self.user = create_user(self.env, {
            'name': 'Secmon MFA Step', 'login': 'secmon-mfa-step',
            'password': 'secmon-mfa-pw',
        })

    def _login(self, interactive, password='secmon-mfa-pw'):
        self.env['res.users']._login(
            {'login': self.user.login, 'password': password, 'type': 'password'},
            {'interactive': interactive})
        return self.env['edb.security.event'].search([
            ('login', '=', self.user.login)]).mapped('event_type')

    def test_mfa_user_password_step_records_pending(self):
        _enable_totp(self.user)
        self.assertEqual(self._login(interactive=True), ['login_mfa_pending'])

    def test_non_mfa_user_unchanged(self):
        self.assertEqual(self._login(interactive=True), ['login_success'])

    def test_mfa_user_rpc_api_key_records_success(self):
        """RPC 인증은 2단계 없이 끝나므로 지금처럼 성공이다 (R4).
        2단계 사용자는 RPC 에서 API 키로만 들어온다 (_rpc_api_keys_only)."""
        _enable_totp(self.user)
        api_key = self.env['res.users.apikeys'].with_user(self.user).sudo()._generate(
            'rpc', 'secmon test key', fields.Datetime.now() + timedelta(days=1))
        self.assertEqual(self._login(interactive=False, password=api_key), ['login_success'])

    def test_is_login_mfa_only_while_logging_in(self):
        """비밀번호 재확인처럼 로그인 중이 아닌 2단계 검사는 기록 대상이 아니다."""
        user = self.user
        module = 'odoo.addons.edb_security.models.res_users.request'
        cases = [
            (None, False),                                                  # 요청 없음
            (SimpleNamespace(session=_Session(uid=user.id)), False),         # 로그인 완료 후 재확인
            (SimpleNamespace(session=_Session(pre_uid=user.id + 1)), False),  # 다른 사용자
            (SimpleNamespace(session=_Session(pre_uid=user.id)), True),      # 로그인 2단계
        ]
        for fake, expected in cases:
            with patch(module, fake):
                self.assertEqual(user._secmon_is_login_mfa(), expected)


class _Session(dict):
    def __init__(self, uid=None, **kw):
        super().__init__(**kw)
        self.uid = uid


@tagged('post_install', '-at_install')
class TestMfaLoginFlow(HttpCase):
    """실제 로그인 화면 흐름 (/web/session/authenticate → /web/login/totp).

    2단계 실패 기록은 분리 커넥션으로 COMMIT 되고 user_id 외래키가 있어,
    테스트 트랜잭션에서 만든 사용자는 그 커넥션에서 보이지 않는다.
    그래서 이미 있는 admin 으로 시험한다 (비밀번호·2단계 설정은 롤백된다).
    """

    def setUp(self):
        super().setUp()
        guards.enable_db(self.env.cr.dbname)
        guards.invalidate(self.env.cr.dbname)
        conn.reset(self.env.cr.dbname)
        self.user = self.env.ref('base.user_admin')
        self.user.password = 'secmon-mfa-flow-pw'
        self.key = _enable_totp(self.user)
        self.start_id = self._max_event_id()

        db = self.env.cr.dbname
        start_id = self.start_id

        def _cleanup():
            with sql_db.db_connect(db).cursor() as cr:
                cr.execute("DELETE FROM edb_security_event WHERE id > %s "
                           "AND event_type = 'login_mfa_failed'", (start_id,))
        self.addCleanup(_cleanup)

    def _max_event_id(self):
        with sql_db.db_connect(self.env.cr.dbname).cursor() as cr:
            cr.execute("SELECT COALESCE(MAX(id), 0) FROM edb_security_event")
            return cr.fetchone()[0]

    def _events(self):
        """(유형, 인증 경로, user_id). 분리 커넥션 기록도 보이게 테스트 커서와 별도 커넥션을 합친다."""
        Event = self.env['edb.security.event']
        Event.invalidate_model()
        rows = [(e.event_type, e.auth_method, e.user_id.id)
                for e in Event.search([('id', '>', self.start_id), ('user_id', '=', self.user.id)],
                                      order='id')]
        with sql_db.db_connect(self.env.cr.dbname).cursor() as cr:
            cr.execute("SELECT event_type, auth_method, user_id FROM edb_security_event "
                       "WHERE id > %s AND user_id = %s ORDER BY id", (self.start_id, self.user.id))
            committed = [tuple(r) for r in cr.fetchall()]
        return rows + [r for r in committed if r not in rows]

    def _password_step(self):
        payload = {'jsonrpc': '2.0', 'method': 'call', 'id': 0, 'params': {
            'db': get_db_name(), 'login': self.user.login, 'password': 'secmon-mfa-flow-pw'}}
        res = self.url_open('/web/session/authenticate', data=json.dumps(payload),
                            headers={'Content-Type': 'application/json'})
        self.assertIsNone(res.json()['result']['uid'], "2단계가 남았는데 로그인됐다")

    def _post_code(self, token, remember=False):
        page = self.url_open('/web/login/totp').text
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        data = {'csrf_token': csrf, 'totp_token': token}
        if remember:
            data['remember'] = '1'
        return self.url_open('/web/login/totp', data=data)

    def _right_code(self):
        return str(hotp(self.key, int(time.time() / TIMESTEP))).zfill(6)

    def _wrong_code(self):
        right = self._right_code()
        return '000000' if right != '000000' else '111111'

    def test_mfa_wrong_code_records_mfa_failed(self):
        self._password_step()
        self._post_code(self._wrong_code())
        events = self._events()
        self.assertIn(('login_mfa_pending', 'password', self.user.id), events)
        self.assertIn(('login_mfa_failed', 'totp', self.user.id), events)
        self.assertNotIn('login_success', [e[0] for e in events])

    def test_mfa_right_code_records_success(self):
        self._password_step()
        self._post_code(self._right_code())
        types = [e[:2] for e in self._events()]
        self.assertEqual(types, [('login_mfa_pending', 'password'), ('login_success', 'totp')])

    def test_trusted_device_records_success(self):
        key = self.env['auth_totp.device'].with_user(self.user).sudo()._generate(
            'browser', 'secmon test device', None)
        self.opener.cookies.set('td_id', key)
        self._password_step()
        self.url_open('/web/login/totp')
        types = [e[:2] for e in self._events()]
        self.assertEqual(types, [('login_mfa_pending', 'password'), ('login_success', 'trusted_device')])

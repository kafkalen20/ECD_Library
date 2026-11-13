# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from .common import create_user


@tagged('post_install', '-at_install')
class TestDeviceAccessDashboard(TransactionCase):

    def test_dashboard_denied_for_plain_internal_user(self):
        """원시 SQL 집계라 ACL 을 타지 않는다. 일반 내부 사용자가 RPC 로 부르면 막혀야 한다."""
        user = create_user(self.env, {
            'name': 'Plain', 'login': 'plain_dash_user',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.env['edb.device.access'].with_user(user).get_access_dashboard_data('week')

    def test_dashboard_reads_failed_logins_from_security_events(self):
        """로그인 실패는 보안 이벤트에만 남는다. 대시보드는 그것을 가린 표시값으로 보여준다."""
        self.env['edb.security.event'].sudo().create({
            'event_type': 'login_failed', 'severity': 'high',
            'login': 'unknown:abcdef123456', 'client_ip': '203.0.113.7',
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
        })
        admin = self.env.ref('base.user_admin')
        data = self.env['edb.device.access'].with_user(admin).get_access_dashboard_data('week')
        self.assertGreaterEqual(data['kpi']['failed_login'], 1)
        row = next(f for f in data['recent_failed'] if f['ip'] == '203.0.113.7')
        self.assertEqual(row['login'], '미등록 계정 (abcd)')
        self.assertEqual(row['device_label'], '모바일 · iOS')

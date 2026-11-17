from odoo.tests.common import TransactionCase


class TestEventModel(TransactionCase):

    def test_create_minimal_event(self):
        event = self.env['edb.security.event'].create({
            'event_type': 'login_failed',
            'severity': 'high',
            'login': 'admin',
            'client_ip': '10.0.0.1',
        })
        self.assertEqual(event.event_type, 'login_failed')
        self.assertEqual(event.record_count, 0)
        self.assertFalse(event.ip_trusted)

    def test_display_name_includes_type(self):
        event = self.env['edb.security.event'].create({
            'event_type': 'login_success',
            'login': 'admin',
        })
        self.assertIn('admin', event.display_name)

    def test_detail_is_masked_on_create(self):
        event = self.env['edb.security.event'].create({
            'event_type': 'config_changed',
            'detail': {'note': 'contact hong@example.com'},
        })
        self.assertIn('[EMAIL]', event.detail['note'])

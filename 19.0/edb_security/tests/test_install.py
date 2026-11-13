from odoo.tests.common import TransactionCase


class TestInstall(TransactionCase):

    def test_group_exists(self):
        group = self.env.ref('edb_security.group_security_monitor')
        self.assertEqual(group.privilege_id.category_id.name, 'Security Monitor')

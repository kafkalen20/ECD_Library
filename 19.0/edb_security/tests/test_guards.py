from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.addons.edb_security.core import guards


@tagged('post_install', '-at_install')
class TestGuards(TransactionCase):

    def test_default_toggle_is_on(self):
        guards.enable_db(self.env.cr.dbname)
        guards.invalidate(self.env.cr.dbname)
        self.assertTrue(guards.is_active(self.env, 'hook_login'))

    def test_disabled_db_blocks_everything(self):
        guards.disable_db(self.env.cr.dbname)
        try:
            self.assertFalse(guards.is_active(self.env, 'hook_login'))
        finally:
            guards.enable_db(self.env.cr.dbname)

    def test_toggle_off_blocks_single_hook(self):
        guards.enable_db(self.env.cr.dbname)
        self.env['ir.config_parameter'].sudo().set_param(
            'edb_security.hook_login', 'False')
        guards.invalidate(self.env.cr.dbname)
        try:
            self.assertFalse(guards.is_active(self.env, 'hook_login'))
            self.assertTrue(guards.is_active(self.env, 'hook_user_write'))
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'edb_security.hook_login', 'True')
            guards.invalidate(self.env.cr.dbname)

    def test_unknown_toggle_is_false(self):
        guards.enable_db(self.env.cr.dbname)
        guards.invalidate(self.env.cr.dbname)
        self.assertFalse(guards.is_active(self.env, 'no_such_toggle'))

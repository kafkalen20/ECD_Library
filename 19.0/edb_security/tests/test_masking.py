from odoo.tests.common import TransactionCase
from odoo.addons.edb_security.core import masking


class TestMasking(TransactionCase):

    def test_email_is_masked(self):
        out = masking.mask("문의: hong@example.com 확인")
        self.assertNotIn('hong@example.com', out)
        self.assertIn('[EMAIL]', out)

    def test_phone_is_masked(self):
        out = masking.mask("연락처 010-1234-5678")
        self.assertNotIn('010-1234-5678', out)
        self.assertIn('[PHONE]', out)

    def test_rrn_is_masked(self):
        out = masking.mask("주민 900101-1234567")
        self.assertNotIn('900101-1234567', out)
        self.assertIn('[RRN]', out)

    def test_none_and_empty_pass_through(self):
        self.assertIsNone(masking.mask(None))
        self.assertEqual(masking.mask(''), '')

    def test_nested_value_is_masked(self):
        out = masking.mask_value({'a': ['hong@example.com'], 'b': 3})
        self.assertEqual(out['b'], 3)
        self.assertIn('[EMAIL]', out['a'][0])

    def test_foreign_rrn_is_masked(self):
        out = masking.mask("외국인번호 900101-5234567")
        self.assertNotIn('900101-5234567', out)
        self.assertIn('[RRN]', out)

    def test_international_phone_is_fully_masked(self):
        out = masking.mask("국제전화 +82-10-1234-5678")
        self.assertNotIn('5678', out)
        self.assertIn('[PHONE]', out)

    def test_dot_separated_phone_is_masked(self):
        out = masking.mask("전화 010.1234.5678")
        self.assertNotIn('010.1234.5678', out)
        self.assertIn('[PHONE]', out)

    def test_iso_date_is_not_masked(self):
        out = masking.mask("날짜 2026-09-17 발생")
        self.assertIn('2026-09-17', out)
        self.assertNotIn('[ACCOUNT]', out)

    def test_short_id_range_is_not_masked(self):
        out = masking.mask("레코드 id 100-200-3000 범위")
        self.assertIn('100-200-3000', out)
        self.assertNotIn('[ACCOUNT]', out)


class TestDisplayLogin(TransactionCase):

    def test_unknown_login_is_shown_as_unregistered(self):
        from odoo.addons.edb_security.models.security_event import display_login
        self.assertEqual(display_login('unknown:5da8aaf66399'), '미등록 계정 (5da8)')
        self.assertEqual(display_login('admin'), 'admin')
        self.assertEqual(display_login('203.0.113.77'), '203.0.113.77')
        self.assertFalse(display_login(False))

    def test_hit_display_name_masks_unknown_login(self):
        rule = self.env.ref('edb_security.rule_r01')
        hit = self.env['edb.security.rule.hit'].sudo().create({
            'rule_id': rule.id, 'severity': 'high', 'group_key': 'unknown:5da8aaf66399'})
        self.assertEqual(hit.display_name, '%s / 미등록 계정 (5da8)' % rule.name)

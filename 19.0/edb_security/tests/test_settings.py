from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tests.common import TransactionCase
from odoo.addons.edb_security.core import guards
from .common import create_user


@tagged('post_install', '-at_install')
class TestSettings(TransactionCase):

    def test_toggle_roundtrip_invalidates_cache(self):
        settings = self.env['res.config.settings'].create({
            'secmon_hook_login': False,
        })
        settings.execute()
        guards.enable_db(self.env.cr.dbname)
        self.assertFalse(guards.is_active(self.env, 'hook_login'))

        settings = self.env['res.config.settings'].create({
            'secmon_hook_login': True,
        })
        settings.execute()
        self.assertTrue(guards.is_active(self.env, 'hook_login'))

    def test_toggle_off_persists_on_reopen(self):
        # 코어 res.config.settings.default_get() 는 저장된 config_parameter
        # 문자열에 bool() 을 씌우는데, bool('False') 는 True 다. get_values()
        # 오버라이드로 이를 바로잡지 않으면 껐다가 다시 연 화면에 켜진 채로
        # 나타난다.
        self.env['res.config.settings'].create({
            'secmon_hook_login': False,
        }).execute()
        reopened = self.env['res.config.settings'].create({})
        self.assertFalse(reopened.secmon_hook_login)

    def test_toggle_change_creates_config_changed_event(self):
        """공격자가 관리자 권한으로 hook_login 을 끄는 행위 자체가 증적으로
        남아야 한다 (병합 전 필수 수정 Important 1). collector.record() 는
        hook_config 토글에 게이트되므로 그 토글도 함께 꺼지면 무기록이 된다
        — 그래서 이 경로는 게이트를 우회해 직접 기록해야 한다."""
        Event = self.env['edb.security.event']
        before = Event.search_count([('event_type', '=', 'config_changed')])

        self.env['res.config.settings'].create({
            'secmon_hook_login': False,
        }).execute()

        events = Event.search([('event_type', '=', 'config_changed')], order='id')
        self.assertEqual(len(events), before + 1)
        last = events[-1]
        self.assertEqual(last.severity, 'high')
        self.assertEqual(last.detail, {'toggle': 'hook_login', 'old': True, 'new': False})

    def test_toggle_unchanged_creates_no_event(self):
        Event = self.env['edb.security.event']
        before = Event.search_count([('event_type', '=', 'config_changed')])
        # hook_login 은 기본이 True 이고 여기서도 True 로 저장하므로 실제로는
        # 바뀐 게 없다 — 이벤트가 생기면 안 된다.
        self.env['res.config.settings'].create({
            'secmon_hook_login': True,
        }).execute()
        after = Event.search_count([('event_type', '=', 'config_changed')])
        self.assertEqual(after, before)

    def test_preset_apply_creates_config_changed_event_only_for_changes(self):
        Event = self.env['edb.security.event']
        before = Event.search_count([('event_type', '=', 'config_changed')])
        # 최소 프리셋은 소비자 없는 7개 토글을 끈다 (전부 기본 True 였음).
        self.env['res.config.settings'].create({}).action_apply_preset_minimal()
        after_first = Event.search_count([('event_type', '=', 'config_changed')])
        self.assertEqual(after_first, before + 7)

        # 표준 프리셋(전부 True)을 적용하면 방금 꺼진 7개가 되돌아온다.
        self.env['res.config.settings'].create({}).action_apply_preset_standard()
        after_second = Event.search_count([('event_type', '=', 'config_changed')])
        self.assertEqual(after_second, after_first + 7)

    def test_preset_minimal_keeps_only_consumed_toggles(self):
        self.env['res.config.settings'].create({}).action_apply_preset_minimal()
        guards.enable_db(self.env.cr.dbname)
        consumed = {'hook_login', 'detect_engine', 'notify_critical'}
        for code in guards.TOGGLES:
            self.assertEqual(guards.is_active(self.env, code), code in consumed, code)

    def test_invalid_timezone_rejected(self):
        with self.assertRaises(ValidationError) as cm:
            self.env['res.config.settings'].create({
                'secmon_business_tz': 'Asia/Seul'}).execute()
        self.assertIn('Asia/Seul', str(cm.exception))

    def test_preset_and_ack_require_monitor_group(self):
        employee = create_user(self.env, {
            'name': 'plain employee', 'login': 'secmon-plain',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        settings = self.env['res.config.settings'].with_user(employee).new({})
        with self.assertRaises(AccessError):
            settings.action_apply_preset_minimal()
        with self.assertRaises(AccessError):
            settings.action_apply_preset_standard()
        rule = self.env['edb.security.rule'].create({
            'name': 'r', 'code': 'ACL-1', 'event_type': 'login_failed'})
        hit = self.env['edb.security.rule.hit'].create({
            'rule_id': rule.id, 'severity': 'high'})
        with self.assertRaises(AccessError):
            hit.with_user(employee).action_ack()
        with self.assertRaises(AccessError):
            hit.with_user(employee).action_close()

    def test_group_system_implies_monitor_group(self):
        admin = self.env.ref('base.user_admin')
        self.assertTrue(admin.has_group('edb_security.group_security_monitor'))
        group = self.env.ref('edb_security.group_security_monitor')
        self.assertIn(admin, group.all_user_ids)

    def test_rule_code_unique(self):
        Rule = self.env['edb.security.rule']
        Rule.create({'name': 'a', 'code': 'DUP-1', 'event_type': 'login_failed'})
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), \
                self.env.cr.savepoint():
            Rule.create({'name': 'b', 'code': 'DUP-1', 'event_type': 'login_failed'})


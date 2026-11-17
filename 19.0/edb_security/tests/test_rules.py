# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytz

from odoo import fields
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tests.common import TransactionCase
from odoo.addons.edb_security.core import guards
from .common import create_user


@tagged('post_install', '-at_install')
class TestRules(TransactionCase):

    def setUp(self):
        super().setUp()
        guards.enable_db(self.env.cr.dbname)
        guards.invalidate(self.env.cr.dbname)
        self.Event = self.env['edb.security.event']
        self.Rule = self.env['edb.security.rule']
        self.Hit = self.env['edb.security.rule.hit']
        self.Rule.search([]).write({'active': False})

    def _make_failures(self, count, login='bruteforce', ip='10.9.9.9'):
        for _i in range(count):
            self.Event.create({
                'event_type': 'login_failed',
                'severity': 'high',
                'login': login,
                'client_ip': ip,
            })

    def _backdate(self, record, dt):
        """create_date 는 LOG_ACCESS_COLUMNS 라 create() vals 로 넘겨도 무시된다
        (odoo/orm/models.py:_add_missing_default_values, pool.ready 인 동안은
        superuser 라도 예외). 과거 이벤트를 재현하려면 SQL 로 직접 되돌린다."""
        self.env.cr.execute(
            "UPDATE %s SET create_date = %%s WHERE id = %%s" % record._table,
            (dt, record.id))
        record.invalidate_recordset(['create_date'])

    def _recent_kst_naive_utc(self, hour, minute=0):
        """최근 24시간 이내이면서 지정한 KST 시/분과 같은 시각을 UTC naive 로
        반환한다.

        _window_start() 의 24시간 캡(Important 2, §5.3)이 생긴 뒤로는
        하드코딩된 달력 날짜(예: 2026-09-16)를 쓰면 테스트를 실행하는
        실제 날짜에 따라 캡에 걸려 이벤트가 창 밖으로 밀려날 수 있다.
        '오늘 또는 어제의 그 시각'을 매번 계산해 항상 24시간 캡 안에
        들어오게 한다.
        """
        tz = pytz.timezone('Asia/Seoul')
        now_kst = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
        candidate = now_kst.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate >= now_kst:
            candidate -= timedelta(days=1)
        return candidate.astimezone(pytz.utc).replace(tzinfo=None)

    def test_threshold_rule_fires(self):
        rule = self.Rule.create({
            'name': '테스트 임계',
            'code': 'T-01',
            'rule_kind': 'threshold',
            'event_type': 'login_failed',
            'aggregate': 'count',
            'group_by': 'login',
            'threshold_count': 5,
            'window_minutes': 10,
            'cooldown_minutes': 60,
            'severity': 'high',
        })
        self._make_failures(6)
        rule._evaluate()
        hits = self.Hit.search([('rule_id', '=', rule.id)])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits.matched_value, 6)

    def test_evaluate_keeps_rule_write_uid(self):
        """1분 cron 이 last_eval 을 갱신해도 룰의 마지막 수정자·수정 시각은
        그대로여야 한다. README B3 이 룰 변경 추적 수단으로 write_uid/write_date
        를 안내하기 때문이다."""
        rule = self.Rule.create({
            'name': '테스트 수정자',
            'code': 'T-WU',
            'rule_kind': 'threshold',
            'event_type': 'login_failed',
            'threshold_count': 5,
        })
        editor = create_user(self.env, {'name': '룰 수정자', 'login': 'secmon_rule_editor'})
        old_date = fields.Datetime.now() - timedelta(days=3)
        self.env.cr.execute(
            "UPDATE edb_security_rule SET write_uid = %s, write_date = %s WHERE id = %s",
            (editor.id, old_date, rule.id))
        rule.invalidate_recordset()

        rule._evaluate()

        self.assertTrue(rule.last_eval)
        self.assertEqual(rule.write_uid, editor)
        self.assertEqual(rule.write_date, old_date)

    def test_threshold_fires_at_exactly_threshold(self):
        rule = self.Rule.create({
            'name': '경계', 'code': 'T-EQ', 'rule_kind': 'threshold',
            'event_type': 'login_failed', 'aggregate': 'count',
            'group_by': 'login', 'threshold_count': 5, 'window_minutes': 10,
            'cooldown_minutes': 60, 'severity': 'high',
        })
        self._make_failures(4)
        rule._evaluate()
        self.assertFalse(self.Hit.search([('rule_id', '=', rule.id)]))
        self._make_failures(1)
        rule._evaluate()
        self.assertEqual(self.Hit.search_count([('rule_id', '=', rule.id)]), 1)

    def test_critical_notifies_group_system_admin_without_leaking_group_key(self):
        rule = self.Rule.create({
            'name': '폴백', 'code': 'T-FB', 'rule_kind': 'threshold',
            'event_type': 'login_failed', 'aggregate': 'count',
            'group_by': 'login', 'threshold_count': 1, 'window_minutes': 10,
            'cooldown_minutes': 60, 'severity': 'critical',
        })
        self._make_failures(2, login='hunter2-typo')
        rule._evaluate()
        hit = self.Hit.search([('rule_id', '=', rule.id)], limit=1)
        acts = self.env['mail.activity'].search([
            ('res_model', '=', 'edb.security.rule.hit'), ('res_id', '=', hit.id)])
        self.assertIn(self.env.ref('base.user_admin'), acts.user_id)
        self.assertNotIn('hunter2-typo', ''.join(acts.mapped('note')))

    def test_cron_isolates_failing_rule(self):
        bad = self.Rule.create({
            'name': 'bad', 'code': 'T-BAD', 'rule_kind': 'threshold',
            'event_type': 'login_failed', 'threshold_count': 1,
            'condition_domain': '[("no_such_field", "=", 1)]'})
        good = self.Rule.create({
            'name': 'good', 'code': 'T-GOOD', 'rule_kind': 'threshold',
            'event_type': 'login_failed', 'aggregate': 'count',
            'group_by': 'global', 'threshold_count': 1, 'severity': 'high'})
        self._make_failures(2)
        with mute_logger('odoo.addons.edb_security.models.security_rule'):
            self.Rule._cron_evaluate()
        self.assertEqual(self.Hit.search_count([('rule_id', '=', good.id)]), 1)

    def test_threshold_group_by_login_separates_accounts(self):
        """group_by=login 은 계정별로 센다. 전역 합산이면 두 계정이 합쳐져
        임계를 넘고 group_key 가 'global' 이 된다."""
        rule = self.Rule.create({
            'name': '그룹', 'code': 'T-GB', 'rule_kind': 'threshold',
            'event_type': 'login_failed', 'aggregate': 'count',
            'group_by': 'login', 'threshold_count': 5, 'window_minutes': 10,
            'cooldown_minutes': 60, 'severity': 'high',
        })
        self._make_failures(3, login='gb-victim-a')
        self._make_failures(3, login='gb-victim-b')
        rule._evaluate()
        self.assertFalse(self.Hit.search([('rule_id', '=', rule.id)]),
                         "각 계정은 3건이라 임계 미만이다")
        self._make_failures(3, login='gb-victim-a')
        rule._evaluate()
        hits = self.Hit.search([('rule_id', '=', rule.id)])
        self.assertEqual(hits.mapped('group_key'), ['gb-victim-a'])
        self.assertEqual(hits.matched_value, 6)
        self.assertEqual(set(hits.event_ids.mapped('login')), {'gb-victim-a'})

    def test_window_start_gap_cover_is_capped_at_24h(self):
        """last_eval 이 3일 전이어도 48시간 전 이벤트를 되짚지 않는다.

        상한이 없으면 장기 정지 후 첫 평가가 전 구간을 스캔한다 (설계서 §5.3).
        """
        now = fields.Datetime.now()
        rule = self.Rule.create({
            'name': '캡', 'code': 'T-CAP', 'rule_kind': 'threshold',
            'event_type': 'login_failed', 'aggregate': 'count',
            'group_by': 'login', 'threshold_count': 3, 'window_minutes': 1,
            'cooldown_minutes': 60, 'severity': 'high',
            'last_eval': now - timedelta(hours=72),
        })
        self._make_failures(3, login='cap-old')
        self._make_failures(3, login='cap-recent')
        for event in self.Event.search([('login', '=', 'cap-old')]):
            self._backdate(event, now - timedelta(hours=48))
        for event in self.Event.search([('login', '=', 'cap-recent')]):
            self._backdate(event, now - timedelta(hours=12))
        rule._evaluate()
        keys = self.Hit.search([('rule_id', '=', rule.id)]).mapped('group_key')
        self.assertEqual(keys, ['cap-recent'])

    def test_non_critical_hit_creates_no_activity(self):
        user = self.env.ref('base.user_admin')
        rule = self.Rule.create({
            'name': '높음은 즉시 알림 없음', 'code': 'T-HI', 'rule_kind': 'threshold',
            'event_type': 'login_failed', 'aggregate': 'count',
            'group_by': 'global', 'threshold_count': 1, 'window_minutes': 10,
            'cooldown_minutes': 60, 'severity': 'high',
            'notify_user_ids': [(6, 0, [user.id])],
        })
        self._make_failures(2)
        rule._evaluate()
        hit = self.Hit.search([('rule_id', '=', rule.id)], limit=1)
        self.assertTrue(hit)
        self.assertFalse(self.env['mail.activity'].search([
            ('res_model', '=', 'edb.security.rule.hit'), ('res_id', '=', hit.id)]))

    def test_cron_respects_detect_engine_toggle(self):
        rule = self.Rule.create({
            'name': 'cron 토글', 'code': 'T-CRON', 'rule_kind': 'threshold',
            'event_type': 'login_failed', 'aggregate': 'count',
            'group_by': 'login', 'threshold_count': 1, 'severity': 'high'})
        self._make_failures(2, login='cron-toggle')
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('edb_security.detect_engine', 'False')
        try:
            self.Rule._cron_evaluate()
            self.assertFalse(self.Hit.search([('rule_id', '=', rule.id)]))
            self.assertFalse(rule.last_eval)
        finally:
            icp.set_param('edb_security.detect_engine', 'True')
        self.Rule._cron_evaluate()
        self.assertEqual(self.Hit.search_count([('rule_id', '=', rule.id)]), 1)

    def test_cooldown_blocks_second_hit(self):
        rule = self.Rule.create({
            'name': '테스트 쿨다운',
            'code': 'T-02',
            'rule_kind': 'threshold',
            'event_type': 'login_failed',
            'aggregate': 'count',
            'group_by': 'login',
            'threshold_count': 5,
            'window_minutes': 10,
            'cooldown_minutes': 60,
            'severity': 'high',
        })
        self._make_failures(6)
        rule._evaluate()
        rule._evaluate()
        self.assertEqual(self.Hit.search_count([('rule_id', '=', rule.id)]), 1)

    def test_sum_aggregate_catches_slow_drip(self):
        """99건씩 9회는 count 로는 안 잡히고 sum 으로만 잡힌다 (설계서 §5.2)."""
        rule = self.Rule.create({
            'name': '테스트 합계',
            'code': 'T-03',
            'rule_kind': 'threshold',
            'event_type': 'password_changed',
            'aggregate': 'sum_record_count',
            'group_by': 'global',
            'threshold_count': 50,
            'window_minutes': 60,
            'cooldown_minutes': 60,
            'severity': 'critical',
        })
        for _i in range(9):
            self.Event.create({
                'event_type': 'password_changed',
                'severity': 'high',
                'model_name': 'res.users',
                'record_count': 99,
            })
        rule._evaluate()
        hits = self.Hit.search([('rule_id', '=', rule.id)])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits.matched_value, 891)

    def test_last_eval_covers_downtime_gap(self):
        """cron 이 멈춘 구간의 이벤트가 재개 후 평가돼야 한다.

        sliding window(1분)만으로는 20분 전 이벤트를 못 잡는다.
        _window_start() 가 last_eval 까지 거슬러 올라가야만 잡힌다.
        """
        now = fields.Datetime.now()
        rule = self.Rule.create({
            'name': '테스트 공백',
            'code': 'T-04',
            'rule_kind': 'threshold',
            'event_type': 'login_failed',
            'aggregate': 'count',
            'group_by': 'login',
            'threshold_count': 5,
            'window_minutes': 1,
            'cooldown_minutes': 60,
            'severity': 'high',
            'last_eval': now - timedelta(minutes=30),
        })
        self._make_failures(6)
        # 20분 전으로 백데이트: sliding window(1분) 밖, last_eval(30분 전) 안쪽
        for event in self.Event.search([('login', '=', 'bruteforce')]):
            self._backdate(event, now - timedelta(minutes=20))
        rule._evaluate()
        self.assertEqual(self.Hit.search_count([('rule_id', '=', rule.id)]), 1)

    def test_new_ip_rule_fires_only_for_unseen_ip(self):
        user = self.env.ref('base.user_admin')
        rule = self.Rule.create({
            'name': '테스트 신규 IP',
            'code': 'T-05',
            'rule_kind': 'new_ip',
            'event_type': 'login_success',
            'window_minutes': 10,
            'cooldown_minutes': 60,
            'severity': 'critical',
        })
        old_event = self.Event.create({
            'event_type': 'login_success', 'user_id': user.id,
            'login': user.login, 'client_ip': '10.1.1.1',
        })
        self._backdate(old_event, datetime.now() - timedelta(days=5))
        self.Event.create({
            'event_type': 'login_success', 'user_id': user.id,
            'login': user.login, 'client_ip': '10.1.1.1',
        })
        rule._evaluate()
        self.assertEqual(self.Hit.search_count([('rule_id', '=', rule.id)]), 0)

        self.Event.create({
            'event_type': 'login_success', 'user_id': user.id,
            'login': user.login, 'client_ip': '203.0.113.7',
        })
        rule._evaluate()
        self.assertEqual(self.Hit.search_count([('rule_id', '=', rule.id)]), 1)

    def test_critical_hit_creates_activity(self):
        user = self.env.ref('base.user_admin')
        rule = self.Rule.create({
            'name': '테스트 알림',
            'code': 'T-06',
            'rule_kind': 'threshold',
            'event_type': 'login_failed',
            'aggregate': 'count',
            'group_by': 'global',
            'threshold_count': 1,
            'window_minutes': 10,
            'cooldown_minutes': 60,
            'severity': 'critical',
            'notify_user_ids': [(6, 0, [user.id])],
        })
        self._make_failures(2)
        rule._evaluate()
        hit = self.Hit.search([('rule_id', '=', rule.id)], limit=1)
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'edb.security.rule.hit'),
            ('res_id', '=', hit.id),
        ])
        self.assertTrue(activity)

    def test_hit_ip_trusted_true_only_when_all_events_trusted(self):
        """히트의 ip_trusted 는 관련 이벤트가 전부 신뢰될 때만 True 다.

        proxy_mode 미설정 상태를 드러내는 유일한 신호이므로, 하나라도
        신뢰 불가면 그 히트의 IP 근거 전체를 신뢰할 수 없다고 봐야 한다.
        """
        rule = self.Rule.create({
            'name': '테스트 IP신뢰 전부',
            'code': 'T-09',
            'rule_kind': 'threshold',
            'event_type': 'login_failed',
            'aggregate': 'count',
            'group_by': 'login',
            'threshold_count': 1,
            'window_minutes': 10,
            'cooldown_minutes': 60,
            'severity': 'high',
        })
        self.Event.create({
            'event_type': 'login_failed', 'severity': 'high',
            'login': 'trusted-all', 'client_ip': '10.9.9.1', 'ip_trusted': True,
        })
        self.Event.create({
            'event_type': 'login_failed', 'severity': 'high',
            'login': 'trusted-all', 'client_ip': '10.9.9.1', 'ip_trusted': True,
        })
        rule._evaluate()
        hit = self.Hit.search([('rule_id', '=', rule.id)], limit=1)
        self.assertTrue(hit.ip_trusted)

    def test_hit_ip_trusted_false_when_any_event_untrusted(self):
        rule = self.Rule.create({
            'name': '테스트 IP신뢰 일부',
            'code': 'T-10',
            'rule_kind': 'threshold',
            'event_type': 'login_failed',
            'aggregate': 'count',
            'group_by': 'login',
            'threshold_count': 1,
            'window_minutes': 10,
            'cooldown_minutes': 60,
            'severity': 'high',
        })
        self.Event.create({
            'event_type': 'login_failed', 'severity': 'high',
            'login': 'trusted-mixed', 'client_ip': '10.9.9.2', 'ip_trusted': True,
        })
        self.Event.create({
            'event_type': 'login_failed', 'severity': 'high',
            'login': 'trusted-mixed', 'client_ip': '10.9.9.2', 'ip_trusted': False,
        })
        rule._evaluate()
        hit = self.Hit.search([('rule_id', '=', rule.id)], limit=1)
        self.assertFalse(hit.ip_trusted)

    def test_r02_only_fires_for_admin_group_system_user(self):
        """R-02 는 base.group_system 을 가진 사용자에게만 적용돼야 한다.

        전 직원에게 적용되면 저녁·자택 접속마다 치명 알림이 쏟아져
        알림 피로로 진짜 알림이 묻힌다 (병합 전 필수 수정 Critical 1).
        """
        rule = self.env.ref('edb_security.rule_r02')
        admin = self.env.ref('base.user_admin')
        non_admin = create_user(self.env, {
            'name': '일반 직원', 'login': 'r02-non-admin-probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.assertTrue(admin.has_group('base.group_system'))
        self.assertFalse(non_admin.has_group('base.group_system'))

        for user in (admin, non_admin):
            self.Event.create({
                'event_type': 'login_success', 'user_id': user.id,
                'login': user.login, 'client_ip': '198.51.100.%d' % user.id,
            })
        rule._evaluate()
        hits = self.Hit.search([('rule_id', '=', rule.id)])
        logins = hits.mapped('group_key')
        self.assertTrue(any(admin.login in key for key in logins))
        self.assertFalse(any(non_admin.login in key for key in logins))

    def _pin_business_hours(self):
        """고객사가 튜닝한 업무시간 설정에 의존하지 않도록 테스트 안에서 고정한다.

        요일은 전부 허용해 시각(hour) 판정만 격리한다. set_param 은 테스트
        트랜잭션과 함께 롤백된다.
        """
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('edb_security.business_tz', 'Asia/Seoul')
        icp.set_param('edb_security.business_start', '9')
        icp.set_param('edb_security.business_end', '19')
        icp.set_param('edb_security.business_weekdays', '0,1,2,3,4,5,6')

    def _offhours_rule(self, code, marker):
        """marker login 의 이벤트만 보는 offhours 룰. 운영 DB 에 쌓인 다른
        login_success 이벤트가 섞여도 단언이 흔들리지 않는다."""
        return self.Rule.create({
            'name': '테스트 업무시간 %s' % code,
            'code': code,
            'rule_kind': 'offhours',
            'event_type': 'login_success',
            'window_minutes': 1440,
            'cooldown_minutes': 60,
            'severity': 'critical',
            'condition_domain': repr([('login', '=', marker)]),
        })

    def _noise_events(self):
        """이미 이벤트가 쌓인 운영 복제본을 흉내낸다. 업무시간 외 시각이라
        룰 범위가 좁혀지지 않았다면 반드시 히트를 만든다."""
        for i in range(3):
            noise = self.Event.create({
                'event_type': 'login_success', 'login': 'noise-%d' % i,
                'client_ip': '10.7.7.%d' % i,
            })
            self._backdate(noise, self._recent_kst_naive_utc(21, 8))

    def test_offhours_uses_korea_timezone(self):
        """KST 21:08(업무시간 외) 로그인 → 업무시간 외로 판정돼야 한다.

        타임존 변환이 빠지면 UTC 시각(12:08)이 업무시간 한가운데로 오인된다.
        '최근 24시간 이내의 21:08 KST' 를 매번 계산해 24시간 캡과 실행일이
        부딪히지 않게 한다. 룰은 프로브 login 으로만 좁히고 업무시간 설정은
        테스트 안에서 고정한다.
        """
        self._pin_business_hours()
        self._noise_events()
        rule = self._offhours_rule('T-07', 'offhours-probe')
        event = self.Event.create({
            'event_type': 'login_success',
            'login': 'offhours-probe',
            'client_ip': '10.5.5.5',
        })
        self._backdate(event, self._recent_kst_naive_utc(21, 8))
        rule._evaluate()
        hits = self.Hit.search([('rule_id', '=', rule.id)])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits.group_key, 'offhours-probe')

    def test_business_hours_does_not_fire(self):
        """KST 12:00(UTC 03:00, 업무시간 내) 로그인 → 발동하지 않아야 한다.

        위 양성 테스트와 같은 설정·같은 잡음에서 시각만 다르다. 잡음은
        업무시간 외라서, 룰이 프로브로 좁혀지지 않았다면 여기서 히트가 난다.
        """
        self._pin_business_hours()
        self._noise_events()
        rule = self._offhours_rule('T-08', 'business-probe')
        event = self.Event.create({
            'event_type': 'login_success',
            'login': 'business-probe',
            'client_ip': '10.5.5.6',
        })
        self._backdate(event, self._recent_kst_naive_utc(12, 0))
        rule._evaluate()
        self.assertEqual(self.Hit.search_count([('rule_id', '=', rule.id)]), 0)

    def test_event_shows_rules_that_hit_it(self):
        event = self.Event.create({'event_type': 'login_success', 'severity': 'info', 'login': 'multi-rule'})
        r02 = self.env.ref('edb_security.rule_r02')
        r03 = self.env.ref('edb_security.rule_r03')
        for rule in (r02, r03):
            self.Hit.sudo().create({'rule_id': rule.id, 'severity': 'critical', 'event_ids': [(6, 0, event.ids)]})
        # setUp 에서 룰을 모두 보관했다. 보관된 룰도 이력에는 보여야 한다.
        self.assertEqual(event.rule_ids, r02 | r03)

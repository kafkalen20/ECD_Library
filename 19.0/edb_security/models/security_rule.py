# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

from ..core import guards
from .security_event import EVENT_TYPES, SEVERITIES, SEVERITY_COLORS

_logger = logging.getLogger(__name__)

RULE_KINDS = [
    ('threshold', '임계 집계'),
    ('new_ip', '신규 출발지 IP'),
    ('offhours', '업무시간 외'),
]

AGGREGATES = [
    ('count', '이벤트 건수'),
    ('sum_record_count', '영향 레코드 합계'),
]

GROUP_BYS = [
    ('global', '전역'),
    ('login', '계정'),
    ('client_ip', 'IP'),
]


class SecurityRule(models.Model):
    _name = 'edb.security.rule'
    _description = '보안 탐지 룰'
    _order = 'code'

    name = fields.Char(string='이름', required=True)
    code = fields.Char(string='코드', required=True)
    active = fields.Boolean(string='활성', default=True)
    rule_kind = fields.Selection(RULE_KINDS, string='종류',
                                 default='threshold', required=True)
    event_type = fields.Selection(EVENT_TYPES, string='대상 이벤트', required=True)
    severity = fields.Selection(SEVERITIES, string='심각도',
                                default='high', required=True)
    severity_color = fields.Integer(compute='_compute_severity_color')

    aggregate = fields.Selection(AGGREGATES, string='집계', default='count')
    group_by = fields.Selection(GROUP_BYS, string='그룹', default='global')
    threshold_count = fields.Integer(string='임계', default=1)
    window_minutes = fields.Integer(string='구간(분)', default=10)
    cooldown_minutes = fields.Integer(string='중복 억제(분)', default=60)
    condition_domain = fields.Char(string='추가 조건')

    notify_user_ids = fields.Many2many('res.users', string='알림 대상')
    last_eval = fields.Datetime(string='마지막 평가')

    @api.depends('severity')
    def _compute_severity_color(self):
        for rec in self:
            rec.severity_color = SEVERITY_COLORS.get(rec.severity, 0)

    _code_uniq = models.Constraint(
        'unique (code)',
        "룰 코드는 중복될 수 없습니다.",
    )

    # ------------------------------------------------------------------
    # 평가
    # ------------------------------------------------------------------
    @api.model
    def _cron_evaluate(self):
        if not guards.is_active(self.env, 'detect_engine'):
            return
        for rule in self.search([]):
            try:
                # cron 컨텍스트라 보호할 호출자 쓰기가 없으므로 flush=True 기본값이 맞다.
                # 한 룰의 DB 오류가 커서를 aborted 로 만들어 나머지 룰을 연쇄
                # 실패시키지 않도록 룰별로 격리한다.
                with self.env.cr.savepoint():
                    rule._evaluate()
            except Exception:
                _logger.exception("보안 룰 평가 실패: %s", rule.code)

    def _window_start(self):
        self.ensure_one()
        now = fields.Datetime.now()
        sliding = now - timedelta(minutes=self.window_minutes or 1)
        # 다운타임 구간이 평가되지 않고 넘어가는 것을 막는다 (설계서 §5.3)
        # 갭 커버는 24시간까지만. 하한이 없으면 장기 정지 후 첫 평가가
        # 전 구간을 스캔하다 타임아웃하고, last_eval 이 전진하지 않아
        # 매분 윈도우가 커지며 영구히 실패한다.
        floor = now - timedelta(hours=24)
        if self.last_eval and self.last_eval < sliding:
            return max(self.last_eval, floor)
        return sliding

    def _base_domain(self, window_start):
        self.ensure_one()
        domain = [
            ('event_type', '=', self.event_type),
            ('create_date', '>=', window_start),
        ]
        if self.condition_domain:
            domain += safe_eval(self.condition_domain)
        return domain

    def _evaluate(self):
        self.ensure_one()
        window_start = self._window_start()
        window_end = fields.Datetime.now()
        handler = getattr(self, '_evaluate_%s' % self.rule_kind)
        handler(window_start, window_end)
        # ORM write() 는 write_uid/write_date 까지 덮어 룰을 마지막으로 고친 사람을
        # 1분마다 지운다 (README B3 의 추적 수단). 이 컬럼만 SQL 로 쓴다.
        self.env.cr.execute(
            "UPDATE edb_security_rule SET last_eval = %s WHERE id = %s",
            (window_end, self.id))
        self.invalidate_recordset(['last_eval'])

    def _evaluate_threshold(self, window_start, window_end):
        """Odoo 19 에서 read_group 은 deprecated 다. _read_group 은 튜플 리스트를 준다."""
        Event = self.env['edb.security.event'].sudo()
        domain = self._base_domain(window_start)
        aggregate = 'record_count:sum' if self.aggregate == 'sum_record_count' else '__count'
        groupby = [] if self.group_by == 'global' else [self.group_by]

        for row in Event._read_group(domain, groupby, [aggregate]):
            # groupby 가 있으면 (그룹값, 집계값), 없으면 (집계값,) 형태다
            key, value = (row[0], row[1]) if groupby else (None, row[0])
            if (value or 0) >= self.threshold_count:
                self._fire(key, value or 0, window_start, window_end, domain)

    def _evaluate_new_ip(self, window_start, window_end):
        Event = self.env['edb.security.event'].sudo()
        recent = Event.search(self._base_domain(window_start))
        for event in recent:
            if not event.client_ip or not event.user_id:
                continue
            seen = Event.search_count([
                ('event_type', '=', self.event_type),
                ('user_id', '=', event.user_id.id),
                ('client_ip', '=', event.client_ip),
                ('id', '!=', event.id),
                ('create_date', '<', window_start),
            ])
            if not seen:
                self._fire('%s@%s' % (event.user_id.login, event.client_ip),
                           1, window_start, window_end, None, events=event)

    def _evaluate_offhours(self, window_start, window_end):
        Event = self.env['edb.security.event'].sudo()
        icp = self.env['ir.config_parameter'].sudo()
        tz_name = icp.get_param('edb_security.business_tz', 'Asia/Seoul')
        start_hour = int(icp.get_param('edb_security.business_start', 9))
        end_hour = int(icp.get_param('edb_security.business_end', 19))
        weekdays = icp.get_param('edb_security.business_weekdays', '0,1,2,3,4')
        allowed_days = {int(x) for x in weekdays.split(',') if x.strip()}

        tz = pytz.timezone(tz_name)
        for event in Event.search(self._base_domain(window_start)):
            local = pytz.utc.localize(event.create_date).astimezone(tz)
            off = local.weekday() not in allowed_days or not (start_hour <= local.hour < end_hour)
            if off:
                self._fire(event.login or '-', 1, window_start, window_end,
                           None, events=event)

    # ------------------------------------------------------------------
    # 발동
    # ------------------------------------------------------------------
    def _in_cooldown(self, group_key):
        self.ensure_one()
        if not self.cooldown_minutes:
            return False
        since = fields.Datetime.now() - timedelta(minutes=self.cooldown_minutes)
        return bool(self.env['edb.security.rule.hit'].sudo().search_count([
            ('rule_id', '=', self.id),
            ('group_key', '=', group_key),
            ('create_date', '>=', since),
        ]))

    def _fire(self, group_key, value, window_start, window_end, domain, events=None):
        self.ensure_one()
        key = group_key or 'global'
        if self._in_cooldown(key):
            return
        if events is None and domain is not None:
            events = self.env['edb.security.event'].sudo().search(
                domain + ([(self.group_by, '=', group_key)] if self.group_by != 'global' else []),
                limit=200)
        # 관련 이벤트가 하나라도 있고 전부 ip_trusted 일 때만 히트의 IP 근거를
        # 신뢰한다. 이벤트가 없거나 하나라도 신뢰 불가면 False (proxy_mode
        # 미설정 상태를 드러내는 유일한 신호이므로 과대평가하면 안 된다).
        ip_trusted = bool(events) and all(events.mapped('ip_trusted'))
        hit = self.env['edb.security.rule.hit'].sudo().create({
            'rule_id': self.id,
            'severity': self.severity,
            'group_key': key,
            'matched_value': value,
            'window_start': window_start,
            'window_end': window_end,
            'event_ids': [(6, 0, events.ids)] if events else False,
            'ip_trusted': ip_trusted,
        })
        hit._notify_hit()
        return hit

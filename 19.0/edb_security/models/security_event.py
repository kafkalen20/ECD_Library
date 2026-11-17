# -*- coding: utf-8 -*-
from odoo import api, fields, models

from ..core import guards, masking

EVENT_TYPES = [
    ('login_success', '로그인 성공'),
    ('login_failed', '로그인 실패'),
    ('password_changed', '비밀번호 변경'),
    ('account_activated', '계정 활성화'),
    ('apikey', 'API 키'),
    ('acl_changed', '권한 변경'),
    ('model_changed', '모델 변경'),
    ('export', '내보내기'),
    ('bulk_read', '대량 조회'),
    ('config_changed', '설정 변경'),
    ('gc', '파기'),
    ('selfcheck', '자가점검'),
]

SEVERITIES = [
    ('info', '정보'),
    ('notice', '주의'),
    ('high', '높음'),
    ('critical', '치명'),
]

# 배지 색 (Odoo 색 팔레트 번호): 치명 빨강, 높음 주황, 주의 노랑, 정보 파랑
SEVERITY_COLORS = {'critical': 1, 'high': 2, 'notice': 3, 'info': 4}


def display_login(value):
    """저장값 `unknown:<HMAC>` 를 사람이 읽는 표시로 바꾼다. 저장값은 그대로 둔다."""
    if value and value.startswith('unknown:'):
        return '미등록 계정 (%s)' % value[len('unknown:'):][:4]
    return value


class SecurityEvent(models.Model):
    _name = 'edb.security.event'
    _description = '보안 이벤트'
    _order = 'id desc'
    _allow_sudo_commands = False

    event_type = fields.Selection(EVENT_TYPES, string='유형', required=True, index=True)
    severity = fields.Selection(SEVERITIES, string='심각도', default='info', required=True, index=True)
    severity_color = fields.Integer(compute='_compute_severity_color')

    user_id = fields.Many2one('res.users', string='사용자', ondelete='set null', index=True)
    login = fields.Char(string='로그인 문자열')
    login_display = fields.Char(string='로그인', compute='_compute_login_display')

    client_ip = fields.Char(string='클라이언트 IP', index=True)
    ip_trusted = fields.Boolean(string='IP 신뢰', default=False,
                                help='프록시 모드가 올바로 설정된 상태에서 수집된 IP인지 여부')
    user_agent = fields.Char(string='User-Agent')
    http_path = fields.Char(string='요청 경로')
    auth_method = fields.Char(string='인증 경로')

    model_name = fields.Char(string='대상 모델')
    record_count = fields.Integer(string='영향 건수', default=0)
    field_names = fields.Char(string='변경 필드', help='필드 이름만 저장한다. 값은 저장하지 않는다.')

    detail = fields.Json(string='부가 정보')

    # 발동 이력의 event_ids 와 같은 관계 표를 반대 방향에서 읽는다
    hit_ids = fields.Many2many('edb.security.rule.hit', 'edb_security_event_edb_security_rule_hit_rel',
                               'edb_security_event_id', 'edb_security_rule_hit_id',
                               string='발동 이력', readonly=True)
    # 나중에 꺼진(보관된) 룰도 당시 발동 기록으로 보여야 한다
    rule_ids = fields.Many2many('edb.security.rule', string='탐지 룰', compute='_compute_rule_ids',
                                context={'active_test': False})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('detail'):
                vals['detail'] = masking.mask_value(vals['detail'])
            if vals.get('field_names'):
                vals['field_names'] = masking.mask(vals['field_names'])
        return super().create(vals_list)

    @api.depends('hit_ids.rule_id')
    def _compute_rule_ids(self):
        for event in self:
            event.rule_ids = event.hit_ids.rule_id

    @api.depends('severity')
    def _compute_severity_color(self):
        for rec in self:
            rec.severity_color = SEVERITY_COLORS.get(rec.severity, 0)

    @api.depends('login')
    def _compute_login_display(self):
        for event in self:
            event.login_display = display_login(event.login)

    @api.depends('event_type', 'login', 'user_id')
    def _compute_display_name(self):
        labels = dict(EVENT_TYPES)
        for event in self:
            who = display_login(event.login) or event.user_id.login or '-'
            event.display_name = '%s / %s' % (labels.get(event.event_type, event.event_type), who)

    def _register_hook(self):
        guards.enable_db(self.env.cr.dbname)
        return super()._register_hook()

    def _unregister_hook(self):
        guards.disable_db(self.env.cr.dbname)
        return super()._unregister_hook()

    def action_trace_user(self):
        """이 계정의 전 이벤트를 시간순으로 연다."""
        self.ensure_one()
        domain = [('user_id', '=', self.user_id.id)] if self.user_id \
            else [('login', '=', self.login)]
        return {
            'type': 'ir.actions.act_window',
            'name': '계정 추적: %s' % (display_login(self.login) or self.user_id.login),
            'res_model': 'edb.security.event',
            'view_mode': 'list',
            'domain': domain,
            'context': {'search_default_g_type': 0},
        }

    def action_trace_ip(self):
        """이 IP 의 전 이벤트를 시간순으로 연다."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'IP 추적: %s' % self.client_ip,
            'res_model': 'edb.security.event',
            'view_mode': 'list',
            'domain': [('client_ip', '=', self.client_ip)],
        }

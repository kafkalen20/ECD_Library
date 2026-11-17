# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..core import guards
from .security_event import SEVERITIES, SEVERITY_COLORS, display_login


class SecurityRuleHit(models.Model):
    _name = 'edb.security.rule.hit'
    _description = '보안 룰 발동 이력'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _allow_sudo_commands = False

    # _allow_sudo_commands = False 로 둔다. 이 모델을 코모델로 참조하는 다른
    # 모델(예: event_ids 같은 관계 필드)이 sudo 컨텍스트에서 (6,0,ids) 류의
    # 커맨드로 이 모델을 우회 생성/수정하지 못하게 막는 용도다. 코어는 이 값이
    # False 인 comodel 에 대해 sudo 커맨드를 예외 없이 조용히 해제하고 트랜잭션
    # 기본 사용자로 되돌린다(fields_relational.py:_check_sudo_commands). 다만
    # 이 강등은 Command.CREATE 로 comodel 에 신규 라인을 만들 때만 의미가
    # 있고, event_ids 처럼 기존 레코드를 (6,0,ids) 로 연결하는 경우는
    # write_real() 끝의 접근 검사(`if not model.env.su:` — model 은 이 모델
    # 자신, comodel 이 아니다)가 관건이다. 이 검사는 model.env 가 이미
    # sudo() 상태(su=True)면 무조건 건너뛴다 — cron 여부와 무관하게, 호출부가
    # .sudo() 를 쓰기만 하면 항상 스킵되는 것이지 "조용히 실패"하는 경로가
    # 아니다. cron 이 superuser 로 도는 것도 설계가 아니라 우연이다:
    # ir.cron.user_id 의 default 는 self.env.user 이고(ir_cron.py), 이
    # 모듈의 크론 레코드(data/ir_cron_data.xml)는 user_id 를 명시하지 않아
    # 모듈 데이터 로딩 시점의 실행 사용자인 SUPERUSER_ID 를 그대로 물려받을
    # 뿐이다.
    rule_id = fields.Many2one('edb.security.rule', string='룰',
                              required=True, ondelete='cascade', index=True)
    severity = fields.Selection(SEVERITIES, string='심각도', required=True, index=True)
    severity_color = fields.Integer(compute='_compute_severity_color')
    group_key = fields.Char(string='그룹 키 (저장값)', help='계정 / IP / 전역')
    group_key_display = fields.Char(string='그룹 키', compute='_compute_group_key_display')
    matched_value = fields.Integer(string='측정값')
    window_start = fields.Datetime(string='구간 시작')
    window_end = fields.Datetime(string='구간 끝')
    event_ids = fields.Many2many('edb.security.event', string='관련 이벤트')
    ip_trusted = fields.Boolean(string='IP 신뢰')
    state = fields.Selection([
        ('new', '신규'),
        ('ack', '확인'),
        ('closed', '종결'),
    ], string='상태', default='new', required=True, index=True)

    @api.depends('severity')
    def _compute_severity_color(self):
        for rec in self:
            rec.severity_color = SEVERITY_COLORS.get(rec.severity, 0)

    @api.depends('group_key')
    def _compute_group_key_display(self):
        for hit in self:
            hit.group_key_display = display_login(hit.group_key)

    @api.depends('rule_id', 'group_key')
    def _compute_display_name(self):
        for hit in self:
            hit.display_name = ' / '.join(filter(None, [hit.rule_id.name, display_login(hit.group_key)]))

    def _check_monitor_access(self):
        # sudo write 는 ACL 을 타지 않으므로 RPC 직접 호출을 여기서 막는다.
        if not (self.env.su or self.env.user.has_group(
                'edb_security.group_security_monitor')):
            raise AccessError("보안 감사자만 실행할 수 있습니다.")

    def action_ack(self):
        self._check_monitor_access()
        self.sudo().write({'state': 'ack'})

    def action_close(self):
        self._check_monitor_access()
        self.sudo().write({'state': 'closed'})

    def _notify_hit(self):
        """치명 등급은 즉시 활동을 만든다.

        mail.activity 생성은 담당자에게 메일을 보낸다 (res.users.notification_type
        기본값이 email). 담당자 != 생성자 조건만 만족하면 된다.
        """
        self.ensure_one()
        if self.severity != 'critical':
            return
        if not guards.is_active(self.env, 'notify_critical'):
            return
        users = self.rule_id.notify_user_ids
        if not users:
            # 상위 그룹(group_system 등)이 imply 하는 사용자까지 포함해야 한다.
            users = self.env.ref('edb_security.group_security_monitor').all_user_ids
        for user in users:
            self.sudo().activity_schedule(
                'mail.mail_activity_data_warning',
                summary='[보안] %s' % self.rule_id.name,
                # group_key 는 사용자가 입력한 로그인 문자열일 수 있어(비밀번호 오타 등)
                # 메일로 내보내지 않는다. 원문은 히트 레코드에서 권한자만 본다.
                note='측정값: %s / 상세는 이 활동이 붙은 히트 레코드에서 확인하세요.' % self.matched_value,
                user_id=user.id,
            )

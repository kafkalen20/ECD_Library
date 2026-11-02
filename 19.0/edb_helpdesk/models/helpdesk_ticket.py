# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    requester_id = fields.Many2one(
        comodel_name='hr.employee', string='요청자', required=True)
    assignee = fields.Char(string='담당자', tracking=True)
    request_date = fields.Date(
        string='요청일자', default=fields.Date.today, required=True)
    expected_completion_date = fields.Date(string='완료예정일자', tracking=True)
    completion_date = fields.Date(string='완료일자', tracking=True)
    ticket_no = fields.Integer(
        string='ID',
        compute='_compute_ticket_no',
        store=True,
        index=True,
    )

    @api.depends('ticket_ref')
    def _compute_ticket_no(self):
        """ ticket_ref(Char 시퀀스) → 정수 ID. 목록 내림차순 정렬용. """
        for ticket in self:
            try:
                ticket.ticket_no = int(ticket.ticket_ref) if ticket.ticket_ref else 0
            except (ValueError, TypeError):
                ticket.ticket_no = 0

    def _track_template(self, changes):
        """ 단계 변경 시 설정(Ecodoobiz)의 담당자 이메일로 알림 발송.

        원본(helpdesk_bsr)은 common_bsr 의 common.code 에서 DEV 이메일을
        읽어 stage 템플릿의 수신자를 덮어썼다. 공용 모듈에서는 common_bsr
        의존을 제거하고, 설정(res.config.settings)의 시스템 파라미터
        ``edb_helpdesk.notify_email`` 에서 주소를 읽는다.
        미설정 시 표준 동작(변경 없음)을 유지한다.
        """
        res = super()._track_template(changes)

        notify_email = self.env['ir.config_parameter'].sudo().get_param(
            'edb_helpdesk.notify_email')
        if not notify_email:
            return res

        ticket = self[0]
        template_id = ticket.stage_id.template_id
        if 'stage_id' in changes and template_id:
            # stage 알림 템플릿의 수신자를 담당자 이메일로 지정.
            template_id.sudo().write({
                'email_to': notify_email,
                'partner_to': '',
            })
            res['stage_id'] = (template_id, {
                'auto_delete_keep_log': False,
                'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
                'email_layout_xmlid': 'mail.mail_notification_light',
            })

        return res

# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AlimtalkResult(models.Model):
    _name = 'barobill.alimtalk.result'
    _description = '알림톡 발송 결과'
    _order = 'send_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='명칭', compute='_compute_name', store=True)
    template_name = fields.Char(string='템플릿명')
    message = fields.Text(string='발송내용')
    to_number = fields.Char(string='수신번호')
    to_name = fields.Char(string='수신자명')
    send_date = fields.Datetime(string='발송일시')
    state = fields.Selection([
        ('전송실패', '전송실패'),
        ('전송성공', '전송성공'),
    ], string='전송상태')
    error_message = fields.Text(string='오류 메시지')

    @api.depends('template_name', 'to_name', 'state')
    def _compute_name(self):
        for rec in self:
            parts = [p for p in (rec.template_name, rec.to_name, rec.state) if p]
            rec.name = '_'.join(parts) or '알림톡 발송 결과'

    def action_resend(self):
        """이 발송 결과의 저장된 내용으로 새 알림톡 초안을 만들어 재발송 준비.

        저장된 템플릿/제목/내용/수신처를 그대로 채운 barobill.alimtalk 초안 레코드를
        생성하고 폼으로 연다. 사용자가 내용 확인 후 [알림톡 발송]을 누르면 발송된다.
        (테스트 모드 redirect 등 발송 로직은 barobill.alimtalk 에서 그대로 적용)
        """
        self.ensure_one()
        alimtalk = self.env['barobill.alimtalk'].create({
            'template_name': self.template_name or '',
            'message': self.message or '',
            'to_number': self.to_number or '',
            'to_name': self.to_name or False,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': '알림톡 재발송',
            'res_model': 'barobill.alimtalk',
            'res_id': alimtalk.id,
            'view_mode': 'form',
            'target': 'current',
        }

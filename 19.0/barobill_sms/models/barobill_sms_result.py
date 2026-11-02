# -*- coding: utf-8 -*-

from odoo import fields, models


class SmsResult(models.Model):
    _name = 'barobill.sms.result'
    _description = 'SMS 발송 결과'
    _order = 'send_date desc, id desc'

    contents = fields.Text(string='발송내용')
    from_number = fields.Char(string='발신번호')
    to_number = fields.Char(string='수신번호')
    to_name = fields.Char(string='수신자명')
    send_date = fields.Datetime(string='발송일시')
    state = fields.Selection([
        ('전송실패', '전송실패'),
        ('전송성공', '전송성공'),
    ], string='전송상태')
    error_message = fields.Text(string='오류 메시지')

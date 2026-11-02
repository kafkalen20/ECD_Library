# -*- coding: utf-8 -*-

from odoo import fields, models


class BarobillTaxInvoiceResult(models.Model):
    _name = 'barobill.tax_invoice.result'
    _description = 'Barobill 세금계산서 처리 결과'
    _order = 'create_date desc, id desc'

    tax_invoice_id = fields.Many2one('barobill.tax_invoice', string='세금계산서',
                                     ondelete='cascade', readonly=True)
    name = fields.Char(related='tax_invoice_id.name', string='문서번호', store=True)
    action = fields.Selection([
        ('regist', '저장'),
        ('update', '수정'),
        ('issue', '발급'),
        ('delete', '삭제'),
        ('cancel', '취소'),
        ('popup', '조회'),
    ], string='처리구분', readonly=True)
    state = fields.Selection([
        ('실패', '실패'),
        ('성공', '성공'),
    ], string='결과', readonly=True)
    management_number = fields.Char(string='관리번호', readonly=True)
    approval_number = fields.Char(string='국세청 승인번호', readonly=True)
    message = fields.Text(string='메시지', readonly=True)
    create_date = fields.Datetime(string='처리일시', readonly=True)

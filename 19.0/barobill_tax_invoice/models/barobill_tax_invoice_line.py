# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BarobillTaxInvoiceLine(models.Model):
    _name = 'barobill.tax_invoice.line'
    _description = 'Barobill 세금계산서 품목'

    tax_invoice_id = fields.Many2one('barobill.tax_invoice', string='세금계산서',
                                     required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='tax_invoice_id.currency_id', string='통화')
    tax_type = fields.Selection(related='tax_invoice_id.tax_type', string='과세형태')

    product_name = fields.Char(string='품목명', required=True)
    product_standard = fields.Char(string='규격')
    quantity = fields.Float(string='수량', digits='Product Unit of Measure', default=1)
    price_unit = fields.Float(string='단가', digits='Product Price', default=0)
    price_subtotal = fields.Monetary(string='공급가액', compute='_compute_amounts', store=True)
    price_tax = fields.Monetary(string='세액', compute='_compute_amounts', store=True)
    price_total = fields.Monetary(string='합계', compute='_compute_amounts', store=True)
    note = fields.Text(string='비고')

    @api.depends('quantity', 'price_unit', 'tax_type')
    def _compute_amounts(self):
        for line in self:
            subtotal = (line.quantity or 0.0) * (line.price_unit or 0.0)
            # 과세('1')만 부가세 10%, 영세/면세는 0
            tax = round(subtotal * 0.1) if line.tax_type == '1' else 0.0
            line.price_subtotal = subtotal
            line.price_tax = tax
            line.price_total = subtotal + tax

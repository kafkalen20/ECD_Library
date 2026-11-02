# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # 인증 정보(mode/certkey/corpnum/id)는 barobill 공통 설정에서 관리.

    # ====================== 환경별 endpoint ======================
    barobill_tax_invoice_server_test = fields.Char(
        string='테스트 서버 URL',
        config_parameter='barobill_tax_invoice.test.server',
    )
    barobill_tax_invoice_server_prod = fields.Char(
        string='운영 서버 URL',
        config_parameter='barobill_tax_invoice.prod.server',
    )

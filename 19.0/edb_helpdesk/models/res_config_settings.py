# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    edb_helpdesk_notify_email = fields.Char(
        string='고객센터 담당자 이메일',
        config_parameter='edb_helpdesk.notify_email',
    )

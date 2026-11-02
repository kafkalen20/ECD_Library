# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    # 타임시트(고객센터 티켓 작업) 라인의 담당자.
    assignee = fields.Char(string='담당자', tracking=True)
    # 표준은 로그인 사용자를 기본 담당자로 넣지만, 고객센터에서는 담당자를
    # 문자열로 직접 입력하므로 user_id 기본값을 비운다.
    user_id = fields.Many2one(default=False)

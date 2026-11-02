# -*- coding: utf-8 -*-
from odoo import models


class ResConfigSettings(models.TransientModel):
    """에코두비즈 공통(edb_common) 설정.

    설정 앱의 'Ecodoobiz' 카테고리에 표시된다.
    공용으로 필요한 설정 필드를 여기에 추가한다. (예: config_parameter 연동 필드)
    현재는 카테고리 등록용 자리표시자이며 필드가 추가되지 않았다.
    """

    _inherit = 'res.config.settings'

    # 예시) 새 공통 설정 필드를 아래에 추가:
    # edb_some_option = fields.Boolean(
    #     string="공통 옵션",
    #     config_parameter='edb_common.some_option',
    # )

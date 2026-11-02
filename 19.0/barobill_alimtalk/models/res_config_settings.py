# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # 인증 정보(mode/certkey/corpnum/id)는 barobill 공통 설정에서 관리.

    # ====================== 환경별 endpoint ======================
    barobill_alimtalk_server_test = fields.Char(
        string='테스트 서버 URL',
        config_parameter='barobill_alimtalk.test.server',
    )
    barobill_alimtalk_server_prod = fields.Char(
        string='운영 서버 URL',
        config_parameter='barobill_alimtalk.prod.server',
    )

    # ====================== 발신프로필 (알림톡 전용) ======================
    barobill_alimtalk_yellowid = fields.Char(
        string='발신프로필 (YellowId)',
        config_parameter='barobill_alimtalk.yellowid',
        help='카카오 비즈니스 채널의 발신프로필 키 (바로빌에 등록된 옐로아이디/senderKey)',
    )

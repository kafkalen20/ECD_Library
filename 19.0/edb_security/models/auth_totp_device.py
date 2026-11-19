# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request

from ..core import collector


class AuthTotpDevice(models.Model):
    _inherit = 'auth_totp.device'

    def _check_credentials_for_uid(self, *, scope, key, uid):
        ok = super()._check_credentials_for_uid(scope=scope, key=key, uid=uid)
        # 신뢰 기기 쿠키로 2단계를 건너뛴 로그인 (auth_totp/controllers/home.py).
        # 로그인 중(pre_uid 만 있고 uid 없음)일 때만 성공으로 남긴다.
        if ok and scope == 'browser' and request \
                and request.session.get('pre_uid') == uid and not request.session.uid:
            user = self.env['res.users'].sudo().browse(uid)
            collector.record(
                self.env, 'hook_login', 'login_success',
                severity='info',
                user_id=uid, login=user.login,
                auth_method='trusted_device',
            )
        return ok

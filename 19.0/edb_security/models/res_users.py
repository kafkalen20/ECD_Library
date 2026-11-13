# -*- coding: utf-8 -*-
import hashlib
import hmac

from odoo import models
from odoo.exceptions import AccessDenied

from ..core import collector, guards


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _secmon_failed_login_value(self, login):
        """실패한 로그인 문자열을 저장용으로 바꾼다.

        실존 계정의 login 이면 평문 그대로(조사에 필요). 아니면 ID 칸에 잘못 친
        비밀번호일 수 있으므로 `unknown:<HMAC 12자>` 로 축약한다. 같은 입력은
        같은 값이라 R-01 의 login 집계는 유지된다. 솔트 없는 sha256 은 약한
        비밀번호를 사전 공격으로 되살릴 수 있어 DB 비밀키로 HMAC 한다.
        조회는 res.users.login 의 UNIQUE 인덱스를 타며 실패 경로에서만 1회 돈다.
        """
        if not login or not isinstance(login, str):
            return login
        if not guards.is_active(self.env, 'hook_login'):
            return None  # 어차피 기록되지 않는다. 조회 비용을 쓰지 않는다.
        try:
            exists = self.sudo().with_context(active_test=False).search_count(
                self._get_login_domain(login), limit=1)
            if exists:
                return login
            secret = self.env['ir.config_parameter'].sudo().get_param('database.secret') or ''
            digest = hmac.new(secret.encode(), login.encode(), hashlib.sha256).hexdigest()
            return 'unknown:' + digest[:12]
        except Exception:
            # 이 값 계산이 원래의 AccessDenied 를 가리면 안 된다. 판정 불가면 평문을 버린다.
            return None

    def _login(self, credential, user_agent_env):
        login = (credential or {}).get('login')
        try:
            auth_info = super()._login(credential, user_agent_env)
        except AccessDenied as exc:
            # 이 경로는 호출자에 따라 요청 트랜잭션이 통째로 롤백된다.
            # 분리 커넥션으로 기록해야 증적이 남는다 (설계서 §3.2).
            collector.record(
                self.env, 'hook_login', 'login_failed',
                severity='high', detached=True,
                login=self._secmon_failed_login_value(login),
                auth_method=(credential or {}).get('type'),
                # AccessDenied 서브클래스가 빈 메시지를 던지는 경우에 대비한 폴백.
                # 사고 조사에서 사유가 빈 문자열로 남는 것을 막는다.
                detail={'reason': str(exc) or 'AccessDenied'},
            )
            raise
        collector.record(
            self.env, 'hook_login', 'login_success',
            severity='info',
            login=login,
            user_id=(auth_info or {}).get('uid'),
            auth_method=(auth_info or {}).get('auth_method'),
        )
        return auth_info

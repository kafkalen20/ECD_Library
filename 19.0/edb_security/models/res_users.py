# -*- coding: utf-8 -*-
import hashlib
import hmac

from odoo import models
from odoo.exceptions import AccessDenied
from odoo.http import request

from ..core import collector, guards

#: 로그인 2단계에서 쓰는 credential 유형 (auth_totp, auth_totp_mail)
_MFA_TYPES = ('totp', 'totp_mail')


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _secmon_mfa_pending(self, auth_info, user_agent_env):
        """비밀번호는 통과했고 2단계 인증이 남았는지.

        코어 `odoo/http.py` `Session.authenticate` 의 finalize 생략 조건과 똑같이
        맞춘다 (코어 조건이 바뀌면 여기도 바꾼다). RPC(`common.authenticate`)는
        interactive 가 없고 2단계 없이 끝난다. 패스키는 mfa='skip' 이다.
        판정 실패가 로그인을 막으면 안 되므로 예외는 '대기 아님'으로 본다.
        """
        try:
            uid = (auth_info or {}).get('uid')
            return bool(
                uid
                and (user_agent_env or {}).get('interactive')
                and (auth_info or {}).get('mfa') != 'skip'
                and self.sudo().browse(uid)._mfa_url()
            )
        except Exception:
            return False

    def _secmon_is_login_mfa(self):
        """지금 2단계 인증 검사가 로그인 중인 것인지.

        `_check_credentials` 는 비밀번호 재확인(res.users.identitycheck) 등에서도
        불린다. 로그인 중이면 세션에 pre_uid 만 있고 uid 는 아직 없다
        (`Session.finalize` 가 pre_uid 를 꺼내 uid 로 옮긴다).
        """
        return bool(request and request.session.get('pre_uid') == self.id
                    and not request.session.uid)

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
        # 2단계 인증이 남았으면 아직 로그인이 아니다. 성공은 2단계 통과 때 남긴다.
        mfa_pending = self._secmon_mfa_pending(auth_info, user_agent_env)
        collector.record(
            self.env, 'hook_login',
            'login_mfa_pending' if mfa_pending else 'login_success',
            severity='info',
            login=login,
            user_id=(auth_info or {}).get('uid'),
            auth_method=(auth_info or {}).get('auth_method'),
        )
        return auth_info

    def _check_credentials(self, credential, env):
        if credential.get('type') not in _MFA_TYPES or not self._secmon_is_login_mfa():
            return super()._check_credentials(credential, env)
        try:
            auth_info = super()._check_credentials(credential, env)
        except AccessDenied as exc:
            # 코드 오류와 검사 한도 초과가 같은 AccessDenied 다. 구분은 reason 문구로
            # 한다 (번역 문구라 집계 키로 쓰지 않는다). 지금 컨트롤러는 예외를 잡아
            # 롤백하지 않지만, 다른 호출 경로를 생각해 login_failed 처럼 분리 기록한다.
            collector.record(
                self.env, 'hook_login', 'login_mfa_failed',
                severity='high', detached=True,
                user_id=self.id, login=self.sudo().login,
                auth_method=credential['type'],
                detail={'reason': str(exc) or 'AccessDenied'},
            )
            raise
        collector.record(
            self.env, 'hook_login', 'login_success',
            severity='info',
            user_id=self.id, login=self.sudo().login,
            auth_method=credential['type'],
        )
        return auth_info

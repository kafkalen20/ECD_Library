# -*- coding: utf-8 -*-
import logging

import pytz

from odoo import fields, models
from odoo.exceptions import AccessError, ValidationError

from ..core import guards
from ..core.collector import create_event_isolated

_logger = logging.getLogger(__name__)

PREFIX = 'edb_security.'

#: 프리셋별로 켜둘 토글. 나열되지 않은 토글은 끈다.
#: 최소 = 실제로 소비자가 있는 토글만 (guards.is_active 소비자 3곳).
PRESET_MINIMAL = {'hook_login', 'detect_engine', 'notify_critical'}
PRESET_STANDARD = set(guards.TOGGLES)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    secmon_hook_login = fields.Boolean(
        string='로그인 이벤트 수집',
        config_parameter=PREFIX + 'hook_login', default=True)
    secmon_hook_user_write = fields.Boolean(
        string='사용자 변경 수집',
        config_parameter=PREFIX + 'hook_user_write', default=True)
    secmon_hook_apikey = fields.Boolean(
        string='API 키 수집',
        config_parameter=PREFIX + 'hook_apikey', default=True)
    secmon_hook_acl = fields.Boolean(
        string='권한 구조 변경 수집',
        config_parameter=PREFIX + 'hook_acl', default=True)
    secmon_hook_config = fields.Boolean(
        string='설정 변경 수집',
        config_parameter=PREFIX + 'hook_config', default=True)
    secmon_detect_engine = fields.Boolean(
        string='탐지 엔진',
        config_parameter=PREFIX + 'detect_engine', default=True)
    secmon_notify_critical = fields.Boolean(
        string='치명 즉시 알림',
        config_parameter=PREFIX + 'notify_critical', default=True)
    secmon_notify_digest = fields.Boolean(
        string='일일 다이제스트',
        config_parameter=PREFIX + 'notify_digest', default=True)
    secmon_gc_enabled = fields.Boolean(
        string='보존기간 파기',
        config_parameter=PREFIX + 'gc_enabled', default=True)
    secmon_selfcheck_enabled = fields.Boolean(
        string='자가점검',
        config_parameter=PREFIX + 'selfcheck_enabled', default=True)

    secmon_business_tz = fields.Char(
        string='업무시간 타임존',
        config_parameter=PREFIX + 'business_tz', default='Asia/Seoul')
    secmon_business_start = fields.Integer(
        string='업무 시작(시)',
        config_parameter=PREFIX + 'business_start', default=9)
    secmon_business_end = fields.Integer(
        string='업무 종료(시)',
        config_parameter=PREFIX + 'business_end', default=19)
    secmon_retention_months = fields.Integer(
        string='이벤트 보존(개월)',
        config_parameter=PREFIX + 'retention_months', default=12)

    @staticmethod
    def _toggle_bool(code, raw):
        # 저장된 원문 문자열을 직접 해석한다. bool('False') 는 True 이므로
        # 그대로 bool() 을 씌우면 안 된다.
        return guards.TOGGLES[code] if raw in (False, None, '') else raw == 'True'

    def get_values(self):
        res = super().get_values()
        # 코어 res.config.settings.default_get() 는 불리언 config_parameter 를
        # bool(value) 로 변환하는데, value 는 DB 에 저장된 문자열이라
        # bool('False') 가 True 가 되어버린다 (빈 문자열이 아닌 모든 문자열은
        # 참). 그 결과 '끔' 으로 저장한 토글도 설정 화면을 다시 열면 켜진
        # 것처럼 보인다. 저장된 원문 문자열을 직접 해석해 덮어쓴다.
        icp = self.env['ir.config_parameter'].sudo()
        for code in guards.TOGGLES:
            res['secmon_' + code] = self._toggle_bool(code, icp.get_param(PREFIX + code))
        return res

    def _log_toggle_change(self, code, old, new):
        """토글 변경 자체를 증적으로 남긴다.

        collector.record() 는 hook_config 토글에 게이트되는데, 공격자가
        그 토글을 먼저 꺼버리면 자신의 토글 변경 자체가 무기록이 된다.
        게이트를 우회해 직접 기록하고, 기록 실패가 설정 저장을 막지
        않도록 격리한다. 값은 True/False 뿐이라 개인정보가 아니다.
        """
        try:
            # 다른 모듈의 설정 쓰기가 보류 중일 수 있어 flush=False 헬퍼를 쓴다.
            create_event_isolated(self.env, {
                'event_type': 'config_changed',
                'severity': 'high',
                'user_id': self.env.user.id,
                'login': self.env.user.login,
                'detail': {'toggle': code, 'old': old, 'new': new},
            })
        except Exception:
            _logger.warning("설정 토글 변경 기록 실패: %s", code, exc_info=True)

    def _check_monitor_access(self):
        if not (self.env.su or self.env.user.has_group(
                'edb_security.group_security_monitor')):
            raise AccessError("보안 감사자만 실행할 수 있습니다.")

    def set_values(self):
        # 오타 하나로 R-03 이 조용히 영구 무발동되지 않도록 저장 전에 검증한다.
        tz_name = self.secmon_business_tz
        if tz_name:
            try:
                pytz.timezone(tz_name)
            except pytz.UnknownTimeZoneError:
                raise ValidationError("알 수 없는 타임존입니다: %s" % tz_name)
        icp = self.env['ir.config_parameter'].sudo()
        # super().set_values() 가 이 필드들의 config_parameter 를 먼저 건드릴
        # 수 있으므로, 변경 여부를 비교할 이전값은 반드시 그 전에 읽어둔다.
        old_values = {code: self._toggle_bool(code, icp.get_param(PREFIX + code))
                      for code in guards.TOGGLES}

        res = super().set_values()
        # 코어 res.config.settings.set_values() 는 불리언 필드를 비교할 때
        # ir.config_parameter 가 아직 저장된 적이 없으면 get_param() 이 False
        # 를 돌려주는데, 이는 '끔'과 '기본값 True 인 채로 미저장'을 구분하지
        # 못한다 (False == False). 그 결과 기본이 True 인 토글을 설치 후
        # 처음 끌 때 ir.config_parameter 에 아예 기록되지 않는다.
        # (odoo/addons/base/models/res_config.py 의 set_values 참조)
        # 토글만은 값 그대로를 명시적으로 다시 써서 이 문제를 피한다.
        for code in guards.TOGGLES:
            icp.set_param(PREFIX + code, 'True' if self['secmon_' + code] else 'False')
        guards.invalidate(self.env.cr.dbname)

        for code in guards.TOGGLES:
            new_value = bool(self['secmon_' + code])
            if old_values[code] != new_value:
                self._log_toggle_change(code, old_values[code], new_value)
        return res

    def _apply_preset(self, enabled):
        icp = self.env['ir.config_parameter'].sudo()
        for code in guards.TOGGLES:
            old = self._toggle_bool(code, icp.get_param(PREFIX + code))
            new = code in enabled
            icp.set_param(PREFIX + code, 'True' if new else 'False')
            if old != new:
                self._log_toggle_change(code, old, new)
        guards.invalidate(self.env.cr.dbname)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_apply_preset_minimal(self):
        self._check_monitor_access()
        return self._apply_preset(PRESET_MINIMAL)

    def action_apply_preset_standard(self):
        self._check_monitor_access()
        return self._apply_preset(PRESET_STANDARD)

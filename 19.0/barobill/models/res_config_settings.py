# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api
from odoo.exceptions import UserError

from .common import (
    get_shared_mode, get_shared_auth, get_base_server,
)
from odoo.addons.barobill.controllers.barobill import BarobillController

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ============================================================
    # 바로빌 공통 계정 — SMS/FAX/알림톡 세 채널이 동일 계정을 사용.
    # (server URL·발신번호·발신프로필·FTP 등 채널별 값은 각 채널 모듈 설정에 유지)
    # ============================================================
    barobill_mode = fields.Selection(
        [('test', '테스트'), ('prod', '운영')],
        string='활성 환경',
        config_parameter='barobill.mode',
        default='test',
        help='실제 전송 시 사용할 환경. 모드 토글로 각 채널 SOAP 서버 endpoint 만 전환되고 '
             '인증 정보는 공통 사용.',
    )
    barobill_certkey = fields.Char(
        string='연동인증키',
        config_parameter='barobill.certkey',
    )
    barobill_corpnum = fields.Char(
        string='사업자등록번호',
        config_parameter='barobill.corpnum',
        help='하이픈 없이 10자리 숫자',
    )
    barobill_id = fields.Char(
        string='바로빌 ID',
        config_parameter='barobill.id',
    )

    # ============================================================
    # 공통 API(포인트/오류조회)용 SOAP 서버 endpoint — 환경별.
    # ============================================================
    barobill_server_test = fields.Char(
        string='테스트 서버 URL',
        config_parameter='barobill.test.server',
    )
    barobill_server_prod = fields.Char(
        string='운영 서버 URL',
        config_parameter='barobill.prod.server',
    )

    # ============================================================
    # 포인트(잔액) — 이력 없이 현재값만 config_parameter 에 덮어쓰기.
    #  - barobill.point.balance    : 최근 조회 잔액
    #  - barobill.point.checked_at : 최근 조회 시각
    # ============================================================
    barobill_point_balance = fields.Float(
        string='현재 포인트 잔액',
        readonly=True,
        compute='_compute_barobill_point_info',
        help='바로빌 보유 포인트(원). cron 이 주기적으로 자동 갱신.',
    )
    barobill_point_checked_at = fields.Datetime(
        string='조회 시각',
        readonly=True,
        compute='_compute_barobill_point_info',
    )

    @api.depends_context('uid')
    def _compute_barobill_point_info(self):
        ICP = self.env['ir.config_parameter'].sudo()
        balance = ICP.get_param('barobill.point.balance')
        checked_at = ICP.get_param('barobill.point.checked_at')
        for rec in self:
            rec.barobill_point_balance = float(balance) if balance else 0.0
            rec.barobill_point_checked_at = checked_at or False

    @api.model
    def _get_point_config(self):
        """포인트 조회용 접속 정보 (공통 서버 + 공통 계정) 반환. 미설정 시 UserError."""
        server = get_base_server(self.env)
        certkey, corpnum, _barobill_id = get_shared_auth(self.env)
        missing = [k for k, v in [
            ('서버 URL', server), ('인증키', certkey), ('사업자번호', corpnum),
        ] if not v]
        if missing:
            raise UserError(
                '바로빌 포인트 조회 설정이 누락되었습니다: %s\n'
                '설정 > 바로빌 > 공통 설정 에서 등록하세요.' % ', '.join(missing)
            )
        return server, certkey, corpnum

    @api.model
    def _fetch_barobill_point_balance(self):
        """바로빌 보유 포인트를 조회해 config_parameter 에 저장하고 잔액을 반환. 실패 시 UserError."""
        server, certkey, corpnum = self._get_point_config()
        api = BarobillController(server, certkey)
        result = api._get_balance_cost_amount(corpnum)
        if result is None:
            raise UserError('바로빌 포인트 조회 실패: 응답이 없습니다.')
        balance = float(result)
        if balance < 0:
            err_code = int(balance)
            try:
                err_msg = api._get_err_string(err_code)
            except Exception:
                err_msg = ''
            raise UserError('바로빌 포인트 조회 실패 (오류코드 %s): %s' % (err_code, err_msg))

        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('barobill.point.balance', balance)
        ICP.set_param('barobill.point.checked_at', fields.Datetime.to_string(fields.Datetime.now()))
        return balance

    def action_check_barobill_point_balance(self):
        """설정 화면 '지금 조회' 버튼 — 즉시 조회 후 화면 새로고침."""
        self._fetch_barobill_point_balance()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model
    def _cron_check_barobill_point_balance(self):
        """주기 cron — 잔액 조회 후 갱신. 실패는 로그만 남기고 넘어간다."""
        try:
            balance = self._fetch_barobill_point_balance()
            _logger.info('바로빌 포인트 잔액 갱신: %s', balance)
        except Exception as e:
            _logger.warning('바로빌 포인트 잔액 조회 실패(cron): %s', e)

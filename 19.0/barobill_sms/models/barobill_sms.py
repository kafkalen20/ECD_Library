# -*- coding: utf-8 -*-

import re
from datetime import datetime

from odoo import models, fields, api
from odoo.exceptions import UserError

from odoo.addons.barobill.models.common import (
    get_shared_mode, get_shared_auth,
)
from odoo.addons.barobill_sms.controllers.barobill_sms import BarobillSmsController


class BarobillSms(models.Model):
    _name = 'barobill.sms'
    _description = 'Barobill SMS'
    _order = 'create_date desc'

    from_number = fields.Char(string='발신번호', required=True, default=lambda self: self._default_from_number())
    to_number = fields.Char(string='수신번호', required=True)
    to_name = fields.Char(string='수신자명')
    contents = fields.Text(string='내용', required=True)

    state = fields.Selection([
        ('draft', '대기'),
        ('sent', '전송성공'),
        ('failed', '전송실패'),
    ], string='상태', default='draft', readonly=True)
    send_key = fields.Char(string='전송키', readonly=True)
    send_date = fields.Datetime(string='발송일시', readonly=True)
    error_message = fields.Text(string='오류메시지', readonly=True)

    # 전송 상태 조회 결과
    send_state = fields.Char(string='전송상태', readonly=True)

    @api.model
    def _default_from_number(self):
        return self.env['ir.config_parameter'].sudo().get_param('barobill_sms.default_from', '')

    @api.model
    def _get_active_mode(self):
        """현재 활성 환경 모드 ('test' 또는 'prod') — 공통 계정 기준."""
        return get_shared_mode(self.env)

    @api.model
    def _get_barobill_config(self):
        """SOAP 인증 설정 조회. server 는 채널별, 인증정보(certkey/corpnum/id)는 공통 계정.

        - 환경별 서버: barobill_sms.{mode}.server
        - 하위호환 fallback: barobill_sms.server (기존 단일 키)
        """
        ICP = self.env['ir.config_parameter'].sudo()
        mode = self._get_active_mode()
        server = (
            ICP.get_param(f'barobill_sms.{mode}.server')
            or ICP.get_param('barobill_sms.server')
        )
        certkey, corpnum, barobill_id = get_shared_auth(self.env)
        missing = [k for k, v in [
            ('서버 URL', server), ('인증키', certkey),
            ('사업자번호', corpnum), ('바로빌 ID', barobill_id),
        ] if not v]
        if missing:
            mode_label = '운영' if mode == 'prod' else '테스트'
            raise UserError(
                '바로빌 SMS 설정이 누락되었습니다 (모드=%s): %s\n'
                '설정 > 바로빌 에서 등록하세요.' % (mode_label, ', '.join(missing))
            )
        return server, certkey, corpnum, barobill_id

    def _get_barobill_api(self):
        """바로빌 SMS API 컨트롤러 및 인증정보(corpnum, barobill_id) 반환."""
        server, certkey, corpnum, barobill_id = self._get_barobill_config()
        return BarobillSmsController(server, certkey), corpnum, barobill_id

    def action_send_sms(self):
        """SMS/LMS 메시지 발송 (내용 길이에 따라 자동 선택)"""
        self.ensure_one()

        api, corpnum, barobill_id = self._get_barobill_api()

        final_to = self.to_number
        final_contents = self.contents

        result = api._send_message(
            corpnum=corpnum,
            sender_id=barobill_id,
            from_number=self.from_number,
            to_name=self.to_name,
            to_number=final_to,
            contents=final_contents,
        )

        self.send_date = datetime.now()

        result_vals = {
            'contents': final_contents,
            'from_number': self.from_number,
            'to_number': final_to,
            'to_name': self.to_name,
            'send_date': self.send_date,
        }

        if re.compile(r'^-[0-9]{5}$').match(result) is not None:
            error = api._get_err_string(result)
            error_msg = f'오류코드: {result}\n오류내용: {error}'
            self.write({
                'state': 'failed',
                'error_message': error_msg,
            })
            result_vals.update({
                'state': '전송실패',
                'error_message': error_msg,
            })
        else:
            self.write({
                'state': 'sent',
                'send_key': result,
                'error_message': False,
            })
            result_vals.update({
                'state': '전송성공',
            })

        self.env['barobill.sms.result'].sudo().create(result_vals)

        return True

    def action_reset(self):
        """상태 초기화"""
        self.ensure_one()
        self.write({
            'state': 'draft',
            'send_key': False,
            'send_date': False,
            'error_message': False,
            'send_state': False,
        })
        return True

    @api.model
    def create_record(self):
        """테스트 레코드 생성 액션"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'SMS 발송 테스트',
            'res_model': 'barobill.sms',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_contents': '안녕하세요.\n테스트 메시지입니다.\n감사합니다.',
            },
        }

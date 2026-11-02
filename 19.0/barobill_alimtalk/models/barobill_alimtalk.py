# -*- coding: utf-8 -*-

import re
from datetime import datetime

from odoo import models, fields, api
from odoo.exceptions import UserError

from odoo.addons.barobill.models.common import (
    get_shared_mode, get_shared_auth,
)
from odoo.addons.barobill_alimtalk.controllers.barobill_alimtalk import BarobillAlimtalkController


class BarobillAlimtalk(models.Model):
    """바로빌 카카오톡 알림톡 발송 (SendATKakaotalksEx).

    barobill_sms 와 동일한 구조: 공통 계정(barobill.*)로 인증, zeep SOAP 클라이언트로
    발송, 결과를 barobill.alimtalk.result 에 로그.
    알림톡은 SMS/LMS 와 달리 YellowId(발신프로필)와 TemplateName(사전 승인 템플릿)이 필요.
    """
    _name = 'barobill.alimtalk'
    _description = 'Barobill KakaoTalk AlimTalk'
    _order = 'create_date desc'

    to_number = fields.Char(string='수신번호', required=True)
    to_name = fields.Char(string='수신자명')
    template_name = fields.Char(
        string='템플릿명', required=True,
        help='바로빌 콘솔에 사전 등록/승인된 알림톡 템플릿명',
    )
    title = fields.Char(string='강조 제목', help='강조표시형 템플릿에서만 사용 (선택)')
    message = fields.Text(string='내용', required=True, help='템플릿 변수 치환이 완료된 최종 발송 내용')

    state = fields.Selection([
        ('draft', '대기'),
        ('sent', '전송성공'),
        ('failed', '전송실패'),
    ], string='상태', default='draft', readonly=True)
    send_key = fields.Char(string='전송키', readonly=True)
    send_date = fields.Datetime(string='발송일시', readonly=True)
    error_message = fields.Text(string='오류메시지', readonly=True)

    @api.model
    def _get_active_mode(self):
        """현재 활성 환경 모드 ('test' 또는 'prod') — 공통 계정 기준."""
        return get_shared_mode(self.env)

    @api.model
    def _get_barobill_config(self):
        """SOAP/인증 설정 조회. server·yellowid 만 알림톡 전용, 인증정보는 공통 계정.

        반환: (server, certkey, corpnum, barobill_id, yellowid)
        """
        ICP = self.env['ir.config_parameter'].sudo()
        mode = self._get_active_mode()
        server = (
            ICP.get_param(f'barobill_alimtalk.{mode}.server')
            or ICP.get_param('barobill_alimtalk.server')
        )
        certkey, corpnum, barobill_id = get_shared_auth(self.env)
        yellowid = ICP.get_param('barobill_alimtalk.yellowid')
        missing = [k for k, v in [
            ('서버 URL', server), ('인증키', certkey), ('사업자번호', corpnum),
            ('바로빌 ID', barobill_id), ('발신프로필(YellowId)', yellowid),
        ] if not v]
        if missing:
            mode_label = '운영' if mode == 'prod' else '테스트'
            raise UserError(
                '바로빌 알림톡 설정이 누락되었습니다 (모드=%s): %s\n'
                '설정 > 바로빌 에서 등록하세요.' % (mode_label, ', '.join(missing))
            )
        return server, certkey, corpnum, barobill_id, yellowid

    def _get_barobill_api(self):
        """바로빌 알림톡 API 컨트롤러 및 인증정보(corpnum, barobill_id, yellowid) 반환."""
        server, certkey, corpnum, barobill_id, yellowid = self._get_barobill_config()
        return BarobillAlimtalkController(server, certkey), corpnum, barobill_id, yellowid

    def action_send_alimtalk(self):
        """알림톡 발송 (SendATKakaotalksEx)."""
        self.ensure_one()
        api, corpnum, barobill_id, yellowid = self._get_barobill_api()

        final_to = self.to_number
        final_message = self.message

        result = api._send_at_kakaotalks(
            corpnum=corpnum,
            sender_id=barobill_id,
            yellowid=yellowid,
            template_name=self.template_name,
            to_number=final_to,
            to_name=self.to_name,
            message=final_message,
            title=self.title,
        )

        self.send_date = datetime.now()

        # 결과는 문자열(또는 문자열 배열). 오류코드는 -XXXXX 형태.
        codes = list(result) if isinstance(result, (list, tuple)) else [result]
        err_code = next(
            (str(c) for c in codes if c is not None and re.compile(r'^-[0-9]{5}$').match(str(c))),
            None,
        )

        result_vals = {
            'template_name': self.template_name,
            'to_number': final_to,
            'to_name': self.to_name,
            'message': final_message,
            'send_date': self.send_date,
        }

        if err_code is not None:
            error = api._get_err_string(err_code)
            error_msg = f'오류코드: {err_code}\n오류내용: {error}'
            self.write({'state': 'failed', 'error_message': error_msg})
            result_vals.update({'state': '전송실패', 'error_message': error_msg})
        else:
            send_key = str(codes[0]) if codes and codes[0] is not None else False
            self.write({'state': 'sent', 'send_key': send_key, 'error_message': False})
            result_vals.update({'state': '전송성공'})

        self.env['barobill.alimtalk.result'].sudo().create(result_vals)
        return True

    def action_reset(self):
        """상태 초기화"""
        self.ensure_one()
        self.write({
            'state': 'draft',
            'send_key': False,
            'send_date': False,
            'error_message': False,
        })
        return True

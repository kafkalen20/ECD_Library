# -*- coding: utf-8 -*-
"""바로빌 SMS SOAP API 호출 래퍼."""

from odoo.addons.barobill.controllers.barobill import BarobillController


class BarobillSmsController(BarobillController):

    def _send_message(self, corpnum, sender_id, from_number, to_number, contents, to_name=None):
        """SMS/LMS 발송 (SendMessage). 성공 시 전송키, 실패 시 -XXXXX 문자열 반환."""
        return self.client.service.SendMessage(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            SenderID=sender_id,
            FromNumber=from_number,
            ToName=to_name or '',
            ToNumber=to_number,
            Contents=contents,
        )

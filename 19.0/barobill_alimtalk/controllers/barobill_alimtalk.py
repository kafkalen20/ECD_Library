# -*- coding: utf-8 -*-
"""바로빌 카카오톡 알림톡 SOAP API 호출 래퍼."""

import re

from odoo.addons.barobill.controllers.barobill import BarobillController


class BarobillAlimtalkController(BarobillController):

    def _send_at_kakaotalks(self, corpnum, sender_id, yellowid, template_name,
                            to_number, message, to_name=None, title=None):
        """알림톡 발송 (SendATKakaotalksEx).

        SOAP 복합 타입(KakaotalkATMessageEx) 구성까지 포함. 본문(message)은 승인
        템플릿과 일치해야 하므로 호출부에서 가공 완료된 값을 그대로 전달할 것.
        결과는 문자열 또는 문자열 배열(전송키/‑XXXXX 오류코드).
        """
        KakaotalkATMessageEx = self.client.get_type('ns0:KakaotalkATMessageEx')
        ArrayOfKakaotalkATMessageEx = self.client.get_type('ns0:ArrayOfKakaotalkATMessageEx')

        msg_data = {
            'ReceiverNum': re.sub(r'\D', '', to_number or ''),
            'ReceiverName': to_name or '',
            'Message': message or '',
            'SmsSubject': '',
            'SmsMessage': '',
            'Buttons': None,
        }
        if title:
            msg_data['Title'] = title
        message_obj = KakaotalkATMessageEx(**msg_data)

        return self.client.service.SendATKakaotalksEx(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            SenderID=sender_id,
            YellowId=yellowid,
            TemplateName=template_name,
            SendDT='',
            SmsReply='N',
            SmsSenderNum='',
            KakaotalkMessages=ArrayOfKakaotalkATMessageEx([message_obj]),
        )

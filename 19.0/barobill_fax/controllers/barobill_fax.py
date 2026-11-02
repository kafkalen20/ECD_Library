# -*- coding: utf-8 -*-
"""바로빌 팩스 SOAP API 호출 래퍼."""

from odoo.addons.barobill.controllers.barobill import BarobillController


class BarobillFaxController(BarobillController):

    def _send_fax_from_ftp(self, corpnum, sender_id, file_name, from_number,
                           to_number, receive_corp, receive_name):
        """FTP 업로드된 파일로 팩스 전송 (SendFaxFromFTP).

        성공 시 접수번호(SendKey), 실패 시 음수 문자열 반환.
        """
        return self.client.service.SendFaxFromFTP(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            SenderID=sender_id,
            FileName=file_name,
            FromNumber=from_number,
            ToNumber=to_number,
            ReceiveCorp=receive_corp,
            ReceiveName=receive_name,
            SendDT='',
            RefKey='',
        )

    def _get_fax_message(self, corpnum, send_key):
        """팩스 전송 상태/결과 조회 (GetFaxMessageEx2). FaxMessage 객체 반환."""
        return self.client.service.GetFaxMessageEx2(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            SendKey=send_key,
        )

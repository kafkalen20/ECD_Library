# -*- coding: utf-8 -*-

from odoo import models, fields, api


# 팩스 전송 상태
FAX_SEND_STATES = [
    ('0', '파일변환대기중'),
    ('1', '파일변환중'),
    ('2', '파일변환완료(전송중)'),
    ('3', '전송완료'),
    ('4', '예약취소'),
    ('5', '파일변환실패'),
    ('6', '전송실패'),
    ('7', '부분성공'),
    ('8', '파일용량초과'),
]

# 팩스 전송결과 코드
FAX_SEND_RESULTS = {
    '802': '완료',
    '803': '통화중 (재전송시도)',
    '804': '잘못된 수신번호',
    '805': '응답없음',
    '807': '수신거부',
    '808': '알수없는 오류',
    '101': '파일변환실패',
    '103': '파일용량초과',
    '801': '부분완료',
}


class BarobillFaxResult(models.Model):
    _name = 'barobill.fax.result'
    _description = 'Barobill Fax 전송 결과'
    _order = 'id desc'

    fax_id = fields.Many2one('barobill.fax', string='팩스 전송', ondelete='cascade', readonly=True)
    send_key = fields.Char(string='접수번호', readonly=True)

    # === FaxMessageEx2 필드 ===
    sender_num = fields.Char(string='발신번호', readonly=True)
    receiver_num = fields.Char(string='수신번호', readonly=True)
    receive_corp = fields.Char(string='수신자 회사명', readonly=True)
    receiver_name = fields.Char(string='수신자명', readonly=True)
    send_file_name = fields.Char(string='전송 파일명', readonly=True)

    reserve_yn = fields.Selection([
        ('0', '즉시전송'),
        ('1', '예약전송'),
    ], string='예약여부', readonly=True)
    reserve_dt = fields.Datetime(string='예약일시', readonly=True)

    send_state = fields.Selection(FAX_SEND_STATES, string='전송상태', readonly=True)
    send_dt = fields.Datetime(string='전송일시', readonly=True)
    end_dt = fields.Datetime(string='전송완료일시', readonly=True)

    send_result = fields.Char(string='전송결과코드', readonly=True)
    send_result_msg = fields.Char(string='전송결과', readonly=True, compute='_compute_send_result_msg')
    send_page_count = fields.Integer(string='전송 페이지 수', readonly=True)
    success_page_count = fields.Integer(string='성공 페이지 수', readonly=True)

    @api.depends('send_result')
    def _compute_send_result_msg(self):
        for rec in self:
            rec.send_result_msg = FAX_SEND_RESULTS.get(rec.send_result, rec.send_result or '')

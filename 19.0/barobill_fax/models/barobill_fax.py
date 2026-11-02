# -*- coding: utf-8 -*-

import base64
import ftplib
import io
import logging
import uuid
from datetime import datetime, timedelta

import pytz

from odoo import models, fields, api
from odoo.exceptions import UserError

from odoo.addons.barobill.models.common import (
    get_shared_mode, get_shared_auth,
)
from odoo.addons.barobill_fax.controllers.barobill_fax import BarobillFaxController

_logger = logging.getLogger(__name__)

# 바로빌 API 시각은 KST 기준으로 반환됨 (YYYYMMDDHHMMSS 14자리).
# Odoo Datetime 컬럼은 UTC naive 로 저장되므로 변환이 필요하다.
_BAROBILL_TZ = pytz.timezone('Asia/Seoul')


def _parse_barobill_dt(raw):
    """바로빌 API 응답의 일시 문자열을 Odoo Datetime(UTC naive) 으로 변환.

    - 14자리 YYYYMMDDHHMMSS (KST) → UTC 변환 후 naive 반환
    - 19자리 ISO 형식 → fields.Datetime.from_string 위임
    - 빈값/파싱 실패 → False
    """
    if not raw:
        return False
    raw = str(raw).strip()
    if len(raw) == 14 and raw.isdigit():
        try:
            naive_kst = datetime.strptime(raw, '%Y%m%d%H%M%S')
        except ValueError:
            return False
        return _BAROBILL_TZ.localize(naive_kst).astimezone(pytz.UTC).replace(tzinfo=None)
    try:
        return fields.Datetime.from_string(raw)
    except (ValueError, TypeError):
        return False


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

# 지원 파일 확장자
ALLOWED_EXTENSIONS = {
    'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
    'jpg', 'gif', 'bmp', 'png', 'tif', 'tiff',
    'hwp', 'gul', 'pdf',
    'txt', 'htm', 'html',
}


class BarobillFax(models.Model):
    _name = 'barobill.fax'
    _description = 'Barobill Fax'
    _order = 'create_date desc'

    # === 발송 정보 ===
    from_number = fields.Char(string='발신번호', required=True, default=lambda self: self._default_from_number())
    to_number = fields.Char(string='수신번호', required=True)
    receive_corp = fields.Char(string='수신자 회사명')
    receive_name = fields.Char(string='수신자명')

    # === 파일 첨부 ===
    file_data = fields.Binary(string='전송 파일', required=True, attachment=True)
    file_name = fields.Char(string='파일명')

    # === 전송 결과 ===
    state = fields.Selection([
        ('draft', '대기'),
        ('sent', '전송접수'),
        ('success', '전송완료'),
        ('failed', '전송실패'),
    ], string='상태', default='draft', readonly=True)
    send_key = fields.Char(string='접수번호', readonly=True)
    send_date = fields.Datetime(string='발송일시', readonly=True)
    error_message = fields.Text(string='오류메시지', readonly=True)

    # === 전송 상태 조회 결과 ===
    send_state = fields.Selection(
        FAX_SEND_STATES, string='전송상태', readonly=True,
    )
    send_result = fields.Char(string='전송결과코드', readonly=True)
    send_result_msg = fields.Char(
        string='전송결과', readonly=True, compute='_compute_send_result_msg',
    )
    send_page_count = fields.Integer(string='전송 페이지 수', readonly=True)
    success_page_count = fields.Integer(string='성공 페이지 수', readonly=True)

    # === 전송 결과 이력 ===
    result_ids = fields.One2many('barobill.fax.result', 'fax_id', string='전송 결과 이력', readonly=True)

    @api.depends('send_result')
    def _compute_send_result_msg(self):
        for rec in self:
            rec.send_result_msg = FAX_SEND_RESULTS.get(rec.send_result, rec.send_result or '')

    @api.model
    def _get_active_mode(self):
        """현재 활성 환경 모드 ('test' 또는 'prod') — 공통 계정 기준."""
        return get_shared_mode(self.env)

    @api.model
    def _default_from_number(self):
        # 발신번호는 환경 공통.
        return self.env['ir.config_parameter'].sudo().get_param('barobill_fax.default_from', '')

    @api.model
    def _get_barobill_config(self):
        """SOAP/인증 설정 조회. server 만 환경별, 나머지(certkey/corpnum/id)는 공통.

        하드코딩 fallback 없음 — 미설정 시 아래 missing 검사에서 오류.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        mode = self._get_active_mode()
        server = ICP.get_param(f'barobill_fax.{mode}.server')
        certkey, corpnum, barobill_id = get_shared_auth(self.env)
        missing = [k for k, v in [
            ('서버 URL', server), ('인증키', certkey),
            ('사업자번호', corpnum), ('바로빌 ID', barobill_id),
        ] if not v]
        if missing:
            mode_label = '운영' if mode == 'prod' else '테스트'
            raise UserError(
                '바로빌 FAX 설정이 누락되었습니다 (모드=%s): %s\n'
                '설정 > 바로빌 에서 등록하세요.' % (mode_label, ', '.join(missing))
            )
        return server, certkey, corpnum, barobill_id

    @api.model
    def _get_ftp_config(self):
        """FTP 호스트/포트는 환경별, 비밀번호는 공통. 하드코딩 fallback 없음 — 미설정 시 오류."""
        ICP = self.env['ir.config_parameter'].sudo()
        mode = self._get_active_mode()
        host = ICP.get_param(f'barobill_fax.{mode}.ftp_host')
        port = ICP.get_param(f'barobill_fax.{mode}.ftp_port')
        password = ICP.get_param('barobill_fax.ftp_password', '')
        missing = [k for k, v in [('FTP 호스트', host), ('FTP 포트', port)] if not v]
        if missing:
            mode_label = '운영' if mode == 'prod' else '테스트'
            raise UserError(
                '바로빌 FAX FTP 설정이 누락되었습니다 (모드=%s): %s\n'
                '설정 > 바로빌 에서 등록하세요.' % (mode_label, ', '.join(missing))
            )
        return host, int(port), password

    def _get_barobill_api(self):
        """바로빌 팩스 API 컨트롤러 및 인증정보(corpnum, barobill_id) 반환."""
        server, certkey, corpnum, barobill_id = self._get_barobill_config()
        return BarobillFaxController(server, certkey), corpnum, barobill_id

    def _is_error_response(self, result):
        """응답값이 오류인지 판별 (음수 값 형식의 문자열이면 오류)"""
        try:
            return int(result) < 0
        except (ValueError, TypeError):
            return False

    def _check_file_extension(self):
        """파일 확장자가 지원되는지 확인"""
        self.ensure_one()
        if not self.file_name:
            return False
        ext = self.file_name.rsplit('.', 1)[-1].lower() if '.' in self.file_name else ''
        return ext in ALLOWED_EXTENSIONS

    def _upload_to_ftp(self):
        """바로빌 FTP에 파일 업로드. 업로드된 파일명을 반환."""
        self.ensure_one()

        # 바로빌 ID(공통 계정) 와 FTP 비밀번호는 환경 공통.
        _certkey, _corpnum, barobill_id = get_shared_auth(self.env)
        if not barobill_id:
            raise UserError('바로빌 ID 설정이 누락되었습니다. 설정 > 바로빌 에서 등록하세요.')
        host, port, password = self._get_ftp_config()
        if not password:
            raise UserError('바로빌 FTP 비밀번호 설정이 누락되었습니다. 설정 > 바로빌 에서 등록하세요.')

        # 바로빌 FTP 서버는 한국 Windows MS949(CP949) 기반.
        # CP949 매핑 가능한 파일명은 그대로 사용, 매핑 불가(이모지/일부 유럽 액센트 등)이면 UUID 로 변환.
        upload_name = self.file_name or ''
        try:
            upload_name.encode('cp949')
        except UnicodeEncodeError:
            ext = upload_name.rsplit('.', 1)[-1].lower() if '.' in upload_name else 'pdf'
            upload_name = '%s.%s' % (uuid.uuid4().hex, ext)
            _logger.info(
                '[barobill_fax] 파일명 CP949 매핑 불가 — UUID 변환: %r → %r',
                self.file_name, upload_name,
            )

        file_content = base64.b64decode(self.file_data)
        file_stream = io.BytesIO(file_content)

        ftp = ftplib.FTP()
        ftp.encoding = 'cp949'  # 바로빌 FTP 서버 기본 multi-byte code page
        ftp.set_pasv(True)
        try:
            ftp.connect(host, port, timeout=10)
            ftp.login(barobill_id, password)
            ftp.storbinary('STOR %s' % upload_name, file_stream)
        finally:
            try:
                ftp.quit()
            except Exception:
                pass

        return upload_name

    def _create_fail_result(self, error_msg):
        """전송 실패 결과를 이력에 저장"""
        self.ensure_one()
        self.env['barobill.fax.result'].create({
            'fax_id': self.id,
            'send_key': self.send_key or '',
            'sender_num': self.from_number,
            'receiver_num': self.to_number,
            'receive_corp': self.receive_corp or '',
            'receiver_name': self.receive_name or '',
            'send_file_name': self.file_name or '',
            'send_state': '6',
            'send_result': error_msg,
            'send_dt': fields.Datetime.now(),
        })

    def action_send_fax(self):
        """FTP에 파일 업로드 후 팩스 전송 API 호출"""
        self.ensure_one()

        if self.state != 'draft':
            return True

        # 파일 확장자 검증
        if not self._check_file_extension():
            error_msg = (f'지원하지 않는 파일 형식입니다.\n'
                         f'지원 확장자: {", ".join(sorted(ALLOWED_EXTENSIONS))}')
            self.write({
                'state': 'failed',
                'send_date': fields.Datetime.now(),
                'error_message': error_msg,
            })
            self._create_fail_result(error_msg)
            return True

        api, corpnum, barobill_id = self._get_barobill_api()

        # 1단계: FTP에 파일 업로드
        try:
            uploaded_filename = self._upload_to_ftp()
        except Exception as e:
            error_msg = f'FTP 업로드 실패: {str(e)}'
            self.write({
                'state': 'failed',
                'send_date': fields.Datetime.now(),
                'error_message': error_msg,
            })
            self._create_fail_result(error_msg)
            return True

        final_to = self.to_number
        final_receive_corp = self.receive_corp or ''
        final_receive_name = self.receive_name or ''

        # 2단계: 팩스 전송 API 호출
        result = api._send_fax_from_ftp(
            corpnum=corpnum,
            sender_id=barobill_id,
            file_name=uploaded_filename,
            from_number=self.from_number,
            to_number=final_to,
            receive_corp=final_receive_corp,
            receive_name=final_receive_name,
        )

        now = fields.Datetime.now()

        if self._is_error_response(result):
            error = api._get_err_string(result)
            self.write({
                'state': 'failed',
                'send_date': now,
                'error_message': f'오류코드: {result}\n오류내용: {error}',
            })
            self._create_fail_result(f'오류코드: {result}\n오류내용: {error}')
        else:
            self.write({
                'state': 'sent',
                'send_key': result,
                'send_date': now,
                'error_message': False,
            })

        return True

    def action_check_status(self):
        """전송 상태 조회 (GetFaxMessageEx2 API 호출)"""
        self.ensure_one()

        if not self.send_key:
            return True

        api, corpnum, barobill_id = self._get_barobill_api()

        message = api._get_fax_message(corpnum=corpnum, send_key=self.send_key)

        send_state = str(message.SendState)

        if self._is_error_response(send_state):
            error = api._get_err_string(send_state)
            self.write({
                'state': 'failed',
                'error_message': f'상태조회 오류코드: {send_state}\n오류내용: {error}',
            })
        else:
            vals = {
                'send_state': send_state,
                'send_result': message.SendResult or '',
                'send_page_count': message.SendPageCount or 0,
                'success_page_count': message.SuccessPageCount or 0,
            }

            # 전송완료(3) 시 최종 상태 반영
            if send_state == '3':
                if message.SendResult == '802':
                    vals['state'] = 'success'
                else:
                    vals['state'] = 'failed'
                    result_msg = FAX_SEND_RESULTS.get(
                        message.SendResult, message.SendResult
                    )
                    vals['error_message'] = f'전송결과: {result_msg}'

            # 파일변환실패(5), 전송실패(6), 파일용량초과(8)
            elif send_state in ('5', '6', '8'):
                vals['state'] = 'failed'
                state_label = dict(FAX_SEND_STATES).get(send_state, send_state)
                vals['error_message'] = f'전송상태: {state_label}'

            # 예약취소(4)
            elif send_state == '4':
                vals['state'] = 'failed'
                vals['error_message'] = '예약이 취소되었습니다.'

            self.write(vals)

            # 전송 결과 이력 저장 — 상태가 바뀔 때만 1건 기록 (전이 이력).
            # 직전 이력과 (send_state, send_result)가 동일하면 폴링마다 누적되는
            # 중복이므로 건너뛴다.
            new_result = message.SendResult or ''
            last_result = self.env['barobill.fax.result'].search(
                [('fax_id', '=', self.id)], order='id desc', limit=1,
            )
            if not (last_result
                    and last_result.send_state == send_state
                    and (last_result.send_result or '') == new_result):
                self.env['barobill.fax.result'].create({
                    'fax_id': self.id,
                    'send_key': self.send_key,
                    'sender_num': getattr(message, 'SenderNum', '') or '',
                    'receiver_num': getattr(message, 'ReceiverNum', '') or '',
                    'receive_corp': getattr(message, 'ReceiveCorp', '') or '',
                    'receiver_name': getattr(message, 'ReceiverName', '') or '',
                    'send_file_name': getattr(message, 'SendFileName', '') or '',
                    'reserve_yn': str(message.ReserveYN) if hasattr(message, 'ReserveYN') and message.ReserveYN in (0, 1) else False,
                    'reserve_dt': _parse_barobill_dt(getattr(message, 'ReserveDT', None)),
                    'send_state': send_state,
                    'send_dt': _parse_barobill_dt(getattr(message, 'SendDT', None)),
                    'end_dt': _parse_barobill_dt(getattr(message, 'EndDT', None)),
                    'send_result': new_result,
                    'send_page_count': message.SendPageCount or 0,
                    'success_page_count': message.SuccessPageCount or 0,
                })

        return True

    @api.model
    def _cron_check_pending_status(self):
        """2분 주기 — 진행 중 barobill.fax record 자동 상태 조회.

        대상: send_key 있음 (발송 접수 완료) AND send_state in ('0','1','2', False) (진행 중 또는 미정의)
        시간 범위: create_date > now - 12h (그 이전은 결과 fix 됐을 가능성 — skip)
        """
        cutoff = fields.Datetime.now() - timedelta(hours=12)
        pending = self.search([
            ('send_key', '!=', False),
            '|', ('send_state', 'in', ['0', '1', '2']), ('send_state', '=', False),
            ('create_date', '>=', cutoff),
        ])
        _logger.info('[barobill_fax cron] %d pending fax records 폴링', len(pending))
        for fax in pending:
            try:
                fax.action_check_status()
            except Exception as e:
                _logger.warning('[barobill_fax cron] fax=%s 폴링 실패: %s', fax.id, e)

    def action_reset(self):
        """상태 초기화"""
        self.ensure_one()
        self.write({
            'state': 'draft',
            'send_key': False,
            'send_date': False,
            'error_message': False,
            'send_state': False,
            'send_result': False,
            'send_page_count': 0,
            'success_page_count': 0,
        })
        return True

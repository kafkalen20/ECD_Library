# -*- coding: utf-8 -*-

import pytz

from odoo import models, fields, api
from odoo.exceptions import UserError

from odoo.addons.barobill.models.common import (
    get_shared_mode, get_shared_auth,
)
from odoo.addons.barobill_cash_receipt.controllers.barobill_cash_receipt import (
    BarobillCashReceiptController,
)

_KST = pytz.timezone('Asia/Seoul')


class BarobillCashReceipt(models.Model):
    _name = 'barobill.cash_receipt'
    _description = 'Barobill 현금영수증'
    _order = 'create_date desc'

    name = fields.Char(string='문서번호', default='신규', readonly=True, copy=False)

    # === 가맹점(발행자) 정보 ===
    franchise_corp_num = fields.Char(string='가맹점 사업자번호', required=True,
                                     default=lambda self: self._default_franchise('corp_num'))
    franchise_member_id = fields.Char(string='가맹점 바로빌ID',
                                      default=lambda self: self._default_franchise('member_id'))
    franchise_corp_name = fields.Char(string='가맹점 상호', required=True,
                                      default=lambda self: self._default_franchise('corp_name'))
    franchise_ceo_name = fields.Char(string='가맹점 대표자명',
                                     default=lambda self: self._default_franchise('ceo_name'))
    franchise_addr = fields.Char(string='가맹점 주소',
                                 default=lambda self: self._default_franchise('addr'))
    franchise_tel = fields.Char(string='가맹점 연락처',
                                default=lambda self: self._default_franchise('tel'))

    # === 거래 정보 ===
    partner_id = fields.Many2one('res.partner', string='고객',
                                 help='선택 시 이메일 등 일부 정보를 자동으로 채웁니다.')
    trade_date = fields.Date(string='거래일자', required=True, default=fields.Date.context_today)
    trade_type = fields.Selection([
        ('N', '승인거래'),
        ('D', '취소거래'),
    ], string='거래구분', default='N', required=True)
    trade_usage = fields.Selection([
        ('1', '소득공제'),
        ('2', '지출증빙'),
    ], string='거래용도', default='1', required=True)
    trade_method = fields.Selection([
        ('5', '휴대폰번호 (자진발급 포함)'),
        ('1', '카드번호'),
        ('3', '주민등록번호'),
        ('4', '사업자번호'),
    ], string='거래방법', default='5', required=True)
    identity_num = fields.Char(string='소비자 신분확인번호', required=True,
                               help='거래방법에 맞는 번호 (휴대폰/카드/주민번호/사업자번호). 자진발급 시 010-000-1234')
    hp = fields.Char(string='휴대폰')
    email = fields.Char(string='이메일')
    item_name = fields.Char(string='품목명')

    # === 금액 ===
    currency_id = fields.Many2one('res.currency', string='통화',
                                  default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string='공급가액', required=True)
    tax = fields.Monetary(string='부가세', required=True)
    amount_total = fields.Monetary(string='합계금액', compute='_compute_amount_total', store=True)

    # === 상태/결과 ===
    state = fields.Selection([
        ('draft', '작성'),
        ('save', '저장'),
        ('issued', '발급'),
        ('cancel', '취소'),
    ], string='상태', default='draft', readonly=True, copy=False)
    management_number = fields.Char(string='관리번호(MgtKey)', readonly=True, copy=False)
    confirm_number = fields.Char(string='국세청 승인번호', readonly=True, copy=False)
    error_message = fields.Text(string='오류메시지', readonly=True, copy=False)

    result_ids = fields.One2many('barobill.cash_receipt.result', 'cash_receipt_id',
                                 string='처리 이력', readonly=True)

    # ------------------------------------------------------------------
    # 기본값 / onchange / compute
    # ------------------------------------------------------------------
    @api.model
    def _default_franchise(self, key):
        """가맹점 기본값 — 공통 계정 사업자번호/바로빌ID + 회사 정보."""
        company = self.env.company
        _, corpnum, barobill_id = get_shared_auth(self.env)
        return {
            'corp_num': corpnum or '',
            'member_id': barobill_id or '',
            'corp_name': company.name or '',
            'ceo_name': '',
            'addr': company.partner_id.contact_address or '',
            'tel': company.phone or '',
        }.get(key, '')

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """고객 선택 시 연락처/이메일 자동 채움."""
        p = self.partner_id
        if not p:
            return
        self.email = p.email or ''
        self.hp = p.mobile or p.phone or ''

    @api.depends('amount', 'tax')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = (rec.amount or 0.0) + (rec.tax or 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '신규') == '신규':
                vals['name'] = self.env['ir.sequence'].next_by_code('barobill.cash_receipt') or '신규'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft_or_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'cancel'):
                raise UserError('저장/발급된 현금영수증은 삭제할 수 없습니다. 먼저 삭제(임시저장 해제) 처리하세요.')

    # ------------------------------------------------------------------
    # config / api
    # ------------------------------------------------------------------
    @api.model
    def _get_active_mode(self):
        """현재 활성 환경 모드 ('test' 또는 'prod') — 공통 계정 기준."""
        return get_shared_mode(self.env)

    @api.model
    def _get_barobill_config(self):
        """SOAP 인증 설정 조회. server 는 채널별, 인증정보(certkey/corpnum/id)는 공통 계정.

        - 환경별 서버: barobill_cash_receipt.{mode}.server
        - 하위호환 fallback: barobill_cash_receipt.server (기존 단일 키)
        """
        ICP = self.env['ir.config_parameter'].sudo()
        mode = self._get_active_mode()
        server = (
            ICP.get_param(f'barobill_cash_receipt.{mode}.server')
            or ICP.get_param('barobill_cash_receipt.server')
        )
        certkey, corpnum, barobill_id = get_shared_auth(self.env)
        missing = [k for k, v in [
            ('서버 URL', server), ('인증키', certkey),
            ('사업자번호', corpnum), ('바로빌 ID', barobill_id),
        ] if not v]
        if missing:
            mode_label = '운영' if mode == 'prod' else '테스트'
            raise UserError(
                '바로빌 현금영수증 설정이 누락되었습니다 (모드=%s): %s\n'
                '설정 > 바로빌 에서 등록하세요.' % (mode_label, ', '.join(missing))
            )
        return server, certkey, corpnum, barobill_id

    def _get_barobill_api(self):
        """바로빌 현금영수증 API 컨트롤러 및 인증정보(corpnum, barobill_id) 반환."""
        server, certkey, corpnum, barobill_id = self._get_barobill_config()
        return BarobillCashReceiptController(server, certkey), corpnum, barobill_id

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_error(result):
        """바로빌 결과가 오류인지 판정 (음수 코드)."""
        try:
            return int(result) < 0
        except (TypeError, ValueError):
            return True

    def _remove_hyphen(self, val):
        return (val or '').replace('-', '')

    def _build_cash_data(self):
        """컨트롤러에 넘길 현금영수증 dict 구성."""
        self.ensure_one()
        mgt_key = self.management_number or self._make_management_number()
        return {
            'mgt_key': mgt_key,
            'franchise_corp_num': self._remove_hyphen(self.franchise_corp_num),
            'franchise_member_id': self.franchise_member_id or '',
            'franchise_corp_name': self.franchise_corp_name or '',
            'franchise_ceo_name': self.franchise_ceo_name or '',
            'franchise_addr': self.franchise_addr or '',
            'franchise_tel': self.franchise_tel or '',
            'identity_num': self.identity_num or '',
            'hp': self.hp or '',
            'fax': '',
            'email': self.email or '',
            'trade_date': self.trade_date.strftime('%Y%m%d'),
            'trade_type': self.trade_type,
            'trade_usage': self.trade_usage,
            'trade_method': self.trade_method,
            'item_name': self.item_name or '',
            'amount': self.amount,
            'tax': self.tax,
        }

    def _make_management_number(self):
        """관리번호(MgtKey) 생성: YYMMDDHHMM-문서번호 (KST 기준)."""
        kst_now = fields.Datetime.now().astimezone(_KST)
        return '%s-%s' % (kst_now.strftime('%y%m%d%H%M'), self.name)

    def _log_result(self, action, ok, message=''):
        """처리 이력 기록."""
        self.env['barobill.cash_receipt.result'].sudo().create({
            'cash_receipt_id': self.id,
            'action': action,
            'state': '성공' if ok else '실패',
            'management_number': self.management_number or '',
            'confirm_number': self.confirm_number or '',
            'message': message or '',
        })

    def _handle_error(self, api, action, result):
        """오류 코드 → 메시지 조회 후 error_message/이력 기록 (상태는 유지)."""
        try:
            err = api._get_err_string(result)
        except Exception:
            err = ''
        message = '오류코드: %s\n오류내용: %s' % (result, err)
        self.write({'error_message': message})
        self._log_result(action, False, message)
        return True

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def action_regist(self):
        """바로빌에 현금영수증 임시저장 (RegistCashBillEx)."""
        self.ensure_one()
        api, corpnum, user_id = self._get_barobill_api()
        if not self.management_number:
            self.management_number = self._make_management_number()
        data = self._build_cash_data()
        result = api._regist_cash_bill(corpnum, user_id, data)
        if self._is_error(result):
            self.management_number = False
            return self._handle_error(api, 'regist', result)
        self.write({'state': 'save', 'error_message': False})
        self._log_result('regist', True)
        return True

    def action_update(self):
        """저장된 현금영수증 수정 (UpdateCashBillEx)."""
        self.ensure_one()
        if self.state != 'save':
            raise UserError("저장 상태의 현금영수증만 수정할 수 있습니다.")
        api, corpnum, user_id = self._get_barobill_api()
        data = self._build_cash_data()
        result = api._update_cash_bill(corpnum, user_id, data)
        if self._is_error(result):
            return self._handle_error(api, 'update', result)
        self.write({'error_message': False})
        self._log_result('update', True)
        return True

    def action_issue(self):
        """저장된 현금영수증 발급 (IssueCashBill)."""
        self.ensure_one()
        if self.state != 'save':
            raise UserError("저장 상태의 현금영수증만 발급할 수 있습니다.")
        api, corpnum, user_id = self._get_barobill_api()
        result = api._issue_cash_bill(corpnum, user_id, self.management_number)
        if self._is_error(result):
            return self._handle_error(api, 'issue', result)
        self.write({'state': 'issued', 'error_message': False})
        # 발급 성공 시 국세청 승인번호 조회
        try:
            state = api._get_cash_bill_state(corpnum, user_id, self.management_number)
            if state is not None and getattr(state, 'BarobillState', 0) > 0:
                self.confirm_number = getattr(state, 'NTSConfirmNum', False) or False
        except Exception:
            pass
        self._log_result('issue', True)
        return True

    def action_delete(self):
        """바로빌에서 현금영수증 삭제 → 작성 상태로 (DeleteCashBill)."""
        self.ensure_one()
        if self.state not in ('save', 'cancel'):
            raise UserError("저장/취소 상태의 현금영수증만 삭제할 수 있습니다.")
        api, corpnum, user_id = self._get_barobill_api()
        result = api._delete_cash_bill(corpnum, user_id, self.management_number)
        if self._is_error(result):
            return self._handle_error(api, 'delete', result)
        self._log_result('delete', True)
        self.write({
            'state': 'draft',
            'management_number': False,
            'confirm_number': False,
            'error_message': False,
        })
        return True

    def action_popup_url(self):
        """바로빌 현금영수증 조회 팝업 URL 열기."""
        self.ensure_one()
        if not self.management_number:
            raise UserError('저장된 현금영수증이 없습니다.')
        api, corpnum, user_id = self._get_barobill_api()
        url = api._get_cash_bill_popup_url(corpnum, user_id, self.management_number)
        if isinstance(url, str) and url.startswith('http'):
            return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}
        return self._handle_error(api, 'popup', url)

    def action_cancel(self):
        """작성 중인 현금영수증을 취소(로컬)로 변경."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("작성 상태의 현금영수증만 취소할 수 있습니다. 저장/발급 건은 삭제 처리하세요.")
        self.write({'state': 'cancel'})
        return True

    def action_reset(self):
        """상태 초기화 (로컬 작성 상태로만 되돌림)."""
        self.ensure_one()
        if self.state in ('save', 'issued'):
            raise UserError('바로빌에 저장/발급된 건은 초기화할 수 없습니다. 삭제 처리 후 이용하세요.')
        self.write({
            'state': 'draft',
            'management_number': False,
            'confirm_number': False,
            'error_message': False,
        })
        return True

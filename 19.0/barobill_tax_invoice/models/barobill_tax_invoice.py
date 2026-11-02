# -*- coding: utf-8 -*-

import pytz

from odoo import models, fields, api
from odoo.exceptions import UserError

from odoo.addons.barobill.models.common import (
    get_shared_mode, get_shared_auth,
)
from odoo.addons.barobill_tax_invoice.controllers.barobill_tax_invoice import (
    BarobillTaxInvoiceController,
)

_KST = pytz.timezone('Asia/Seoul')


class BarobillTaxInvoice(models.Model):
    _name = 'barobill.tax_invoice'
    _description = 'Barobill 세금계산서'
    _order = 'create_date desc'

    name = fields.Char(string='문서번호', default='신규', readonly=True, copy=False)

    # === 문서 정보 ===
    tax_date = fields.Date(string='작성일자', required=True, default=fields.Date.context_today)
    tax_invoice_type = fields.Selection([
        ('1', '세금계산서'),
        ('2', '계산서'),
    ], string='계산서형태', default='1', required=True)
    tax_type = fields.Selection([
        ('1', '과세'),
        ('2', '영세'),
        ('3', '면세'),
    ], string='과세형태', default='1', required=True)
    purpose_type = fields.Selection([
        ('1', '영수'),
        ('2', '청구'),
    ], string='영수/청구', default='2', required=True)
    note = fields.Text(string='비고')

    # === 공급자 (invoicer) ===
    invoicer_corp_num = fields.Char(string='공급자 사업자번호', required=True,
                                    default=lambda self: self._default_invoicer('corp_num'))
    invoicer_corp_name = fields.Char(string='공급자 상호', required=True,
                                     default=lambda self: self._default_invoicer('corp_name'))
    invoicer_ceo_name = fields.Char(string='공급자 대표자명',
                                    default=lambda self: self._default_invoicer('ceo_name'))
    invoicer_addr = fields.Char(string='공급자 주소',
                                default=lambda self: self._default_invoicer('addr'))
    invoicer_biz_class = fields.Char(string='공급자 업태')
    invoicer_biz_type = fields.Char(string='공급자 종목')
    invoicer_contact_name = fields.Char(string='공급자 담당자명',
                                        default=lambda self: self._default_invoicer('ceo_name'))
    invoicer_tel = fields.Char(string='공급자 연락처',
                               default=lambda self: self._default_invoicer('tel'))
    invoicer_email = fields.Char(string='공급자 이메일',
                                 default=lambda self: self._default_invoicer('email'))

    # === 공급받는자 (invoicee) ===
    partner_id = fields.Many2one('res.partner', string='공급받는자',
                                 help='선택 시 아래 공급받는자 정보를 자동으로 채웁니다.')
    invoicee_corp_num = fields.Char(string='공급받는자 사업자번호', required=True)
    invoicee_corp_name = fields.Char(string='공급받는자 상호', required=True)
    invoicee_ceo_name = fields.Char(string='공급받는자 대표자명')
    invoicee_addr = fields.Char(string='공급받는자 주소')
    invoicee_biz_class = fields.Char(string='공급받는자 업태')
    invoicee_biz_type = fields.Char(string='공급받는자 종목')
    invoicee_contact_name = fields.Char(string='공급받는자 담당자명')
    invoicee_tel = fields.Char(string='공급받는자 연락처')
    invoicee_email = fields.Char(string='공급받는자 이메일')

    # === 품목 ===
    line_ids = fields.One2many('barobill.tax_invoice.line', 'tax_invoice_id',
                               string='품목', copy=True)
    currency_id = fields.Many2one('res.currency', string='통화',
                                  default=lambda self: self.env.company.currency_id)
    amount_untaxed = fields.Monetary(string='공급가액', compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary(string='세액', compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(string='합계금액', compute='_compute_amounts', store=True)

    # === 상태/결과 ===
    state = fields.Selection([
        ('draft', '작성'),
        ('save', '저장'),
        ('issued', '발급'),
        ('cancel', '취소'),
    ], string='상태', default='draft', readonly=True, copy=False)
    management_number = fields.Char(string='관리번호(MgtKey)', readonly=True, copy=False)
    approval_number = fields.Char(string='국세청 승인번호', readonly=True, copy=False)
    error_message = fields.Text(string='오류메시지', readonly=True, copy=False)

    result_ids = fields.One2many('barobill.tax_invoice.result', 'tax_invoice_id',
                                 string='처리 이력', readonly=True)

    # ------------------------------------------------------------------
    # 기본값 / onchange / compute
    # ------------------------------------------------------------------
    @api.model
    def _default_invoicer(self, key):
        """공급자 기본값 — 공통 계정 사업자번호 + 회사 정보."""
        company = self.env.company
        _, corpnum, _ = get_shared_auth(self.env)
        return {
            'corp_num': corpnum or '',
            'corp_name': company.name or '',
            'ceo_name': '',
            'addr': company.partner_id.contact_address or '',
            'tel': company.phone or '',
            'email': company.email or '',
        }.get(key, '')

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """공급받는자 선택 시 정보 자동 채움."""
        p = self.partner_id
        if not p:
            return
        self.invoicee_corp_num = (p.vat or '').replace('-', '')
        self.invoicee_corp_name = p.name or ''
        self.invoicee_addr = p.contact_address or ''
        self.invoicee_tel = p.phone or ''
        self.invoicee_email = p.email or ''

    @api.onchange('tax_type')
    def _onchange_tax_type(self):
        """면세 선택 시 계산서형태를 '계산서'로 자동 변경."""
        self.tax_invoice_type = '2' if self.tax_type == '3' else '1'

    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax', 'line_ids.price_total')
    def _compute_amounts(self):
        for rec in self:
            rec.amount_untaxed = sum(rec.line_ids.mapped('price_subtotal'))
            rec.amount_tax = sum(rec.line_ids.mapped('price_tax'))
            rec.amount_total = rec.amount_untaxed + rec.amount_tax

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '신규') == '신규':
                vals['name'] = self.env['ir.sequence'].next_by_code('barobill.tax_invoice') or '신규'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft_or_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'cancel'):
                raise UserError('저장/발급된 세금계산서는 삭제할 수 없습니다. 먼저 삭제(임시저장 해제) 처리하세요.')

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

        - 환경별 서버: barobill_tax_invoice.{mode}.server
        - 하위호환 fallback: barobill_tax_invoice.server (기존 단일 키)
        """
        ICP = self.env['ir.config_parameter'].sudo()
        mode = self._get_active_mode()
        server = (
            ICP.get_param(f'barobill_tax_invoice.{mode}.server')
            or ICP.get_param('barobill_tax_invoice.server')
        )
        certkey, corpnum, barobill_id = get_shared_auth(self.env)
        missing = [k for k, v in [
            ('서버 URL', server), ('인증키', certkey),
            ('사업자번호', corpnum), ('바로빌 ID', barobill_id),
        ] if not v]
        if missing:
            mode_label = '운영' if mode == 'prod' else '테스트'
            raise UserError(
                '바로빌 세금계산서 설정이 누락되었습니다 (모드=%s): %s\n'
                '설정 > 바로빌 에서 등록하세요.' % (mode_label, ', '.join(missing))
            )
        return server, certkey, corpnum, barobill_id

    def _get_barobill_api(self):
        """바로빌 세금계산서 API 컨트롤러 및 인증정보(corpnum, barobill_id) 반환."""
        server, certkey, corpnum, barobill_id = self._get_barobill_config()
        return BarobillTaxInvoiceController(server, certkey), corpnum, barobill_id

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

    def _build_invoice_data(self):
        """컨트롤러에 넘길 세금계산서 dict 구성."""
        self.ensure_one()
        mgt_num = self.management_number or self._make_management_number()
        write_date = self.tax_date.strftime('%Y%m%d')
        _, _, _, barobill_id = self._get_barobill_config()

        invoicer = {
            'mgt_num': mgt_num,
            'corp_num': self._remove_hyphen(self.invoicer_corp_num),
            'corp_name': self.invoicer_corp_name or '',
            'ceo_name': self.invoicer_ceo_name or '',
            'addr': self.invoicer_addr or '',
            'biz_class': self.invoicer_biz_class or '',
            'biz_type': self.invoicer_biz_type or '',
            'contact_id': barobill_id,
            'contact_name': self.invoicer_contact_name or self.invoicer_ceo_name or '',
            'tel': self.invoicer_tel or '',
            'hp': self.invoicer_tel or '',
            'email': self.invoicer_email or '',
        }
        invoicee = {
            # 정발행(공급자 발행): 공급받는자 관리번호는 비운다 (공급자와 동일 시 -11028 오류)
            'mgt_num': '',
            'corp_num': self._remove_hyphen(self.invoicee_corp_num),
            'corp_name': self.invoicee_corp_name or '',
            'ceo_name': self.invoicee_ceo_name or '',
            'addr': self.invoicee_addr or '',
            'biz_class': self.invoicee_biz_class or '',
            'biz_type': self.invoicee_biz_type or '',
            'contact_name': self.invoicee_contact_name or self.invoicee_ceo_name or '',
            'tel': self.invoicee_tel or '',
            'hp': self.invoicee_tel or '',
            'email': self.invoicee_email or '',
        }
        header = {
            'tax_invoice_type': self.tax_invoice_type,
            'tax_type': self.tax_type,
            'purpose_type': self.purpose_type,
            'write_date': write_date,
            'amount_total': self.amount_untaxed,
            'tax_total': int(self.amount_tax) if self.amount_tax == 0.0 else self.amount_tax,
            'total_amount': self.amount_total,
            'remark1': self.note or '',
        }
        lines = [{
            'purchase_expiry': write_date,
            'name': line.product_name or '',
            'information': line.product_standard or '',
            'chargeable_unit': line.quantity,
            'unit_price': line.price_unit,
            'amount': line.price_subtotal,
            'tax': line.price_tax,
            'description': line.note or '',
        } for line in self.line_ids]

        return {'invoicer': invoicer, 'invoicee': invoicee, 'header': header, 'lines': lines}

    def _make_management_number(self):
        """관리번호(MgtKey) 생성: YYMMDDHHMM-문서번호 (KST 기준)."""
        kst_now = fields.Datetime.now().astimezone(_KST)
        return '%s-%s' % (kst_now.strftime('%y%m%d%H%M'), self.name)

    def _log_result(self, action, ok, message=''):
        """처리 이력 기록."""
        self.env['barobill.tax_invoice.result'].sudo().create({
            'tax_invoice_id': self.id,
            'action': action,
            'state': '성공' if ok else '실패',
            'management_number': self.management_number or '',
            'approval_number': self.approval_number or '',
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
        """바로빌에 세금계산서 임시저장 (RegistTaxInvoiceEX)."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError('품목을 1개 이상 입력하세요.')
        api, corpnum, _ = self._get_barobill_api()
        if not self.management_number:
            self.management_number = self._make_management_number()
        data = self._build_invoice_data()
        result = api._regist_tax_invoice(corpnum, data)
        if self._is_error(result):
            self.management_number = False
            return self._handle_error(api, 'regist', result)
        self.write({'state': 'save', 'error_message': False})
        self._log_result('regist', True)
        return True

    def action_update(self):
        """저장된 세금계산서 수정 (UpdateTaxInvoiceEX)."""
        self.ensure_one()
        if self.state != 'save':
            raise UserError("저장 상태의 세금계산서만 수정할 수 있습니다.")
        api, corpnum, _ = self._get_barobill_api()
        data = self._build_invoice_data()
        result = api._update_tax_invoice(corpnum, data)
        if self._is_error(result):
            return self._handle_error(api, 'update', result)
        self.write({'error_message': False})
        self._log_result('update', True)
        return True

    def action_issue(self):
        """저장된 세금계산서 발급 (IssueTaxInvoice)."""
        self.ensure_one()
        if self.state != 'save':
            raise UserError("저장 상태의 세금계산서만 발급할 수 있습니다.")
        api, corpnum, _ = self._get_barobill_api()
        corpnum_only = self._remove_hyphen(self.invoicer_corp_num) or corpnum
        result = api._issue_tax_invoice(corpnum_only, self.management_number)
        if self._is_error(result):
            return self._handle_error(api, 'issue', result)
        self.write({'state': 'issued', 'error_message': False})
        # 발급 성공 시 국세청 승인번호 조회
        try:
            state = api._get_tax_invoice_state(corpnum_only, self.management_number)
            if state is not None and getattr(state, 'BarobillState', 0) > 0:
                self.approval_number = (
                    getattr(state, 'NTSConfirmNum', False)
                    or getattr(state, 'NTSSendKey', False)
                    or False
                )
        except Exception:
            pass
        self._log_result('issue', True)
        return True

    def action_delete(self):
        """바로빌에서 세금계산서 삭제 → 작성 상태로 (DeleteTaxInvoice)."""
        self.ensure_one()
        if self.state not in ('save', 'cancel'):
            raise UserError("저장/취소 상태의 세금계산서만 삭제할 수 있습니다.")
        api, corpnum, _ = self._get_barobill_api()
        corpnum_only = self._remove_hyphen(self.invoicer_corp_num) or corpnum
        result = api._delete_tax_invoice(corpnum_only, self.management_number)
        if self._is_error(result):
            return self._handle_error(api, 'delete', result)
        self._log_result('delete', True)
        self.write({
            'state': 'draft',
            'management_number': False,
            'approval_number': False,
            'error_message': False,
        })
        return True

    def action_cancel(self):
        """발급된 세금계산서 발행취소 (ProcTaxInvoice)."""
        self.ensure_one()
        if self.state != 'issued':
            raise UserError("발급 상태의 세금계산서만 취소할 수 있습니다.")
        api, corpnum, _ = self._get_barobill_api()
        corpnum_only = self._remove_hyphen(self.invoicer_corp_num) or corpnum
        result = api._proc_tax_invoice(corpnum_only, self.management_number)
        if self._is_error(result):
            return self._handle_error(api, 'cancel', result)
        self.write({'state': 'cancel', 'error_message': False})
        self._log_result('cancel', True)
        return True

    def action_popup_url(self):
        """바로빌 세금계산서 조회 팝업 URL 열기."""
        self.ensure_one()
        if not self.management_number:
            raise UserError('저장된 세금계산서가 없습니다.')
        api, corpnum, barobill_id = self._get_barobill_api()
        corpnum_only = self._remove_hyphen(self.invoicer_corp_num) or corpnum
        url = api._get_tax_invoice_popup_url(corpnum_only, self.management_number, barobill_id)
        if isinstance(url, str) and url.startswith('http'):
            return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}
        return self._handle_error(api, 'popup', url)

    def action_reset(self):
        """상태 초기화 (로컬 작성 상태로만 되돌림)."""
        self.ensure_one()
        if self.state in ('save', 'issued'):
            raise UserError('바로빌에 저장/발급된 건은 초기화할 수 없습니다. 삭제 처리 후 이용하세요.')
        self.write({
            'state': 'draft',
            'management_number': False,
            'approval_number': False,
            'error_message': False,
        })
        return True

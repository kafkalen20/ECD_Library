# -*- coding: utf-8 -*-
"""바로빌 세금계산서 SOAP API 호출 래퍼.

세금계산서 API 는 ``ns0:TaxInvoice`` / ``ns0:InvoiceParty`` /
``ns0:TaxInvoiceTradeLineItem`` 등 SOAP 복합타입을 조립해야 한다. 알림톡과 동일하게
복합타입 조립은 이 컨트롤러 안에서 수행하고, 모델은 순수 dict 만 넘긴다.

모델이 넘기는 ``invoice_data`` 구조:
    {
        'invoicer': { mgt_num, corp_num, corp_name, ceo_name, addr,
                      biz_class, biz_type, contact_id, contact_name,
                      tel, hp, email },
        'invoicee': { mgt_num, corp_num, corp_name, ceo_name, addr,
                      biz_class, biz_type, contact_name, tel, hp, email },
        'header':   { tax_invoice_type, tax_type, purpose_type, write_date,
                      amount_total, tax_total, total_amount, remark1 },
        'lines':    [ { purchase_expiry, name, information, chargeable_unit,
                        unit_price, amount, tax, description }, ... ],
    }

성공/실패 판정은 모델이 담당한다(음수면 오류). 이 컨트롤러는 SOAP 호출만 감싼다.
"""

from odoo.addons.barobill.controllers.barobill import BarobillController


class BarobillTaxInvoiceController(BarobillController):

    # ------------------------------------------------------------------
    # 복합타입 조립
    # ------------------------------------------------------------------
    def _build_invoice_party(self, party, with_contact_id=False):
        """ns0:InvoiceParty 복합타입 생성."""
        InvoiceParty = self.client.get_type('ns0:InvoiceParty')
        vals = {
            'MgtNum': party.get('mgt_num', ''),
            'CorpNum': party.get('corp_num', ''),
            'CorpName': party.get('corp_name', ''),
            'CEOName': party.get('ceo_name', ''),
            'Addr': party.get('addr', ''),
            'BizClass': party.get('biz_class', ''),
            'BizType': party.get('biz_type', ''),
            'ContactName': party.get('contact_name', ''),
            'TEL': party.get('tel', ''),
            'HP': party.get('hp', ''),
            'Email': party.get('email', ''),
        }
        if with_contact_id:
            vals['ContactID'] = party.get('contact_id', '')
        return InvoiceParty(**vals)

    def _build_line_items(self, lines):
        """ns0:ArrayOfTaxInvoiceTradeLineItem 복합타입 생성."""
        LineItem = self.client.get_type('ns0:TaxInvoiceTradeLineItem')
        ArrayLine = self.client.get_type('ns0:ArrayOfTaxInvoiceTradeLineItem')
        items = [
            LineItem(
                PurchaseExpiry=line.get('purchase_expiry', ''),
                Name=line.get('name', ''),
                Information=line.get('information', ''),
                ChargeableUnit=line.get('chargeable_unit', 0),
                UnitPrice=line.get('unit_price', 0),
                Amount=line.get('amount', 0),
                Tax=line.get('tax', 0),
                Description=line.get('description', ''),
            )
            for line in lines
        ]
        return ArrayLine(items)

    def _build_invoice(self, data):
        """ns0:TaxInvoice 복합타입 생성."""
        header = data['header']
        TaxInvoice = self.client.get_type('ns0:TaxInvoice')
        return TaxInvoice(
            InvoicerParty=self._build_invoice_party(data['invoicer'], with_contact_id=True),
            InvoiceeParty=self._build_invoice_party(data['invoicee']),
            IssueDirection=1,
            TaxInvoiceType=header['tax_invoice_type'],
            TaxType=header['tax_type'],
            PurposeType=header['purpose_type'],
            TaxCalcType=1,
            ModifyCode='',
            WriteDate=header['write_date'],
            AmountTotal=header['amount_total'],
            TaxTotal=header['tax_total'],
            TotalAmount=header['total_amount'],
            Remark1=header.get('remark1', ''),
            TaxInvoiceTradeLineItems=self._build_line_items(data['lines']),
        )

    # ------------------------------------------------------------------
    # SOAP API
    # ------------------------------------------------------------------
    def _regist_tax_invoice(self, corpnum, data):
        """세금계산서 임시 저장 (RegistTaxInvoiceEX). 성공 시 1, 실패 시 음수 반환."""
        return self.client.service.RegistTaxInvoiceEX(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            Invoice=self._build_invoice(data),
            IssueTiming=1,
        )

    def _update_tax_invoice(self, corpnum, data):
        """저장된 세금계산서 수정 (UpdateTaxInvoiceEX). 성공 시 1, 실패 시 음수 반환."""
        return self.client.service.UpdateTaxInvoiceEX(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            Invoice=self._build_invoice(data),
            IssueTiming=1,
        )

    def _issue_tax_invoice(self, corpnum, mgt_key, send_sms=False):
        """저장된 세금계산서 발급 (IssueTaxInvoice). 성공 시 1, 실패 시 음수 반환."""
        return self.client.service.IssueTaxInvoice(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            MgtKey=mgt_key,
            SendSMS=send_sms,
            NTSSendOption=1,
            ForceIssue=False,
        )

    def _get_tax_invoice_state(self, corpnum, mgt_key):
        """세금계산서 상태 조회 (GetTaxInvoiceStateEX). TaxInvoiceStateEX 객체 반환."""
        return self.client.service.GetTaxInvoiceStateEX(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            MgtKey=mgt_key,
        )

    def _delete_tax_invoice(self, corpnum, mgt_key):
        """세금계산서 삭제 (DeleteTaxInvoice). 성공 시 1/2, 실패 시 음수 반환."""
        return self.client.service.DeleteTaxInvoice(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            MgtKey=mgt_key,
        )

    def _proc_tax_invoice(self, corpnum, mgt_key):
        """발급된 세금계산서 발행취소 (ProcTaxInvoice). 성공 시 1, 실패 시 음수 반환."""
        return self.client.service.ProcTaxInvoice(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            MgtKey=mgt_key,
            ProcType='ISSUE_CANCEL',
        )

    def _get_tax_invoice_popup_url(self, corpnum, mgt_key, barobill_id):
        """세금계산서 조회 팝업 URL (GetTaxInvoicePopUpURL). 성공 시 URL, 실패 시 음수 문자열."""
        return self.client.service.GetTaxInvoicePopUpURL(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            MgtKey=mgt_key,
            ID=barobill_id,
        )

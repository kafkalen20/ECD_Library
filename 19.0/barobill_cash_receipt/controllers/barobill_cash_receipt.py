# -*- coding: utf-8 -*-
"""바로빌 현금영수증 SOAP API 호출 래퍼.

현금영수증 API 는 ``ns0:CashBillEx`` 복합타입을 조립해야 한다. 알림톡/세금계산서와
동일하게 복합타입 조립은 이 컨트롤러 안에서 수행하고, 모델은 순수 dict 만 넘긴다.

모델이 넘기는 ``cash_data`` 구조:
    {
        'mgt_key',
        'franchise_corp_num', 'franchise_member_id', 'franchise_corp_name',
        'franchise_ceo_name', 'franchise_addr', 'franchise_tel',
        'identity_num', 'hp', 'fax', 'email',
        'trade_date', 'trade_type', 'trade_usage', 'trade_method',
        'item_name', 'amount', 'tax',
    }

바로빌 현금영수증 API 는 계정 사업자번호(CorpNum)와 바로빌 ID(UserID)를 함께 넘긴다.
성공/실패 판정은 모델이 담당한다(음수면 오류). 이 컨트롤러는 SOAP 호출만 감싼다.
"""

from odoo.addons.barobill.controllers.barobill import BarobillController


class BarobillCashReceiptController(BarobillController):

    # ------------------------------------------------------------------
    # 복합타입 조립
    # ------------------------------------------------------------------
    def _build_cash_bill(self, data):
        """ns0:CashBillEx 복합타입 생성."""
        CashBillEx = self.client.get_type('ns0:CashBillEx')
        return CashBillEx(
            MgtKey=data['mgt_key'],
            FranchiseCorpNum=data.get('franchise_corp_num', ''),
            FranchiseMemberID=data.get('franchise_member_id', ''),
            FranchiseCorpName=data.get('franchise_corp_name', ''),
            FranchiseCEOName=data.get('franchise_ceo_name', ''),
            FranchiseAddr=data.get('franchise_addr', ''),
            FranchiseTel=data.get('franchise_tel', ''),
            IdentityNum=data.get('identity_num', ''),
            HP=data.get('hp', ''),
            Fax=data.get('fax', ''),
            Email=data.get('email', ''),
            TradeDate=data.get('trade_date', ''),
            TradeType=data.get('trade_type', 'N'),
            TradeUsage=data.get('trade_usage', '1'),
            TradeDeductionType='',
            TradeMethod=data.get('trade_method', '5'),
            ItemName=data.get('item_name', ''),
            Amount=data.get('amount', 0),
            Tax=data.get('tax', 0),
            ServiceCharge=0,
            CancelType='',
            CancelNTSConfirmNum='',
            CancelNTSConfirmDate='',
        )

    # ------------------------------------------------------------------
    # SOAP API
    # ------------------------------------------------------------------
    def _regist_cash_bill(self, corpnum, user_id, data):
        """현금영수증 임시 저장 (RegistCashBillEx). 성공 시 1, 실패 시 음수 반환."""
        return self.client.service.RegistCashBillEx(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            UserID=user_id,
            Invoice=self._build_cash_bill(data),
        )

    def _update_cash_bill(self, corpnum, user_id, data):
        """저장된 현금영수증 수정 (UpdateCashBillEx). 성공 시 1, 실패 시 음수 반환."""
        return self.client.service.UpdateCashBillEx(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            UserID=user_id,
            Invoice=self._build_cash_bill(data),
        )

    def _issue_cash_bill(self, corpnum, user_id, mgt_key, send_sms=False):
        """저장된 현금영수증 발급 (IssueCashBill). 성공 시 1, 실패 시 음수 반환."""
        return self.client.service.IssueCashBill(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            UserID=user_id,
            MgtKey=mgt_key,
            SMSSendYN=send_sms,
            MailTitle='',
        )

    def _get_cash_bill_state(self, corpnum, user_id, mgt_key):
        """현금영수증 상태 조회 (GetCashBillState). CashBillState 객체 반환."""
        return self.client.service.GetCashBillState(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            UserID=user_id,
            MgtKey=mgt_key,
        )

    def _delete_cash_bill(self, corpnum, user_id, mgt_key):
        """현금영수증 삭제 (DeleteCashBill). 성공 시 1/2, 실패 시 음수 반환."""
        return self.client.service.DeleteCashBill(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            UserID=user_id,
            MgtKey=mgt_key,
        )

    def _get_cash_bill_popup_url(self, corpnum, user_id, mgt_key):
        """현금영수증 조회 팝업 URL (GetCashBillPopUpURL). 성공 시 URL, 실패 시 음수 문자열."""
        return self.client.service.GetCashBillPopUpURL(
            CERTKEY=self._certkey,
            CorpNum=corpnum,
            UserID=user_id,
            PWD='',
            MgtKey=mgt_key,
        )

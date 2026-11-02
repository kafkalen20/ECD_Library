# -*- coding: utf-8 -*-
"""바로빌 SOAP API 호출 래퍼 (공통 기반).

모델의 업무 로직(상태 관리·검증·테스트모드 redirect)과 실제 바로빌 SOAP 호출을
분리한다. 각 채널 컨트롤러(SMS/FAX/알림톡)는 이 클래스를 상속해 채널 API 를 더한다.

인증정보(certkey)와 서버 URL 은 모델이 config 를 해석해 생성자로 넘긴다
(서버는 채널·환경별로 다르고 certkey 는 공통 계정 값).

사용:
    api = BarobillController(server, certkey)
    api._get_balance_cost_amount(corpnum)
    api._get_err_string(err_code)
"""

from zeep import Client

from odoo.exceptions import UserError


class BarobillController:

    def __init__(self, server, certkey):
        self._server = server
        self._certkey = certkey
        self._client = None

    @property
    def client(self):
        """Lazy init: WSDL 연결을 실제 사용 시점에 수행 (생성 시 블로킹 방지)."""
        if self._client is None:
            if not self._server:
                raise UserError('바로빌 서버 URL이 설정되지 않았습니다.')
            self._client = Client(self._server)
        return self._client

    def _get_err_string(self, err_code):
        """바로빌 오류코드의 설명 문자열 조회 (모든 서비스 WSDL 공통 API)."""
        return self.client.service.GetErrString(
            CERTKEY=self._certkey, ErrCode=int(err_code),
        )

    def _get_balance_cost_amount(self, corpnum):
        """바로빌 보유 포인트(잔액) 조회 (GetBalanceCostAmountEx)."""
        return self.client.service.GetBalanceCostAmountEx(
            CERTKEY=self._certkey, CorpNum=corpnum,
        )

# -*- coding: utf-8 -*-
"""바로빌 공통 헬퍼 — 계정/모드/서버 config 조회.

세 채널(SMS/FAX/알림톡)이 동일 바로빌 계정을 쓰므로 계정 정보는 ``barobill.*``
단일 키로 통합 관리한다. 채널 모듈은 이 헬퍼를 import 해 인증정보/모드를 얻는다.

- ``barobill.mode``    : 활성 환경 ('test' | 'prod')
- ``barobill.certkey`` : 연동인증키(CERTKEY)
- ``barobill.corpnum`` : 사업자등록번호(10자리)
- ``barobill.id``      : 바로빌 ID
- ``barobill.<mode>.server`` : 공통 API(포인트/오류조회)용 SOAP 서버 URL

실제 SOAP 호출(``GetErrString`` / ``GetBalanceCostAmountEx`` / 발송 API 등)은
``barobill.controllers.barobill.BarobillController`` (및 채널별 상속 컨트롤러)에
분리돼 있다. 이 모듈은 config(계정/모드/서버) 해석 헬퍼만 제공한다.

``GetErrString`` / ``GetBalanceCostAmountEx`` 는 모든 서비스 WSDL 에 공통 포함된
기반 API 라, 서버 URL 은 임의의 유효한 바로빌 WSDL 이면 된다.

설정값은 소스에 하드코딩하지 않는다 — data(ir_config_parameter)로 빈 키만 생성하고
값은 서버에서 직접 입력한다.
"""


def get_shared_mode(env):
    """현재 활성 환경 모드 ('test' 또는 'prod') — 세 채널 공통."""
    mode = env['ir.config_parameter'].sudo().get_param('barobill.mode', 'test')
    return mode if mode in ('test', 'prod') else 'test'


def get_shared_auth(env):
    """공통 인증 정보 (certkey, corpnum, barobill_id) 튜플 반환."""
    ICP = env['ir.config_parameter'].sudo()
    return (
        ICP.get_param('barobill.certkey'),
        ICP.get_param('barobill.corpnum'),
        ICP.get_param('barobill.id'),
    )


def get_base_server(env):
    """공통 API(포인트/오류조회)용 SOAP 서버 URL — 미설정 시 빈 값(호출부에서 검증)."""
    ICP = env['ir.config_parameter'].sudo()
    mode = get_shared_mode(env)
    return ICP.get_param('barobill.%s.server' % mode)

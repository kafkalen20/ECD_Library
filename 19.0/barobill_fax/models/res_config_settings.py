# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # 인증 정보(mode/certkey/corpnum/id)는 barobill 공통 설정에서 관리.
    # ※ FTP 로그인 계정도 공통 '바로빌 ID'(barobill.id)를 사용한다.
    # ※ 서버 URL·FTP 호스트/포트는 하드코딩 기본값 없음 — 서버에서 직접 입력,
    #    미설정 시 발송 단계에서 오류(barobill_fax._get_barobill_config/_get_ftp_config).

    # ====================== FTP 비밀번호 (FAX 전용) ======================
    barobill_fax_ftp_password = fields.Char(
        string='FTP 비밀번호',
        config_parameter='barobill_fax.ftp_password',
        help='바로빌 회원 비밀번호',
    )
    barobill_fax_default_from = fields.Char(
        string='기본 발신번호',
        config_parameter='barobill_fax.default_from',
        help='신규 FAX 레코드의 발신번호 기본값',
    )

    # ====================== 테스트 환경 endpoint ======================
    barobill_fax_test_server = fields.Char(
        string='테스트 서버 URL',
        config_parameter='barobill_fax.test.server',
    )
    barobill_fax_test_ftp_host = fields.Char(
        string='테스트 FTP 호스트',
        config_parameter='barobill_fax.test.ftp_host',
    )
    barobill_fax_test_ftp_port = fields.Integer(
        string='테스트 FTP 포트',
        config_parameter='barobill_fax.test.ftp_port',
    )

    # ====================== 운영 환경 endpoint ======================
    barobill_fax_prod_server = fields.Char(
        string='운영 서버 URL',
        config_parameter='barobill_fax.prod.server',
    )
    barobill_fax_prod_ftp_host = fields.Char(
        string='운영 FTP 호스트',
        config_parameter='barobill_fax.prod.ftp_host',
    )
    barobill_fax_prod_ftp_port = fields.Integer(
        string='운영 FTP 포트',
        config_parameter='barobill_fax.prod.ftp_port',
    )

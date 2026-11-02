# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from odoo import http
from odoo.http import request, content_disposition

_logger = logging.getLogger(__name__)


class EdbDeviceAccessController(http.Controller):
    """접속 현황 엑셀 다운로드."""

    @http.route('/edb_security/device_access/export', type='http', auth='user')
    def export_xlsx(self, period='month', **kwargs):
        """대시보드 접속 현황을 선택 기간(주/월/년)으로 엑셀 다운로드(표만)."""
        if period not in ('week', 'month', 'year'):
            period = 'month'
        content = request.env['edb.device.access'].build_dashboard_xlsx(period)
        label = {'week': '주간', 'month': '월간', 'year': '연간'}.get(period, '')
        fname = f"접속통계_{label}_{datetime.now().strftime('%y%m%d')}.xlsx"
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(fname)),
        ])

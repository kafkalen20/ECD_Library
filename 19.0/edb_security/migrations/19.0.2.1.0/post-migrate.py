# -*- coding: utf-8 -*-
"""19.0.2.0.0 → 19.0.2.1.0: R-02·R-03 이 2단계 인증 대기 시점도 보게 한다 (SEC-1).

data/security_rule_data.xml 은 noupdate="1" 이라 업그레이드로는 새 필드 값이
들어가지 않는다. 고객사가 지운 룰은 건너뛴다. 고객사가 고친 다른 값은 건드리지 않는다.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in ('edb_security.rule_r02', 'edb_security.rule_r03'):
        rule = env.ref(xmlid, raise_if_not_found=False)
        if rule:
            rule.include_mfa_pending = True

# -*- coding: utf-8 -*-
"""19.0.1.0.0 → 19.0.2.0.0: 접속 이력에 남은 옛 로그인 실패 행을 지운다.

통합 전에는 로그인 실패를 edb_device_access(event_type='login_failed')에 넣었다.
통합 후 실패는 edb.security.event 로만 기록하고 selection 값도 지웠지만,
코어는 지운 selection 값을 가진 행을 그대로 둔다. 대시보드는 'access' 만 읽어
숫자는 맞지만 목록에는 유형 없는 행으로 보인다. 옛 실패 이력은 옮기지 않는다
(개발 단계 결정, 2026-11-13).

평문 login 컬럼은 코어가 업그레이드 끝에 지운다 (ir.model.fields unlink →
_drop_column). 여기서 따로 지우지 않는다.
"""


def migrate(cr, version):
    cr.execute("DELETE FROM edb_device_access WHERE event_type = 'login_failed'")

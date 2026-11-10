# -*- coding: utf-8 -*-
"""수집 훅의 게이트. 모든 훅이 첫 줄에서 호출하므로 절대 느려서는 안 된다."""
import logging
import threading

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'edb_security.'

#: 토글 코드 → 기본값. 관측 기능은 ON, 사전 설정이 필요한 기능은 OFF.
TOGGLES = {
    'hook_login': True,          # H-1 로그인 이벤트
    'hook_user_write': True,     # H-2 사용자 변경
    'hook_apikey': True,         # H-3 API 키
    'hook_acl': True,            # H-4 권한 구조 변경
    'hook_config': True,         # H-7 설정 변경
    'detect_engine': True,       # 탐지 cron
    'notify_critical': True,     # 치명 즉시 알림
    'notify_digest': True,       # 일일 다이제스트
    'gc_enabled': True,          # 파기 cron
    'selfcheck_enabled': True,   # 자가점검
}

#: 이 모듈이 설치된 DB. _register_hook 에서 채운다.
_ENABLED_DBS = set()


def enable_db(dbname):
    _ENABLED_DBS.add(dbname)


def disable_db(dbname):
    _ENABLED_DBS.discard(dbname)


def current_dbname():
    """코어 netsvc.py 와 동일한 방식. 속성이 삭제되는 구간이 있어 getattr 필수."""
    return getattr(threading.current_thread(), 'dbname', None)


def invalidate(dbname=None):
    """no-op. ir.config_parameter._get_param 은 이미 ormcache 로 캐시되고,
    create/write/unlink 가 registry.clear_cache('stable') 로 워커 간 무효화를
    전파한다. 자체 캐시가 없으므로 별도 조치가 필요 없다.
    Task 9 가 이 함수를 호출하므로 호출 호환성을 위해 유지한다.
    """


def is_active(env, toggle):
    """이 DB에 모듈이 설치됐고, 레지스트리 로드가 끝났고, 토글이 켜져 있는가."""
    try:
        if toggle not in TOGGLES:
            return False
        if env.cr.dbname not in _ENABLED_DBS:
            return False
        if not env.registry.ready:
            # 모듈 설치·업그레이드·마이그레이션 전 구간
            return False
        raw = env['ir.config_parameter'].sudo().get_param(PARAM_PREFIX + toggle)
        if raw is False or raw is None or raw == '':
            return TOGGLES[toggle]
        return raw == 'True'
    except Exception:
        # 게이트가 예외를 내면 본 동작이 죽는다. 무조건 비활성으로 처리한다.
        _logger.debug("보안 모니터링 게이트 판정 실패", exc_info=True)
        return False

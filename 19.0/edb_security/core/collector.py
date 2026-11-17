# -*- coding: utf-8 -*-
"""수집 훅의 단일 진입점.

여기서 나는 예외는 절대 호출자에게 전파되지 않는다.
"""
import logging

from psycopg2.extras import Json as PsycopgJson

from odoo.http import request
from odoo.tools import config

from . import conn, guards, masking

_logger = logging.getLogger(__name__)

#: edb.security.event 에 직접 넣을 수 있는 컬럼
_ALLOWED_FIELDS = {
    'event_type', 'severity', 'user_id', 'login', 'client_ip', 'ip_trusted',
    'user_agent', 'http_path', 'auth_method', 'model_name', 'record_count',
    'field_names', 'detail',
}


def _proxy_mode_ok():
    """코어는 proxy_mode 와 X-Forwarded-Host 가 모두 있어야 REMOTE_ADDR 을 치환한다."""
    if not config.get('proxy_mode'):
        return False
    if not request:
        return False
    return bool(request.httprequest.environ.get('HTTP_X_FORWARDED_HOST'))


def request_context():
    """현재 요청의 맥락. 요청이 없으면 전부 None."""
    if not request:
        return {'client_ip': None, 'ip_trusted': False,
                'user_agent': None, 'http_path': None}
    env = request.httprequest.environ
    return {
        'client_ip': env.get('REMOTE_ADDR'),
        'ip_trusted': _proxy_mode_ok(),
        'user_agent': (env.get('HTTP_USER_AGENT') or '')[:256] or None,
        'http_path': request.httprequest.path,
    }


def create_event_isolated(env, vals):
    """세이브포인트 안에서 보안 이벤트를 만든다.

    savepoint(flush=False) 를 쓰는 이유: 기본값 flush=True 는 세이브포인트를
    만들기 전에 cr.flush() 를 돌려 호출자의 보류 쓰기까지 flush 한다. 그 실패는
    세이브포인트 보호 밖에서 일어나므로 우리 except 가 호출자의 예외를 삼키게 된다.
    대신 우리 모델만 명시적으로 flush 해 우리 INSERT 만 세이브포인트 안에서 확정한다.
    """
    with env.cr.savepoint(flush=False):
        event = env['edb.security.event'].sudo().create(vals)
        env['edb.security.event'].flush_model()
    return event


def record(env, toggle, event_type, severity='info', detached=False, **vals):
    try:
        if not guards.is_active(env, toggle):
            return
        payload = {k: v for k, v in vals.items() if k in _ALLOWED_FIELDS}
        payload['event_type'] = event_type
        payload['severity'] = severity
        for key, value in request_context().items():
            payload.setdefault(key, value)

        # detached 경로는 raw SQL INSERT 라 security_event.create() 의 마스킹
        # 오버라이드를 타지 않는다. 여기서 분기 이전에 두 필드 모두 마스킹해
        # ORM 경로와 detached 경로가 같은 값을 저장하도록 한다.
        if payload.get('detail'):
            payload['detail'] = masking.mask_value(payload['detail'])
        if payload.get('field_names'):
            payload['field_names'] = masking.mask(payload['field_names'])

        if detached or env.cr.readonly:
            columns, values = [], []
            for key, value in payload.items():
                if key == 'detail':
                    # jsonb 컬럼이므로 어댑터로 감싼다. 값은 위에서 이미 마스킹됐다.
                    value = PsycopgJson(value)
                columns.append(key)
                values.append(value)
            conn.enqueue(env.cr.dbname, columns, values)
        else:
            create_event_isolated(env, payload)
    except Exception:
        _logger.warning("보안 이벤트 기록 실패: %s", event_type, exc_info=True)

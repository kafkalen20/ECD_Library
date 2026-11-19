# -*- coding: utf-8 -*-
{
    'name': '에코두비즈 보안',
    'summary': '접속 이력 · 보안 이벤트 기록 · 이상징후 탐지 · 알림 (막지 않음)',
    'description': '에코두비즈 보안',
    'author': 'Ecodoobiz',
    'website': 'https://ecodoobiz.com',
    'category': 'Tools',
    'version': '19.0.2.1.0',
    'license': 'OEEL-1',
    'depends': [
        'edb_common',
        'base',
        'web',
        'mail',
        # 2단계 인증 실패를 보려면 우리 _check_credentials 가 MRO 에서 auth_totp(_mail)
        # 보다 위에 있어야 한다 (자기 유형이면 super() 를 부르지 않음). 둘 다 auto_install.
        'auth_totp_mail',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/security_rule_data.xml',
        'data/ir_cron_data.xml',
        'views/menus.xml',
        'views/edb_device_access_views.xml',
        'views/security_event_views.xml',
        'views/security_rule_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edb_security/static/src/dashboard/device_access_dashboard.js',
            'edb_security/static/src/dashboard/device_access_dashboard.xml',
            'edb_security/static/src/dashboard/device_access_dashboard.css',
            'edb_security/static/src/scss/security_monitor.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}

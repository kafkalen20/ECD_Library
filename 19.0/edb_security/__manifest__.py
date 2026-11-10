# -*- coding: utf-8 -*-
{
    'name': '에코두비즈 보안',
    'summary': '접속 이력 · 보안 이벤트 기록 · 이상징후 탐지 · 알림 (막지 않음)',
    'description': '에코두비즈 보안',
    'author': 'Ecodoobiz',
    'website': 'https://ecodoobiz.com',
    'category': 'Tools',
    'version': '19.0.2.0.0',
    'license': 'OEEL-1',
    'depends': [
        'edb_common',
        'base',
        'web',
        'mail',
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

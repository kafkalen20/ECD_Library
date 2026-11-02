# -*- coding: utf-8 -*-

{
    'name': '바로빌',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': '바로빌 공통',
    'description': '바로빌 공통',
    'author': 'Ecodoobiz',
    'website': 'https://www.ecodoobiz.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
    ],
    'external_dependencies': {
        'python': ['zeep'],
    },
    'data': [
        'data/ir_config_parameter.xml',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'barobill/static/src/scss/res_config_settings.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}

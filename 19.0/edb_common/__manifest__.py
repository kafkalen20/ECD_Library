# -*- coding: utf-8 -*-
{
    'name': '에코두비즈 공통',
    'summary': '에코두비즈 공통',
    'description': '에코두비즈 공통',
    'author': 'Ecodoobiz',
    'website': 'https://ecodoobiz.com',
    'category': 'Tools',
    'version': '19.0.1.0.0',
    'license': 'OEEL-1',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edb_common/static/src/css/list_vertical_lines.css',
            'edb_common/static/src/css/status_colors.css',
            'edb_common/static/src/js/list_arrow_nav.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

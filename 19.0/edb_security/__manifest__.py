# -*- coding: utf-8 -*-
{
    'name': '에코두비즈 보안',
    'summary': '에코두비즈 보안',
    'description': '에코두비즈 보안',
    'author': 'Ecodoobiz',
    'website': 'https://ecodoobiz.com',
    'category': 'Tools',
    'version': '19.0.1.0.0',
    'license': 'OEEL-1',
    'depends': [
        'edb_common',
        'base',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/edb_device_access_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'edb_security/static/src/dashboard/device_access_dashboard.js',
            'edb_security/static/src/dashboard/device_access_dashboard.xml',
            'edb_security/static/src/dashboard/device_access_dashboard.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

# -*- coding: utf-8 -*-

{
    'name': '바로빌 FAX',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': '바로빌 FAX',
    'description': '바로빌 FAX',
    'author': 'Ecodoobiz',
    'website': 'https://www.ecodoobiz.com',
    'license': 'LGPL-3',
    'depends': [
        'barobill',
    ],
    'external_dependencies': {
        'python': ['zeep', 'pytz'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'data/ir_cron_data.xml',
        'views/barobill_fax_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

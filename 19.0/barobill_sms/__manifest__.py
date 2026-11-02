# -*- coding: utf-8 -*-

{
    'name': '바로빌 SMS',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': '바로빌 SMS',
    'description': '바로빌 SMS',
    'author': 'Ecodoobiz',
    'website': 'https://www.ecodoobiz.com',
    'license': 'LGPL-3',
    'depends': [
        'barobill',
    ],
    'external_dependencies': {
        'python': ['zeep'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/barobill_sms_views.xml',
        'views/barobill_sms_result_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

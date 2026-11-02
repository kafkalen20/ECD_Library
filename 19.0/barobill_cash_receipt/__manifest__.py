# -*- coding: utf-8 -*-

{
    'name': '바로빌 현금영수증',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': '바로빌 현금영수증',
    'description': '바로빌 현금영수증 (직접 작성/저장/발급/취소)',
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
        'data/ir_sequence_data.xml',
        'views/barobill_cash_receipt_views.xml',
        'views/barobill_cash_receipt_result_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

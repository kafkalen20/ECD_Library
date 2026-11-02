# -*- coding: utf-8 -*-
{
    'name': '에코두비즈 고객센터',
    'summary': '에코두비즈 고객센터',
    'description': '에코두비즈 고객센터.',
    'author': 'Ecodoobiz',
    'website': 'https://ecodoobiz.com',
    'category': 'Services/Helpdesk',
    'version': '19.0.1.0.0',
    'license': 'OEEL-1',
    'depends': [
        'edb_common',
        'helpdesk',
        'helpdesk_timesheet',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/helpdesk_ticket_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

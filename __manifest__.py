# -*- coding: utf-8 -*-
{
    'name': "SK odoo Inter Company Transaction Transfer",
    'summary': """Inter Company Transaction Transfer""",
    'description': """Inter Company Transaction Transfer""",
    'author': 'Sritharan K',
    'company': 'SKengineer',
    'maintainer': 'SKengineer',
    'website': "https://www.skengineer.be/",
    'category': 'Transfer',
    'version': '17.1',
    'depends': ['purchase_stock', 'sale_stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/group.xml',
        'data/sequence.xml',

        'views/res_company_view.xml',
        'views/res_config_setting_view.xml',
        'views/inter_company_transfer_view.xml',
        'views/sale_order_view.xml',
        'views/purchase_order_view.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
    'icon': 'skInterCompanyTransactionTransfer/static/description/image.png'
}

# __manifest__.py
{
    'name': 'Account Move Related document Link',
    'version': '15.0.2',
    'category': 'Accounting',
    'summary': 'Add a link from Account Move to Related Document',
    'author': 'zvERP',
    'license': 'AGPL-3',
    'website': 'https://www.zverp.com',
    'depends': ['account', 'sale'],
    'data': [
        'views/account_move_form.xml',
    ],
    'installable': True,
    'application': False,
}


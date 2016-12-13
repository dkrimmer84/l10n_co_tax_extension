# -*- coding: utf-8 -*-
{
    'name': 'Colombia - Impuestos',
    'category': 'Localization',
    'version': '0.1',
    'author': 'Luis Alfredo da Silva, Dominic Krimmer, Plastinorte S.A.S',
    'license': 'AGPL-3',
    'maintainer': 'dominic.krimmer@gmail.com',
    'website': 'https://www.plastinorte.com',
    'summary': 'Colombian Taxes: Invoice Module - Odoo 9.0',
    'images': ['images/'],
    'description': """
Colombia Impuestos:
======================
    * This module calculates some Colombian taxes that have to apply
    * First tax: withholding tax, which is calculated by 2,4% from the untaxed amount and calculated with the total amount
    """,
    'depends': [
        'account',
        'sale',
        'purchase',
        'l10n_co'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/l10n_co_tax_extension.xml',
        'views/report_invoice.xml',
        'views/ir_sequence_view.xml'
    ],
    'installable': True,
}



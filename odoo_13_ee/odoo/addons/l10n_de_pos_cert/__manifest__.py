{
    'name': "Germany - Certification for Point of Sale",

    'summary': """
Germany TSS Regulation
""",

    'description': """
This module brings the technical requirement for the new Germany regulation with the Technical Security System by using a cloud-based solution with Fiskaly.

Install this if you are using the Point of Sale app in Germany.    

""",

    'category': 'Localization',
    'version': '0.1',

    'depends': ['l10n_de', 'point_of_sale', 'iap'],
    'installable': True,
    'auto_install': True,

    'data': [
        'security/ir.model.access.csv',
        'security/l10n_de_pos_cert_security.xml',
        'views/l10n_de_pos_cert_templates.xml',
        'views/l10n_de_pos_dsfinvk_export_views.xml',
        'views/pos_config_views.xml',
        'views/pos_order_views.xml',
        'views/res_company_views.xml',
    ],
    'qweb': ['static/src/xml/pos.xml'],
    'license': 'OEEL-1',
}

{
    "name": "Intereses de demora en facturas",
    "version": "16.0.1.0.0",
    "category": "Accounting",
    "summary": "Calcula los intereses de demora (Ley 3/2004) en facturas vencidas "
    "y genera el escrito de reclamación.",
    "author": "zvERP.com",
    "website": "https://www.zverp.com",
    "license": "AGPL-3",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "security/late_interest_security.xml",
        "views/account_late_interest_config_views.xml",
        "views/res_partner_views.xml",
        "views/account_move_views.xml",
        "report/late_interest_claim_report.xml",
    ],
    "installable": True,
    "application": False,
}

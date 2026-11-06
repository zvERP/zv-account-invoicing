from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    late_interest_addressee = fields.Char(
        string="Encabezado de reclamación de intereses",
        help="Encabezado del escrito de reclamación, p. ej. «AL EXCMO. CONCELLO DE LUGO» "
        "o «A LA EXCMA. DIPUTACIÓN DE A CORUÑA». Si se deja vacío se usa "
        "«AL EXCMO. » seguido del nombre del cliente.",
    )

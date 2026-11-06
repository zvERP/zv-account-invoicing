from odoo import _, api, fields, models


class AccountLateInterestConfig(models.Model):
    _name = "account.late.interest.config"
    _description = "Configuración de intereses de demora"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company", string="Compañía", required=True, ondelete="cascade",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")

    # Aplicación
    partner_category_ids = fields.Many2many(
        "res.partner.category",
        "account_late_interest_config_partner_category_rel",
        "config_id",
        "category_id",
        string="Etiquetas de contacto",
        help="Solo se calculan y reclaman intereses de demora en las facturas de los "
        "contactos que tengan alguna de estas etiquetas.",
    )
    # Importes
    rate = fields.Float(
        string="Tipo de interés nominal anual (%)",
        digits=(5, 2),
        default=10.40,
        required=True,
        help="Tipo legal de interés de demora (art. 7 Ley 3/2004): tipo del BCE + 8 "
        "puntos, publicado cada semestre en el BOE. 2.º semestre de 2026: 10,40 %.",
    )
    compensation = fields.Monetary(
        string="Gastos de cobro por factura",
        default=40.0,
        help="Indemnización fija por costes de cobro (art. 8 Ley 3/2004).",
    )
    # Reclamante (la empresa es la compañía de Odoo)
    representative_name = fields.Char(string="Representante")
    representative_vat = fields.Char(string="DNI del representante")
    representation_document = fields.Char(
        string="Acreditación de la representación",
        default="el correspondiente poder notarial",
        help="Texto del escrito: «… y para lo cual se acompaña <este texto>».",
    )
    notification_address = fields.Char(
        string="Domicilio a efectos de notificaciones",
        compute="_compute_company_defaults", store=True, readonly=False,
    )
    city = fields.Char(
        string="Lugar de firma",
        compute="_compute_company_defaults", store=True, readonly=False,
    )

    _sql_constraints = [
        ("company_uniq", "unique(company_id)", "Solo puede haber una configuración por compañía."),
    ]

    @api.depends("company_id")
    def _compute_company_defaults(self):
        for config in self:
            company = config.company_id
            if not config.notification_address:
                config.notification_address = ", ".join(filter(None, [
                    company.street,
                    company.street2,
                    " ".join(filter(None, [company.zip, company.city])),
                    company.state_id.name,
                ]))
            if not config.city:
                config.city = company.city

    @api.model
    def _get_for_company(self, company):
        return self.search([("company_id", "=", company.id)], limit=1)

    @api.model
    def action_open(self):
        config = self._get_for_company(self.env.company) or self.create(
            {"company_id": self.env.company.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Intereses de demora"),
            "res_model": self._name,
            "res_id": config.id,
            "view_mode": "form",
            "target": "current",
        }

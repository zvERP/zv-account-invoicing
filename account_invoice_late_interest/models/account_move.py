from odoo import api, fields, models
from odoo.tools.misc import formatLang, format_date

from .late_interest_calc import compute_late_interest, legal_due_date


class AccountMove(models.Model):
    _inherit = "account.move"

    late_interest_registration_date = fields.Date(
        string="Fecha de presentación (FACe)",
        copy=False,
        help="Fecha de presentación de la factura en el registro administrativo / FACe. "
        "Solo se usa en el escrito de reclamación; si se deja vacía se usa la fecha de factura.",
    )
    late_interest_recognition_date = fields.Date(
        string="Fecha de aprobación de la conformidad",
        copy=False,
        help="Fecha en la que la factura pasó al estado «Contabilizada la obligación "
        "reconocida». Solo se usa en el escrito de reclamación.",
    )
    late_interest_due_date_manual = fields.Date(
        string="Vencimiento a efectos de demora (manual)",
        copy=False,
        help="Sustituye el vencimiento legal calculado. Los intereses se devengan desde "
        "el día siguiente.",
    )

    late_interest_enabled = fields.Boolean(
        string="Intereses de demora activos",
        compute="_compute_late_interest_enabled",
        help="El contacto tiene alguna de las etiquetas de la configuración de intereses de demora.",
    )
    late_interest_applicable = fields.Boolean(
        string="Devenga intereses de demora", compute="_compute_late_interest"
    )
    late_interest_due_date = fields.Date(
        string="Vencimiento legal", compute="_compute_late_interest",
        help="Vencimiento pactado, 30 días si no consta, con un máximo de 60 días desde "
        "la fecha de factura (art. 4 Ley 3/2004), salvo que se indique uno manual.",
    )
    late_interest_end_date = fields.Date(string="Calculado hasta", compute="_compute_late_interest")
    late_interest_fully_paid = fields.Boolean(string="Cobrada", compute="_compute_late_interest")
    late_interest_days = fields.Integer(string="Días de demora", compute="_compute_late_interest")
    late_interest_base = fields.Monetary(
        string="Base de cálculo (IVA incluido)", compute="_compute_late_interest"
    )
    late_interest_amount = fields.Monetary(
        string="Intereses de demora", compute="_compute_late_interest"
    )
    late_interest_compensation = fields.Monetary(
        string="Indemnización por costes de cobro", compute="_compute_late_interest"
    )
    late_interest_total = fields.Monetary(string="Total a reclamar", compute="_compute_late_interest")
    late_interest_detail_html = fields.Html(
        string="Liquidación", compute="_compute_late_interest", sanitize=False
    )

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def _late_interest_payments(self):
        """Cobros y compensaciones conciliados con la factura: [(fecha, importe)]."""
        self.ensure_one()
        payments = []
        for partial in self._get_all_reconciled_invoice_partials():
            if partial.get("is_exchange"):
                continue
            payments.append((partial["aml"].date, abs(partial["amount"])))
        return payments

    def _late_interest_config(self):
        self.ensure_one()
        return self.env["account.late.interest.config"]._get_for_company(self.company_id)

    def _late_interest_partner_allowed(self, config):
        """El contacto tiene alguna de las etiquetas configuradas."""
        self.ensure_one()
        tags = (self.partner_id | self.commercial_partner_id).category_id
        return bool(config.partner_category_ids & tags)

    def _late_interest_legal_due_date(self):
        self.ensure_one()
        if self.late_interest_due_date_manual:
            return self.late_interest_due_date_manual
        return legal_due_date(self.invoice_date, self.invoice_date_due)

    def _late_interest_data(self):
        """Devuelve un dict con todos los datos del cálculo de intereses."""
        self.ensure_one()
        empty = {"applicable": False, "segments": []}
        if self.move_type != "out_invoice" or self.state != "posted" or not self.amount_total:
            return empty
        if not self.late_interest_enabled:
            return empty
        config = self._late_interest_config()
        due_date = self._late_interest_legal_due_date()
        if not due_date:
            return empty

        payments = self._late_interest_payments()
        fully_paid = self.currency_id.is_zero(self.amount_residual)
        if fully_paid:
            end_date = max((d for d, _a in payments), default=False)
        else:
            end_date = fields.Date.context_today(self)
        if not end_date or end_date <= due_date:
            return empty

        segments = compute_late_interest(
            due_date, end_date, self.amount_total, payments, config.rate
        )
        if not segments:
            return empty

        currency = self.currency_id
        for seg in segments:
            seg["base"] = currency.round(seg["base"])
            seg["interest"] = currency.round(seg["interest"])
        interest = currency.round(sum(s["interest"] for s in segments))
        compensation = config.compensation
        return {
            "applicable": True,
            "due_date": due_date,
            "end_date": end_date,
            "fully_paid": fully_paid,
            "days": (end_date - due_date).days,
            "base": segments[0]["base"],
            "segments": segments,
            "interest": interest,
            "compensation": compensation,
            "total": interest + compensation,
        }

    def _late_interest_render_html(self, data):
        rows = []
        for seg in data["segments"]:
            rows.append(
                "<tr><td>%s</td><td>%s</td><td class='text-end'>%s</td>"
                "<td class='text-end'>%s</td><td class='text-end'>%s %%</td>"
                "<td class='text-end'>%s</td></tr>"
                % (
                    format_date(self.env, seg["date_from"]),
                    format_date(self.env, seg["date_to"]),
                    seg["days"],
                    formatLang(self.env, seg["base"], currency_obj=self.currency_id),
                    formatLang(self.env, seg["rate"], digits=2),
                    formatLang(self.env, seg["interest"], currency_obj=self.currency_id),
                )
            )
        return (
            "<table class='table table-sm'><thead><tr>"
            "<th>Desde</th><th>Hasta</th><th class='text-end'>Días</th>"
            "<th class='text-end'>Base</th><th class='text-end'>Tipo</th>"
            "<th class='text-end'>Intereses</th></tr></thead><tbody>%s</tbody></table>"
            % "".join(rows)
        )

    @api.depends("move_type", "partner_id.category_id", "commercial_partner_id.category_id")
    def _compute_late_interest_enabled(self):
        for move in self:
            config = move._late_interest_config() if move.company_id else False
            move.late_interest_enabled = bool(
                move.move_type == "out_invoice"
                and config
                and move._late_interest_partner_allowed(config)
            )

    @api.depends_context("tz")
    @api.depends(
        "move_type",
        "state",
        "invoice_date",
        "invoice_date_due",
        "late_interest_due_date_manual",
        "amount_total",
        "amount_residual",
        "partner_id.category_id",
        "commercial_partner_id.category_id",
    )
    def _compute_late_interest(self):
        for move in self:
            data = move._late_interest_data()
            if not data["applicable"]:
                move.update({
                    "late_interest_applicable": False,
                    "late_interest_due_date": move._late_interest_legal_due_date()
                    if move.move_type == "out_invoice" else False,
                    "late_interest_end_date": False,
                    "late_interest_fully_paid": False,
                    "late_interest_days": 0,
                    "late_interest_base": 0.0,
                    "late_interest_amount": 0.0,
                    "late_interest_compensation": 0.0,
                    "late_interest_total": 0.0,
                    "late_interest_detail_html": False,
                })
                continue
            move.update({
                "late_interest_applicable": True,
                "late_interest_due_date": data["due_date"],
                "late_interest_end_date": data["end_date"],
                "late_interest_fully_paid": data["fully_paid"],
                "late_interest_days": data["days"],
                "late_interest_base": data["base"],
                "late_interest_amount": data["interest"],
                "late_interest_compensation": data["compensation"],
                "late_interest_total": data["total"],
                "late_interest_detail_html": move._late_interest_render_html(data),
            })

    # ------------------------------------------------------------------
    # Escrito de reclamación
    # ------------------------------------------------------------------
    def _late_interest_claim_values(self):
        """Valores usados por la plantilla QWeb del escrito.

        La empresa reclamante es la compañía de la factura; el representante y el
        resto de datos salen de la configuración de intereses de demora.
        """
        self.ensure_one()
        company = self.company_id
        partner = self.commercial_partner_id
        config = self._late_interest_config()
        data = self._late_interest_data()
        registration_date = self.late_interest_registration_date or self.invoice_date
        return {
            "data": data,
            "claimant_name": company.name or "",
            "representative_name": config.representative_name or "",
            "representative_vat": config.representative_vat or "",
            "representation_document": config.representation_document
            or "el correspondiente poder notarial",
            "notification_address": config.notification_address or "",
            "addressee_heading": partner.late_interest_addressee
            or "AL EXCMO. %s" % (partner.name or "").upper(),
            "addressee_name": partner.name or "",
            "contract_description": "un contrato menor y, en consecuencia, de adjudicación "
            "directa, en los términos a los que se refiere el artículo 118.1 de la Ley "
            "9/2017, de 8 de noviembre, de Contratos del Sector Público",
            "city": config.city or company.city or "",
            "claim_date": fields.Date.context_today(self),
            "registration_date": registration_date,
            "recognition_date": self.late_interest_recognition_date,
            "days_since_registration": (
                (data["end_date"] - registration_date).days
                if data["applicable"] and registration_date else 0
            ),
            "fmt_date": lambda d: d and d.strftime("%d/%m/%Y") or "",
            "fmt_amount": lambda a: formatLang(self.env, a, currency_obj=self.currency_id),
            "fmt_rate": lambda r: formatLang(self.env, r, digits=2),
        }

    def _get_late_interest_claim_filename(self):
        self.ensure_one()
        return "Reclamación_a_%s_de_los_intereses_de_mora_devengados_por_la_factura_%s" % (
            self.commercial_partner_id.name or "",
            (self.name or "").replace("/", "-"),
        )

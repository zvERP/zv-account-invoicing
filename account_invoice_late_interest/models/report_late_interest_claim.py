from odoo import _, api, models
from odoo.exceptions import UserError


class ReportLateInterestClaim(models.AbstractModel):
    _name = "report.account_invoice_late_interest.report_late_interest_claim"
    _description = "Escrito de reclamación de intereses de demora"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["account.move"].browse(docids)
        not_applicable = docs.filtered(lambda m: not m.late_interest_applicable)
        if not_applicable:
            raise UserError(_(
                "Estas facturas no han devengado intereses de demora: %s"
            ) % ", ".join(not_applicable.mapped("name")))
        return {
            "doc_ids": docids,
            "doc_model": "account.move",
            "docs": docs,
        }

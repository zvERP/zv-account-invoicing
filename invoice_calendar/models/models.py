from odoo import models, fields

class AccountMove(models.Model):
    _inherit = "account.move"

    color_index = fields.Integer(
        string="Color Index",
        compute="_compute_color_index",
        store=True
    )

    def _compute_color_index(self):
        for record in self:
            if record.move_type == 'in_invoice':
                if record.payment_state == 'paid':
                    record.color_index = 10
                else:
                    record.color_index = 2
            elif record.move_type == 'out_invoice':
                if record.payment_state == 'paid':
                    record.color_index = 6
                else:
                    record.color_index = 1
            else:
                record.color_index = 0

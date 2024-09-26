from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    related_document = fields.Reference(
        selection=[
            ('sale.order', 'Sale Order'),
            ('purchase.order', 'Purchase Order'),
            ('contract.contract', 'Contract'),
        ],
        string="Related Document",
        compute='_compute_related_document',
        store=False
    )

    def _compute_related_document(self):
        for record in self:
            related_document = False
            sale_order = self.env['sale.order'].search([('name', '=', record.invoice_origin)], limit=1)
            if sale_order:
                related_document = f'sale.order,{sale_order.id}'
                continue
            elif self.env['ir.model']._get('purchase.order'):
                purchase_order = self.env['purchase.order'].search([('name', '=', record.invoice_origin)], limit=1)
                if purchase_order:
                    related_document = f'purchase.order,{purchase_order.id}'
                    continue
            elif self.env['ir.model']._get('contract.contract'):
                contract = self.env['contract.contract'].search([('name', '=', record.invoice_origin)], limit=1)
                if contract:
                    related_document = f'contract.contract,{contract.id}'

        record.related_document = related_document

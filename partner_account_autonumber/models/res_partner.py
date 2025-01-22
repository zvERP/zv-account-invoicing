from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_next_account(self, account_type, prefix, partner_name):
        """
        Fetch the next available account number based on the account type, prefix, and partner name.
        :param account_type: 'asset_receivable' or 'liability_payable'
        :param prefix: The prefix for the account number (e.g., '430' or '400')
        :param partner_name: The name of the partner for which the account is created
        :return: Account.account record
        """
        Account = self.env['account.account']

        domain = [
            ('code', '=like', f"{prefix}%"),
        ]
        last_account = Account.search(domain, order='code desc', limit=1)

        if account_type == 'asset_receivable':
            nombre = "Cliente"
        else:
            nombre = "Proveedor"

        if last_account:
            next_code = int(last_account.code) + 1
        else:
            next_code = int(prefix + '001')

        account = Account.create({
            'name': f"{nombre} {partner_name} (euros)",
            'code': str(next_code),
            'reconcile': True,
        })

        return account

    @api.model
    def create(self, vals):
        if vals.get('is_company', False):
            partner_name = vals.get('name', 'Indefinido')

            receivable_account = self._get_next_account('asset_receivable', '4300000', partner_name)
            payable_account = self._get_next_account('liability_payable', '4000000', partner_name)

            vals['property_account_receivable_id'] = receivable_account.id
            vals['property_account_payable_id'] = payable_account.id

        return super(ResPartner, self).create(vals)

# -*- coding: utf-8 -*-
###############################################################################
#                                                                             #
# Copyright (C) 2016  Dominic Krimmer                                         #
#                     Luis Alfredo da Silva (luis.adasilvaf@gmail.com)        #
#                                                                             #
# This program is free software: you can redistribute it and/or modify        #
# it under the terms of the GNU Affero General Public License as published by #
# the Free Software Foundation, either version 3 of the License, or           #
# (at your option) any later version.                                         #
#                                                                             #
# This program is distributed in the hope that it will be useful,             #
# but WITHOUT ANY WARRANTY; without even the implied warranty of              #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the               #
# GNU Affero General Public License for more details.                         #
#                                                                             #
# You should have received a copy of the GNU Affero General Public License    #
# along with this program.  If not, see <http://www.gnu.org/licenses/>.       #
###############################################################################

from openerp import api, fields, models

import pprint
import logging
_logger = logging.getLogger(__name__)

class ColombianTaxes(models.Model):
    """ This Model calculates and saves withholding tax that apply in
    Colombia"""

    _description = 'Model to create and save withholding taxes'
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    TWH = 0.025

    # Define withholding as new tax.
    wh_taxes = fields.Monetary('Withholding Tax', store="True",
                               compute="_compute_amount")

    amount_without_wh_tax = fields.Monetary('Total With Tax', store="True",
                                            compute="_compute_amount")

    # Calculate withholding tax and (new) total amount
    def _compute_amount(self):
        """
        This functions computes the withholding tax on the untaxed amount
        @return: void
        """
        # Calling the original calculation
        super(ColombianTaxes, self)._compute_amount()

        self.amount_without_wh_tax = self.amount_total
        # Extending the calculation with the colombian withholding tax
        # TODO: 0.025 is a static value right now. This will be dynamic
        self.wh_taxes = self.amount_untaxed * self.TWH
        self.amount_total -= self.wh_taxes

        #Calling the original calculation did not call the local var sign.
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1

        # Because python is interpreted it need to recalculate
        # amount_total_signed again.
        self.amount_total_signed = self.amount_total * sign

    @api.multi
    def finalize_invoice_move_lines(self, move_lines):
        account = self.env['account.account'].search([('code', '=', '135515')])

        for tp_line in move_lines:
            line = tp_line[2]
            if line['account_id'] == self.account_id.id:
                line['debit'] = line['debit'] - self.wh_taxes
                wh_line = (0, 0,
                             {
                                 'date_maturity': False,
                                 'partner_id': self.partner_id.id,
                                 'name': 'Retención a la fuente',
                                 'debit': self.wh_taxes,
                                 'credit': False,
                                 'account_id': account.id,
                                 'analytic_line_ids': False,
                                 'amount_currency': 0,
                                 'currency_id': False,
                                 'quantity': 1,
                                 'product_id': False,
                                 'product_uom_id': False,
                                 'analytic_account_id': False,
                                 'invoice_id': self.id,
                                 'tax_ids': False,
                                 'tax_line_id': False,
                             })        
        
        move_lines.insert(-1, wh_line)
        return move_lines

    def _get_tax_amount_by_group(self):
        res = super(ColombianTaxes, self)._get_tax_amount_by_group()
        groups_not_in_invoice = self.env['account.tax.group'].search([('not_in_invoice','=',True)])

        for g in groups_not_in_invoice:
            for i in res:
                if g.name == i[0]:
                    res.remove(i) 
        
        return res

class AccountTax(models.Model):
    _name = 'account.tax'
    _inherit = 'account.tax'
    
    tax_in_invoice = fields.Boolean(string="Evaluate in invoice", default=False,
        help="Check this if you want to hide the tax from the taxes list in products") 
    dont_impact_balance = fields.Boolean(string="Don't impact balance", default=False,
        help="Check this if you want to assign counterpart taxes accounts")
    account_id_counterpart = fields.Many2one('account.account', string='Tax Account Counterpart', ondelete='restrict',
        help="Account that will be set on invoice tax lines for invoices. Leave empty to use the expense account.")
    refund_account_id_counterpart = fields.Many2one('account.account', string='Tax Account Counterpart on Refunds', ondelete='restrict',                                         
        help="Account that will be set on invoice tax lines for refunds. Leave empty to use the expense account.")

class AccountTaxGroup(models.Model):
    _name = 'account.tax.group'
    _inherit = 'account.tax.group'

    not_in_invoice = fields.Boolean(string="Don't show in invoice", default=False,
        help="Check this if you want to hide the taxes in this group when print an invoice") 
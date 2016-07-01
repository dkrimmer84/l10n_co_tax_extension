# -*- coding: utf-8 -*-
###############################################################################
#                                                                             #
# Copyright (C) 2016  Dominic Krimmer                                         #
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


class ColombianTaxes(models.Model):
    """ This Model calculates and saves withholding tax that apply in
    Colombia"""

    _description = 'Model to create and save withholding taxes'
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    # Define withholding as new tax.
    wh_taxes = fields.Monetary('Withholding Tax:', store="True",
                               compute="_compute_amount")

    # Calculate withholding tax and total amount
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount',
                 'currency_id', 'company_id')
    def _compute_amount(self):
        """
        This functions computes the withholding tax on the untaxed amount
        @return: void
        """
        self.amount_untaxed = sum(line.price_subtotal for line in
                                  self.invoice_line_ids)

        # TODO: 0.025 is a static value right now. This will be dynamic
        # calculate colombian withholding tax
        self.wh_taxes = self.amount_untaxed * 0.025
        # Calculate the sum of all taxes
        self.amount_tax = sum(line.amount for line in self.tax_line_ids)
        # Calculate the sum of total amount with all taxes
        self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed

        if self.currency_id \
                and self.currency_id != self.company_id.currency_id:
            amount_total_company_signed = \
                self.currency_id.compute(self.amount_total,
                                         self.company_id.currency_id)
            amount_untaxed_signed = self.currency_id.compute(
                self.amount_untaxed, self.company_id.currency_id
            )

        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign
        self.amount_total -= self.wh_taxes

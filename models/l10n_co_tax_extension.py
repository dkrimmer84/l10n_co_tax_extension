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

    TWH = 0.025

    # Define withholding as new tax.
    wh_taxes = fields.Monetary('Withholding Tax:', store="True",
                               compute="_compute_amount")

    # Calculate withholding tax and (new) total amount
    def _compute_amount(self):
        """
        This functions computes the withholding tax on the untaxed amount
        @return: void
        """
        # Calling the original calculation
        super(ColombianTaxes, self)._compute_amount()

        # Extending the calculation with the colombian withholding tax
        # TODO: 0.025 is a static value right now. This will be dynamic
        self.wh_taxes = self.amount_untaxed * self.TWH
        self.amount_total -= self.wh_taxes

        #Calling the original calculation did not call the local var sign.
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1

        # Because python is interpreted it need to recalculate
        # amount_total_signed again.
        self.amount_total_signed = self.amount_total * sign



    def _compute_residual(self):

    # Calling the original calculation from residual
        super(ColombianTaxes, self)._compute_residual()

    #recalculating each var from residual.
        self.residual_company_signed -= self.wh_taxes
        self.residual_signed -= self.wh_taxes
        self.residual -= self.wh_taxes


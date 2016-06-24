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

# Extended Partner Module
from openerp import models, fields, api, exceptions

class ColombianTaxes(models.Model):

    """ Model to create and manipulate personal taxes"""
    _description=  "Model to create own taxes"
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    myresult = fields.Char('Retencion:')

    @api.onchange('amount_untaxed')
    def test(self):
        if self.amount_untaxed > 0:
            self.myresult = self.amount_untaxed + 5

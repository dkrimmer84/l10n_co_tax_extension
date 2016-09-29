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


from openerp.exceptions import UserError, ValidationError
from openerp.tools.translate import _
from openerp.tools import float_is_zero, float_compare

import pprint
import logging
_logger = logging.getLogger(__name__)


class IrSequence(models.Model):
    _name = 'ir.sequence'
    _inherit = 'ir.sequence'

    use_dian_control = fields.Boolean('Use DIAN control resolutions')
    remaining_numbers = fields.Integer(default=1, help='Remaining numbers')
    remaining_days = fields.Integer(default=1, help='Remaining days')
    sequence_dian_type = fields.Selection([
                        ('invoice_computer_generated', 'Invoice generated from computer')],
                        'Type', required=True, default='invoice_computer_generated')
    dian_resolution_ids = fields.One2many('ir.sequence.dian_resolution', 'sequence_id', 'DIAN Resolutions')

    _defaults = {
        'remaining_numbers': 400,
        'remaining_days': 30,
    }


class IrSequenceDianResolution(models.Model):
    _name = 'ir.sequence.dian_resolution'
    _rec_name = "sequence_id"

    resolution_number = fields.Integer('Resolution number', required=True)
    date_from = fields.Date('From', required=True)
    date_to = fields.Date('To', required=True)
    number_from = fields.Integer('Initial number', required=True)
    number_to = fields.Integer('Final number', required=True)
    active = fields.Boolean('Active resolution')
    sequence_id = fields.Many2one("ir.sequence", 'Main Sequence', required=True, ondelete='cascade')

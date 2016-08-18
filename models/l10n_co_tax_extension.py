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
from openerp.exceptions import UserError, ValidationError
from openerp.tools.translate import _

import logging
_logger = logging.getLogger(__name__)

class AccountInvoice(models.Model):
    """ This Model calculates and saves withholding tax that apply in
    Colombia"""

    _description = 'Model to create and save withholding taxes'
    _name = 'account.invoice'
    _inherit = 'account.invoice'

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
        super(AccountInvoice, self)._compute_amount()

        if self.fiscal_position_id:
            fp = self.env['account.fiscal.position'].search([('id','=',self.fiscal_position_id.id)])
            tax_ids = [base_tax.tax_id.id for base_tax in fp.tax_ids_invoice]
            # ids = [tax.id for tax in tax_ids]
            
            self.amount_tax = sum(line.amount for line in self.tax_line_ids if line.tax_id.id not in tax_ids)            
            self.wh_taxes = abs(sum(line.amount for line in self.tax_line_ids if line.tax_id.id in tax_ids))
        else: 
            self.amount_tax = sum(line.amount for line in self.tax_line_ids)

        self.amount_without_wh_tax = self.amount_untaxed + self.amount_tax

        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_signed = self.amount_total * sign

    def _get_tax_amount_by_group(self):
        res = super(AccountInvoice, self)._get_tax_amount_by_group()
        groups_not_in_invoice = self.env['account.tax.group'].search([('not_in_invoice','=',True)])

        for g in groups_not_in_invoice:
            for i in res:
                if g.name == i[0]:
                    res.remove(i)

        return res

    def at_least_one_tax_group_enabled(self):
        res = False
        groups_not_in_invoice = [i.id for i in self.env['account.tax.group'].search([('not_in_invoice','=',True)])]

        for line in self.tax_line_ids:
            if line.tax_id.tax_group_id.id in groups_not_in_invoice:
                res = True

        return res 
    
    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        super(AccountInvoice, self)._onchange_partner_id()
        
    @api.multi
    def get_taxes_values(self):
        tax_grouped = super(AccountInvoice, self).get_taxes_values()

        if self.fiscal_position_id:
            fp = self.env['account.fiscal.position'].search([('id','=',self.fiscal_position_id.id)])
            fp.ensure_one()
            tax_ids = self.env['account.tax'].browse([tax.tax_id.id for tax in fp.tax_ids_invoice])
            
            price_unit = self.amount_untaxed 
            taxes = tax_ids.compute_all(price_unit, self.currency_id, partner=self.partner_id)['taxes']

            tax_ids = [base_tax.tax_id.id for base_tax in fp.tax_ids_invoice]
            base_taxes = self.env['account.base.tax'].search_read([('start_date','<=',self.date_invoice),
                                                                   ('end_date','>=',self.date_invoice),
                                                                   ('tax_id','in',tax_ids)], ['amount'])

            for tax in taxes:
                for base in base_taxes: 
                    if self.amount_without_wh_tax >= base['amount']:
                        val = {
                            'invoice_id': self.id,
                            'name': tax['name'],
                            'tax_id': tax['id'],
                            'amount': tax['amount'],
                            'manual': False,
                            'sequence': tax['sequence'],
                            'account_analytic_id': tax['analytic'] or False,
                            'account_id': self.type in ('out_invoice', 'in_invoice') and tax['account_id'] or tax['refund_account_id'],
                        }

                        key = tax['id']

                        if key not in tax_grouped:
                            tax_grouped[key] = val
                        else:
                            tax_grouped[key]['amount'] += val['amount']

        return tax_grouped

    @api.onchange('fiscal_position_id','date_invoice')
    def _onchange_fiscal_position_id(self):
        self._onchange_invoice_line_ids()

        if not self.date_invoice:
            warning = {
                'title': _('Warning!'),
                'message': _('You must assign a date')
            }
            return {'warning': warning}

class AccountInvoiceLine(models.Model):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

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
    position_id = fields.Many2one('account.fiscal.position', string='Fiscal position related id')
    base_taxes = fields.One2many('account.base.tax', 'tax_id', string='Base taxes', help='This field show related taxes applied to this tax')

class AccountBaseTax(models.Model): 
    _name = 'account.base.tax'
    
    tax_id = fields.Many2one('account.tax', string='Tax related')
    start_date = fields.Date(string='Since date', required=True)
    end_date = fields.Date(string='Until date', required=True)
    amount = fields.Float(digits=0, default=0, string="Tax amount", required=True)
    # currency_id = fields.Many2one('res.currency', related='tax_id.company_id.currency_id', store=True)

    @api.one
    @api.constrains('start_date', 'end_date')
    def _check_closing_date(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Error! End date cannot be set before start date.")

    @api.multi
    @api.constrains('start_date', 'end_date')
    def _dont_overlap_date(self):
        bases_ids = self.search([('start_date', '<=', self.end_date),
                                 ('end_date', '>=', self.start_date),
                                 ('tax_id', '=', self.tax_id.id),
                                 ('id', '<>', self.id)])
        
        if bases_ids:
            raise ValidationError("Error! cannot have overlap date range.")
        

class AccountTaxGroup(models.Model):
    _name = 'account.tax.group'
    _inherit = 'account.tax.group'

    not_in_invoice = fields.Boolean(string="Don't show in invoice", default=False,
        help="Check this if you want to hide the taxes in this group when print an invoice") 

class AccountFiscalPositionTaxes(models.Model):
    _name = 'account.fiscal.position.base.tax'

    position_id = fields.Many2one('account.fiscal.position', string='Fiscal position related')
    tax_id = fields.Many2one('account.tax', string='Tax')
    amount = fields.Float(related='tax_id.amount', store=True, readonly=True)

    # _sql_constraints = [
    #     ('tax_fiscal_position_uniq', 'unique(position_id, tax_id)', _('Error! cannot have repeated taxes'))
    # ]
    
    @api.constrains('tax_id')
    def _check_dont_repeat_tax(self):
        local_taxes = self.search([('position_id', '=', self.position_id.id),
                                   ('tax_id', '=', self.tax_id.id),
                                   ('id', '<>', self.id)])
        
        if local_taxes:
            raise ValidationError("Error! cannot have repeated taxes")

class AccountFiscalPosition(models.Model):
    _name = 'account.fiscal.position'
    _inherit = 'account.fiscal.position'

    tax_ids_invoice = fields.One2many('account.fiscal.position.base.tax', 'position_id',
        string='Taxes that refer to the fiscal position')
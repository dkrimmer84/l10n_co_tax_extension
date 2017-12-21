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
from openerp.tools import float_is_zero, float_compare
from openerp.tools.misc import formatLang
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)

class AccountInvoice(models.Model):
    """ This Model calculates and saves withholding tax that apply in
    Colombia"""

    _description = 'Model to create and save withholding taxes'
    _name = 'account.invoice'
    _inherit = 'account.invoice'

    @api.one
    def _get_has_valid_dian_info_JSON(self):
        if self.journal_id.sequence_id.use_dian_control:
            remaining_numbers = self.journal_id.sequence_id.remaining_numbers
            remaining_days = self.journal_id.sequence_id.remaining_days
            dian_resolution = self.env['ir.sequence.dian_resolution'].search([('sequence_id','=',self.journal_id.sequence_id.id),('active_resolution','=',True)])
            today = datetime.strptime(fields.Date.context_today(self), '%Y-%m-%d')

            not_valid = False
            spent = False
            if len(dian_resolution) == 1 and self.state == 'draft':
                dian_resolution.ensure_one()
                date_to = datetime.strptime(dian_resolution['date_to'], '%Y-%m-%d')
                days = (date_to - today).days

                if dian_resolution['number_to'] - dian_resolution['number_next'] < remaining_numbers or days < remaining_days:
                    not_valid = True

                if dian_resolution['number_next'] > dian_resolution['number_to']:
                    spent = True

            if spent:
                pass # This is when the resolution it's spent and we keep generating numbers
            self.not_has_valid_dian = not_valid

    # Define withholding as new tax.
    wh_taxes = fields.Monetary('Withholding Tax', store="True",
                               compute="_compute_amount")

    amount_without_wh_tax = fields.Monetary('Total With Tax', store="True",
                                            compute="_compute_amount")
    date_invoice = fields.Date(required=True)

    not_has_valid_dian = fields.Boolean(compute='_get_has_valid_dian_info_JSON')

    resolution_number = fields.Char('Resolution number in invoice')
    resolution_date = fields.Date()
    resolution_date_to = fields.Date()
    resolution_number_from = fields.Integer("")
    resolution_number_to = fields.Integer("")

    # Calculate withholding tax and (new) total amount 

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id')
    def _compute_amount(self):
        """
        This functions computes the withholding tax on the untaxed amount
        @return: void
        """
        # Calling the original calculation
        super(AccountInvoice, self)._compute_amount()
        fp_company = self.env['account.fiscal.position'].search(
            [('id', '=', self.company_id.partner_id.property_account_position_id.id)])
        company_tax_ids = [base_tax.tax_id.id for base_tax in fp_company.tax_ids_invoice]

        if self.fiscal_position_id:
            fp_partner = self.env['account.fiscal.position'].search(
                [('id','=',self.fiscal_position_id.id)])

            partner_tax_ids = [base_tax.tax_id.id for base_tax in fp_partner.tax_ids_invoice]

            self.amount_tax = sum(line.amount for line in self.tax_line_ids if line.tax_id.id not in (partner_tax_ids + company_tax_ids))
            self.wh_taxes = abs(sum(line.amount for line in self.tax_line_ids if line.tax_id.id in partner_tax_ids))
        else:
            self.amount_tax = sum(line.amount for line in self.tax_line_ids if line.tax_id.id not in company_tax_ids)

        self.amount_without_wh_tax = self.amount_untaxed + self.amount_tax
        self.amount_total = self.amount_without_wh_tax - self.wh_taxes
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_signed = self.amount_total * sign

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        fp_company = self.env['account.fiscal.position'].search(
            [('id', '=', self.company_id.partner_id.property_account_position_id.id)])
        company_tax_ids = [base_tax.tax_id.id for base_tax in fp_company.tax_ids_invoice]

        residual = 0.0
        residual_company_signed = 0.0
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        for line in self.sudo().move_id.line_ids:
            if line.tax_line_id.id not in company_tax_ids:
                if line.account_id.internal_type in ('receivable', 'payable'):
                    residual_company_signed += line.amount_residual
                    if line.currency_id == self.currency_id:
                        residual += line.amount_residual_currency if line.currency_id else line.amount_residual
                    else:
                        from_currency = (line.currency_id and line.currency_id.with_context(date=line.date)) or line.company_id.currency_id.with_context(date=line.date)
                        residual += from_currency.compute(line.amount_residual, self.currency_id)
        self.residual_company_signed = abs(residual_company_signed) * sign
        self.residual_signed = abs(residual) * sign
        self.residual = abs(residual)
        digits_rounding_precision = self.currency_id.rounding
        if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
            self.reconciled = True
        else:
            self.reconciled = False

    @api.multi
    def _get_tax_amount_by_group(self):
        self.ensure_one()
        res = {}
        currency = self.currency_id or self.company_id.currency_id
        for line in self.tax_line_ids:
            if not line.tax_id.dont_impact_balance:
                res.setdefault(line.tax_id.tax_group_id, 0.0)
                res[line.tax_id.tax_group_id] += line.amount
            
        res = sorted(res.items(), key=lambda l: l[0].sequence)
        res = map(lambda l: (l[0].name, formatLang(self.env, l[1], currency_obj=currency)), res)

        groups_not_in_invoice = self.env['account.tax.group'].search_read([('not_in_invoice','=',True)],['name'])

        for g in groups_not_in_invoice:
            for i in res:
                if g['name'] == i[0]:
                    res.remove(i)
        return res

    def at_least_one_tax_group_enabled(self):
        res = False
        groups = self.env['account.tax'].search_read([('id','in',[invoice_tax.tax_id.id for invoice_tax in self.tax_line_ids])],['tax_group_id'])

        in_invoice = set()
        for group in groups:
            in_invoice.add(group['tax_group_id'][0])
        in_invoice = list(in_invoice)

        dont_show = [i.id for i in self.env['account.tax.group'].search([('not_in_invoice','=',True),
                                                                         ('id','in',in_invoice)])]
        if len(dont_show) < len(in_invoice):
            res = True

        return res


    @api.multi
    def get_taxes_values(self):
        tax_grouped = super(AccountInvoice, self).get_taxes_values()
        for order in self:
            tipo_factura = 'sale'
            if order.type in ('in_invoice', 'in_refund'):
                tipo_factura = 'purchase'
            if order.company_id.partner_id.property_account_position_id:
                
                fp = self.env['account.fiscal.position'].search(
                    [('id', '=', self.env.user.company_id.partner_id.property_account_position_id.id)])
                fp.ensure_one()
                
                for taxs in fp.tax_ids_invoice:
                    sql_diarios = "Select * from account_journal_taxes_ids_rel where tax_id = "+ str(taxs.id)+"" 
                    self.env.cr.execute( sql_diarios )
                    records = self.env.cr.dictfetchall()
                    if not records:
                        tax_ids = self.env['account.tax'].browse(taxs.tax_id.id)
                        for tax_id in tax_ids:
                            if tax_id.type_tax_use == tipo_factura:
                                if tax_id.based_tax_group:
                                    base = 0;
                                    for key_tax_grouped in tax_grouped:

                                        _tax_ids_invoice = self.env['account.tax'].search([('id', '=', tax_grouped[ key_tax_grouped ].get('tax_id'))])
                                        if _tax_ids_invoice:
                                            for tax_invoice in _tax_ids_invoice:
                                                if tax_invoice.tax_group_id.id == tax_id.tax_group_id_header.id:
                                                    base += tax_grouped[ key_tax_grouped ].get('amount')
                                
                                    tax = tax_id.compute_all(base, self.currency_id, partner=self.partner_id)['taxes'][0]
                            
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

                                    key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                                    if key not in tax_grouped:
                                        tax_grouped[key] = val
                                    else:
                                        tax_grouped[key]['amount'] += val['amount']

                                else:        
                                    tax = tax_id.compute_all(self.amount_untaxed, self.currency_id, partner=self.partner_id)['taxes'][0]
                                
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

                                    key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                                    if key not in tax_grouped:
                                        tax_grouped[key] = val
                                    else:
                                        tax_grouped[key]['amount'] += val['amount']
                    if records:
                        for loc in records:
                            if loc.get('journal_id') ==  order.journal_id.id:
                                ql_tax_id = "Select tax_id from account_fiscal_position_base_tax slt where id = "+ str(loc.get('tax_id'))+"" 
                                self.env.cr.execute( ql_tax_id )
                                records_tax = self.env.cr.dictfetchall()
                                fp_tax_ids = [tax.get('tax_id') for tax in records_tax]
                                tax_ids = self.env['account.tax'].browse(fp_tax_ids)
                                for tax_id in tax_ids:
                                    if tax_id.type_tax_use == tipo_factura:

                                        if tax_id.based_tax_group:
                                            base = 0;
                                            for key_tax_grouped in tax_grouped:
                                                _tax_ids_invoice = self.env['account.tax'].search([('id', '=', tax_grouped[ key_tax_grouped ].get('tax_id'))])
                                                if _tax_ids_invoice:
                                                    for tax_invoice in _tax_ids_invoice:
                                                        if tax_invoice.tax_group_id.id == tax_id.tax_group_id_header.id:
                                                            base += tax_grouped[ key_tax_grouped ].get('amount')
                                            tax = tax_id.compute_all(base, self.currency_id, partner=self.partner_id)['taxes'][0]
                                    
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

                                            key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                                            if key not in tax_grouped:
                                                tax_grouped[key] = val
                                            else:
                                                tax_grouped[key]['amount'] += val['amount']

                                        else:        
                                            tax = tax_id.compute_all(self.amount_untaxed, self.currency_id, partner=self.partner_id)['taxes'][0]
                                        
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

                                            key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                                            if key not in tax_grouped:
                                                tax_grouped[key] = val
                                            else:
                                                tax_grouped[key]['amount'] += val['amount']
            else:
                raise UserError(_('Debe definir una posicion fiscal para el partner asociado a la compañía actual'))
            
            if self.fiscal_position_id:
                fp = self.env['account.fiscal.position'].search([('id','=',self.fiscal_position_id.id)])
                fp.ensure_one()

                type_tax = 'sale' if self.type in ('out_invoice', 'out_refund') else 'purchase'
                tax_ids = self.env['account.tax'].search([('id','in',[tax.tax_id.id for tax in fp.tax_ids_invoice]),
                                                          ('type_tax_use','=',type_tax),
                                                          ('base_taxes','>',0)])

                #tax_ids = [tax.id for tax in tax_ids]
                for tax in tax_ids:
                    base_taxes = []
                    if self.type in ('in_refund', 'out_refund') and self.wh_taxes:
                        base_taxes = self.env['account.base.tax'].search([('start_date', '<=', self.date_invoice),
                                                                          ('end_date', '>=', self.date_invoice),
                                                                          # ('amount', '<=', self.amount_untaxed),
                                                                          ('tax_id', '=', tax.id)])
                    else:
                        base_taxes = self.env['account.base.tax'].search([('start_date','<=',self.date_invoice),
                                                                          ('end_date','>=',self.date_invoice),
                                                                          ('amount', '<=', self.amount_untaxed),
                                                                          ('tax_id','=',tax.id)])

                    for base in base_taxes:
                        _logger.info('base.tax_id.based_tax_group')
                        _logger.info(base.tax_id.based_tax_group)
                        if base.tax_id.based_tax_group:
                            _base = 0;
                            for key_tax_grouped in tax_grouped:
                                _tax_ids_invoice = self.env['account.tax'].search([('id', '=', tax_grouped[ key_tax_grouped ].get('tax_id'))])
                                if _tax_ids_invoice:
                                    for tax_invoice in _tax_ids_invoice:
                                        if tax_invoice.tax_group_id.id == base.tax_id.tax_group_id_header.id:
                                            _base += tax_grouped[ key_tax_grouped ].get('amount')
                            tax = base.tax_id.compute_all(_base, self.currency_id, partner=self.partner_id)['taxes'][0]
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

                            key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                            if key not in tax_grouped:
                                tax_grouped[key] = val
                            else:
                                tax_grouped[key]['amount'] += val['amount']                
                        else:                    
                            tax = base.tax_id.compute_all(self.amount_untaxed, self.currency_id, partner=self.partner_id)['taxes'][0]
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

                            key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                            if key not in tax_grouped:
                                tax_grouped[key] = val
                            else:
                                tax_grouped[key]['amount'] += val['amount']

        return tax_grouped

    @api.model
    def tax_line_move_line_get(self):
        result = super(AccountInvoice, self).tax_line_move_line_get()

        if self.type in ('out_invoice', 'out_refund'):
            fp = self.env['account.fiscal.position'].search(
                [('id', '=', self.company_id.partner_id.property_account_position_id.id)])
            fp.ensure_one()

            tax_ids = self.env['account.tax'].search([('id', 'in', [tax.tax_id.id for tax in fp.tax_ids_invoice]),
                                                      ('type_tax_use', '=', 'sale'),
                                                      ('dont_impact_balance','=',True)])
            tax_ids = [tax.id for tax in tax_ids]
            done_taxes = []
            for tax_line in sorted(self.tax_line_ids, key=lambda x: -x.sequence):
                if tax_line.tax_id.id in tax_ids:
                    if tax_line.tax_id.account_id_counterpart and tax_line.tax_id.refund_account_id_counterpart:
                        done_taxes.append(tax_line.tax_id.id)
                        result.append({
                            'invoice_tax_line_id': tax_line.id,
                            'tax_line_id': tax_line.tax_id.id,
                            'type': 'tax',
                            'name': tax_line.name,
                            'price_unit': tax_line.amount,
                            'quantity': 1,
                            'price': tax_line.amount * -1,
                            'account_id': tax_line.tax_id.account_id_counterpart.id,
                            'account_analytic_id': tax_line.account_analytic_id.id,
                            'invoice_id': self.id,
                            'tax_ids': [(6, 0, done_taxes)] if tax_line.tax_id.include_base_amount else []
                        })
                    else:
                        raise UserError(_('You have not a counterpart account on one of your company taxes'))
        return result

    @api.onchange('fiscal_position_id','date_invoice')
    def _onchange_fiscal_position_id(self):
        #if not self.date_invoice:
            #self.date_invoice = fields.Date.context_today(self)
        self._onchange_invoice_line_ids()

    @api.multi
    def action_move_create(self):
        result = super(AccountInvoice, self).action_move_create()

        for inv in self:
            sequence = self.env['ir.sequence.dian_resolution'].search([('sequence_id','=',self.journal_id.sequence_id.id),('active_resolution','=',True)], limit=1)
            inv.resolution_number = sequence['resolution_number']
            inv.resolution_date = sequence['date_from']
            inv.resolution_date_to = sequence['date_to']
            inv.resolution_number_from = sequence['number_from']
            inv.resolution_number_to = sequence['number_to']
        return result

class AccountInvoiceLine(models.Model):
    _name = 'account.invoice.line'
    _inherit = 'account.invoice.line'

class AccountTax(models.Model):
    _name = 'account.tax'
    _inherit = 'account.tax'

    tax_in_invoice = fields.Boolean(string="Evaluate in invoice", default=False,
        help="Check this if you want to hide the tax from the taxes list in products")
    based_tax_group = fields.Boolean(string="Based on Tax Group", default=False,
        help="Check this if you want to show the field taxes group list")

    #Grupo de impuestos de encabezado
    tax_group_id_header = fields.Many2one('account.tax.group', string="Tax Group")
    
    dont_impact_balance = fields.Boolean(string="Don't impact balance", default=False,
        help="Check this if you want to assign counterpart taxes accounts")
    account_id_counterpart = fields.Many2one('account.account', string='Tax Account Counterpart', ondelete='restrict',
        help="Account that will be set on invoice tax lines for invoices. Leave empty to use the expense account.")
    refund_account_id_counterpart = fields.Many2one('account.account', string='Tax Account Counterpart on Refunds', ondelete='restrict',
        help="Account that will be set on invoice tax lines for refunds. Leave empty to use the expense account.")
    position_id = fields.Many2one('account.fiscal.position', string='Fiscal position related id')
    base_taxes = fields.One2many('account.base.tax', 'tax_id', string='Base taxes', help='This field show related taxes applied to this tax')

    @api.onchange('account_id_counterpart')
    def onchange_account_id_counterpart(self):
        self.refund_account_id_counterpart = self.account_id_counterpart

    @api.v8
    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None):
        result = super(AccountTax, self).compute_all(price_unit, currency=currency, quantity=quantity, product=product, partner=partner)
        for tax in self.sorted(key=lambda r: r.sequence):
            for iter_tax in result['taxes']:
                if iter_tax['id'] == tax.id:
                    iter_tax['account_id_counterpart'] = tax.account_id_counterpart.id
                    iter_tax['refund_account_id_counterpart'] = tax.refund_account_id_counterpart.id

        return result


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
    account_journal_ids = fields.Many2many('account.journal', 'account_journal_taxes_ids_rel', 'tax_id', 'journal_id', 'Journal')
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
    

class AccountJournal(models.Model):
    _name = "account.journal"
    _inherit = "account.journal"

    @api.model
    def create(self, vals):
        
        return super(AccountJournal, self).create(vals)

    @api.model
    def _create_sequence(self, vals, refund=False):
        
        return super(AccountJournal, self)._create_sequence(vals, refund)

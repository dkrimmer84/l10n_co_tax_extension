import time

from openerp import api, fields, models, _
import openerp.addons.decimal_precision as dp

import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    @api.multi
    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals['date_invoice'] = fields.Date.context_today(self)
        return invoice_vals
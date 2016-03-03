# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import osv, fields
import time
from datetime import datetime, date
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import openerp.addons.decimal_precision as dp
from openerp import netsvc
from pytz import timezone


# Impuestos para desglose en Cartas Porte
class tms_waybill_taxes(osv.osv):
    _name = "tms.waybill.taxes"
    _description = "Waybill Taxes"

    _columns = {
        'waybill_id': fields.many2one('tms.waybill', 'Waybill', readonly=True),
        'name'      : fields.char('Impuesto', size=64, required=True),
        'tax_id'    : fields.many2one('account.tax', 'Impuesto', readonly=True),
        'account_id': fields.many2one('account.account', 'Tax Account', required=False, domain=[('type','<>','view'),('type','<>','income'), ('type', '<>', 'closed')]),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Analytic account'),
        'base'      : fields.float('Base', digits_compute=dp.get_precision('Account'), readonly=True),
        'tax_amount': fields.float('Monto Impuesto', digits_compute=dp.get_precision('Account'), readonly=True),
    }
    
    _order = "tax_amount desc"
    
    def compute(self, cr, uid, waybill_ids, context=None):
        for id in waybill_ids:
            cr.execute("DELETE FROM tms_waybill_taxes WHERE waybill_id=%s", (id,))
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        wb_taxes_obj = self.pool.get('tms.waybill.taxes')
        for waybill in self.pool.get('tms.waybill').browse(cr, uid, waybill_ids, context=context):
            tax_grouped = {}
            cur = waybill.currency_id
            company_currency = self.pool['res.company'].browse(cr, uid, waybill.company_id.id).currency_id.id
            for line in waybill.waybill_line: 
                for tax in tax_obj.compute_all(cr, uid, line.tax_id, line.price_unit, line.product_uom_qty, line.product_id, waybill.partner_id)['taxes']:
                    val={}
                    val['waybill_id'] = waybill.id
                    val['name'] = tax['name']
                    val['tax_id'] = tax['id']
                    val['amount'] = tax['amount']
                    val['base'] = cur_obj.round(cr, uid, cur, tax['price_unit'] * line['product_uom_qty'])
                    val['base_amount'] = cur_obj.compute(cr, uid, waybill.currency_id.id, company_currency, val['base'] * tax['base_sign'], context={'date': waybill.date_order or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, waybill.currency_id.id, company_currency, val['amount'] * tax['tax_sign'], context={'date': waybill.date_order or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_collected_id'] or False
                    val['account_analytic_id'] = tax['account_analytic_collected_id']
                    key = (val['tax_id'], val['name'], val['account_id'], val['account_analytic_id'])
                    if not key in tax_grouped:
                        tax_grouped[key] = val
                    else:
                        tax_grouped[key]['amount'] += val['amount']
                        tax_grouped[key]['base'] += val['base']
                        tax_grouped[key]['base_amount'] += val['base_amount']
                        tax_grouped[key]['tax_amount'] += val['tax_amount']
            
            for t in tax_grouped.values():
                vals = {'waybill_id' : waybill.id,
                        'name'     : t['name'],
                        'tax_id'   : t['tax_id'],
                        'account_id': t['account_id'],
                        'account_analytic_id': t['account_analytic_id'],
                        'tax_amount': t['amount'],
                        'base'      : t['base'],
                        }
                res = wb_taxes_obj.create(cr, uid, vals)
                t['base'] = cur_obj.round(cr, uid, cur, t['base'])
                t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
                t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
                t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])
        return 

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
import threading

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    invoice_commission_count = fields.Integer(
        'Source Invoices',
        compute='_compute_source_invoice_count',
        compute_sudo=True,
        help='Invoices that have generated commissions included in this order'
    )

    def _compute_source_invoice_count(self):
        for purchase_order in self:
            purchase_order.invoice_commission_count = self.env['account.move'].search_count([('commission_po_line_id.order_id', '=', purchase_order.id)])

    def action_view_customer_invoices(self):
        self.ensure_one()

        res = self.env['ir.actions.act_window'].for_xml_id('partner_commission', 'action_view_customer_invoices')
        res.update({
            'domain': [('commission_po_line_id.order_id', 'in', self.ids)],
        })
        return res

    @api.model
    def _cron_confirm_purchase_orders(self):
        # Frequency is company dependent.
        companies = self.env['res.company'].search([])
        for company in companies:
            frequency = company.commission_automatic_po_frequency

            # noop
            if frequency == 'manually':
                continue

            today = fields.Date.today()
            monday = frequency == 'weekly' and today.isoweekday() == 1
            first_of_the_month = frequency == 'monthly' and today.day == 1
            new_quarter = frequency == 'quarterly' and today.day == 1 and today.month in [1, 4, 7, 10]
            run = monday or first_of_the_month or new_quarter

            if not run:
                continue

            purchases = self.env['purchase.order'].search([
                ('company_id', '=', company.id),
                ('date_order', '<', today),
                ('state', '=', 'draft'),
            ])

            for po in purchases.filtered(lambda p: p.invoice_commission_count > 0):
                try:
                    po.button_confirm()
                    auto_commit = not getattr(threading.currentThread(), 'testing', False)
                    if auto_commit:
                        self.env.cr.commit()
                except:
                    _logger.exception('_cron_confirm_purchase_orders: PO (id=%s) could not be confirmed', po.id)

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, tools


class RentalReport(models.Model):
    _name = "sale.rental.report"
    _description = "Rental Analysis Report"
    _auto = False

    date = fields.Date('Date', readonly=True)
    order_id = fields.Many2one('sale.order', 'Order #', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    product_uom = fields.Many2one('uom.uom', 'Unit of Measure', readonly=True)
    quantity = fields.Float('Daily Ordered Qty', readonly=True)
    qty_delivered = fields.Float('Daily Picked-Up Qty', readonly=True)
    qty_returned = fields.Float('Daily Returned Qty', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Customer', readonly=True)
    user_id = fields.Many2one('res.users', 'Salesman', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', readonly=True)
    categ_id = fields.Many2one('product.category', 'Product Category', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Sales Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)
    price = fields.Float('Daily Amount', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', readonly=True)

    def _query(self):
        return """
        select
            sol.id,
            sol.order_id,
            sol.product_id,
            sol.product_uom_qty  / (u.factor * u2.factor) as quantity,
            sol.qty_delivered  / (u.factor * u2.factor) as qty_delivered,
            sol.qty_returned  / (u.factor * u2.factor) as qty_returned,
            sol.product_uom,
            sol.order_partner_id as partner_id,
            sol.salesman_id as user_id,
            pt.categ_id,
            p.product_tmpl_id,
            generate_series(sol.pickup_date::date, sol.return_date::date, '1 day'::interval)::date date,
            sol.price_subtotal / (date_part('day',sol.return_date - sol.pickup_date) + 1) as price,
            sol.company_id,
            sol.state,
            sol.currency_id
        from sale_order_line sol
            join product_product p on p.id=sol.product_id
            join product_template pt on p.product_tmpl_id=pt.id
            join uom_uom u on u.id=sol.product_uom
            join uom_uom u2 on u2.id=pt.uom_id
        where sol.is_rental
        """

    def init(self):
        # self._table = sale_rental_report
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, self._query()))

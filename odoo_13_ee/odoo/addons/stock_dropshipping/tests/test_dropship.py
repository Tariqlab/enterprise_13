# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common, Form
from odoo.tools import mute_logger


class TestDropship(common.TransactionCase):
    def test_change_qty(self):
        # enable the dropship and MTO route on the product
        prod = self.env.ref('product.product_product_8')
        dropshipping_route = self.env.ref('stock_dropshipping.route_drop_shipping')
        mto_route = self.env.ref('stock.route_warehouse0_mto')
        prod.write({'route_ids': [(6, 0, [dropshipping_route.id, mto_route.id])]})

        # add a vendor
        vendor1 = self.env['res.partner'].create({'name': 'vendor1'})
        seller1 = self.env['product.supplierinfo'].create({
            'name': vendor1.id,
            'price': 8,
        })
        prod.write({'seller_ids': [(6, 0, [seller1.id])]})

        # sell one unit of this product
        cust = self.env['res.partner'].create({'name': 'customer1'})
        so = self.env['sale.order'].create({
            'partner_id': cust.id,
            'partner_invoice_id': cust.id,
            'partner_shipping_id': cust.id,
            'order_line': [(0, 0, {
                'name': prod.name,
                'product_id': prod.id,
                'product_uom_qty': 1.00,
                'product_uom': prod.uom_id.id,
                'price_unit': 12,
            })],
            'pricelist_id': self.env.ref('product.list0').id,
            'picking_policy': 'direct',
        })
        so.action_confirm()
        po = self.env['purchase.order'].search([('group_id', '=', so.procurement_group_id.id)])
        po_line = po.order_line

        # Check the qty on the P0
        self.assertAlmostEqual(po_line.product_qty, 1.00)

        # Update qty on SO and check PO
        so.write({'order_line': [[1, so.order_line.id, {'product_uom_qty': 2.00}]]})
        self.assertAlmostEqual(po_line.product_qty, 2.00)

        # Create a new so line
        sol2 = self.env['sale.order.line'].create({
            'order_id': so.id,
            'name': prod.name,
            'product_id': prod.id,
            'product_uom_qty': 3.00,
            'product_uom': prod.uom_id.id,
            'price_unit': 12,
        })
        # there is a new line
        pol2 = po.order_line - po_line
        # the first line is unchanged
        self.assertAlmostEqual(po_line.product_qty, 2.00)
        # the new line matches the new line on the so
        self.assertAlmostEqual(pol2.product_qty, sol2.product_uom_qty)

    def test_00_dropship(self):

        # Create a vendor
        supplier_dropship = self.env['res.partner'].create({'name': 'Vendor of Dropshipping test'})

        # Create new product without any routes
        drop_shop_product = self.env['product.product'].create({
            'name': "Pen drive",
            'type': "product",
            'categ_id': self.env.ref('product.product_category_1').id,
            'lst_price': 100.0,
            'standard_price': 0.0,
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'uom_po_id': self.env.ref('uom.product_uom_unit').id,
            'seller_ids': [(0, 0, {
                'delay': 1,
                'name': supplier_dropship.id,
                'min_qty': 2.0
            })]
        })

        # Create a sales order with a line of 200 PCE incoming shipment, with route_id drop shipping
        so_form = Form(self.env['sale.order'])
        so_form.partner_id = self.env.ref('base.res_partner_2')
        so_form.payment_term_id = self.env.ref('account.account_payment_term_end_following_month')
        with mute_logger('odoo.tests.common.onchange'):
            # otherwise complains that there's not enough inventory and
            # apparently that's normal according to @jco and @sle
            with so_form.order_line.new() as line:
                line.product_id = drop_shop_product
                line.product_uom_qty = 200
                line.price_unit = 1.00
                line.route_id = self.env.ref('stock_dropshipping.route_drop_shipping')
        sale_order_drp_shpng = so_form.save()

        # Confirm sales order
        sale_order_drp_shpng.action_confirm()

        # Check the sales order created a procurement group which has a procurement of 200 pieces
        self.assertTrue(sale_order_drp_shpng.procurement_group_id, 'SO should have procurement group')

        # Check a quotation was created to a certain vendor and confirm so it becomes a confirmed purchase order
        purchase = self.env['purchase.order'].search([('partner_id', '=', supplier_dropship.id)])
        self.assertTrue(purchase, "an RFQ should have been created by the scheduler")
        purchase.button_confirm()
        self.assertEquals(purchase.state, 'purchase', 'Purchase order should be in the approved state')
        self.assertEquals(len(purchase.ids), 1, 'There should be one picking')

        # Send the 200 pieces
        purchase.picking_ids.move_lines.quantity_done = purchase.picking_ids.move_lines.product_qty
        purchase.picking_ids.button_validate()

        # Check one move line was created in Customers location with 200 pieces
        move_line = self.env['stock.move.line'].search([
            ('location_dest_id', '=', self.env.ref('stock.stock_location_customers').id),
            ('product_id', '=', drop_shop_product.id)])
        self.assertEquals(len(move_line.ids), 1, 'There should be exactly one move line')

    def test_01_dropship_with_different_uom(self):
        
        location = self.env.ref('stock.stock_location_stock')
        
        # Create a vendor
        supplier_dropship = self.env['res.partner'].create({'name': 'Vendor of Dropshipping test'})
        
        # Create a product
        test_product = self.env['product.template'].create({"name": "Product"})
        
        # Create a component with UoM Liters with dropshipping route
        dropshipping_route = self.env.ref('stock_dropshipping.route_drop_shipping')
        component_liter = self.env['product.template'].create({
            "name": "component liter",
            "route_ids": [(6, 0, [dropshipping_route.id])],
            "seller_ids": [(0, 0, {
                'delay': 1,
                'name': supplier_dropship.id,
                'min_qty': 1.0
            })],
            "uom_id": 11,
            "uom_po_id": 11,
        })
        
        # Create an other component with UoM Units without dropshipping route
        component_unit = self.env['product.template'].create({
            "name": "component liter",
            "type": "product",
            "uom_id": 1,
            "uom_po_id": 1,
        })
        
        self.env['stock.quant']._update_available_quantity(component_unit.product_variant_id, location, 100)
        
        # Create a BoM for the product with the two components
        self.env['mrp.bom'].create({
            "product_tmpl_id": test_product.id,
            "product_id": False,
            "product_qty": 1,
            "type": "phantom",
            "bom_line_ids": [
                [0, 0, {"product_id": component_liter.product_variant_id.id, "product_qty": 1}],
                [0, 0, {"product_id": component_unit.product_variant_id.id, "product_qty": 1}],
            ]
        })
        
        # Create a sales order with a line of 1 test_product
        so_form = Form(self.env['sale.order'])
        so_form.partner_id = self.env.ref('base.res_partner_2')
        so_form.payment_term_id = self.env.ref('account.account_payment_term_end_following_month')
        with so_form.order_line.new() as line:
            line.product_id = test_product.product_variant_id
            line.product_uom_qty = 1
            line.price_unit = 1.00
        sale_order = so_form.save()
        sale_order.action_confirm()
        
        # Modify the quantity on sale order line
        sale_order.write({'order_line': [[1, sale_order.order_line.id, {'product_uom_qty': 2.00}]]})
        
        self.assertEqual(sale_order.order_line.product_uom_qty, 2)

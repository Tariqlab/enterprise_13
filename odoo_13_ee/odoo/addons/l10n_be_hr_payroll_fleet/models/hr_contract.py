# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.osv import expression


class HrContract(models.Model):
    _inherit = 'hr.contract'

    @api.model
    def default_get(self, field_list):
        res = super(HrContract, self).default_get(field_list)
        driver_id = self.env['hr.employee'].search([
            ('user_id', '=', self.env.uid),
            ('company_id', '=', self.env.company.id),
        ])
        domain = self._get_available_cars_domain(driver_id)
        res['car_id'] = res.get('car_id', self.env['fleet.vehicle'].sudo().search(domain, limit=1).id)
        return res

    @api.model
    def _get_available_cars_domain(self, driver_id=None):
        return expression.AND([
            expression.OR([
                [('future_driver_id', '=', False)],
                [('future_driver_id', '=', driver_id.id if driver_id else False)],
            ]),
            expression.OR([
                [('driver_id', '=', False)],
                [('driver_id', '=', driver_id.id if driver_id else False)],
                [('plan_to_change_car', '=', True)]
            ])
        ])

    def _get_possible_model_domain(self):
        return [('can_be_requested', '=', True)]

    car_id = fields.Many2one('fleet.vehicle', string='Company Car',
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Employee's company car.",
        groups='fleet.fleet_group_manager')
    car_atn = fields.Float(compute='_compute_car_atn_and_costs', string='ATN Company Car', store=True, compute_sudo=True)
    company_car_total_depreciated_cost = fields.Float(compute='_compute_car_atn_and_costs', store=True, compute_sudo=True)
    available_cars_amount = fields.Integer(compute='_compute_available_cars_amount', string='Number of available cars')
    new_car = fields.Boolean('Request a new car')
    new_car_model_id = fields.Many2one('fleet.vehicle.model', string="Model", domain=lambda self: self._get_possible_model_domain())
    max_unused_cars = fields.Integer(compute='_compute_max_unused_cars')
    acquisition_date = fields.Date(related='car_id.acquisition_date', readonly=False, groups="fleet.fleet_group_manager")
    car_value = fields.Float(related="car_id.car_value", readonly=False, groups="fleet.fleet_group_manager")
    fuel_type = fields.Selection(related="car_id.fuel_type", readonly=False, groups="fleet.fleet_group_manager")
    co2 = fields.Float(related="car_id.co2", readonly=False, groups="fleet.fleet_group_manager")
    driver_id = fields.Many2one('res.partner', related="car_id.driver_id", readonly=False, groups="fleet.fleet_group_manager")
    car_open_contracts_count = fields.Integer(compute='_compute_car_open_contracts_count', groups="fleet.fleet_group_manager")
    recurring_cost_amount_depreciated = fields.Float(
        groups="fleet.fleet_group_manager",
        compute='_compute_recurring_cost_amount_depreciated',
        inverse="_inverse_recurring_cost_amount_depreciated")

    @api.depends('car_id', 'new_car', 'new_car_model_id', 'car_id.total_depreciated_cost',
        'car_id.atn', 'new_car_model_id.default_atn', 'new_car_model_id.default_total_depreciated_cost')
    def _compute_car_atn_and_costs(self):
        self.car_atn = False
        self.company_car_total_depreciated_cost = False
        for contract in self:
            if not contract.new_car and contract.car_id:
                contract.car_atn = contract.car_id.atn
                contract.company_car_total_depreciated_cost = contract.car_id.total_depreciated_cost
            elif contract.new_car and contract.new_car_model_id:
                contract.car_atn = contract.new_car_model_id.default_atn
                contract.company_car_total_depreciated_cost = contract.new_car_model_id.default_total_depreciated_cost

    @api.depends('car_id.log_contracts.state')
    def _compute_car_open_contracts_count(self):
        for contract in self:
            contract.car_open_contracts_count = len(contract.car_id.log_contracts.filtered(
                lambda c: c.state == 'open').ids)

    @api.depends('car_open_contracts_count', 'car_id.log_contracts.recurring_cost_amount_depreciated')
    def _compute_recurring_cost_amount_depreciated(self):
        for contract in self:
            if contract.car_open_contracts_count == 1:
                contract.recurring_cost_amount_depreciated = contract.car_id.log_contracts.filtered(
                    lambda c: c.state == 'open'
                ).recurring_cost_amount_depreciated
            else:
                contract.recurring_cost_amount_depreciated = 0.0

    def _inverse_recurring_cost_amount_depreciated(self):
        for contract in self:
            if contract.car_open_contracts_count == 1:
                contract.car_id.log_contracts.filtered(
                    lambda c: c.state == 'open'
                ).recurring_cost_amount_depreciated = contract.recurring_cost_amount_depreciated

    @api.depends('name')
    def _compute_available_cars_amount(self):
        for contract in self:
            contract.available_cars_amount = self.env['fleet.vehicle'].sudo().search_count(contract._get_available_cars_domain(contract.employee_id.address_home_id))

    @api.depends('name')
    def _compute_max_unused_cars(self):
        params = self.env['ir.config_parameter'].sudo()
        max_unused_cars = params.get_param('l10n_be_hr_payroll_fleet.max_unused_cars', default=1000)
        for contract in self:
            contract.max_unused_cars = int(max_unused_cars)

    @api.onchange('transport_mode_car', 'transport_mode_public', 'transport_mode_others')
    def _onchange_transport_mode(self):
        super(HrContract, self)._onchange_transport_mode()
        if not self.transport_mode_car:
            self.car_id = False
            self.new_car_model_id = False

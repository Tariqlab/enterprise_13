odoo.define('l10n_de_pos_res_cert.screens', function (require) {
    'use strict';
    const screens = require('point_of_sale.screens');
    const core = require('web.core');
    const _t = core._t;

    screens.PaymentScreenWidget.include({
        async finalize_validation() {
            const _super = this._super.bind(this);
            const order = this.pos.get_order();
            if (this.pos.isRestaurantCountryGermany() && (!order.is_to_invoice() || order.get_client())) {
                // In order to not modify the base code, the second condition is needed for invoicing
                try {
                    await order.retrieveAndSendLineDifference()
                } catch (e) {
                    // do nothing with the error
                }
            }
            await _super();
        }
    });
});

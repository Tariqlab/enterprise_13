odoo.define('l10n_de_pos_res_cert.floor', function(require) {
    'use strict';

    require('pos_restaurant.floors');
    const models = require('point_of_sale.models');
    const { uuidv4 } = require('l10n_de_pos_cert.utils');
    const rpc = require('web.rpc');

    const _super_posmodel = models.PosModel.prototype;
    models.PosModel = models.PosModel.extend({
        isRestaurantCountryGermany() {
            return this.isCountryGermany() && this.config.iface_floorplan;
        },
        //@Override
        update_table_order(server_id, table_orders) {
            const order = _super_posmodel.update_table_order.apply(this,arguments);
            if (this.isRestaurantCountryGermany() && server_id.differences && order) {
                    order.createAndFinishOrderTransaction(server_id.differences)
                }
            return order
        },
        _post_remove_from_server(server_ids, data) {
            if (this.isRestaurantCountryGermany() && data.length > 0) {
                // at this point of the flow, it's impossible to retrieve the local order, only the ids were stored
                // therefore we create an "empty" order object in order to call the needed methods
                data.forEach(async elem => {
                    const order = new models.Order({},{pos:this});
                    await order.cancelOrderTransaction(elem.differences);
                    order.destroy();
                })
            }
            return _super_posmodel._post_remove_from_server.apply(this, arguments);
        }
    });

    const _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        _updateTimeStart(seconds) {
            if (!(this.pos.isRestaurantCountryGermany() && this.tssInformation.time_start.value)) {
                _super_order._updateTimeStart.apply(this, arguments);
            }
        },
        async createAndFinishOrderTransaction(lineDifference) {
            const transactionUuid = uuidv4();
            if (!this.pos.getApiToken()) {
                await this._authenticate();
            }

            const data = {
                'state': 'ACTIVE',
                'client_id': this.pos.getClientId()
            };
            return $.ajax({
                url: `${this.pos.getApiUrl()}/tss/${this.pos.getTssId()}/tx/${transactionUuid}`,
                method: 'PUT',
                headers: { 'Authorization': `Bearer ${this.pos.getApiToken()}` },
                data: JSON.stringify(data),
                contentType: 'application/json',
                timeout: 5000
            }).then(() => {
                const data = {
                    'state': 'FINISHED',
                    'client_id': this.pos.getClientId(),
                    'schema': {
                        'standard_v1': {
                            'order': {
                                'line_items': lineDifference
                            }
                        }
                    }
                };
                return $.ajax({
                    url: `${this.pos.getApiUrl()}/tss/${this.pos.getTssId()}/tx/${transactionUuid}?last_revision=1`,
                    method: 'PUT',
                    headers: {'Authorization': `Bearer ${this.pos.getApiToken()}`},
                    data: JSON.stringify(data),
                    contentType: 'application/json',
                    timeout: 5000
                });
            }).catch(async (error) => {
                if (error.status === 401) {  // Need to update the token
                    await this._authenticate();
                    return this.createAndFinishOrderTransaction(lineDifference);
                }
                // Return a Promise with rejected value for errors that are not handled here
                return Promise.reject(error);
            });
        },
        exportOrderLinesAsJson() {
            const orderLines = [];
            this.orderlines.each(_.bind( function(item) {
                return orderLines.push([0, 0, item.export_as_JSON()]);
            }, this));

            return {
                server_id: this.server_id ? this.server_id : false,
                lines: orderLines
            }
        },
        async retrieveAndSendLineDifference() {
            await rpc.query({
                model: 'pos.order',
                method: 'retrieve_line_difference',
                args: [this.exportOrderLinesAsJson()]
            }).then(async data => {
                if (data.differences.length > 0) {
                    await this.createAndFinishOrderTransaction(data.differences);
                }
            });
        },
         async cancelOrderTransaction(lineDifference) {
            if (lineDifference.length > 0) {
                await this.createAndFinishOrderTransaction(lineDifference);
            }
            await this.createTransaction();
            await this.cancelTransaction();
        }
    });
});

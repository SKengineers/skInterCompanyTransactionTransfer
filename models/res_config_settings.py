from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    allow_auto_inter_transaction = fields.Boolean(string='Allow Auto Intercompany Transaction')
    auto_validate_delivery_receipt = fields.Boolean(string='Auto Validate Delivery/Receipt')
    auto_create_invoice_bill = fields.Boolean(string='Auto Create Invoice/Vendor Bills')
    auto_validate_invoice_bill = fields.Boolean(string='Auto Validate Invoice/Vendor Bills')

    @api.onchange('allow_auto_inter_transaction')
    def onchange_allow_auto_inter_transaction(self):
        if self.allow_auto_inter_transaction:
            self.auto_create_invoice_bill = True
            self.auto_validate_delivery_receipt = True
            self.auto_validate_invoice_bill = True
        else:
            self.auto_create_invoice_bill = False
            self.auto_validate_delivery_receipt = False
            self.auto_validate_invoice_bill = False

    @api.model
    def get_values(self):
        res = super(ResConfigSetting, self).get_values()
        Param = self.env['ir.config_parameter'].sudo()
        res.update(
            allow_auto_inter_transaction=Param.get_param('agInterCompanyTransactionTransfer.allow_auto_inter_transaction'),
            auto_validate_delivery_receipt=Param.get_param('agInterCompanyTransactionTransfer.auto_validate_delivery_receipt'),
            auto_create_invoice_bill=Param.get_param('agInterCompanyTransactionTransfer.auto_create_invoice_bill'),
            auto_validate_invoice_bill=Param.get_param('agInterCompanyTransactionTransfer.auto_validate_invoice_bill'),
        )
        return res

    def set_values(self):
        super(ResConfigSetting, self).set_values()
        self.env['ir.config_parameter'].set_param('agInterCompanyTransactionTransfer.allow_auto_inter_transaction', self.allow_auto_inter_transaction)
        self.env['ir.config_parameter'].set_param('agInterCompanyTransactionTransfer.auto_validate_delivery_receipt', self.auto_validate_delivery_receipt)
        self.env['ir.config_parameter'].set_param('agInterCompanyTransactionTransfer.auto_create_invoice_bill', self.auto_create_invoice_bill)
        self.env['ir.config_parameter'].set_param('agInterCompanyTransactionTransfer.auto_validate_invoice_bill', self.auto_validate_invoice_bill)
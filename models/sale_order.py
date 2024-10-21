from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from datetime import datetime, date, time, timedelta


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    inter_transfer_ids = fields.One2many('inter.company.transfer', 'sale_order_id')
    count_inter_transfer = fields.Integer(string='Count Inter Transfer', compute='compute_count_inter_transfer', store=True)

    @api.depends('inter_transfer_ids')
    def compute_count_inter_transfer(self):
        for rec in self:
            rec.count_inter_transfer = len(rec.inter_transfer_ids)

    def check_setting_auto_workflow_inter_transaction(self):
        checking_auto_workflow = self.env['ir.config_parameter'].get_param('agInterCompanyTransactionTransfer.allow_auto_inter_transaction')
        return checking_auto_workflow

    def create_line_inter_transaction(self, transfer_id, order_line):
        if any(order_line.filtered(lambda x: not x.product_id)) or any(order_line.filtered(lambda x: x.product_uom_qty <= 0)) or not order_line:
            raise UserError(_("You have to input Product and Quantity if you want to create a Inter Company Transfer!"))
        for line in order_line:
            self.env['product.detail'].create({
                'transfer_id': transfer_id.id,
                'product_id': line.product_id.id,
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit
            })

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for rec in self:
            if not self.env.context.get('skip_auto'):
                currency_company = rec.company_id
                other_company = self.env['res.company'].search([
                    ('id', '!=', currency_company.id)
                ])
                partner_company = other_company.filtered(lambda x: x.partner_id.id == rec.partner_id.id)
                if (self.check_setting_auto_workflow_inter_transaction()
                        and self.env.user.has_group('agInterCompanyTransactionTransfer.group_allow_internal_transfer')
                        and partner_company):
                    # Create inter transaction and process it
                    inter_company_transaction = self.env['inter.company.transfer'].create({
                        'from_warehouse_id': rec.company_id.intercompany_warehouse_id.id,
                        'to_warehouse_id': partner_company.intercompany_warehouse_id.id,
                        'type': 'transfer',
                        'apply_type': 'purchase',
                        'currency_id': rec.currency_id.id,
                        'pricelist_id': rec.pricelist_id.id,
                        'sale_order_id': rec.id
                    })
                    self.create_line_inter_transaction(inter_company_transaction, rec.order_line)

                    # auto validate picking of Sale
                    rec.picking_ids.filtered(lambda x: x.state != 'cancel' and x.state == 'assigned').with_context(skip_backorder=True).button_validate()

                    # Create invoice for sale and post
                    invoice = rec._create_invoices()
                    invoice.action_post()
                    inter_company_transaction.invoice_id = invoice.id

                    # Do the process of Inter Company transaction
                    inter_company_transaction.action_process()
        return res

    def _get_action_view_inter_transfer(self):
        self.ensure_one()
        if len(self.inter_transfer_ids) == 1:
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Inter Company Transfer'),
                'res_model': 'inter.company.transfer',
                'view_mode': 'form',
                'view_id': self.env.ref('agInterCompanyTransactionTransfer.inter_company_transfer_form_view').id,
                'res_id': self.inter_transfer_ids.id
            }
        else:
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Inter/Return Company Transfer'),
                'res_model': 'inter.company.transfer',
                'view_mode': 'tree',
                'domain': [('id', 'in', self.inter_transfer_ids.ids)]
            }
        return action

    def action_view_inter_transfer(self):
        return self._get_action_view_inter_transfer()

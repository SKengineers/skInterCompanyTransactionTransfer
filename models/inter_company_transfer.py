from odoo import api, fields, models, SUPERUSER_ID, _
from datetime import date, datetime, timedelta, time
from odoo.exceptions import AccessError, UserError, ValidationError


class InterCompanyTransfer(models.Model):
    _name = 'inter.company.transfer'
    _description = 'Inter Company Transfer'
    _inherit = [
        'portal.mixin',
        'mail.thread.cc',
        'mail.activity.mixin',
        'rating.mixin',
        'mail.tracking.duration.mixin'
    ]

    name = fields.Char(string='Name')
    from_warehouse_id = fields.Many2one('stock.warehouse', string='From Warehouse')
    from_company_id = fields.Many2one('res.company', string='From Company', compute='compute_company', store=True)
    to_warehouse_id = fields.Many2one('stock.warehouse', string='To Warehouse')
    to_company_id = fields.Many2one('res.company', string='To Company', compute='compute_company', store=True)

    sale_order_id = fields.Many2one('sale.order', string='Sale Order')
    count_sale = fields.Integer(string='Count Sale', compute='count_data', store=True)

    invoice_id = fields.Many2one('account.move', string='Invoice')
    count_invoice = fields.Integer(string='Count Invoice', compute='count_data', store=True)

    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order')
    count_purchase = fields.Integer(string='Count Purchase', compute='count_data', store=True)

    bill_id = fields.Many2one('account.move', string='Bill')
    count_bill = fields.Integer(string='Count Bill', compute='count_data', store=True)

    type = fields.Selection([
        ('transfer', 'Transfer'),
        ('return', 'Return')
    ], string='Type', default=None)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('process', 'Process'),
        ('return', 'Return')
    ], string='State', default='draft')
    apply_type = fields.Selection([
        ('sale', 'Sale Order'),
        ('purchase', 'Purchase Order'),
        ('sale_purchase', 'Sale and Purchase Order')
    ], string='Apply Type', default=None)
    currency_id = fields.Many2one('res.currency', string='Currency')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')

    backorder_of_id = fields.Many2one('inter.company.transfer', string='Return Of')
    count_backorder_of = fields.Integer(string='Count Backorder', compute='count_data', store=True)

    product_line_ids = fields.One2many('product.detail', 'transfer_id', string='Product Detail')

    @api.depends('from_warehouse_id', 'to_warehouse_id')
    def compute_company(self):
        for rec in self:
            from_company = self.env['res.company'].search([
                ('intercompany_warehouse_id', '=', rec.from_warehouse_id.id)
            ])
            to_company = self.env['res.company'].search([
                ('intercompany_warehouse_id', '=', rec.to_warehouse_id.id)
            ])
            rec.from_company_id = from_company.id
            rec.to_company_id = to_company.id

    @api.depends('sale_order_id', 'invoice_id', 'purchase_order_id', 'bill_id', 'backorder_of_id')
    def count_data(self):
        for rec in self:
            rec.count_sale = len(rec.sale_order_id)
            rec.count_invoice = len(rec.invoice_id)

            rec.count_purchase = len(rec.purchase_order_id)
            rec.count_bill = len(rec.bill_id)

            rec.count_backorder_of = len(rec.backorder_of_id)

    @api.model
    def create(self, vals_list):
        result = super(InterCompanyTransfer, self).create(vals_list)
        for rec in result:
            if rec.type == 'transfer':
                rec.name = self.env['ir.sequence'].next_by_code('inter.company.transfer')
            if rec.type == 'return':
                rec.name = self.env['ir.sequence'].next_by_code('return.inter.company.transfer')
        return result

    def process_order(self, order, rec, purchase=False):
        if purchase:
            order.with_context(skip_auto=True).button_confirm()
            order.picking_ids.filtered(
                lambda x: x.state != 'cancel' and x.state == 'assigned').with_context(
                skip_backorder=True).button_validate()
            order.action_create_invoice()
            bill = order.invoice_ids.filtered(lambda x: x.state not in ['posted', 'cancel'])
            bill.invoice_date = date.today()
            bill.action_post()
            rec.purchase_order_id = order.id
            rec.bill_id = bill.id
        else:
            order.with_context(skip_auto=True).action_confirm()
            order.picking_ids.filtered(
                lambda x: x.state != 'cancel' and x.state == 'assigned').with_context(
                skip_backorder=True).button_validate()
            invoice = order._create_invoices()
            invoice.action_post()
            rec.invoice_id = invoice.id
            rec.sale_order_id = order.id

    def get_company(self, rec, field_name):
        return self.env['res.company'].search([('intercompany_warehouse_id', '=', getattr(rec, field_name).id)])

    def action_process(self):
        for rec in self:
            if rec.type == 'transfer':
                if not rec.product_line_ids or sum(rec.product_line_ids.mapped('quantity')) == 0:
                    raise UserError(_("Please check your Product Detail before making a Inter company Transaction!"))
                # input value for company
                from_company = self.get_company(rec, 'from_warehouse_id')
                to_company = self.get_company(rec, 'to_warehouse_id')

                if rec.apply_type == 'purchase':
                    purchase_order = self.create_purchase_order_transaction(from_company, to_company)
                    self.process_order(purchase_order, rec, purchase=True)

                if rec.apply_type == 'sale':
                    if not rec.pricelist_id:
                        pricelist_id = self.env['product.pricelist'].search([
                            ('currency_id', '=', rec.currency_id.id),
                            ('company_id', '=', from_company.id)
                        ], limit=1)
                        if not pricelist_id:
                            raise UserError(_("Please define the pricelist with currency %s for create Sale Order") % rec.currency_id.name)
                        rec.pricelist_id = pricelist_id.id
                    sale_order = self.create_sale_order_transaction(from_company, to_company)
                    self.process_order(sale_order, rec)

                if rec.apply_type == 'sale_purchase':
                    # Working for Purchase Order
                    purchase_order = self.create_purchase_order_transaction(from_company, to_company)
                    self.process_order(purchase_order, rec, purchase=True)

                    # Working for Sale Order
                    if not rec.pricelist_id:
                        pricelist_id = self.env['product.pricelist'].search([
                            ('currency_id', '=', rec.currency_id.id),
                            ('company_id', '=', from_company.id)
                        ], limit=1)
                        if not pricelist_id:
                            raise UserError(_("Please define the pricelist with currency %s for create Sale Order") % rec.currency_id.name)
                        rec.pricelist_id = pricelist_id.id
                    sale_order = self.create_sale_order_transaction(from_company, to_company)
                    self.process_order(sale_order, rec)
            if rec.type == 'return':
                self.do_return()
            rec.state = 'process'

    def do_picking_return(self, order, type_picking=None):
        picking_ids = order.picking_ids.filtered(
            lambda x: x.state == 'done' and x.picking_type_id.code == type_picking)
        for pick in picking_ids:
            return_wizard = self.env['stock.return.picking'].with_context(active_id=pick.id, active_ids=pick.ids).create({
                'location_id': pick.location_id.id,
                'picking_id': pick.id,
            })
            return_wizard._compute_moves_locations()
            dict_return_picking = return_wizard.create_returns()
            picking_return = self.env['stock.picking'].browse(dict_return_picking['res_id'])
            picking_return.with_context(skip_backorder=True).button_validate()

    def do_credit_notes_move(self, order, type=None):
        invoice_ids = order.invoice_ids.filtered(lambda x: x.state == 'posted')
        for inv in invoice_ids:
            move_reversal = self.env['account.move.reversal'].with_context(active_model="account.move", active_ids=inv.ids).create({
                'date': date.today(),
                'reason': 'Reversal of %s' % inv.name,
                'journal_id': inv.journal_id.id,
            })
            reversal = move_reversal.refund_moves()

    def do_return(self):
        for rec in self:
            self.do_picking_return(rec.sale_order_id, type_picking='outgoing')
            self.do_picking_return(rec.purchase_order_id, type_picking='incoming')
            self.do_credit_notes_move(rec.sale_order_id)
            self.do_credit_notes_move(rec.purchase_order_id)
        return

    def create_sale_order_transaction(self, from_company, to_company):
        partner_sale = to_company.partner_id
        value = {
            'partner_id': partner_sale.id,
            'origin': self.sale_order_id.name,
            'currency_id': self.currency_id.id,
            'pricelist_id': self.pricelist_id.id,
            'company_id': from_company.id
        }
        sale_order = self.env['sale.order'].create(value)
        self.purchase_order_id.write({
            'partner_ref': sale_order.name,
            'origin': sale_order.name
        })
        if self.apply_type == 'sale':
            self.create_sale_order_line_transaction(sale_order, self.purchase_order_id.order_line)
        if self.apply_type == 'sale_purchase':
            self.create_sale_order_line_transaction(sale_order, self.product_line_ids)
        return sale_order

    def create_sale_order_line_transaction(self, sale_order, order_line):
        for line in order_line:
            value = {
                'product_id': line.product_id.id,
                'price_unit': line.price_unit,
                'order_id': sale_order.id
            }
            if self.apply_type == 'sale':
                value.update({
                    'product_uom_qty': line.product_qty,
                    'name': line.name,
                })
            else:
                value.update({
                    'product_uom_qty': line.quantity,
                    'name': line.product_id.display_name,
                })
            self.env['sale.order.line'].create(value)

    def create_purchase_order_transaction(self, from_company, to_company):
        partner_purchase = from_company.partner_id
        value = {
            'partner_id': partner_purchase.id,
            'partner_ref': self.sale_order_id.name,
            'origin': self.sale_order_id.name,
            'company_id': to_company.id
        }
        purchase_order = self.env['purchase.order'].create(value)
        if self.apply_type == 'purchase':
            self.create_purchase_order_line_transaction(purchase_order, self.sale_order_id.order_line)
        if self.apply_type == 'sale_purchase':
            self.create_purchase_order_line_transaction(purchase_order, self.product_line_ids)
        return purchase_order

    def create_purchase_order_line_transaction(self, purchase_order, order_line):
        for line in order_line:
            value = {
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'price_unit': line.price_unit,
                'order_id': purchase_order.id
            }
            if self.apply_type == 'purchase':
                value.update({
                    'product_qty': line.product_uom_qty
                })
            else:
                value.update({
                    'product_qty': line.quantity
                })
            self.env['purchase.order.line'].create(value)

    def create_return_inter_company_transfer(self, inter_transaction):
        value = {
            'type': 'return',
            'from_warehouse_id': inter_transaction.from_warehouse_id.id,
            'to_warehouse_id': inter_transaction.to_warehouse_id.id,
            'pricelist_id': inter_transaction.pricelist_id.id,
            'currency_id': inter_transaction.currency_id.id,
            'backorder_of_id': inter_transaction.id,
            'sale_order_id': inter_transaction.sale_order_id.id,
            'purchase_order_id': inter_transaction.purchase_order_id.id,
            'invoice_id': inter_transaction.invoice_id.id,
            'bill_id': inter_transaction.bill_id.id
        }
        return_transaction = self.env['inter.company.transfer'].create(value)
        return return_transaction

    def create_product_line_return_inter_company_transfer(self, return_transaction, product_line):
        for line in product_line:
            value_line = {
                'product_id': line.product_id.id,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'transfer_id': return_transaction.id
            }
            self.env['product.detail'].create(value_line)

    def action_return(self):
        for rec in self:
            return_transaction = self.create_return_inter_company_transfer(rec)
            self.create_product_line_return_inter_company_transfer(return_transaction, product_line=rec.product_line_ids)
            rec.state = 'return'
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Return Internal Company Transfer'),
                'res_model': 'inter.company.transfer',
                'view_mode': 'form',
                'view_id': self.env.ref('agInterCompanyTransactionTransfer.inter_company_transfer_return_form_view').id,
                'res_id': return_transaction.id
            }
            return action

    def action_view_sale_order(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.sale_order_id.ids)]
        }
        return action

    def action_view_inter_transaction_company(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Inter Company Transfer'),
            'res_model': 'inter.company.transfer',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.backorder_of_id.ids)]
        }
        return action

    def action_view_invoice(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_id.ids)]
        }
        return action

    def action_view_purchase_order(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.purchase_order_id.ids)]
        }
        return action

    def action_view_bill(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Bill'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.bill_id.ids)]
        }
        return action

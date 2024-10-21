from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ProductDetail(models.Model):
    _name = 'product.detail'
    _description = "Product Detail For Inter Company Transfer"

    transfer_id = fields.Many2one('inter.company.transfer')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Integer(string='Quantity')
    price_unit = fields.Float(string='Price')

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.lst_price
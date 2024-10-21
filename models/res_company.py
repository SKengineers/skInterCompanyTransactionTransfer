from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    intercompany_warehouse_id = fields.Many2one('stock.warehouse', string='Intercompany Warehouse')
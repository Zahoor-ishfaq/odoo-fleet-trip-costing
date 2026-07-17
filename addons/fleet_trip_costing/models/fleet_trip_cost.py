from odoo import fields, models


class FleetTripCostType(models.Model):
    _name = "fleet.trip.cost.type"
    _description = "Fleet Trip Cost Type"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    active = fields.Boolean(default=True)

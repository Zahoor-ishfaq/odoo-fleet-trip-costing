from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetTripCostType(models.Model):
    _name = "fleet.trip.cost.type"
    _description = "Fleet Trip Cost Type"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    active = fields.Boolean(default=True)


class FleetTripCost(models.Model):
    _name = "fleet.trip.cost"
    _description = "Fleet Trip Cost Line"

    trip_id = fields.Many2one(
        "fleet.trip", required=True, ondelete="cascade", index=True
    )
    cost_type_id = fields.Many2one("fleet.trip.cost.type", required=True)
    currency_id = fields.Many2one(
        related="trip_id.currency_id", store=True, readonly=True
    )
    amount = fields.Monetary(required=True)
    date = fields.Date(default=fields.Date.context_today)
    note = fields.Char()

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Cost amount must be strictly positive."))

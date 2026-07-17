"""Cost type master data and per-trip cost lines."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetTripCostType(models.Model):
    """Master list of cost categories usable on a trip cost line."""

    # pylint: disable=too-few-public-methods
    # Odoo models carry no explicit public methods beyond declarative
    # fields; CRUD behavior comes from the ORM base class.
    _name = "fleet.trip.cost.type"
    _description = "Fleet Trip Cost Type"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    active = fields.Boolean(default=True)


class FleetTripCost(models.Model):
    """A single cost entry (fuel, toll, ...) attached to a fleet.trip."""

    # pylint: disable=too-few-public-methods
    # Odoo models carry no explicit public methods beyond declarative
    # fields; CRUD behavior comes from the ORM base class.
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
        """Block zero or negative cost amounts."""
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Cost amount must be strictly positive."))

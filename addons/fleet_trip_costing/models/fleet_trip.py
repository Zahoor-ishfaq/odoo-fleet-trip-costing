from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetTrip(models.Model):
    _name = "fleet.trip"
    _description = "Fleet Trip"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc"

    name = fields.Char(default=lambda self: _("New"), readonly=True, copy=False)
    vehicle_id = fields.Many2one("fleet.vehicle", required=True, index=True)
    driver_id = fields.Many2one("res.partner")
    date_start = fields.Datetime()
    date_end = fields.Datetime()
    route_from = fields.Char()
    route_to = fields.Char()
    odometer_start = fields.Float()
    odometer_end = fields.Float()
    distance_km = fields.Float(compute="_compute_distance_km", store=True, readonly=False)
    is_return_empty = fields.Boolean()
    revenue = fields.Monetary()
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    notes = fields.Text()

    @api.depends("odometer_start", "odometer_end")
    def _compute_distance_km(self):
        for trip in self:
            if trip.odometer_start and trip.odometer_end:
                trip.distance_km = trip.odometer_end - trip.odometer_start
            else:
                trip.distance_km = trip.distance_km

    @api.onchange("vehicle_id")
    def _onchange_vehicle_id(self):
        for trip in self:
            if trip.vehicle_id.driver_id:
                trip.driver_id = trip.vehicle_id.driver_id

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for trip in self:
            if trip.date_start and trip.date_end and trip.date_end < trip.date_start:
                raise ValidationError(
                    _("Trip end date/time cannot be before the start date/time.")
                )

    @api.constrains("odometer_start", "odometer_end")
    def _check_odometer(self):
        for trip in self:
            if (
                trip.odometer_start
                and trip.odometer_end
                and trip.odometer_end < trip.odometer_start
            ):
                raise ValidationError(
                    _("End odometer reading cannot be before the start reading.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "fleet.trip"
                ) or _("New")
        return super().create(vals_list)

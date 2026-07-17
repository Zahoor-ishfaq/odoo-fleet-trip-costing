from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero


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
    cost_line_ids = fields.One2many("fleet.trip.cost", "trip_id")
    revenue = fields.Monetary()
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    total_cost = fields.Monetary(compute="_compute_total_cost", store=True)
    cost_per_km = fields.Float(compute="_compute_cost_per_km", store=True)
    margin = fields.Monetary(compute="_compute_margin", store=True)
    margin_pct = fields.Float(compute="_compute_margin", store=True)
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
            if trip.odometer_end:
                trip.distance_km = trip.odometer_end - trip.odometer_start
            else:
                trip.distance_km = trip.distance_km

    @api.depends("cost_line_ids.amount")
    def _compute_total_cost(self):
        for trip in self:
            trip.total_cost = sum(trip.cost_line_ids.mapped("amount"))

    @api.depends("total_cost", "distance_km")
    def _compute_cost_per_km(self):
        for trip in self:
            if float_is_zero(trip.distance_km, precision_digits=2):
                trip.cost_per_km = 0.0
            else:
                trip.cost_per_km = trip.total_cost / trip.distance_km

    @api.depends("revenue", "total_cost")
    def _compute_margin(self):
        for trip in self:
            trip.margin = trip.revenue - trip.total_cost
            if float_is_zero(trip.revenue, precision_digits=2):
                trip.margin_pct = 0.0
            else:
                trip.margin_pct = trip.margin / trip.revenue * 100

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
            if trip.odometer_end and trip.odometer_end < trip.odometer_start:
                raise ValidationError(
                    _("End odometer reading cannot be before the start reading.")
                )

    def action_start(self):
        if any(trip.state != "draft" for trip in self):
            raise UserError(_("Only draft trips can be started."))
        self.write({"state": "in_progress"})

    def action_done(self):
        if any(trip.state != "in_progress" for trip in self):
            raise UserError(_("Only trips in progress can be marked done."))
        self.write({"state": "done"})

    def action_cancel(self):
        if any(trip.state == "cancelled" for trip in self):
            raise UserError(_("Trip is already cancelled."))
        self.write({"state": "cancelled"})

    def action_draft(self):
        if any(trip.state != "cancelled" for trip in self):
            raise UserError(_("Only cancelled trips can be reset to draft."))
        self.write({"state": "draft"})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "fleet.trip"
                ) or _("New")
        return super().create(vals_list)

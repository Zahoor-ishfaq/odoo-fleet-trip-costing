import ast

from lxml import etree

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestFleetTrip(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Test Brand"})
        model = cls.env["fleet.vehicle.model"].create(
            {"name": "Test Model", "brand_id": brand.id}
        )
        cls.vehicle = cls.env["fleet.vehicle"].create({"model_id": model.id})
        cls.driver = cls.env["res.partner"].create({"name": "Test Driver"})
        cls.fuel = cls.env.ref("fleet_trip_costing.fleet_trip_cost_type_fuel")
        cls.toll = cls.env.ref("fleet_trip_costing.fleet_trip_cost_type_toll")
        cls.trip = cls.env["fleet.trip"].create(
            {"vehicle_id": cls.vehicle.id, "driver_id": cls.driver.id}
        )

    def test_01_sequence_name(self):
        self.assertRegex(self.trip.name, r"^TRIP/\d{4}/\d{5}$")

    def test_02_total_cost_recompute(self):
        trip = self.env["fleet.trip"].create(
            {
                "vehicle_id": self.vehicle.id,
                "cost_line_ids": [
                    (0, 0, {"cost_type_id": self.fuel.id, "amount": 100.0}),
                    (0, 0, {"cost_type_id": self.toll.id, "amount": 50.0}),
                ],
            }
        )
        self.assertEqual(trip.total_cost, 150.0)

        toll_line = trip.cost_line_ids.filtered(lambda l: l.cost_type_id == self.toll)
        toll_line.unlink()
        self.assertEqual(trip.total_cost, 100.0)

        trip.write(
            {"cost_line_ids": [(0, 0, {"cost_type_id": self.toll.id, "amount": 25.0})]}
        )
        self.assertEqual(trip.total_cost, 125.0)

    def test_03_distance_and_odometer_constraint(self):
        trip = self.env["fleet.trip"].create(
            {
                "vehicle_id": self.vehicle.id,
                "odometer_start": 1000.0,
                "odometer_end": 1250.0,
            }
        )
        self.assertEqual(trip.distance_km, 250.0)

        with self.assertRaises(ValidationError):
            self.env["fleet.trip"].create(
                {
                    "vehicle_id": self.vehicle.id,
                    "odometer_start": 500.0,
                    "odometer_end": 100.0,
                }
            )

    def test_04_cost_per_km_zero_distance_guard(self):
        trip = self.env["fleet.trip"].create(
            {
                "vehicle_id": self.vehicle.id,
                "cost_line_ids": [(0, 0, {"cost_type_id": self.fuel.id, "amount": 80.0})],
            }
        )
        self.assertEqual(trip.distance_km, 0.0)
        self.assertEqual(trip.cost_per_km, 0.0)

    def test_05_margin_math_including_zero_revenue(self):
        trip = self.env["fleet.trip"].create(
            {
                "vehicle_id": self.vehicle.id,
                "revenue": 500.0,
                "cost_line_ids": [
                    (0, 0, {"cost_type_id": self.fuel.id, "amount": 200.0})
                ],
            }
        )
        self.assertEqual(trip.margin, 300.0)
        self.assertEqual(trip.margin_pct, 60.0)

        trip_no_revenue = self.env["fleet.trip"].create(
            {
                "vehicle_id": self.vehicle.id,
                "cost_line_ids": [
                    (0, 0, {"cost_type_id": self.fuel.id, "amount": 50.0})
                ],
            }
        )
        self.assertEqual(trip_no_revenue.revenue, 0.0)
        self.assertEqual(trip_no_revenue.margin, -50.0)
        self.assertEqual(trip_no_revenue.margin_pct, 0.0)

    def test_06_state_flow_and_default_filter(self):
        trip = self.trip
        self.assertEqual(trip.state, "draft")

        with self.assertRaises(UserError):
            trip.action_done()
        with self.assertRaises(UserError):
            trip.action_draft()

        trip.action_start()
        self.assertEqual(trip.state, "in_progress")
        with self.assertRaises(UserError):
            trip.action_start()

        trip.action_done()
        self.assertEqual(trip.state, "done")
        with self.assertRaises(UserError):
            trip.action_done()

        trip.action_cancel()
        self.assertEqual(trip.state, "cancelled")
        with self.assertRaises(UserError):
            trip.action_cancel()

        # cancelled trips must be excluded from the search view's default filter
        search_view = self.env.ref("fleet_trip_costing.fleet_trip_view_search")
        arch = etree.fromstring(search_view.arch)
        filter_node = arch.xpath("//filter[@name='not_cancelled']")[0]
        domain = ast.literal_eval(filter_node.get("domain"))
        self.assertEqual(domain, [("state", "!=", "cancelled")])
        self.assertNotIn(trip, self.env["fleet.trip"].search(domain))

        action = self.env.ref("fleet_trip_costing.fleet_trip_action")
        action_context = safe_eval(action.context or "{}")
        self.assertEqual(action_context.get("search_default_not_cancelled"), 1)

        trip.action_draft()
        self.assertEqual(trip.state, "draft")

    def test_07_access_and_multi_company_rule(self):
        company_b = self.env["res.company"].create({"name": "Test Company B"})
        user = self.env["res.users"].create(
            {
                "name": "Fleet Trip Test User",
                "login": "fleet_trip_test_user",
                "groups_id": [
                    (6, 0, [self.env.ref("fleet_trip_costing.group_fleet_trip_user").id])
                ],
                "company_id": self.env.company.id,
                "company_ids": [(6, 0, [self.env.company.id])],
            }
        )

        trip = self.env["fleet.trip"].with_user(user).create(
            {"vehicle_id": self.vehicle.id}
        )
        self.assertEqual(trip.company_id, self.env.company)
        trip.write({"notes": "updated by user"})
        self.assertEqual(trip.notes, "updated by user")

        # Users cannot delete trips: unlink is Manager-only by design (see
        # ir.model.access.csv access_fleet_trip_user perm_unlink=0)
        with self.assertRaises(AccessError):
            trip.unlink()

        trip_company_b = self.env["fleet.trip"].create(
            {"vehicle_id": self.vehicle.id, "company_id": company_b.id}
        )
        with self.assertRaises(AccessError):
            self.env["fleet.trip"].with_user(user).browse(trip_company_b.id).read(
                ["name"]
            )
        self.assertNotIn(
            trip_company_b, self.env["fleet.trip"].with_user(user).search([])
        )

    def test_08_odometer_zero_start_regression(self):
        # Regression: 0.0 is falsy in Python but a legitimate odometer_start
        # value; must not be treated as "unset" (PROJECT_BLUEPRINT.md §6).
        trip = self.env["fleet.trip"].create(
            {
                "vehicle_id": self.vehicle.id,
                "odometer_start": 0.0,
                "odometer_end": 120.0,
            }
        )
        self.assertEqual(trip.distance_km, 120.0)

        trip.write({"odometer_start": 0.0, "odometer_end": 50.0})
        self.assertEqual(trip.distance_km, 50.0)

        with self.assertRaises(ValidationError):
            self.env["fleet.trip"].create(
                {
                    "vehicle_id": self.vehicle.id,
                    "odometer_start": 0.0,
                    "odometer_end": -5.0,
                }
            )

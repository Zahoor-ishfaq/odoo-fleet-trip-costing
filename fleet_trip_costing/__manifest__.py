# pylint: disable=missing-module-docstring,pointless-statement
# Odoo loads this file via ast.literal_eval(), which requires the file to
# contain exactly one bare expression -- no docstring or other statement
# can precede the dict literal.
{
    "name": "Fleet Trip Costing & Profitability",
    "summary": "Per-trip cost capture, cost/km, and margin analytics on Fleet",
    "version": "17.0.1.0.0",
    "category": "Human Resources/Fleet",
    "license": "LGPL-3",
    "author": "Zahoor Ishfaq",
    "website": "https://github.com/Zahoor-ishfaq/odoo-fleet-trip-costing",
    "depends": ["fleet"],
    "data": [
        "security/fleet_trip_security.xml",
        "security/ir.model.access.csv",
        "data/fleet_trip_sequence.xml",
        "data/fleet_trip_cost_type_data.xml",
        "views/fleet_trip_views.xml",
        "views/fleet_trip_menus.xml",
        "views/fleet_trip_analytics.xml",
    ],
    "images": ["static/description/thumbnail.png"],
    "application": False,
    "installable": True,
}

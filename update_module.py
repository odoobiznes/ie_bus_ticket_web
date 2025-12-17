#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, '/opt/odoo19')

import odoo
from odoo.tools import config

# Parse config
config.parse_config(['-c', '/etc/odoo19/odoo.conf', '-d', 'symcherabus'])

# Connect to database
db = odoo.sql_db.db_connect('symcherabus')
with db.cursor() as cr:
    # Create environment
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    
    # Find and update the module
    module = env['ir.module.module'].search([('name', '=', 'ie_bus_ticket_web')])
    if module:
        print(f"Module found: {module.name}, state: {module.state}")
        if module.state == 'installed':
            module.button_upgrade()
            print("Module upgrade initiated")
        elif module.state == 'to upgrade':
            print("Module already marked for upgrade")
        else:
            module.button_install()
            print("Module installation initiated")
    else:
        print("Module ie_bus_ticket_web not found")
    
    # Commit the transaction
    cr.commit()
    print("Transaction committed")

# -*- coding: utf-8 -*-

{
    "name": "Bus Ticket Web",
    "version": "19.0.1.0.2",
    "category": "Website/Website",
    "summary": "Modern, responsive bus ticket booking system",
    "description": """
        Modern Bus Booking System
        =========================

        A clean, modern, and responsive bus ticket booking system with:
        - Beautiful responsive design for web, tablet, and mobile
        - Simple 3-step booking process
        - Integrated payment flow with Odoo
        - QR code generation for tickets
        - Email confirmations and invoices

        Features:
        - Page 1: Route search with modern UI
        - Page 2: Search results with route selection
        - Page 3: Seat selection and passenger details
        - Integrated payment processing
        - Automatic invoice generation
        - QR code tickets
    """,
    "author": "IT Enterprise",
    "website": "https://www.it-enterprise.solutions",
    "depends": [
        'website',
        'website_sale',
        'ie_bus_ticket_admin',
        'account',
        'sale_management',
    ],
    "data": [
        # 'security/ir.model.access.csv',  # Moved to ie_bus_ticket_admin
        # 'data/sequence.xml',  # Moved to ie_bus_ticket_admin
        'data/email_templates.xml',
        'views/templates.xml',
        'views/jizdenky_views.xml',
        'data/website_pages.xml',
        'data/menu.xml',
        'report/report_registration.xml',
        'report/templates/ticket_report.xml',
        'report/templates/payment_confirmation_report.xml',
    ],
    # Assets temporarily disabled - causing compilation errors
    # 'assets': {
    #     'web.assets_frontend': [
    #         'ie_bus_ticket_web/static/src/css/modern_booking.css',
    #     ],
    # },
    "i18n": [
        'i18n/uk_UA.po',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

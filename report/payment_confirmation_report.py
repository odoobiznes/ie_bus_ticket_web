# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PaymentConfirmationReport(models.AbstractModel):
    _name = 'report.ie_bus_ticket_web.payment_confirmation_report'
    _description = 'Payment Confirmation Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['modern.bus.reservation'].browse(docids)
        payment_logs = self.env['monobank.payment.log'].search([
            ('reservation_id', 'in', docids)
        ])
        return {
            'doc_ids': docids,
            'doc_model': 'modern.bus.reservation',
            'docs': docs,
            'payment_logs': payment_logs,
            'data': data,
        }

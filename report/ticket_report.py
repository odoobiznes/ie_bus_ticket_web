# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.addons.base.models.ir_qweb import QWeb


class TicketReport(models.AbstractModel):
    _name = 'report.ie_bus_ticket_web.ticket_report'
    _description = 'Ticket Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['modern.bus.reservation'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'modern.bus.reservation',
            'docs': docs,
            'data': data,
        }

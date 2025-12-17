# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta
import qrcode
import io
import base64
import json
import logging

_logger = logging.getLogger(__name__)


class ModernBusReservation(models.Model):
    _name = 'modern.bus.reservation'
    _description = 'Modern Bus Reservation'
    _order = 'create_date desc'

    name = fields.Char('Reservation Number', required=True, default=lambda self: self._generate_reservation_number())
    route_id = fields.Many2one('ie.bus.search.result', 'Route', required=True)

    # Related fields for trip info
    trip_id = fields.Many2one(
        'ie.bus.trip', string='Linka',
        related='route_id.trip_id', store=True, readonly=True)
    trip_number = fields.Char(
        string='Číslo linky',
        related='route_id.trip_id.name', store=True, readonly=True)
    trip_date = fields.Date(
        string='Datum jízdy',
        related='route_id.trip_date', store=True, readonly=True)

    route_display = fields.Char(
        string='Linka', compute='_compute_route_display', store=True)

    status_icon = fields.Html(
        string='Stav', compute='_compute_status_icon')

    passenger_name = fields.Char('Passenger Name', required=True)
    passenger_email = fields.Char('Passenger Email', required=True)
    passenger_phone = fields.Char('Passenger Phone', required=True)
    seat_number = fields.Char('Seat Number', default='AUTO')
    selected_seats = fields.Char('Selected Seats')
    boarding_point = fields.Many2one('ie.bus.point', 'Boarding Point')
    dropping_point = fields.Many2one('ie.bus.point', 'Dropping Point')
    status = fields.Selection([
        ('reserved', 'Reserved'),
        ('paid', 'Paid'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired')
    ], default='reserved', required=True)

    reservation_date = fields.Datetime('Reservation Date', default=fields.Datetime.now)
    expires_at = fields.Datetime('Expires At', default=lambda self: fields.Datetime.now() + timedelta(hours=24))

    # Invoice details
    needs_invoice = fields.Boolean('Needs Invoice', default=False)
    invoice_company = fields.Char('Company Name')
    invoice_address = fields.Text('Address')
    invoice_tax_id = fields.Char('Tax ID')
    invoice_vat = fields.Char('VAT Number')

    # Payment
    sale_order_id = fields.Many2one('sale.order', 'Sale Order')
    
    # Computed fields for UI
    payment_info_html = fields.Html(
        string='Datum a čas nákupu', 
        compute='_compute_payment_info_html'
    )

    def _compute_payment_info_html(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            # Default to reservation/creation date
            date_val = rec.reservation_date or rec.create_date
            date_str = date_val.strftime('%d.%m.%Y %H:%M') if date_val else ""
            
            url = None
            
            # Try to find payment transaction first
            if rec.sale_order_id:
                # Check for transactions linked to the sale order
                txs = rec.sale_order_id.transaction_ids
                if txs:
                    last_tx = txs.sorted('create_date', reverse=True)[0]
                    url = f"{base_url}/web#id={last_tx.id}&model=payment.transaction&view_type=form"
                    if last_tx.create_date:
                        date_str = last_tx.create_date.strftime('%d.%m.%Y %H:%M')
                else:
                    # Fallback to sale order
                    url = f"{base_url}/web#id={rec.sale_order_id.id}&model=sale.order&view_type=form"
                    if rec.sale_order_id.date_order:
                        date_str = rec.sale_order_id.date_order.strftime('%d.%m.%Y %H:%M')
            
            if url:
                # Green link for paid, normal for others
                color = "green" if rec.status in ['paid', 'confirmed'] else "#004aad"
                rec.payment_info_html = f'<a href="{url}" target="_blank" style="color: {color}; font-weight: bold; text-decoration: underline;" onclick="event.stopPropagation();">{date_str}</a>'
            else:
                rec.payment_info_html = f'<span>{date_str}</span>'

    # QR Code
    qr_code = fields.Binary('QR Code', compute='_compute_qr_code')

    @api.model
    def _generate_reservation_number(self):
        return self.env['ir.sequence'].next_by_code('modern.bus.reservation') or 'RES-0001'

    def get_correct_price(self):
        self.ensure_one()
        from_point = self.boarding_point if self.boarding_point else self.route_id.bording_from
        to_point = self.dropping_point if self.dropping_point else self.route_id.to

        if not from_point or not to_point:
            return self.route_id.price

        route_mgmt = None
        if hasattr(self.route_id, 'route') and self.route_id.route:
            route_mgmt = self.route_id.route
        elif hasattr(self.route_id, 'trip_id') and self.route_id.trip_id and self.route_id.trip_id.route:
            route_mgmt = self.route_id.trip_id.route

        if not route_mgmt:
            route_mgmt = self.env['ie.route.management'].sudo().search([
                ('special_price_ids.bording_from', '=', from_point.id),
                ('special_price_ids.to', '=', to_point.id),
            ], limit=1)

        if not route_mgmt:
            return self.route_id.price

        return route_mgmt.get_price(from_point, to_point)

    @api.depends('route_id', 'trip_id', 'trip_number')
    def _compute_route_display(self):
        for record in self:
            parts = []
            # Add trip number if available
            if record.trip_id:
                parts.append(f'#{record.trip_id.id}')
            elif record.trip_number:
                parts.append(record.trip_number)
            # Add route name
            if record.route_id:
                parts.append(record.route_id.name or '')
            record.route_display = ' | '.join(parts) if parts else ''

    @api.depends('status')
    def _compute_status_icon(self):
        for record in self:
            if record.status in ('paid', 'confirmed'):
                # Green checkmark for paid
                record.status_icon = '<span style="color: #27ae60; font-size: 18px;" title="Zaplaceno">✓</span>'
            elif record.status == 'reserved':
                # Orange clock for reserved
                record.status_icon = '<span style="color: #f39c12; font-size: 18px;" title="Rezervováno">⏱</span>'
            elif record.status == 'cancelled':
                # Red X for cancelled
                record.status_icon = '<span style="color: #e74c3c; font-size: 18px;" title="Zrušeno">✗</span>'
            elif record.status == 'expired':
                # Gray for expired
                record.status_icon = '<span style="color: #95a5a6; font-size: 18px;" title="Vypršelo">⌛</span>'
            else:
                record.status_icon = ''

    @api.depends('name', 'route_id', 'passenger_name')
    def _compute_qr_code(self):
        for record in self:
            if record.name and record.route_id:
                qr_data = {
                    'reservation': record.name,
                    'route': '%s - %s' % (record.route_id.bording_from.name, record.route_id.to.name),
                    'passenger': record.passenger_name,
                    'date': record.route_id.trip_date.strftime('%d.%m.%Y'),
                    'time': record.route_id.trip_start_date,
                }
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(json.dumps(qr_data))
                qr.make(fit=True)
                img = qr.make_image(fill_color='black', back_color='white')
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                record.qr_code = base64.b64encode(buffer.getvalue())
            else:
                record.qr_code = False

    def action_cancel(self):
        self.write({'status': 'cancelled'})

    def action_pay(self):
        self.write({'status': 'paid'})

    def action_send_ticket(self):
        """Znovu poslat jízdenku emailem"""
        self.ensure_one()
        if not self.passenger_email:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chyba',
                    'message': 'Email cestujícího není vyplněn',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        try:
            # Vytvořit nebo najít email template
            template = self.env.ref('ie_bus_ticket_web.email_template_ticket_confirmation', raise_if_not_found=False)
            if not template:
                # Vytvořit jednoduchý email
                mail_values = {
                    'subject': f'Jízdenka {self.name}',
                    'body_html': self._generate_ticket_email_body(),
                    'email_to': self.passenger_email,
                    'email_from': self.env.user.email or 'noreply@example.com',
                }
                self.env['mail.mail'].sudo().create(mail_values).send()
            else:
                template.send_mail(self.id, force_send=True)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Úspěch',
                    'message': f'Jízdenka byla odeslána na {self.passenger_email}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error('Failed to send ticket email: %s', e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chyba',
                    'message': f'Chyba při odesílání emailu: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def action_download_ticket(self):
        """Stáhnout jízdenku jako PDF"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/report/pdf/ie_bus_ticket_web.ticket_report/{self.id}',
            'target': 'new',
        }
    def action_download_qr(self):
        """Stáhnout QR kód jako obrázek"""
        self.ensure_one()
        if not self.qr_code:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chyba',
                    'message': 'QR kód není k dispozici',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/image/modern.bus.reservation/{self.id}/qr_code',
            'target': 'new',
        }
    def action_download_invoice(self):
        """Stáhnout fakturu"""
        self.ensure_one()
        if not self.sale_order_id or not self.sale_order_id.invoice_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chyba',
                    'message': 'Faktura není k dispozici',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        invoice = self.sale_order_id.invoice_ids[0]
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/account.move/{invoice.id}/invoice_pdf',
            'target': 'new',
        }

    def action_download_payment_confirmation(self):
        """Stáhnout potvrzení o platbě"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/report/pdf/ie_bus_ticket_web.payment_confirmation_report/{self.id}',
            'target': 'new',
        }

    def action_show_payment_details(self):
        """Zobrazit údaje o platbě od banky"""
        self.ensure_one()
        payment_logs = self.env['payment.monobank.log'].search([
            ('reservation_id', '=', self.id)
        ])

        if not payment_logs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'Údaje o platbě od banky nejsou k dispozici',
                    'type': 'info',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Údaje o platbě',
            'res_model': 'payment.monobank.log',
            'domain': [('reservation_id', '=', self.id)],
            'view_mode': 'tree,form',
            'target': 'new',
        }

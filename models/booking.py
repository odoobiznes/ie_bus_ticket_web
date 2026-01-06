# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta
import qrcode
import io
import base64
import json
import logging

_logger = logging.getLogger(__name__)

# Email translations for multi-language support
EMAIL_TRANSLATIONS = {
    'uk': {
        'reservation_subject': '🎫 Бронювання {name} - SymcheraBUS',
        'reservation_title': '🚌 Ваше бронювання {name} створено!',
        'reservation_greeting': 'Шановний(а) {passenger},',
        'paid_subject': '✅ Квиток {name} - SymcheraBUS',
        'paid_title': '✅ Квиток {name} оплачено!',
        'paid_greeting': 'Шановний(а) {passenger}, дякуємо за оплату!',
        'boarding': 'Посадка',
        'dropping': 'Висадка',
        'seat': 'Місце',
        'price': 'Ціна',
        'payment_label': 'Оплата',
        'payment_warning': 'Бронювання має бути оплачене не пізніше ніж за 2 години до відправлення, або за домовленістю з водієм чи диспетчером - при посадці.',
        'pay_online': 'ОПЛАТИТИ ОНЛАЙН',
        'pay_online_comfort': 'Якщо Ви ще не оплатили, можете будь-коли зручно оплатити онлайн:',
        'driver': 'Водій',
        'dispatcher': 'Диспетчер',
        'contacts': 'Контакти',
        'new_reservation': 'Нове бронювання',
        'thank_you': 'Дякуємо, що обрали SymcheraBUS!',
        'ticket_download': 'Завантажити квиток',
        'new_booking': 'Нове бронювання',
        'route': 'Маршрут',
        'date': 'Дата',
        'admin_subject': '📋 Нове бронювання {name} - SymcheraBUS',
    },
    'cs': {
        'reservation_subject': '🎫 Rezervace {name} - SymcheraBUS',
        'reservation_title': '🚌 Vaše rezervace {name} byla vytvořena!',
        'reservation_greeting': 'Vážený(á) {passenger},',
        'paid_subject': '✅ Jízdenka {name} - SymcheraBUS',
        'paid_title': '✅ Jízdenka {name} zaplacena!',
        'paid_greeting': 'Vážený(á) {passenger}, děkujeme za platbu!',
        'boarding': 'Nástup',
        'dropping': 'Výstup',
        'seat': 'Sedadlo',
        'price': 'Cena',
        'payment_label': 'Platba',
        'payment_warning': 'Rezervace musí být zaplacena nejpozději 2 hodiny před odjezdem, nebo po domluvě s řidičem či dispečerem - při nástupu.',
        'pay_online': 'ZAPLATIT ONLINE',
        'pay_online_comfort': 'Pokud jste ještě nezaplatili, můžete kdykoliv pohodlně zaplatit online:',
        'driver': 'Řidič',
        'dispatcher': 'Dispečer',
        'contacts': 'Kontakty',
        'new_reservation': 'Nová rezervace',
        'thank_you': 'Děkujeme, že jste si vybrali SymcheraBUS!',
        'ticket_download': 'Stáhnout jízdenku',
        'new_booking': 'Nová rezervace',
        'route': 'Trasa',
        'date': 'Datum',
        'admin_subject': '📋 Nová rezervace {name} - SymcheraBUS',
    },
    'en': {
        'reservation_subject': '🎫 Reservation {name} - SymcheraBUS',
        'reservation_title': '🚌 Your reservation {name} has been created!',
        'reservation_greeting': 'Dear {passenger},',
        'paid_subject': '✅ Ticket {name} - SymcheraBUS',
        'paid_title': '✅ Ticket {name} paid!',
        'paid_greeting': 'Dear {passenger}, thank you for your payment!',
        'boarding': 'Boarding',
        'dropping': 'Drop-off',
        'seat': 'Seat',
        'price': 'Price',
        'payment_label': 'Payment',
        'payment_warning': 'Reservation must be paid at least 2 hours before departure, or by arrangement with the driver or dispatcher - at boarding.',
        'pay_online': 'PAY ONLINE',
        'pay_online_comfort': 'If you haven\'t paid yet, you can conveniently pay online anytime:',
        'driver': 'Driver',
        'dispatcher': 'Dispatcher',
        'contacts': 'Contacts',
        'new_reservation': 'New reservation',
        'thank_you': 'Thank you for choosing SymcheraBUS!',
        'ticket_download': 'Download ticket',
        'new_booking': 'New reservation',
        'route': 'Route',
        'date': 'Date',
        'admin_subject': '📋 New reservation {name} - SymcheraBUS',
    },
}

LANGUAGE_NAMES = {
    'uk': '🇺🇦 Українська',
    'cs': '🇨🇿 Čeština',
    'en': '🇬🇧 English',
}

ADMIN_EMAIL = 'symchera@email.cz'


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
    ], default='reserved', required=True, tracking=True)

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

    # Payment relations
    payment_transaction_ids = fields.One2many(
        'payment.transaction', compute='_compute_payment_transaction_ids',
        string='Platební transakce')
    payment_log_ids = fields.Many2many(
        'monobank.payment.log',
        string='Záznamy plateb z banky', compute='_compute_payment_log_ids')

    def _compute_payment_log_ids(self):
        """Compute payment logs - reservation_id is now Integer field."""
        for record in self:
            if 'monobank.payment.log' in self.env:
                logs = self.env['monobank.payment.log'].sudo().search([
                    ('reservation_id', '=', record.id)
                ])
                record.payment_log_ids = logs
            else:
                record.payment_log_ids = False

    # Invoice/Accounting relations
    invoice_id = fields.Many2one('account.move', string='Faktura',
        compute='_compute_invoice_id', store=True)
    payment_move_id = fields.Many2one('account.move', string='Příjmový doklad')

    # Payment computed fields (not stored to avoid dependency issues)
    payment_status = fields.Selection([
        ('not_paid', 'Nezaplaceno'),
        ('pending', 'Čeká na platbu'),
        ('paid', 'Zaplaceno'),
        ('partial', 'Částečně zaplaceno'),
        ('refunded', 'Vráceno'),
    ], string='Stav platby', compute='_compute_payment_status')

    payment_date = fields.Datetime(string='Datum platby',
        compute='_compute_payment_details')
    payment_amount = fields.Float(string='Částka platby',
        compute='_compute_payment_details')
    payment_reference = fields.Char(string='Reference z banky',
        compute='_compute_payment_details')
    payment_method = fields.Char(string='Způsob platby',
        compute='_compute_payment_details')

    # Payment info HTML for display
    payment_details_html = fields.Html(
        string='Podrobnosti platby',
        compute='_compute_payment_details_html')

    # Accounting HTML for display
    accounting_info_html = fields.Html(
        string='Účetnictví',
        compute='_compute_accounting_info_html')

    # Computed fields for UI
    payment_info_html = fields.Html(
        string='Datum a čas nákupu',
        compute='_compute_payment_info_html'
    )

    def _compute_payment_transaction_ids(self):
        """Get payment transactions for this reservation"""
        for rec in self:
            if rec.sale_order_id:
                rec.payment_transaction_ids = rec.sale_order_id.transaction_ids
            else:
                rec.payment_transaction_ids = False

    @api.depends('sale_order_id', 'sale_order_id.invoice_ids')
    def _compute_invoice_id(self):
        """Get invoice for this reservation"""
        for rec in self:
            if rec.sale_order_id and rec.sale_order_id.invoice_ids:
                rec.invoice_id = rec.sale_order_id.invoice_ids[0]
            else:
                rec.invoice_id = False

    @api.depends('status')
    def _compute_payment_status(self):
        """Compute payment status from MonoBank logs"""
        for rec in self:
            if rec.status in ('paid', 'confirmed'):
                rec.payment_status = 'paid'
            else:
                # Check payment logs
                payment_logs = self.env['monobank.payment.log'].sudo().search([
                    ('reservation_id', '=', rec.id)
                ])
                if payment_logs:
                    success_logs = payment_logs.filtered(lambda l: l.status == 'success')
                    if success_logs:
                        rec.payment_status = 'paid'
                    elif payment_logs.filtered(lambda l: l.status in ('processing', 'hold')):
                        rec.payment_status = 'pending'
                    elif payment_logs.filtered(lambda l: l.status == 'reversed'):
                        rec.payment_status = 'refunded'
                    else:
                        rec.payment_status = 'not_paid'
                else:
                    rec.payment_status = 'not_paid'

    def _compute_payment_details(self):
        """Compute payment details from successful MonoBank logs"""
        for rec in self:
            payment_logs = self.env['monobank.payment.log'].sudo().search([
                ('reservation_id', '=', rec.id)
            ])
            success_logs = payment_logs.filtered(lambda l: l.status == 'success')
            if success_logs:
                latest = success_logs.sorted('modified_date', reverse=True)[0]
                rec.payment_date = latest.modified_date
                rec.payment_amount = latest.amount
                rec.payment_reference = latest.invoice_id  # MonoBank invoice ID
                rec.payment_method = 'MonoBank'
            else:
                rec.payment_date = False
                rec.payment_amount = 0
                rec.payment_reference = False
                rec.payment_method = False

    def _compute_payment_details_html(self):
        """Generate HTML for payment details display"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            if rec.payment_status == 'paid' and rec.payment_log_ids:
                success_logs = rec.payment_log_ids.filtered(lambda l: l.status == 'success')
                if success_logs:
                    latest = success_logs.sorted('modified_date', reverse=True)[0]
                    date_str = latest.modified_date.strftime('%d.%m.%Y %H:%M') if latest.modified_date else ''
                    html = f'''
                    <div style="background: #d4edda; padding: 15px; border-radius: 8px; border: 1px solid #c3e6cb;">
                        <h4 style="color: #155724; margin-top: 0;">✅ Platba přijata</h4>
                        <table style="width: 100%; font-size: 13px;">
                            <tr><td style="padding: 4px 0;"><strong>Datum:</strong></td><td>{date_str}</td></tr>
                            <tr><td style="padding: 4px 0;"><strong>Částka:</strong></td><td><strong style="color: #28a745;">{latest.amount:.2f} {latest.currency or 'UAH'}</strong></td></tr>
                            <tr><td style="padding: 4px 0;"><strong>Reference:</strong></td><td>{latest.invoice_id or '-'}</td></tr>
                            <tr><td style="padding: 4px 0;"><strong>Způsob:</strong></td><td>MonoBank</td></tr>
                        </table>
                    </div>
                    '''
                    rec.payment_details_html = html
                else:
                    rec.payment_details_html = '<span style="color: #28a745;">✅ Zaplaceno</span>'
            elif rec.payment_status == 'pending':
                rec.payment_details_html = '''
                <div style="background: #fff3cd; padding: 15px; border-radius: 8px; border: 1px solid #ffc107;">
                    <h4 style="color: #856404; margin-top: 0;">⏳ Čeká na platbu</h4>
                    <p style="margin: 0;">Platba je ve zpracování...</p>
                </div>
                '''
            else:
                payment_url = rec._get_payment_url() if hasattr(rec, '_get_payment_url') else '#'
                rec.payment_details_html = f'''
                <div style="background: #f8d7da; padding: 15px; border-radius: 8px; border: 1px solid #f5c6cb;">
                    <h4 style="color: #721c24; margin-top: 0;">❌ Nezaplaceno</h4>
                    <p style="margin: 5px 0;">Rezervace čeká na platbu.</p>
                    <a href="{payment_url}" target="_blank" style="background: #28a745; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; display: inline-block; margin-top: 10px;">💳 Platební link</a>
                </div>
                '''

    def _compute_accounting_info_html(self):
        """Generate HTML for accounting info display"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            html_parts = []

            # Sale Order
            if rec.sale_order_id:
                so_url = f"{base_url}/web#id={rec.sale_order_id.id}&model=sale.order&view_type=form"
                so_state = dict(rec.sale_order_id._fields['state'].selection).get(rec.sale_order_id.state, rec.sale_order_id.state)
                html_parts.append(f'''
                <div style="margin-bottom: 10px;">
                    <strong>📦 Objednávka:</strong>
                    <a href="{so_url}" target="_blank" style="color: #004aad;">{rec.sale_order_id.name}</a>
                    <span style="background: #e9ecef; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 5px;">{so_state}</span>
                </div>
                ''')

            # Invoice
            if rec.invoice_id:
                inv_url = f"{base_url}/web#id={rec.invoice_id.id}&model=account.move&view_type=form"
                inv_state_label = dict(rec.invoice_id._fields['state'].selection).get(rec.invoice_id.state, rec.invoice_id.state)
                color = '#28a745' if rec.invoice_id.payment_state == 'paid' else '#ffc107'
                html_parts.append(f'''
                <div style="margin-bottom: 10px;">
                    <strong>📄 Faktura:</strong>
                    <a href="{inv_url}" target="_blank" style="color: #004aad;">{rec.invoice_id.name}</a>
                    <span style="background: {color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 5px;">{inv_state_label}</span>
                </div>
                ''')
            elif rec.sale_order_id and rec.status in ('paid', 'confirmed'):
                html_parts.append(f'''
                <div style="margin-bottom: 10px; color: #856404;">
                    <strong>📄 Faktura:</strong> Není vytvořena
                </div>
                ''')

            # Payment Move (receipt)
            if rec.payment_move_id:
                pm_url = f"{base_url}/web#id={rec.payment_move_id.id}&model=account.move&view_type=form"
                html_parts.append(f'''
                <div style="margin-bottom: 10px;">
                    <strong>🧾 Příjmový doklad:</strong>
                    <a href="{pm_url}" target="_blank" style="color: #004aad;">{rec.payment_move_id.name}</a>
                </div>
                ''')

            # Payment transactions
            if rec.sale_order_id and rec.sale_order_id.transaction_ids:
                tx_count = len(rec.sale_order_id.transaction_ids)
                done_count = len(rec.sale_order_id.transaction_ids.filtered(lambda t: t.state == 'done'))
                html_parts.append(f'''
                <div style="margin-bottom: 10px;">
                    <strong>💳 Platební transakce:</strong> {done_count}/{tx_count} úspěšných
                </div>
                ''')

            if html_parts:
                rec.accounting_info_html = f'''
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #e9ecef;">
                    {''.join(html_parts)}
                </div>
                '''
            else:
                rec.accounting_info_html = '<span style="color: #6c757d;">Žádné účetní záznamy</span>'

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

    def _generate_ticket_email_body(self):
        """Generate simple ticket email body"""
        self.ensure_one()
        boarding_name, boarding_time = self._get_boarding_info()
        dropping_name, _ = self._get_dropping_info()
        trip_date_str = self.trip_date.strftime('%d.%m.%Y') if self.trip_date else ''
        price = self.get_correct_price()
        seat_display = self.selected_seats or self.seat_number or 'AUTO'

        return f'''
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #ff8906;">🚌 Jízdenka {self.name}</h2>

            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <p><strong>Trasa:</strong> {boarding_name} → {dropping_name}</p>
                <p><strong>Datum:</strong> {trip_date_str} {boarding_time}</p>
                <p><strong>Místo:</strong> {seat_display}</p>
                <p><strong>Cena:</strong> {price:.0f} Kč</p>
                <p><strong>Cestující:</strong> {self.passenger_name}</p>
            </div>

            <p style="color: #666;">SymcheraBUS | symcherabus.eu</p>
        </div>
        '''

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
        payment_logs = self.env['monobank.payment.log'].search([
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
            'res_model': 'monobank.payment.log',
            'domain': [('reservation_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'new',
        }

    def action_send_payment_link(self):
        """Poslat platební link emailem"""
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
            payment_url = self._get_payment_url()
            lang = self._get_passenger_language()
            t = self._get_translations(lang)

            # Get trip info
            boarding_name, boarding_time = self._get_boarding_info()
            dropping_name, _ = self._get_dropping_info()
            trip_date_str = self.trip_date.strftime('%d.%m.%Y') if self.trip_date else ''
            price = self.get_correct_price()

            mail_values = {
                'subject': f'💳 Platební link - {self.name} - SymcheraBUS',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #ff8906;">💳 Platební link pro vaši rezervaci</h2>

                        <p>Šanovný(á) {self.passenger_name},</p>
                        <p>Zde je váš platební link pro rezervaci <strong>{self.name}</strong>:</p>

                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                            <p><strong>Trasa:</strong> {boarding_name} → {dropping_name}</p>
                            <p><strong>Datum:</strong> {trip_date_str} {boarding_time}</p>
                            <p><strong>Částka k úhradě:</strong> <span style="color: #28a745; font-size: 18px; font-weight: bold;">{price:.0f} UAH</span></p>
                        </div>

                        <div style="text-align: center; margin: 25px 0;">
                            <a href="{payment_url}" style="background: linear-gradient(135deg, #28a745, #20c997); color: white; padding: 15px 40px; text-decoration: none; border-radius: 25px; font-size: 18px; font-weight: bold; display: inline-block; box-shadow: 0 4px 15px rgba(40,167,69,0.3);">
                                💳 ZAPLATIT NYNÍ
                            </a>
                        </div>

                        <p style="color: #666; font-size: 12px; text-align: center;">
                            Link je platný 24 hodin od odeslání.
                        </p>

                        <hr style="margin: 20px 0;"/>
                        <p style="color: #666; font-size: 12px;">SymcheraBUS | symcherabus.eu</p>
                    </div>
                ''',
                'email_to': self.passenger_email,
                'email_from': 'tickets@mail.symcherabus.eu',
            }
            self.env['mail.mail'].sudo().create(mail_values).send()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Úspěch',
                    'message': f'Platební link byl odeslán na {self.passenger_email}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f'Failed to send payment link: {e}')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chyba',
                    'message': f'Chyba při odesílání: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def action_copy_payment_link(self):
        """Kopírovat platební link do schránky"""
        self.ensure_one()
        payment_url = self._get_payment_url()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Platební link',
                'message': f'Platební link: {payment_url}',
                'type': 'info',
                'sticky': True,
            }
        }

    def action_create_invoice(self):
        """Vytvořit fakturu z objednávky"""
        self.ensure_one()

        if not self.sale_order_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chyba',
                    'message': 'Není propojeno s objednávkou',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if self.invoice_id:
            # Show existing invoice
            return {
                'type': 'ir.actions.act_window',
                'name': 'Faktura',
                'res_model': 'account.move',
                'res_id': self.invoice_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        try:
            # Confirm sale order if not confirmed
            if self.sale_order_id.state in ('draft', 'sent'):
                self.sale_order_id.action_confirm()

            # Create invoice
            invoice = self.sale_order_id._create_invoices()
            if invoice:
                # Post invoice if paid
                if self.status in ('paid', 'confirmed'):
                    invoice.action_post()

                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Faktura',
                    'res_model': 'account.move',
                    'res_id': invoice.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
        except Exception as e:
            _logger.error(f'Failed to create invoice: {e}')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chyba',
                    'message': f'Chyba při vytváření faktury: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def action_view_sale_order(self):
        """Otevřít objednávku"""
        self.ensure_one()
        if not self.sale_order_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'Objednávka není k dispozici',
                    'type': 'info',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Objednávka',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_invoice(self):
        """Otevřít fakturu"""
        self.ensure_one()
        if not self.invoice_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'Faktura není k dispozici',
                    'type': 'info',
                    'sticky': False,
                }
            }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Faktura',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_payment_logs(self):
        """Zobrazit všechny záznamy plateb z MonoBank"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Záznamy plateb MonoBank',
            'res_model': 'monobank.payment.log',
            'domain': [('reservation_id', '=', self.id)],
            'view_mode': 'list,form',
            'target': 'current',
            'context': {'default_reservation_id': self.id},
        }

    def action_register_payment(self):
        """Registrovat manuální platbu a propojit s účetnictvím"""
        self.ensure_one()

        if not self.sale_order_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Chyba',
                    'message': 'Není propojeno s objednávkou',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Ensure invoice exists
        if not self.invoice_id:
            self.action_create_invoice()

        if self.invoice_id and self.invoice_id.state == 'draft':
            self.invoice_id.action_post()

        if self.invoice_id and self.invoice_id.payment_state != 'paid':
            return {
                'type': 'ir.actions.act_window',
                'name': 'Registrovat platbu',
                'res_model': 'account.payment.register',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'active_model': 'account.move',
                    'active_ids': [self.invoice_id.id],
                },
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Info',
                'message': 'Faktura je již zaplacena',
                'type': 'info',
                'sticky': False,
            }
        }

    # ========== Email Methods with Multi-Language Support ==========

    def _get_passenger_language(self):
        """Detect passenger language from phone number or email domain"""
        self.ensure_one()

        # Check phone number prefix
        phone = self.passenger_phone or ''
        if phone.startswith('+380') or phone.startswith('380'):
            return 'uk'
        elif phone.startswith('+420') or phone.startswith('420'):
            return 'cs'
        elif phone.startswith('+44') or phone.startswith('+1'):
            return 'en'

        # Check email domain
        email = self.passenger_email or ''
        if '.ua' in email:
            return 'uk'
        elif '.cz' in email:
            return 'cs'

        # Check for Cyrillic characters in name
        if self.passenger_name:
            for char in self.passenger_name:
                if '\u0400' <= char <= '\u04FF':
                    return 'uk'

        # Default to Ukrainian
        return 'uk'

    def _get_translations(self, lang=None):
        """Get translations for specified language"""
        if not lang:
            lang = self._get_passenger_language()
        return EMAIL_TRANSLATIONS.get(lang, EMAIL_TRANSLATIONS['uk'])

    def _get_payment_url(self):
        """Get URL for online payment"""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'https://symcherabus.eu')
        return f"{base_url}/bus-booking/pay?reservation_id={self.id}"

    def _get_language_switcher_html(self, email_type, current_lang):
        """Generate HTML for language switcher"""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'https://symcherabus.eu')

        available_langs = ['uk', 'cs', 'en']
        links = []

        for lang_code in available_langs:
            lang_name = LANGUAGE_NAMES.get(lang_code, lang_code.upper())
            url = f"{base_url}/bus/email/{email_type}/{self.id}?lang={lang_code}"

            if lang_code == current_lang:
                links.append(f'<strong>{lang_name}</strong>')
            else:
                links.append(f'<a href="{url}" style="color:#004aad;text-decoration:none;">{lang_name}</a>')

        return ' | '.join(links)

    def _get_contacts_html(self, t):
        """Generate HTML for contacts section"""
        dispatcher_phone = '+380673124850'
        dispatcher_email = 'symchera@email.cz'

        return f'''
            <div style="background: #f0fdf4; padding: 15px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #166534;">📞 {t['contacts']}</h4>
                <p><strong>{t['dispatcher']} - Symchera BUS:</strong><br/>
                📱 <a href="tel:{dispatcher_phone}" style="color:#004aad;font-weight:bold;">{dispatcher_phone}</a><br/>
                📧 <a href="mailto:{dispatcher_email}" style="color:#004aad;font-weight:bold;">{dispatcher_email}</a></p>
            </div>
        '''

    def _get_boarding_info(self):
        """Get boarding point info"""
        self.ensure_one()
        boarding_name = ''
        boarding_time = ''

        if self.boarding_point:
            boarding_name = self.boarding_point.name or ''
            # Try to get departure time from route
            if hasattr(self.route_id, 'trip_start_date') and self.route_id.trip_start_date:
                hours = int(self.route_id.trip_start_date)
                minutes = int((self.route_id.trip_start_date - hours) * 60)
                boarding_time = f"{hours:02d}:{minutes:02d}"
        elif self.route_id and self.route_id.bording_from:
            boarding_name = self.route_id.bording_from.name or ''
            if hasattr(self.route_id, 'trip_start_date') and self.route_id.trip_start_date:
                hours = int(self.route_id.trip_start_date)
                minutes = int((self.route_id.trip_start_date - hours) * 60)
                boarding_time = f"{hours:02d}:{minutes:02d}"

        return boarding_name, boarding_time

    def _get_dropping_info(self):
        """Get dropping point info"""
        self.ensure_one()
        dropping_name = ''
        dropping_time = ''

        if self.dropping_point:
            dropping_name = self.dropping_point.name or ''
        elif self.route_id and self.route_id.to:
            dropping_name = self.route_id.to.name or ''

        return dropping_name, dropping_time

    def _send_reservation_email(self):
        """Send reservation email to passenger with payment link"""
        self.ensure_one()
        if not self.passenger_email:
            _logger.warning(f"No email for reservation {self.name}")
            return False

        try:
            lang = self._get_passenger_language()
            t = self._get_translations(lang)

            payment_url = self._get_payment_url()
            lang_switcher = self._get_language_switcher_html('reservation', lang)
            contacts_html = self._get_contacts_html(t)

            # Get boarding/dropping info
            boarding_name, boarding_time = self._get_boarding_info()
            dropping_name, dropping_time = self._get_dropping_info()

            boarding_html = f"🚏 <strong>{t['boarding']}:</strong> {boarding_name or 'N/A'}"
            if boarding_time:
                boarding_html += f" <strong>({boarding_time})</strong>"

            dropping_html = f"🏁 <strong>{t['dropping']}:</strong> {dropping_name or 'N/A'}"
            if dropping_time:
                dropping_html += f" ({dropping_time})"

            # Date
            trip_date_str = self.trip_date.strftime('%d.%m.%Y') if self.trip_date else ''

            # Price
            price = self.get_correct_price()
            currency = 'Kč'

            # Seat
            seat_display = self.selected_seats or self.seat_number or 'AUTO'

            mail_values = {
                'subject': t['reservation_subject'].format(name=self.name),
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #22c55e;">✅ {t['reservation_title'].format(name=self.name)}</h2>

                        <p>{t['reservation_greeting'].format(passenger=self.passenger_name)}</p>

                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; border: 2px solid #e9ecef;">
                            <h3 style="margin-top: 0;">📋 {boarding_name} → {dropping_name}</h3>
                            <p style="font-size: 14px; color: #666;">📅 {trip_date_str} {boarding_time}</p>

                            <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                                <tr>
                                    <td style="text-align: left; padding: 8px 0; vertical-align: top;">{boarding_html}</td>
                                    <td style="text-align: right; padding: 8px 0; vertical-align: top;">{dropping_html}</td>
                                </tr>
                                <tr>
                                    <td style="text-align: left; padding: 5px 0;">🪑 <strong>{t['seat']}:</strong> {seat_display}</td>
                                    <td style="text-align: right; padding: 5px 0;">💰 <strong>{price:.0f} {currency}</strong></td>
                                </tr>
                            </table>
                        </div>

                        <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #f59e0b;">
                            <p style="margin: 0; color: #92400e;">
                                <strong>⚠️ {t['payment_label']}:</strong> {t['payment_warning']}
                            </p>
                        </div>

                        <div style="background: #e7f3ff; padding: 20px; border-radius: 8px; margin: 15px 0; text-align: center; border: 1px solid #b8daff;">
                            <p style="margin: 0 0 15px 0; color: #004085;">{t['pay_online_comfort']}</p>
                            <a href="{payment_url}" style="background: linear-gradient(135deg, #28a745, #20c997); color: white; padding: 15px 40px; text-decoration: none; border-radius: 25px; font-size: 18px; font-weight: bold; display: inline-block; box-shadow: 0 4px 15px rgba(40,167,69,0.3);">💳 {t['pay_online']}</a>
                        </div>

                        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;"/>

                        {contacts_html}

                        <div style="text-align: center; margin-top: 20px; padding: 10px; background: #f8f9fa; border-radius: 8px;">
                            <small style="color: #666;">🌐 {lang_switcher}</small>
                        </div>

                        <p style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
                            {t['thank_you']}
                        </p>
                    </div>
                ''',
                'email_to': self.passenger_email,
                'email_from': 'tickets@mail.symcherabus.eu',
            }
            self.env['mail.mail'].sudo().create(mail_values).send()
            _logger.info(f"Reservation email sent to {self.passenger_email} for {self.name}")
            return True
        except Exception as e:
            _logger.error(f"Error sending reservation email: {e}")
            return False

    def _send_admin_notification_email(self):
        """Send notification email to admin about new reservation"""
        self.ensure_one()

        try:
            t = EMAIL_TRANSLATIONS['cs']  # Admin email in Czech

            # Get boarding/dropping info
            boarding_name, boarding_time = self._get_boarding_info()
            dropping_name, dropping_time = self._get_dropping_info()

            # Date
            trip_date_str = self.trip_date.strftime('%d.%m.%Y') if self.trip_date else ''

            # Price
            price = self.get_correct_price()

            # Seat
            seat_display = self.selected_seats or self.seat_number or 'AUTO'

            mail_values = {
                'subject': t['admin_subject'].format(name=self.name),
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px;">
                        <h2 style="color: #004aad;">📋 {t['new_booking']} - {self.name}</h2>

                        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                            <h3 style="margin-top: 0;">📋 {t['route']}: {boarding_name} → {dropping_name}</h3>
                            <p><strong>{t['date']}:</strong> {trip_date_str} {boarding_time}</p>
                            <p><strong>{t['seat']}:</strong> {seat_display}</p>
                            <p><strong>{t['price']}:</strong> {price:.0f} Kč</p>
                        </div>

                        <div style="background: #e7f3ff; padding: 15px; border-radius: 8px; margin: 15px 0;">
                            <h4 style="margin-top: 0;">👤 Cestující:</h4>
                            <p><strong>Jméno:</strong> {self.passenger_name}</p>
                            <p><strong>Email:</strong> {self.passenger_email}</p>
                            <p><strong>Telefon:</strong> {self.passenger_phone}</p>
                        </div>

                        <p style="color: #666; font-size: 12px;">
                            Stav: <strong>{'Rezervováno' if self.status == 'reserved' else self.status}</strong>
                        </p>
                    </div>
                ''',
                'email_to': ADMIN_EMAIL,
                'email_from': 'tickets@mail.symcherabus.eu',
            }
            self.env['mail.mail'].sudo().create(mail_values).send()
            _logger.info(f"Admin notification email sent for {self.name}")
            return True
        except Exception as e:
            _logger.error(f"Error sending admin notification email: {e}")
            return False

    def _send_payment_confirmation_email(self):
        """Send email when payment is confirmed"""
        self.ensure_one()
        if not self.passenger_email:
            return False

        try:
            lang = self._get_passenger_language()
            t = self._get_translations(lang)

            lang_switcher = self._get_language_switcher_html('paid', lang)
            contacts_html = self._get_contacts_html(t)

            # Get boarding/dropping info
            boarding_name, boarding_time = self._get_boarding_info()
            dropping_name, dropping_time = self._get_dropping_info()

            boarding_html = f"🚏 <strong>{t['boarding']}:</strong> {boarding_name or 'N/A'}"
            if boarding_time:
                boarding_html += f" <strong>({boarding_time})</strong>"

            dropping_html = f"🏁 <strong>{t['dropping']}:</strong> {dropping_name or 'N/A'}"
            if dropping_time:
                dropping_html += f" ({dropping_time})"

            # Date
            trip_date_str = self.trip_date.strftime('%d.%m.%Y') if self.trip_date else ''

            # Price
            price = self.get_correct_price()
            currency = 'Kč'

            # Seat
            seat_display = self.selected_seats or self.seat_number or 'AUTO'

            # QR Code
            qr_img_html = ""
            if self.qr_code:
                qr_data = self.qr_code
                if isinstance(qr_data, bytes):
                    qr_data = qr_data.decode()
                qr_img_html = f'<img src="data:image/png;base64,{qr_data}" style="width:150px;height:150px;"/>'

            mail_values = {
                'subject': t['paid_subject'].format(name=self.name),
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #22c55e;">{t['paid_title'].format(name=self.name)}</h2>

                        <p>{t['paid_greeting'].format(passenger=self.passenger_name)}</p>

                        <div style="background: #f0fdf4; padding: 15px; border-radius: 8px; margin: 15px 0; border: 2px solid #22c55e;">
                            <h3 style="margin-top: 0;">🎫 {boarding_name} → {dropping_name}</h3>
                            <p style="font-size: 14px; color: #666;">📅 {trip_date_str} {boarding_time}</p>

                            <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                                <tr>
                                    <td style="text-align: left; padding: 8px 0; vertical-align: top;">{boarding_html}</td>
                                    <td style="text-align: right; padding: 8px 0; vertical-align: top;">{dropping_html}</td>
                                </tr>
                                <tr>
                                    <td style="text-align: left; padding: 5px 0;">🪑 <strong>{t['seat']}:</strong> {seat_display}</td>
                                    <td style="text-align: right; padding: 5px 0;">💰 <strong>{price:.0f} {currency}</strong></td>
                                </tr>
                            </table>

                            <div style="text-align: center; margin-top: 15px;">
                                {qr_img_html}
                                <p style="font-size: 12px; color: #666;">QR: {self.name}</p>
                            </div>
                        </div>

                        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;"/>

                        {contacts_html}

                        <div style="text-align: center; margin-top: 20px; padding: 10px; background: #f8f9fa; border-radius: 8px;">
                            <small style="color: #666;">🌐 {lang_switcher}</small>
                        </div>

                        <p style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
                            {t['thank_you']}
                        </p>
                    </div>
                ''',
                'email_to': self.passenger_email,
                'email_from': 'tickets@mail.symcherabus.eu',
            }
            self.env['mail.mail'].sudo().create(mail_values).send()
            _logger.info(f"Payment confirmation email sent to {self.passenger_email} for {self.name}")
            return True
        except Exception as e:
            _logger.error(f"Error sending payment confirmation email: {e}")
            return False

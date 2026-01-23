# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ChangeStatusWizard(models.TransientModel):
    _name = 'modern.bus.reservation.change.status.wizard'
    _description = 'Změna statusu rezervace'

    reservation_id = fields.Many2one(
        'modern.bus.reservation',
        string='Rezervace',
        required=True,
        default=lambda self: self.env.context.get('active_id')
    )
    current_status = fields.Selection(related='reservation_id.status', string='Aktuální status', readonly=True)
    new_status = fields.Selection([
        ('reserved', 'Rezervováno'),
        ('paid', 'Zaplaceno'),
        ('confirmed', 'Potvrzeno'),
        ('cancelled', 'Zrušeno'),
        ('expired', 'Vypršelo'),
    ], string='Nový status', required=True)
    reason = fields.Text('Důvod změny')

    def action_change_status(self):
        """Změnit status rezervace a odeslat příslušné notifikace a dokumenty"""
        self.ensure_one()
        if not self.reservation_id or not self.new_status:
            return {'type': 'ir.actions.act_window_close'}

        old_status = self.current_status
        reservation = self.reservation_id

        # Změnit status
        reservation.write({'status': self.new_status})

        # Log změny do chatter
        status_labels = dict(self._fields["new_status"].selection)
        old_label = status_labels.get(old_status, old_status)
        new_label = status_labels.get(self.new_status, self.new_status)

        log_message = f"📋 Status změněn: {old_label} → {new_label}"
        if self.reason:
            log_message += f"<br/>Důvod: {self.reason}"

        try:
            reservation.message_post(
                body=log_message,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        except Exception as e:
            _logger.warning(f"Could not post message: {e}")

        # === ODESLAT NOTIFIKACE A DOKUMENTY PODLE NOVÉHO STATUSU ===
        notifications_sent = []

        try:
            if reservation.passenger_email:
                if self.new_status == 'paid':
                    # Zaplaceno: Faktura + příjmový doklad + jízdenka s QR + email
                    self._process_paid_status(reservation)
                    notifications_sent.append('✅ Faktura + Jízdenka + QR + Email')

                elif self.new_status == 'confirmed':
                    # Potvrzeno: Stejné jako zaplaceno (jízdenka + QR)
                    self._process_confirmed_status(reservation)
                    notifications_sent.append('✅ Jízdenka + QR + Email')

                elif self.new_status == 'reserved':
                    # Rezervováno: Email s rezervací + platební link
                    self._process_reserved_status(reservation)
                    notifications_sent.append('📋 Rezervační email + platební link')

                elif self.new_status == 'cancelled':
                    # Zrušeno: Email o zrušení + storno faktury
                    self._process_cancelled_status(reservation, self.reason)
                    notifications_sent.append('❌ Storno email + Storno dokumenty')

                elif self.new_status == 'expired':
                    # Vypršelo: Email o vypršení
                    self._process_expired_status(reservation)
                    notifications_sent.append('⏰ Email o vypršení')

            # Upozornit administrátora
            self._notify_admin(reservation, old_status, self.new_status, self.reason)
            notifications_sent.append('📧 Admin notifikace')

        except Exception as e:
            _logger.error(f"Error sending notifications for {reservation.name}: {e}")
            notifications_sent.append(f'⚠️ Chyba: {str(e)[:50]}')

        # Sestavit zprávu o výsledku
        message = f'Status změněn na "{new_label}"'
        if notifications_sent:
            message += f'\n\nOdesláno:\n' + '\n'.join(notifications_sent)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Status změněn',
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def _process_paid_status(self, reservation):
        """Zpracovat změnu na status Zaplaceno - vytvořit fakturu, poslat jízdenku s QR"""
        _logger.info(f"Processing PAID status for {reservation.name}")

        # 1. Zajistit sale order a vytvořit fakturu
        try:
            if hasattr(reservation, '_ensure_sale_order'):
                reservation._ensure_sale_order()
            if hasattr(reservation, '_create_and_confirm_invoice'):
                reservation._create_and_confirm_invoice()
            elif hasattr(reservation, 'action_create_invoice'):
                reservation.action_create_invoice()
        except Exception as e:
            _logger.warning(f"Could not create invoice: {e}")

        # 2. Odeslat kompletní email s jízdenkou, fakturou a QR kódem
        if hasattr(reservation, '_send_payment_email_with_documents'):
            reservation._send_payment_email_with_documents()
        elif hasattr(reservation, '_send_simple_payment_email'):
            reservation._send_simple_payment_email()
        else:
            self._send_paid_email_fallback(reservation)

    def _process_confirmed_status(self, reservation):
        """Zpracovat změnu na status Potvrzeno - poslat jízdenku s QR"""
        _logger.info(f"Processing CONFIRMED status for {reservation.name}")

        # Odeslat email s jízdenkou a QR kódem (stejný jako paid)
        if hasattr(reservation, '_send_payment_email_with_documents'):
            reservation._send_payment_email_with_documents()
        elif hasattr(reservation, '_send_simple_payment_email'):
            reservation._send_simple_payment_email()
        else:
            self._send_paid_email_fallback(reservation)

    def _process_reserved_status(self, reservation):
        """Zpracovat změnu na status Rezervováno - poslat rezervační email s platebním linkem"""
        _logger.info(f"Processing RESERVED status for {reservation.name}")

        if hasattr(reservation, '_send_simple_reservation_email'):
            reservation._send_simple_reservation_email()
        elif hasattr(reservation, 'send_reservation_confirmation'):
            reservation.send_reservation_confirmation()
        else:
            self._send_reservation_email_fallback(reservation)

    def _process_cancelled_status(self, reservation, reason=None):
        """Zpracovat změnu na status Zrušeno - storno faktury + email"""
        _logger.info(f"Processing CANCELLED status for {reservation.name}")

        # 1. Provést účetní storno operace
        if hasattr(reservation, '_process_cancellation_accounting'):
            try:
                reservation._process_cancellation_accounting()
            except Exception as e:
                _logger.warning(f"Could not process cancellation accounting: {e}")

        # 2. Odeslat email o zrušení
        if hasattr(reservation, '_send_simple_cancellation_email'):
            reservation._send_simple_cancellation_email()
        else:
            self._send_cancellation_email_fallback(reservation, reason)

    def _process_expired_status(self, reservation):
        """Zpracovat změnu na status Vypršelo - poslat email o vypršení"""
        _logger.info(f"Processing EXPIRED status for {reservation.name}")

        self._send_expiration_email(reservation)

    def _send_paid_email_fallback(self, reservation):
        """Fallback - odeslat jednoduchý email o zaplacení"""
        details = reservation._get_trip_details() if hasattr(reservation, '_get_trip_details') else {}
        t = reservation._get_translations() if hasattr(reservation, '_get_translations') else {}

        # QR kód
        qr_html = ''
        if hasattr(reservation, '_get_qr_code_base64'):
            qr = reservation._get_qr_code_base64()
            if qr:
                qr_html = f'<div style="text-align: center; margin: 20px 0;"><img src="data:image/png;base64,{qr}" style="width: 180px; border-radius: 8px;"/><br/><small>{reservation.name}</small></div>'

        # Kontakty
        contacts_html = self._get_contacts_html()

        body = f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #22c55e;">✅ {t.get('paid_title', 'Platba přijata')} - {reservation.name}</h2>
                <p>{t.get('paid_greeting', 'Děkujeme za platbu!').format(passenger=reservation.passenger_name)}</p>

                <div style="background: #f0fdf4; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #22c55e;">
                    <h3 style="margin-top: 0;">📋 {details.get('route_name', '')}</h3>
                    <p>📅 {details.get('trip_date', '')} {details.get('boarding_time', '')}</p>
                    <p>🚏 <strong>Nástup:</strong> {details.get('boarding_stop', '') or details.get('boarding_city', '')} {f"({details.get('boarding_time', '')})" if details.get('boarding_time') else ''}</p>
                    {f"<small style='color:#666;'>{details.get('boarding_address', '')}</small>" if details.get('boarding_address') else ''}
                    <p>🏁 <strong>Výstup:</strong> {details.get('dropping_stop', '') or details.get('dropping_city', '')} {f"({details.get('dropping_time', '')})" if details.get('dropping_time') else ''}</p>
                    {f"<small style='color:#666;'>{details.get('dropping_address', '')}</small>" if details.get('dropping_address') else ''}
                    <p>🪑 <strong>Místo:</strong> {reservation.selected_seats or getattr(reservation, 'seat_number', '') or 'AUTO'}</p>
                    <p>💰 <strong>Cena:</strong> {details.get('price', 0):.0f} ₴ ✓</p>
                </div>

                {qr_html}

                <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0; color: #92400e;">
                        <strong>⚠️ Důležité:</strong><br/>
                        • Dostavte se na zastávku minimálně 15 minut před odjezdem<br/>
                        • Mějte u sebe doklad totožnosti<br/>
                        • Tento email slouží jako jízdenka
                    </p>
                </div>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;"/>

                {contacts_html}

                <p style="color: #666; font-size: 12px; text-align: center;">SymcheraBUS | symcherabus.eu</p>
            </div>
        '''

        self._send_email(reservation, f'✅ Jízdenka {reservation.name} - ZAPLACENO', body)

    def _send_reservation_email_fallback(self, reservation):
        """Fallback - odeslat jednoduchý rezervační email"""
        details = reservation._get_trip_details() if hasattr(reservation, '_get_trip_details') else {}
        payment_url = reservation._get_payment_url() if hasattr(reservation, '_get_payment_url') else ''

        contacts_html = self._get_contacts_html()

        payment_btn = ''
        if payment_url:
            payment_btn = f'''
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{payment_url}" style="background: #22c55e; color: white; padding: 15px 40px; text-decoration: none; border-radius: 25px; font-weight: bold; font-size: 16px;">💳 Zaplatit online</a>
                </div>
            '''

        body = f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #f59e0b;">📋 Rezervace {reservation.name}</h2>
                <p>Vážený/á {reservation.passenger_name}, Vaše rezervace byla úspěšně vytvořena.</p>

                <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #f59e0b;">
                    <h3 style="margin-top: 0;">📋 {details.get('route_name', '')}</h3>
                    <p>📅 {details.get('trip_date', '')} {details.get('boarding_time', '')}</p>
                    <p>🚏 <strong>Nástup:</strong> {details.get('boarding_stop', '') or details.get('boarding_city', '')} {f"({details.get('boarding_time', '')})" if details.get('boarding_time') else ''}</p>
                    {f"<small style='color:#666;'>{details.get('boarding_address', '')}</small>" if details.get('boarding_address') else ''}
                    <p>🏁 <strong>Výstup:</strong> {details.get('dropping_stop', '') or details.get('dropping_city', '')} {f"({details.get('dropping_time', '')})" if details.get('dropping_time') else ''}</p>
                    {f"<small style='color:#666;'>{details.get('dropping_address', '')}</small>" if details.get('dropping_address') else ''}
                    <p>🪑 <strong>Místo:</strong> {reservation.selected_seats or getattr(reservation, 'seat_number', '') or 'AUTO'}</p>
                    <p>💰 <strong>Cena:</strong> {details.get('price', 0):.0f} ₴</p>
                </div>

                <div style="background: #fee2e2; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0; color: #dc2626;">
                        <strong>⚠️ Platba:</strong> Rezervace musí být zaplacena nejpozději 2 hodiny před odjezdem, nebo po telefonické domluvě s řidičem či dispečerem - při nástupu.
                    </p>
                </div>

                {payment_btn}

                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;"/>

                {contacts_html}

                <p style="color: #666; font-size: 12px; text-align: center;">SymcheraBUS | symcherabus.eu</p>
            </div>
        '''

        self._send_email(reservation, f'📋 Rezervace {reservation.name}', body)

    def _send_cancellation_email_fallback(self, reservation, reason=None):
        """Fallback - odeslat jednoduchý email o zrušení"""
        details = reservation._get_trip_details() if hasattr(reservation, '_get_trip_details') else {}
        contacts_html = self._get_contacts_html()

        reason_text = f"<p><strong>Důvod:</strong> {reason}</p>" if reason else ""

        body = f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #dc3545;">❌ Rezervace {reservation.name} zrušena</h2>
                <p>Vážený/á {reservation.passenger_name}, Vaše rezervace byla zrušena.</p>

                <div style="background: #f8d7da; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p><strong>Trasa:</strong> {details.get('route_name', '')}</p>
                    <p><strong>Datum:</strong> {details.get('trip_date', '')}</p>
                    <p><strong>Místo:</strong> {reservation.selected_seats or getattr(reservation, 'seat_number', '') or 'AUTO'}</p>
                </div>

                {reason_text}

                <p>Pokud máte dotazy, kontaktujte nás.</p>

                <div style="text-align: center; margin: 20px 0;">
                    <a href="https://symcherabus.eu/bus-booking" style="background: #22c55e; color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold;">🎫 Nová rezervace</a>
                </div>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;"/>

                {contacts_html}

                <p style="color: #666; font-size: 12px; text-align: center;">SymcheraBUS | symcherabus.eu</p>
            </div>
        '''

        self._send_email(reservation, f'❌ Rezervace {reservation.name} zrušena', body)

    def _send_expiration_email(self, reservation):
        """Odeslat email o vypršení rezervace"""
        details = reservation._get_trip_details() if hasattr(reservation, '_get_trip_details') else {}
        contacts_html = self._get_contacts_html()

        body = f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #f59e0b;">⏰ Rezervace {reservation.name} vypršela</h2>
                <p>Vážený/á {reservation.passenger_name}, Vaše rezervace vypršela kvůli nezaplacení.</p>

                <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p><strong>Trasa:</strong> {details.get('route_name', '')}</p>
                    <p><strong>Datum:</strong> {details.get('trip_date', '')}</p>
                </div>

                <p>Pokud máte zájem, vytvořte novou rezervaci na našich stránkách.</p>

                <div style="text-align: center; margin: 20px 0;">
                    <a href="https://symcherabus.eu/bus-booking" style="background: #f59e0b; color: white; padding: 12px 30px; text-decoration: none; border-radius: 25px; font-weight: bold;">🎫 Nová rezervace</a>
                </div>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;"/>

                {contacts_html}

                <p style="color: #666; font-size: 12px; text-align: center;">SymcheraBUS | symcherabus.eu</p>
            </div>
        '''

        self._send_email(reservation, f'⏰ Rezervace {reservation.name} vypršela', body)

    def _notify_admin(self, reservation, old_status, new_status, reason=None):
        """Upozornit administrátora o změně statusu"""
        try:
            admin_email = self.env['ir.config_parameter'].sudo().get_param('bus_admin_email', 'admin@biznes.cz')

            status_labels = dict(self._fields["new_status"].selection)
            old_label = status_labels.get(old_status, old_status)
            new_label = status_labels.get(new_status, new_status)

            reason_text = f"<p><strong>Důvod:</strong> {reason}</p>" if reason else ""

            details = reservation._get_trip_details() if hasattr(reservation, '_get_trip_details') else {}

            body = f'''
                <div style="font-family: Arial, sans-serif;">
                    <h3>📋 Změna statusu rezervace</h3>
                    <table style="border-collapse: collapse; width: 100%;">
                        <tr><td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Rezervace:</strong></td><td style="padding: 5px; border-bottom: 1px solid #ddd;">{reservation.name}</td></tr>
                        <tr><td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Změna:</strong></td><td style="padding: 5px; border-bottom: 1px solid #ddd;">{old_label} → <strong>{new_label}</strong></td></tr>
                        <tr><td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Zákazník:</strong></td><td style="padding: 5px; border-bottom: 1px solid #ddd;">{reservation.passenger_name}</td></tr>
                        <tr><td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Email:</strong></td><td style="padding: 5px; border-bottom: 1px solid #ddd;">{reservation.passenger_email}</td></tr>
                        <tr><td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Telefon:</strong></td><td style="padding: 5px; border-bottom: 1px solid #ddd;">{reservation.passenger_phone}</td></tr>
                        <tr><td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Trasa:</strong></td><td style="padding: 5px; border-bottom: 1px solid #ddd;">{details.get('route_name', '')}</td></tr>
                        <tr><td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Datum:</strong></td><td style="padding: 5px; border-bottom: 1px solid #ddd;">{details.get('trip_date', '')}</td></tr>
                        <tr><td style="padding: 5px; border-bottom: 1px solid #ddd;"><strong>Změnil:</strong></td><td style="padding: 5px; border-bottom: 1px solid #ddd;">{self.env.user.name}</td></tr>
                    </table>
                    {reason_text}
                </div>
            '''

            mail_values = {
                'subject': f'📋 [{reservation.name}] Status: {old_label} → {new_label}',
                'body_html': body,
                'email_to': admin_email,
                'email_from': 'tickets@mail.symcherabus.eu',
            }
            self.env['mail.mail'].sudo().create(mail_values).send()
            _logger.info(f"Admin notification sent for {reservation.name}")
        except Exception as e:
            _logger.error(f"Error sending admin notification: {e}")

    def _get_contacts_html(self):
        """Generovat HTML pro kontakty"""
        return '''
            <div style="background: #f0fdf4; padding: 15px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #166534;">📞 Kontakty</h4>
                <p><strong>Dispečer - Symchera BUS:</strong><br/>
                📱 <a href="tel:+380673124850" style="color:#004aad;font-weight:bold;">+380673124850</a><br/>
                📱 <a href="tel:+420776359353" style="color:#004aad;font-weight:bold;">+420776359353</a><br/>
                📧 <a href="mailto:symchera@email.cz" style="color:#004aad;font-weight:bold;">symchera@email.cz</a></p>
            </div>
        '''

    def _send_email(self, reservation, subject, body):
        """Odeslat email"""
        if not reservation.passenger_email:
            return

        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_to': reservation.passenger_email,
            'email_from': 'tickets@mail.symcherabus.eu',
        }
        self.env['mail.mail'].sudo().create(mail_values).send()

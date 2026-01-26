from odoo import http, fields
from odoo.http import request
import datetime
import json
import logging
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

_logger = logging.getLogger(__name__)

# Prague timezone for all time calculations
PRAGUE_TZ = ZoneInfo('Europe/Prague')

def get_prague_now():
    """Get current datetime in Prague timezone (CET/CEST)"""
    return datetime.datetime.now(PRAGUE_TZ)

def get_prague_today():
    """Get current date in Prague timezone"""
    return get_prague_now().date()

def float_to_time(float_time):
    """Convert float time (e.g. 12.75) to HH:MM format (12:45)"""
    if isinstance(float_time, str):
        # Already in HH:MM format or similar
        return float_time
    if isinstance(float_time, (int, float)) and float_time:
        hours = int(float_time)
        minutes = int((float_time - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"
    return '08:00'  # Default time

class ModernBusBooking(http.Controller):

    def _auto_assign_seat(self, trip_id):
        """Získat další volné sedadlo pro trip - vrátí string např. 'AUTO-5A'"""
        try:
            trip = request.env['ie.bus.trip'].sudo().browse(trip_id)
            if not trip.exists():
                return 'AUTO-1'

            # Získat konfiguraci autobusu
            bus_type = trip.bus_id.fleet_type if trip.bus_id else None
            rows = bus_type.row_count if bus_type else 10
            cols = bus_type.col_count if bus_type else 4

            # Získat všechna obsazená sedadla
            occupied_seats = set()
            if 'modern.bus.reservation' in request.env:
                reservations = request.env['modern.bus.reservation'].sudo().search([
                    ('trip_id', '=', trip_id),
                    ('status', 'in', ['reserved', 'paid', 'confirmed'])
                ])
                # Fallback na route_id
                if not reservations and hasattr(trip, '_get_matching_search_result_ids'):
                    matching_sr_ids = trip._get_matching_search_result_ids()
                    if matching_sr_ids:
                        reservations = request.env['modern.bus.reservation'].sudo().search([
                            ('route_id', 'in', matching_sr_ids),
                            ('status', 'in', ['reserved', 'paid', 'confirmed'])
                        ])

                for res in reservations:
                    seats_str = res.selected_seats or res.seat_number or ''
                    for seat in seats_str.split(','):
                        seat = seat.strip()
                        if seat and seat != 'AUTO' and not seat.startswith('AUTO-'):
                            occupied_seats.add(seat)

            # Najít první volné sedadlo
            for row in range(1, rows + 1):
                for col in range(1, cols + 1):
                    seat_label = f"{row}{chr(64 + col)}"
                    if seat_label not in occupied_seats:
                        return f"AUTO-{seat_label}"

            return f"AUTO-{len(occupied_seats) + 1}"

        except Exception as e:
            _logger.warning(f"Error getting available seat: {e}")
            return 'AUTO-1'

    @http.route('/bus-booking-test', type='http', auth='public', website=True)
    def bus_booking_test(self, **kw):
        """Test page to check if updates work"""
        current_time = get_prague_now().strftime('%Y-%m-%d %H:%M:%S (Prague)')
        return f"""
        <html>
        <head><title>Test Page</title></head>
        <body style="font-family: Arial; padding: 20px; background: #f0f0f0;">
            <h1 style="color: #004aad;">🎯 ТЕСТ ОНОВЛЕННЯ ПРАЦЮЄ!</h1>
            <p style="font-size: 18px;">Час оновлення: <strong>{current_time}</strong></p>
            <p style="color: green;">✅ Якщо ви бачите цю сторінку - контролер працює!</p>
            <p><a href="/bus-booking-new" style="color: #004aad;">→ Нова версія сторінки</a></p>
            <p><a href="/bus-booking" style="color: #004aad;">← Стара версія сторінки</a></p>
        </body>
        </html>
        """

    @http.route('/bus-booking-new', type='http', auth='public', website=True)
    def bus_booking_new(self, **kw):
        """New booking page without cache issues"""
        import time

        today = get_prague_today().strftime('%d.%m.%y')
        today_iso = get_prague_today().strftime('%Y-%m-%d')
        current_time = get_prague_now().strftime('%H:%M:%S (Prague)')
        timestamp = str(int(time.time()))

        points = request.env['ie.bus.point'].sudo().search([])

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>🚀 Symchera BUS - Нова версія</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <style>
                body {{
                    margin: 0;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #004aad 0%, #003080 100%);
                    min-height: 100vh;
                    color: white;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 40px;
                }}
                .header h1 {{
                    font-size: 3rem;
                    margin-bottom: 10px;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                }}
                .header p {{
                    font-size: 1.2rem;
                    opacity: 0.9;
                }}
                .update-info {{
                    background: rgba(255,255,255,0.1);
                    padding: 10px;
                    border-radius: 8px;
                    margin: 20px 0;
                    text-align: center;
                }}
                .features {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin-top: 40px;
                }}
                .feature-card {{
                    background: rgba(255,255,255,0.1);
                    padding: 30px;
                    border-radius: 15px;
                    text-align: center;
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.2);
                }}
                .feature-icon {{
                    width: 80px;
                    height: 80px;
                    background: linear-gradient(135deg, #004aad 0%, #003080 100%);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 20px;
                    font-size: 2rem;
                    box-shadow: 0 10px 30px rgba(0, 74, 173, 0.3);
                }}
                .nav-links {{
                    text-align: center;
                    margin-top: 40px;
                }}
                .nav-links a {{
                    color: white;
                    text-decoration: none;
                    margin: 0 15px;
                    padding: 10px 20px;
                    background: rgba(255,255,255,0.2);
                    border-radius: 25px;
                    transition: all 0.3s ease;
                }}
                .nav-links a:hover {{
                    background: rgba(255,255,255,0.3);
                    transform: translateY(-2px);
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 Подорожуй з комфортом 🚀</h1>
                    <p>✨ Обирай Symchera BUS ✨</p>
                    <div class="update-info">
                        🔄 НОВА ВЕРСІЯ ПРАЦЮЄ! Час: {current_time} | Версія: {timestamp}
                    </div>
                </div>

                <div class="features">
                    <div class="feature-card">
                        <div class="feature-icon">🛋️</div>
                        <h3>Комфорт та зручність</h3>
                        <p>Сучасні автобуси з усіма умовами для приємної подорожі</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🛡️</div>
                        <h3>Надійність і безпека</h3>
                        <p>Досвідчені водії та регулярний технічний огляд транспорту</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">📱</div>
                        <h3>Онлайн-сервіси</h3>
                        <p>Швидке бронювання квитків, зручна оплата та електронні квитки</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">💰</div>
                        <h3>Доступні ціни</h3>
                        <p>Чесні тарифи без прихованих платежів</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🎧</div>
                        <h3>Підтримка 24/7</h3>
                        <p>Ми завжди на зв'язку з клієнтами</p>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">⏰</div>
                        <h3>Гнучкість розкладу</h3>
                        <p>Регулярні рейси для вашої зручності</p>
                    </div>
                </div>

                <div class="nav-links">
                    <a href="/bus-booking-test">🔧 Тестова сторінка</a>
                    <a href="/bus-booking">📄 Стара версія</a>
                    <a href="javascript:location.reload(true)">🔄 Оновити</a>
                </div>
            </div>

            <script>
                console.log('🎉 Нова версія завантажена успішно!');
                console.log('Час завантаження:', new Date().toLocaleTimeString());

                // Тест зміни кольорів іконок
                document.querySelectorAll('.feature-icon').forEach(function(icon, index) {{
                    icon.style.background = 'linear-gradient(135deg, #004aad 0%, #003080 100%)';
                    console.log('✅ Іконка', index + 1, 'оновлена на синій колір');
                }});
            </script>
        </body>
        </html>
        """

    @http.route('/bus-booking', type='http', auth='public', website=True)
    def bus_booking_page(self, **kw):
        """Main booking page with search form - uses Prague timezone"""
        today = get_prague_today().strftime('%d.%m.%y')
        today_iso = get_prague_today().strftime('%Y-%m-%d')
        points = request.env['ie.bus.point'].sudo().search([])

        # Check if user is admin
        is_admin = request.env.user.has_group('base.group_system')

        admin_trips = []
        total_sales = 0
        unpaid_count = 0
        unpaid_total = 0

        if is_admin:
            # Count unpaid reservations - simplified to avoid transaction issues
            try:
                # Simple count query that won't fail
                unpaid_count = request.env['modern.bus.reservation'].sudo().search_count([
                    ('status', '=', 'reserved')
                ])
                # Skip calculating total to avoid potential field access issues
                unpaid_total = 0
            except Exception as e:
                _logger.warning(f"Error counting unpaid reservations: {e}")
                unpaid_count = 0
                unpaid_total = 0

            # Get upcoming trips for admin view
            today_date = fields.Date.today()
            trips = request.env['ie.bus.trip'].sudo().search([
                ('trip_date', '>=', today_date)
            ], order='trip_date asc, route asc', limit=10)

            for trip in trips:
                # Get search results for this trip
                search_results = request.env['ie.bus.search.result'].sudo().search([
                    ('trip_id', '=', trip.id)
                ])

                # Calculate sold tickets and revenue
                sold_seats = 0
                trip_revenue = 0

                for result in search_results:
                    reservations = request.env['modern.bus.reservation'].sudo().search([
                        ('route_id', '=', result.id),
                        ('status', 'in', ['reserved', 'paid'])
                    ])

                    for res in reservations:
                        seats = len(res.selected_seats.split(',')) if res.selected_seats else 0
                        sold_seats += seats
                        if res.status == 'paid':
                            trip_revenue += result.price * seats

                admin_trips.append({
                    'id': trip.id,
                    'date': trip.trip_date,
                    'route_name': trip.route.name if trip.route else 'N/A',
                    'from': trip.route.baording_id.name if trip.route and trip.route.baording_id else 'N/A',
                    'to': trip.route.dropping_id.name if trip.route and trip.route.dropping_id else 'N/A',
                    'start_time': float_to_time(trip.route.str_time) if trip.route and trip.route.str_time else '08:00',
                    'total_seats': trip.total_seat,
                    'sold_seats': sold_seats,
                    'revenue': trip_revenue,
                })

                total_sales += trip_revenue

        # Add custom CSS for blue icons
        custom_css = """
        <style>
            /* FORCE BLUE ICONS - HIGHEST PRIORITY */
            .feature-icon.comfort,
            .feature-icon.safety,
            .feature-icon.online,
            .feature-icon.price,
            .feature-icon.support,
            .feature-icon.flexibility {
                background: linear-gradient(135deg, #004aad 0%, #003080 100%) !important;
                box-shadow: 0 10px 30px rgba(0, 74, 173, 0.3) !important;
            }
        </style>
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(function() {
                    document.querySelectorAll('.feature-icon').forEach(function(icon) {
                        icon.style.setProperty('background', 'linear-gradient(135deg, #004aad 0%, #003080 100%)', 'important');
                        icon.style.setProperty('box-shadow', '0 10px 30px rgba(0, 74, 173, 0.3)', 'important');
                    });
                }, 100);
            });
        </script>
        """

        # Add timestamp to force template reload
        import time
        template_version = str(int(time.time()))

        return request.render('ie_bus_ticket_web.bus_booking_search_template', {
            'points': points,
            'default_date': today,
            'default_date_iso': today_iso,
            'is_admin': is_admin,
            'admin_trips': admin_trips,
            'total_sales': total_sales,
            'unpaid_count': unpaid_count,
            'unpaid_total': unpaid_total,
            'custom_css': custom_css,
            'template_version': template_version,
            'current_timestamp': template_version,
        })

    @http.route('/bus-booking/get-destinations', type='json', auth='public', website=True, csrf=False)
    def get_destinations(self, start_point_id=None, **kw):
        """Get available destinations based on selected boarding point from Special Price"""
        _logger.info(f"=== GET DESTINATIONS: start_point_id={start_point_id}")

        if not start_point_id:
            # Return all points if no start point selected
            points = request.env['ie.bus.point'].sudo().search([])
            return [{'id': p.id, 'name': p.name} for p in points]

        try:
            start_point_id = int(start_point_id)
        except (ValueError, TypeError):
            return []

        # Find all destinations from Special Price that have this boarding point
        special_prices = request.env['ie.special.price'].sudo().search([
            ('bording_from', '=', start_point_id)
        ])

        # Get unique destination IDs
        destination_ids = list(set(special_prices.mapped('to').ids))

        if not destination_ids:
            _logger.warning(f"No destinations found for start_point_id={start_point_id}")
            # Fallback to all points except the start point
            points = request.env['ie.bus.point'].sudo().search([('id', '!=', start_point_id)])
            return [{'id': p.id, 'name': p.name} for p in points]

        # Get destination points
        destinations = request.env['ie.bus.point'].sudo().browse(destination_ids)
        _logger.info(f"Found {len(destinations)} destinations for start_point_id={start_point_id}")

        return [{'id': d.id, 'name': d.name} for d in destinations.sorted(key=lambda r: r.name)]

    @http.route('/bus-booking/upcoming-routes', type='json', auth='public', methods=['POST'], csrf=False)
    def get_upcoming_routes(self, start_point_id=None, **kw):
        """Get next 3 upcoming routes from a specific stop (hint for users)"""
        _logger.info(f"[UPCOMING] Called with start_point_id={start_point_id}")
        if not start_point_id:
            _logger.warning("[UPCOMING] No start_point_id provided")
            return []

        try:
            start_point_id = int(start_point_id)
        except (ValueError, TypeError):
            _logger.warning(f"[UPCOMING] Invalid start_point_id: {start_point_id}")
            return []

        now = get_prague_now()
        today = get_prague_today()
        _logger.info(f"[UPCOMING] Prague time: {now}, date: {today}")
        results = []

        # Get all routes that have this boarding point
        routes = request.env['ie.route.management'].sudo().search([])
        _logger.info(f"[UPCOMING] Found {len(routes)} total routes")

        for route in routes:
            try:
                # Find route_line for this boarding point
                boarding_line = route.route_line_ids.filtered(
                    lambda rl: rl.bording_from.id == start_point_id
                )
                if not boarding_line:
                    _logger.debug(f"[UPCOMING] Route {route.name}: no boarding line for point {start_point_id}")
                    continue

                start_time_float = boarding_line[0].start_times
                departure_hour = int(start_time_float)
                departure_minute = int((start_time_float - departure_hour) * 60)
                _logger.info(f"[UPCOMING] Route {route.name}: departure time {departure_hour:02d}:{departure_minute:02d}")

                # Check today and next 2 days
                for day_offset in range(3):
                    check_date = today + datetime.timedelta(days=day_offset)

                    # Check if route is active on this date
                    if not route.is_active_on_date(check_date):
                        _logger.debug(f"[UPCOMING] Route {route.name}: not active on {check_date}")
                        continue

                    # Check if date is blocked
                    try:
                        BlockedDates = request.env['ie.bus.blocked.dates'].sudo()
                        if BlockedDates.is_date_blocked(check_date, route.id):
                            _logger.debug(f"[UPCOMING] Route {route.name}: date {check_date} blocked")
                            continue
                    except:
                        pass

                    departure_datetime = datetime.datetime.combine(
                        check_date,
                        datetime.time(departure_hour, departure_minute),
                        tzinfo=PRAGUE_TZ
                    )

                    # Skip if already departed (with 5 min buffer)
                    if departure_datetime < now + datetime.timedelta(minutes=5):
                        _logger.debug(f"[UPCOMING] Route {route.name}: already departed ({departure_datetime} < {now})")
                        continue

                    # Get all destinations from this boarding point
                    sp_lines = route.special_price_ids.sudo().filtered(
                        lambda sp: sp.bording_from.id == start_point_id
                    )

                    destinations = []
                    for sp in sp_lines:
                        if sp.to:
                            destinations.append(sp.to.name)

                    if not destinations:
                        _logger.debug(f"[UPCOMING] Route {route.name}: no destinations from point {start_point_id}")
                        continue

                    _logger.info(f"[UPCOMING] Adding route {route.name} to {', '.join(destinations)}")
                    results.append({
                        'route_name': route.name,
                        'departure_time': f"{departure_hour:02d}:{departure_minute:02d}",
                        'departure_date': check_date.strftime('%d.%m.%Y'),
                        'destinations': ', '.join(set(destinations)[:3]),  # Max 3 destinations
                        'is_today': day_offset == 0,
                    })

            except Exception as e:
                _logger.warning(f"[UPCOMING] Error checking route {route.name}: {e}")
                continue

        # Sort by departure time and return first 3
        results.sort(key=lambda x: (x['departure_date'], x['departure_time']))
        return results[:3]

    @http.route('/bus-booking/search-routes', type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def search_routes(self, **kw):
        """Search for bus routes - if nothing selected, show next 5 departures"""
        _logger.info(f"=== SEARCH ROUTES: method={request.httprequest.method}, params={kw}")

        if request.httprequest.method == 'POST':
            start_point = kw.get('start_point')
            end_point = kw.get('end_point')  # Optional - can be empty
            travel_trip_date = kw.get('travel_date')

            _logger.info(f"=== SEARCH PARAMS: start={start_point}, end={end_point}, date={travel_trip_date}")

            # If no start_point selected, show next 5 upcoming departures
            if not start_point:
                _logger.info("=== NO START POINT - showing upcoming departures")
                routes = self._get_upcoming_departures(limit=5)
                return request.render('ie_bus_ticket_web.bus_booking_results_template', {
                    'routes': routes,
                    'next_route': None,
                    'search_params': {
                        'start_point': '',
                        'end_point': '',
                        'travel_trip_date': travel_trip_date or get_prague_today().strftime('%Y-%m-%d'),
                    },
                    'show_all_directions': True,  # Flag to show "All directions" header
                })

            # If no date, use today
            if not travel_trip_date:
                travel_trip_date = get_prague_today().strftime('%Y-%m-%d')

            routes = self._search_routes(start_point, end_point, travel_trip_date)
            _logger.info(f"=== FOUND ROUTES: {len(routes)} results")

            # If no routes found, find next available route
            next_route = None
            if not routes:
                next_route = self._find_next_available_route(start_point, end_point, travel_trip_date)
                if next_route:
                    _logger.info(f"=== NEXT AVAILABLE ROUTE: {next_route}")

            return request.render('ie_bus_ticket_web.bus_booking_results_template', {
                'routes': routes,
                'next_route': next_route,
                'search_params': {
                    'start_point': start_point,
                    'end_point': end_point or '',  # Can be empty
                    'travel_trip_date': travel_trip_date,
                }
            })

        # Handle GET request - redirect to main page
        _logger.warning("=== GET REQUEST - redirecting to main page")
        return request.redirect('/bus-booking')

    def _search_routes(self, start_point, end_point, travel_trip_date):
        """Search for available routes - end_point is optional (shows all routes from start_point)"""
        # Handle date format - can be either dd.mm.yy or yyyy-mm-dd
        try:
            if '-' in travel_trip_date:
                # HTML5 date input format: yyyy-mm-dd
                trip_date = datetime.datetime.strptime(travel_trip_date, '%Y-%m-%d').date()
                # Convert to display format for UI
                display_date = trip_date.strftime('%d.%m.%y')
            else:
                # Old format: dd.mm.yy
                day, month, year = travel_trip_date.split('.')
                year = '20' + year if len(year) == 2 else year
                formatted_trip_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                trip_date = datetime.datetime.strptime(formatted_trip_date, '%Y-%m-%d').date()
                display_date = travel_trip_date
        except Exception as e:
            _logger.error(f"Date parsing error: {e}")
            return []

        start_point_int = int(start_point)
        # end_point is optional - if not provided, show all routes from start_point
        end_point_int = int(end_point) if end_point else None

        # First, get all active routes
        routes = request.env['ie.route.management'].sudo().search([])
        result = []
        unique_routes = {}

        for route in routes:
            try:
                # Check if route is active on this date (day of week)
                if not route.is_active_on_date(trip_date):
                    _logger.info(f"[MBB] Skip {route.name}: not active on {trip_date}")
                    continue

                # Check if date is blocked (only if model exists)
                try:
                    BlockedDates = request.env['ie.bus.blocked.dates'].sudo()
                    if BlockedDates.is_date_blocked(trip_date, route.id):
                        _logger.info(f"[MBB] Skip {route.name}: date {trip_date} blocked")
                        continue
                except Exception as e:
                    _logger.warning(f"[MBB] Blocked dates check skipped: {e}")
                    # Continue without blocking check

            except Exception as e:
                _logger.error(f"[MBB] Error checking route {route.name}: {e}")
                continue

            try:
                # Get special prices for this boarding point
                if end_point_int:
                    # Specific destination - get only that combination
                    sp_lines = route.special_price_ids.sudo().filtered_domain([
                        ('bording_from', '=', start_point_int),
                        ('to', '=', end_point_int),
                    ])
                else:
                    # No destination specified - get ALL destinations from this boarding point
                    sp_lines = route.special_price_ids.sudo().filtered_domain([
                        ('bording_from', '=', start_point_int),
                    ])

                if not sp_lines:
                    _logger.info(f"[MBB] Skip {route.name}: no special price from {start_point_int}")
                    continue

                # Find route_line for boarding point (start) - REQUIRED
                boarding_route_line = route.route_line_ids.filtered(
                    lambda rl: rl.bording_from.id == start_point_int
                )
                if not boarding_route_line:
                    _logger.warning(f"[MBB] Skip {route.name}: no route_line found for boarding point {start_point_int}")
                    continue

                # Use start_times from the route_line where boarding happens (departure from selected stop)
                start_time_float = boarding_route_line[0].start_times
                _logger.info(f"[MBB] Using departure time from selected boarding stop: {start_time_float} (route_line: {boarding_route_line[0].id})")

                # Process each special price line (each destination from this boarding point)
                for sp_line in sp_lines:
                    current_end_point_int = sp_line.to.id

                    # Find route_line for dropping point (end)
                    dropping_route_line = route.route_line_ids.filtered(
                        lambda rl: rl.to.id == current_end_point_int
                    )
                    if dropping_route_line:
                        # Use end_times from the route_line where dropping happens
                        end_time_float = dropping_route_line[0].end_times
                        _logger.info(f"[MBB] Using arrival time for {sp_line.to.name}: {end_time_float}")
                    else:
                        # Fallback to route end_time if dropping route_line not found
                        end_time_float = getattr(route, 'end_time', 18.0) or 18.0
                        _logger.warning(f"[MBB] Using route end_time as fallback: {end_time_float}")

                    # Process this destination
                    route_result = self._process_route_destination(
                        route, sp_line, trip_date, start_point_int, current_end_point_int,
                        start_time_float, end_time_float, boarding_route_line[0]
                    )
                    if route_result:
                        if not end_point_int:
                            # Group by route and date to avoid duplicates
                            # Use route.id and trip_date as key
                            key = (route.id, trip_date)

                            should_replace = False
                            if key not in unique_routes:
                                should_replace = True
                            else:
                                existing = unique_routes[key]
                                # Check if current is final destination
                                if route.dropping_id and route_result.get('end_point_id') == route.dropping_id.id:
                                    should_replace = True
                                # If existing is NOT final, and current is more expensive (further)
                                elif (not (route.dropping_id and existing.get('end_point_id') == route.dropping_id.id) and
                                      route_result['price'] > existing['price']):
                                    should_replace = True

                            if should_replace:
                                unique_routes[key] = route_result
                        else:
                            result.append(route_result)

            except Exception as e:
                _logger.error(f"[MBB] Error processing route {route.name}: {e}")
                continue

        if not end_point_int:
            result = list(unique_routes.values())

        return result

    def _process_route_destination(self, route, sp_line, trip_date, start_point_int, end_point_int, start_time_float, end_time_float, boarding_route_line):
        """Process a single route-destination combination and return search result dict or None"""
        trip = None  # Initialize trip to avoid UnboundLocalError
        try:
            start_time = float_to_time(start_time_float)
            end_time = float_to_time(end_time_float)

            # Check if departure time from SELECTED STOP has passed (with 5-minute buffer for sales)
            # Get current time in Prague timezone (all times in system are in Prague/CET)
            now = get_prague_now()

            # Create departure datetime from SELECTED boarding stop (not route start)
            # All times are in Prague timezone
            departure_hour = int(start_time_float)
            departure_minute = int((start_time_float - departure_hour) * 60)
            departure_datetime = datetime.datetime.combine(
                trip_date,
                datetime.time(departure_hour, departure_minute),
                tzinfo=PRAGUE_TZ
            )

            # Stop sales 5 minutes before departure from selected stop
            sales_cutoff = departure_datetime - datetime.timedelta(minutes=5)

            # Check if we can still sell tickets (must be before departure from selected stop)
            if now > sales_cutoff:
                # Calculate how long ago sales ended
                time_diff = now - departure_datetime
                if time_diff.total_seconds() > 0:
                    hours_ago = int(time_diff.total_seconds() / 3600)
                    minutes_ago = int((time_diff.total_seconds() % 3600) / 60)
                    if hours_ago > 0:
                        _logger.info(f"[MBB] Skip {route.name} to {end_point_int}: departed {hours_ago}h {minutes_ago}m ago")
                    else:
                        _logger.info(f"[MBB] Skip {route.name} to {end_point_int}: departed {minutes_ago} minutes ago")
                else:
                    minutes_until = int((departure_datetime - now).total_seconds() / 60)
                    _logger.info(f"[MBB] Skip {route.name} to {end_point_int}: sales closed (departs in {minutes_until} min)")
                return None

            # Check if trip exists for this date
            trip = request.env['ie.bus.trip'].sudo().search([
                ('route', '=', route.id),
                ('trip_date', '=', trip_date)
            ], limit=1)

            # Create if it doesn't exist
            if not trip:
                _logger.info(f"[MBB] Creating trip for {route.name} on {trip_date}")
                try:
                    trip = request.env['ie.bus.trip'].sudo().create({
                        'route': route.id,
                        'trip_date': trip_date,
                        'bus_id': route.fleet_id.id if route.fleet_id else False,
                    })
                except Exception as e:
                    _logger.error(f"[MBB] Could not create trip: {e}")
                    # Pokus znovu načíst (možná někdo jiný vytvořil)
                    trip = request.env['ie.bus.trip'].sudo().search([
                        ('route', '=', route.id),
                        ('trip_date', '=', trip_date)
                    ], limit=1)

            # Pokud trip stále neexistuje, skip
            if not trip:
                _logger.warning(f"[MBB] No trip found/created for {route.name} on {trip_date}")
                return None

            # Check if sales are disabled for this trip
            if trip and getattr(trip, 'disable_sales', False):
                _logger.info(f"[MBB] Skip {route.name} on {trip_date}: sales disabled in trip settings")
                return None

            # Upsert search result for that start->end (must include route.id to avoid date mismatch!)
            search_result = request.env['ie.bus.search.result'].sudo().search([
                ('trip_date', '=', trip_date),
                ('bording_from', '=', start_point_int),
                ('to', '=', end_point_int),
                ('route', '=', route.id),  # Critical: match route to prevent wrong date
            ], limit=1)

            price_val = sp_line.price or 0.0

            if not search_result:
                trip_start_time = boarding_route_line.start_times
                trip_end_time = end_time_float

                search_result = request.env['ie.bus.search.result'].sudo().create({
                    'name': f"{route.name}_{trip_date}",
                    'trip_date': trip_date,
                    'trip_start_date': trip_start_time,
                    'trip_end_date': trip_end_time,
                    'price': price_val,
                    'bording_from': start_point_int,
                    'to': end_point_int,
                    'bus_id': getattr(trip, 'bus_id', False).id if getattr(trip, 'bus_id', False) else False,
                    'route': route.id,
                    'trip_id': trip.id if trip else False,
                })
                _logger.info(f"[MBB] Created search result {search_result.id} for {route.name}")
            else:
                update_vals = {}
                # Update trip_date if it doesn't match (critical for correct date display)
                if search_result.trip_date != trip_date:
                    update_vals['trip_date'] = trip_date
                if search_result.price != price_val:
                    update_vals['price'] = price_val
                if trip and not search_result.trip_id:
                    update_vals['trip_id'] = trip.id
                if route and not search_result.route:
                    update_vals['route'] = route.id
                # Update times
                trip_start_time = boarding_route_line.start_times
                trip_end_time = end_time_float
                if search_result.trip_start_date != trip_start_time:
                    update_vals['trip_start_date'] = trip_start_time
                if search_result.trip_end_date != trip_end_time:
                    update_vals['trip_end_date'] = trip_end_time
                if update_vals:
                    search_result.write(update_vals)
                    _logger.info(f"[MBB] Updated search result {search_result.id}: {update_vals}")

            # Get display date
            days_cz = ['Po', 'Út', 'St', 'Čt', 'Pá', 'So', 'Ne']
            day_name = days_cz[trip_date.weekday()]
            display_date = f"{trip_date.strftime('%d.%m.%y')} {day_name}"

            return {
                'id': search_result.id,
                'name': f"{route.name}",
                'price': search_result.price or price_val,
                'start_point': request.env['ie.bus.point'].sudo().browse(start_point_int).name,
                'start_point_id': start_point_int,
                'end_point': request.env['ie.bus.point'].sudo().browse(end_point_int).name,
                'end_point_id': end_point_int,
                'start_time': start_time,
                'end_time': end_time,
                'date': display_date,
                'available_seats': (trip.remaining_seats if trip else 50) or 50,
                'currency': 'UAH',
                'trip_id': trip.id if trip else None,
                'route_id': route.id,
            }

        except Exception as e:
            _logger.error(f"Error processing route {route.name} to {end_point_int}: {e}")
            return None

    def _find_next_available_route(self, start_point, end_point, original_date):
        """Find the next available route after the given date - end_point is optional"""
        try:
            # Parse original date
            if '-' in original_date:
                base_date = datetime.datetime.strptime(original_date, '%Y-%m-%d').date()
            else:
                day, month, year = original_date.split('.')
                year = '20' + year if len(year) == 2 else year
                base_date = datetime.datetime.strptime(f"{year}-{month.zfill(2)}-{day.zfill(2)}", '%Y-%m-%d').date()

            start_point_int = int(start_point)
            end_point_int = int(end_point) if end_point else None

            # Search up to 14 days ahead
            for days_ahead in range(1, 15):
                check_date = base_date + datetime.timedelta(days=days_ahead)
                check_date_str = check_date.strftime('%Y-%m-%d')

                # Try to find routes for this date
                routes = self._search_routes(start_point, end_point, check_date_str)
                if routes:
                    # Found available route!
                    next_route = routes[0]  # Take first available
                    _logger.info(f"[MBB] Found next available route on {check_date}: {next_route}")

                    # Get point names
                    start_point_name = request.env['ie.bus.point'].sudo().browse(start_point_int).name
                    end_point_name = next_route.get('end_point', '')
                    if not end_point_name and end_point_int:
                        end_point_name = request.env['ie.bus.point'].sudo().browse(end_point_int).name

                    return {
                        'id': next_route.get('id'),  # search_result ID for navigation
                        'date': check_date.strftime('%d.%m.%Y'),
                        'date_iso': check_date_str,
                        'start_point': start_point_name,
                        'end_point': end_point_name,
                        'start_time': next_route.get('start_time', ''),
                        'end_time': next_route.get('end_time', ''),
                        'price': next_route.get('price', 0),
                        'available_seats': next_route.get('available_seats', 0),
                        'route_id': next_route.get('route_id'),  # ie.route.management ID
                        'route_name': next_route.get('name', ''),
                    }

            _logger.info(f"[MBB] No routes found in next 14 days for {start_point} -> {end_point or 'any'}")
            return None

        except Exception as e:
            _logger.error(f"[MBB] Error finding next route: {e}")
            return None

    def _get_upcoming_departures(self, limit=5):
        """Get next upcoming departures from all routes (when user doesn't select anything)
        SIMPLIFIED VERSION - returns basic route info without creating search_results
        """
        _logger.warning(f"[MBB] _get_upcoming_departures called with limit={limit}")

        now = get_prague_now()
        today = get_prague_today()
        results = []

        # Get all routes
        try:
            routes = request.env['ie.route.management'].sudo().search([])
            _logger.warning(f"[MBB] Found {len(routes)} routes in database")
        except Exception as e:
            _logger.error(f"[MBB] Error getting routes: {e}")
            return results

        for route in routes:
            try:
                _logger.warning(f"[MBB] Processing route {route.id}: {route.name}")

                # Get route_line_ids
                route_lines = route.route_line_ids if route.route_line_ids else []
                _logger.warning(f"[MBB] Route {route.id} has {len(route_lines)} route_lines")

                if not route_lines:
                    continue

                # Sort by start_times and get first
                sorted_lines = sorted(route_lines, key=lambda l: l.start_times)
                first_line = sorted_lines[0]
                start_point = first_line.bording_from
                start_time_float = first_line.start_times

                _logger.warning(f"[MBB] First line start_point={start_point.name if start_point else 'None'}, time={start_time_float}")

                if not start_point:
                    continue

                # Get end point from route
                end_point = route.dropping_id
                end_time_float = 18.0  # Default end time

                # Check next 7 days for a valid departure
                for day_offset in range(7):
                    check_date = today + datetime.timedelta(days=day_offset)

                    # Calculate departure datetime
                    departure_hour = int(start_time_float)
                    departure_minute = int((start_time_float - departure_hour) * 60)
                    try:
                        departure_datetime = datetime.datetime.combine(
                            check_date,
                            datetime.time(departure_hour, departure_minute),
                            tzinfo=PRAGUE_TZ
                        )
                    except Exception as e:
                        _logger.warning(f"[MBB] Error creating departure time: {e}")
                        continue

                    # Skip if already departed
                    if departure_datetime < now + datetime.timedelta(minutes=5):
                        continue

                    # Get price
                    price = first_line.price if hasattr(first_line, 'price') else 0

                    # Format date
                    days_ua = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
                    day_name = days_ua[check_date.weekday()]
                    display_date = f"{check_date.strftime('%d.%m.%y')} {day_name}"

                    # Create or find search_result record (CRITICAL for correct navigation)
                    end_point_id = end_point.id if end_point else None
                    search_result = None
                    if end_point_id:
                        search_result = request.env['ie.bus.search.result'].sudo().search([
                            ('trip_date', '=', check_date),
                            ('bording_from', '=', start_point.id),
                            ('to', '=', end_point_id),
                            ('route', '=', route.id),
                        ], limit=1)

                        if not search_result:
                            # Create trip first if needed
                            trip = request.env['ie.bus.trip'].sudo().search([
                                ('route', '=', route.id),
                                ('trip_date', '=', check_date)
                            ], limit=1)
                            if not trip:
                                try:
                                    trip = request.env['ie.bus.trip'].sudo().create({
                                        'route': route.id,
                                        'trip_date': check_date,
                                        'bus_id': route.fleet_id.id if route.fleet_id else False,
                                    })
                                except Exception as e:
                                    _logger.warning(f"[MBB] Could not create trip: {e}")

                            # Create search_result
                            search_result = request.env['ie.bus.search.result'].sudo().create({
                                'name': f"{route.name}_{check_date}",
                                'trip_date': check_date,
                                'trip_start_date': start_time_float,
                                'trip_end_date': end_time_float,
                                'price': price,
                                'bording_from': start_point.id,
                                'to': end_point_id,
                                'bus_id': trip.bus_id.id if trip and trip.bus_id else False,
                                'route': route.id,
                                'trip_id': trip.id if trip else False,
                            })
                            _logger.info(f"[MBB] Created search_result {search_result.id} for upcoming departure")

                    # Use search_result.id or skip if no end_point
                    if not search_result:
                        _logger.warning(f"[MBB] Skipping {route.name} - no end_point or search_result")
                        continue

                    result = {
                        'id': search_result.id,  # CORRECT: Use search_result ID
                        'name': route.name,
                        'price': price,
                        'start_point': start_point.name,
                        'start_point_id': start_point.id,
                        'end_point': end_point.name if end_point else route.name,
                        'end_point_id': end_point_id,
                        'start_time': float_to_time(start_time_float),
                        'end_time': float_to_time(end_time_float),
                        'date': display_date,
                        'departure_datetime': departure_datetime,
                        'available_seats': (trip.remaining_seats if trip else 50) or 50,
                        'currency': 'UAH',
                        'trip_id': trip.id if trip else None,
                        'route_id': route.id,
                    }
                    results.append(result)
                    _logger.warning(f"[MBB] Added result: {result['name']} on {result['date']} (search_result_id={search_result.id})")
                    break  # Only one result per route

            except Exception as e:
                _logger.error(f"[MBB] Error processing route {route.id}: {e}")
                continue

        # Sort by departure time and return first N
        results.sort(key=lambda x: x['departure_datetime'])

        # Remove datetime object from results (not JSON serializable for template)
        for r in results:
            if 'departure_datetime' in r:
                del r['departure_datetime']

        _logger.warning(f"[MBB] Returning {len(results)} results")
        return results[:limit]

    def _create_trips_for_date(self, trip_date):
        """Automaticky vytvoří trips pro dané datum z dostupných tras"""
        # Nejdřív zkontrolujeme, jestli není datum úplně blokované
        BlockedDates = request.env['ie.bus.blocked.dates'].sudo()
        if BlockedDates.is_date_blocked(trip_date):
            _logger.info(f"=== Date {trip_date} is completely blocked (holiday/maintenance) ===")
            return 0

        # Získáme všechny aktivní trasy
        routes = request.env['ie.route.management'].sudo().search([])

        # Pro každou trasu vytvoříme trip, pokud neexistuje
        created_count = 0
        for route in routes:
            # Kontrola, zda trasa jede v tento den v týdnu
            if not route.is_active_on_date(trip_date):
                _logger.info(f"Route {route.name} is not active on {trip_date} (weekday check)")
                continue

            # Kontrola, zda není datum blokované pro tuto konkrétní trasu
            if BlockedDates.is_date_blocked(trip_date, route.id):
                _logger.info(f"Route {route.name} is blocked on {trip_date} (specific route block)")
                continue

            # Kontrola, zda už trip existuje
            existing_trip = request.env['ie.bus.trip'].sudo().search([
                ('route', '=', route.id),
                ('trip_date', '=', trip_date)
            ], limit=1)

            if not existing_trip:
                # Získáme autobus pro tuto trasu
                bus_id = None
                if route.fleet_id:
                    bus_id = route.fleet_id.id

                # Vytvoříme nový trip
                if bus_id:
                    new_trip = request.env['ie.bus.trip'].sudo().create({
                        'route': route.id,
                        'trip_date': trip_date,
                        'bus_id': bus_id,
                    })
                    created_count += 1
                    _logger.info(f"Created trip {new_trip.name} for route {route.name} on {trip_date}")

        _logger.info(f"=== Created {created_count} trips for date {trip_date} ===")
        return created_count

    @http.route('/bus-booking/get-passenger-info', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def get_passenger_info(self, **kw):
        """Get passenger info for a seat (admin only)"""
        # Check if user is admin
        if not request.env.user.has_group('base.group_system'):
            return {'error': 'Unauthorized'}

        route_id = kw.get('route_id')
        seat_id = kw.get('seat_id')

        if not route_id or not seat_id:
            return {'error': 'Missing parameters'}

        # Find reservation with this seat
        reservations = request.env['modern.bus.reservation'].sudo().search([
            ('route_id', '=', int(route_id)),
            ('status', 'in', ['reserved', 'paid'])
        ])

        for reservation in reservations:
            if seat_id in reservation.selected_seats.split(','):
                return {
                    'success': True,
                    'passenger_name': reservation.passenger_name,
                    'passenger_email': reservation.passenger_email,
                    'passenger_phone': reservation.passenger_phone,
                    'reservation_number': reservation.name,
                    'status': reservation.status
                }

        return {'error': 'No reservation found'}

    @http.route('/bus-booking/get-unpaid-reservations', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def get_unpaid_reservations(self, **kw):
        """Get list of unpaid reservations (admin only)"""
        # Check if user is admin
        if not request.env.user.has_group('base.group_system'):
            return {'error': 'Unauthorized'}

        # Get all unpaid reservations
        reservations = request.env['modern.bus.reservation'].sudo().search([
            ('status', '=', 'reserved')
        ], order='create_date desc')

        reservation_list = []
        for res in reservations:
            reservation_list.append({
                'id': res.id,
                'name': res.name,
                'passenger_name': res.passenger_name,
                'passenger_email': res.passenger_email,
                'passenger_phone': res.passenger_phone,
                'route': f"{res.route_id.bording_from.name if res.route_id.bording_from else ''} → {res.route_id.to.name if res.route_id.to else ''}",
                'date': res.route_id.trip_date.strftime('%d.%m.%Y') if res.route_id.trip_date else '',
                'seats': res.selected_seats,
                'price': res.get_correct_price() * len(res.selected_seats.split(',')) if res.selected_seats else 0,
                'created': res.create_date.strftime('%d.%m.%Y %H:%M') if res.create_date else '',
            })

        return {
            'success': True,
            'count': len(reservation_list),
            'reservations': reservation_list
        }

    @http.route('/bus-booking/book', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def book_ticket(self, **kw):
        """Show booking page for seat selection"""
        route_id = kw.get('route_id')

        if not route_id:
            return request.redirect('/bus-booking/search-routes')

        try:
            # Get route
            route = request.env['ie.bus.search.result'].sudo().browse(int(route_id))
            if not route.exists():
                return request.redirect('/bus-booking/search-routes')

            # CRITICAL: Validate trip_date is not in the past (allow today and future)
            today = get_prague_today()
            if route.trip_date and route.trip_date < today:
                _logger.warning(f"[MBB] Outdated search result {route_id} with date {route.trip_date} - redirecting to search")
                # Redirect to search with same parameters
                return request.redirect(f'/bus-booking?from_point={route.bording_from.id}&to_point={route.to.id}')

            # Get bus info from trip or fallback to route.bus_id
            trip = route.trip_id
            bus = trip.bus_id if trip else (route.bus_id if hasattr(route, 'bus_id') else False)

            # Get seat layout (normalize to safe JSON for JS)
            seat_data_raw = route.js_get_booked_seat_data() if hasattr(route, 'js_get_booked_seat_data') else {}
            seat_data_obj = {}
            try:
                if isinstance(seat_data_raw, str):
                    try:
                        seat_data_obj = json.loads(seat_data_raw)
                    except Exception:
                        # Attempt to fix single-quoted python-like dict representation
                        seat_data_obj = json.loads(seat_data_raw.replace("'", '"'))
                elif isinstance(seat_data_raw, dict):
                    seat_data_obj = seat_data_raw
                else:
                    seat_data_obj = {}
            except Exception:
                seat_data_obj = {}
            # Ensure expected keys exist
            if 'booked_seat' not in seat_data_obj:
                seat_data_obj['booked_seat'] = []
            seat_data_json = json.dumps(seat_data_obj)

            # Check if user is admin
            is_admin = request.env.user.has_group('base.group_system')

            # Get boarding and dropping points
            boarding_points = []
            dropping_points = []

            if route.bording_from:
                boarding_points.append({
                    'id': route.bording_from.id,
                    'name': route.bording_from.name
                })

            # Get available dropping points for this route
            # If search result has a route management linked, use it to find all destinations
            if route.route and route.bording_from:
                sp_lines = route.route.special_price_ids.sudo().filtered(
                    lambda sp: sp.bording_from.id == route.bording_from.id
                )
                for sp in sp_lines:
                    if sp.to:
                        # Calculate price if not set on sp_line (though it should be)
                        price = sp.price
                        if not price:
                            price = route.route.get_price(route.bording_from, sp.to)

                        dropping_points.append({
                            'id': sp.to.id,
                            'name': sp.to.name,
                            'price': price or 0.0
                        })

                # Sort by price (distance)
                dropping_points.sort(key=lambda x: x['price'])

            # Fallback if no special prices found (should not happen if search worked)
            if not dropping_points and route.to:
                dropping_points.append({
                    'id': route.to.id,
                    'name': route.to.name,
                    'price': route.price
                })

            # Get bus type info for seat layout
            bus_type = bus.fleet_type if bus and getattr(bus, 'fleet_type', False) else False

            # HARDCODED CONFIGURATION for symcherabus.eu
            # Change these values as needed for your bus configuration
            row_count = 15  # Number of rows in the bus
            col_count = 4   # Number of columns (seats per row)
            layout = '2-2'  # Seat layout pattern (2 seats - aisle - 2 seats)

            # Override with bus_type if it exists (for future use)
            if bus_type:
                row_count = getattr(bus_type, 'row_count', row_count) or row_count
                col_count = getattr(bus_type, 'col_count', col_count) or col_count
                layout = getattr(bus_type, 'layout', layout) or layout

            # Log for debugging
            _logger.info(f"[MBB] Bus seat config - bus_type: {bus_type}, rows: {row_count}, cols: {col_count}, layout: {layout}")

            # Calculate departure and arrival times from route search result
            _logger.info(f"[MBB] Route data - trip_start_date: {route.trip_start_date}, trip_end_date: {route.trip_end_date}")
            departure_time = float_to_time(route.trip_start_date) if route.trip_start_date else '—'
            arrival_time = float_to_time(route.trip_end_date) if route.trip_end_date else '—'
            _logger.info(f"[MBB] Times - departure: {departure_time}, arrival: {arrival_time}")

            # Get logged-in user data for form pre-fill
            user = request.env.user
            user_data = {
                'name': '',
                'email': '',
                'phone': '',
            }
            if user and not user._is_public():
                # User is logged in - get their data
                partner = user.partner_id
                if partner:
                    user_data['name'] = partner.name or ''
                    user_data['email'] = partner.email or ''
                    user_data['phone'] = partner.phone or partner.mobile or ''
                _logger.info(f"[MBB] Pre-filling form for user {user.name}: {user_data}")

            return request.render('ie_bus_ticket_web.bus_booking_book_template', {
                'route': route,
                'trip': trip,
                'bus': bus,
                'bus_type': bus_type,
                'row_count': row_count,
                'col_count': col_count,
                'layout': layout,
                'seat_data_json': seat_data_json,
                'price_per_seat': float(route.price or 0.0),
                'boarding_points': boarding_points,
                'dropping_points': dropping_points,
                'is_admin': is_admin,
                'departure_time': departure_time,
                'arrival_time': arrival_time,
                'user_data': user_data,
            })

        except Exception as e:
            _logger.error(f"Error in book_ticket: {e}")
            return request.redirect('/bus-booking/search-routes')

    # --- VERIFICATION API ENDPOINTS ---

    @http.route('/bus-booking/api/send-verification', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def send_verification_code(self, **kw):
        """Send verification code to email or phone"""
        try:
            contact = kw.get('contact', '').strip()
            if not contact:
                return {'success': False, 'error': 'Введіть контакт'}

            # Generate 6-digit code
            import random
            code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

            # Store code in session (expires in 10 minutes)
            request.session['verification_code'] = code
            request.session['verification_contact'] = contact
            request.session['verification_time'] = datetime.datetime.now().isoformat()

            is_email = '@' in contact

            if is_email:
                # Send email
                try:
                    mail_values = {
                        'subject': f'SymcheraBUS - Код підтвердження: {code}',
                        'body_html': f'''
                            <div style="font-family: Arial, sans-serif; max-width: 400px; margin: 0 auto; text-align: center;">
                                <h2 style="color: #004aad;">🔐 Код підтвердження</h2>
                                <p style="font-size: 14px; color: #666;">Ваш код для підтвердження контакту:</p>
                                <div style="background: #f0f0f0; padding: 20px; border-radius: 10px; margin: 20px 0;">
                                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #333;">{code}</span>
                                </div>
                                <p style="font-size: 12px; color: #999;">Код дійсний 10 хвилин</p>
                            </div>
                        ''',
                        'email_to': contact,
                        'email_from': 'tickets@mail.symcherabus.eu',
                    }
                    request.env['mail.mail'].sudo().create(mail_values).send()
                    _logger.info(f"[MBB] Verification code sent to {contact}")
                except Exception as e:
                    _logger.error(f"[MBB] Error sending verification email: {e}")
                    return {'success': False, 'error': 'Помилка надсилання email'}
            else:
                # For phone - just log (SMS integration could be added later)
                _logger.info(f"[MBB] Verification code for phone {contact}: {code}")
                # For now, we'll use the session-stored code

            return {'success': True, 'message': 'Код надіслано'}

        except Exception as e:
            _logger.error(f"[MBB] Error in send_verification_code: {e}")
            return {'success': False, 'error': str(e)}

    @http.route('/bus-booking/api/verify-code', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def verify_code(self, **kw):
        """Verify the code entered by user"""
        try:
            contact = kw.get('contact', '').strip()
            code = kw.get('code', '').strip()

            if not contact or not code:
                return {'success': False, 'error': 'Введіть код'}

            stored_code = request.session.get('verification_code')
            stored_contact = request.session.get('verification_contact')
            stored_time_str = request.session.get('verification_time')

            if not stored_code or not stored_contact:
                return {'success': False, 'error': 'Спочатку запросіть код'}

            # Check if code is still valid (10 minutes)
            if stored_time_str:
                stored_time = datetime.datetime.fromisoformat(stored_time_str)
                if (datetime.datetime.now() - stored_time).total_seconds() > 600:
                    return {'success': False, 'error': 'Код закінчився. Запросіть новий.'}

            if stored_contact != contact:
                return {'success': False, 'error': 'Контакт не співпадає'}

            if stored_code != code:
                return {'success': False, 'error': 'Невірний код'}

            # Code is valid - clear session
            request.session.pop('verification_code', None)
            request.session.pop('verification_contact', None)
            request.session.pop('verification_time', None)

            # Mark contact as verified in session
            request.session['verified_contact'] = contact

            _logger.info(f"[MBB] Contact verified: {contact}")
            return {'success': True, 'message': 'Контакт підтверджено'}

        except Exception as e:
            _logger.error(f"[MBB] Error in verify_code: {e}")
            return {'success': False, 'error': str(e)}

    @http.route('/bus-booking/reserve', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def reserve_seats(self, **kw):
        """Reserve selected seats"""
        try:
            route_id = int(kw.get('route_id'))
            selected_seats = kw.get('selected_seats', [])
            passenger_name = kw.get('passenger_name')
            passenger_email = kw.get('passenger_email')
            passenger_phone = kw.get('passenger_phone')
            boarding_point = kw.get('boarding_point')
            dropping_point = kw.get('dropping_point')

            # selected_seats není povinné - může být AUTO
            if not all([route_id, passenger_email, passenger_phone]):
                return {'success': False, 'message': 'Vyplňte všechna povinná pole (email, telefon)'}

            route = request.env['ie.bus.search.result'].sudo().browse(route_id)
            if not route.exists():
                return {'success': False, 'message': 'Neplatný spoj'}

            # Check if departure time from selected boarding point has passed (Prague timezone)
            now = get_prague_now()
            trip_date = route.trip_date
            trip_start_time = route.trip_start_date or 0

            if trip_date and trip_start_time:
                # Create departure datetime from selected boarding point (Prague timezone)
                departure_hour = int(trip_start_time)
                departure_minute = int((trip_start_time - departure_hour) * 60)
                departure_datetime = datetime.datetime.combine(
                    trip_date,
                    datetime.time(departure_hour, departure_minute),
                    tzinfo=PRAGUE_TZ
                )

                # Stop sales 5 minutes before departure from selected stop
                sales_cutoff = departure_datetime - datetime.timedelta(minutes=5)

                if now > sales_cutoff:
                    time_diff = now - departure_datetime
                    if time_diff.total_seconds() > 0:
                        hours_ago = int(time_diff.total_seconds() / 3600)
                        minutes_ago = int((time_diff.total_seconds() % 3600) / 60)
                        if hours_ago > 0:
                            return {'success': False, 'message': f'Autobus již odjel před {hours_ago} hodinami. Rezervace není možná.'}
                        else:
                            return {'success': False, 'message': f'Autobus již odjel před {minutes_ago} minutami. Rezervace není možná.'}
                    else:
                        minutes_until = int((departure_datetime - now).total_seconds() / 60)
                        return {'success': False, 'message': f'Rezervace není možná. Autobus odjíždí za {minutes_until} minut.'}

            # Create reservation
            # Convert seat IDs from "1_4" to "1D" format
            formatted_seats = []
            for seat in selected_seats:
                parts = seat.split('_')
                if len(parts) == 2:
                    row = parts[0]
                    col = int(parts[1])
                    formatted_seat = row + chr(64 + col)  # Convert to letter (A=1, B=2, etc.)
                    formatted_seats.append(formatted_seat)
                else:
                    formatted_seats.append(seat)  # Keep as is if already formatted

            # Automaticky přiřadit sedadlo pokud je prázdné
            if not formatted_seats or (len(formatted_seats) == 1 and formatted_seats[0] in ['', 'AUTO']):
                trip_id = route.trip_id.id if route.trip_id else None
                if trip_id:
                    assigned_seat = self._auto_assign_seat(trip_id)
                    formatted_seats = [assigned_seat]
                else:
                    formatted_seats = ['AUTO-1']

            reservation_vals = {
                'route_id': route_id,
                'passenger_name': passenger_name,
                'passenger_email': passenger_email,
                'passenger_phone': passenger_phone,
                'status': 'reserved',
                'selected_seats': ','.join(formatted_seats),
            }

            if boarding_point:
                reservation_vals['boarding_point'] = int(boarding_point)
            if dropping_point:
                reservation_vals['dropping_point'] = int(dropping_point)

            reservation = request.env['modern.bus.reservation'].sudo().create(reservation_vals)

            # Find or create trip for this route and link booked seats
            route_obj = request.env['ie.bus.search.result'].sudo().browse(route_id)
            trip = None

            if route_obj and route_obj.trip_date:
                # First check if trip_id is already set in search result
                if route_obj.trip_id:
                    trip = route_obj.trip_id
                    _logger.info(f"[MBB] Using existing trip {trip.id} from search result")
                else:
                    # Find existing trip for this date and route
                    route_management = route_obj.route

                    if route_management:
                        # Find trip by route and date
                        trip = request.env['ie.bus.trip'].sudo().search([
                            ('route', '=', route_management.id),
                            ('trip_date', '=', route_obj.trip_date),
                        ], limit=1)

                    # If trip doesn't exist, try to find by matching from/to points
                    if not trip and route_obj.bording_from and route_obj.to:
                        trips = request.env['ie.bus.trip'].sudo().search([
                            ('trip_date', '=', route_obj.trip_date),
                        ])
                        for t in trips:
                            if t.bording_from and route_obj.bording_from and t.bording_from.id == route_obj.bording_from.id:
                                if t.to and route_obj.to and t.to.id == route_obj.to.id:
                                    trip = t
                                    break

                    # If still no trip, try to create one
                    if not trip:
                        # Try to find route management by from/to points
                        if route_obj.bording_from and route_obj.to:
                            route_management = request.env['ie.route.management'].sudo().search([
                                ('baording_id', '=', route_obj.bording_from.id),
                                ('dropping_id', '=', route_obj.to.id),
                            ], limit=1)

                        if route_management:
                            bus_id = route_obj.bus_id.id if route_obj.bus_id else (route_management.fleet_id.id if route_management.fleet_id else False)
                            trip = request.env['ie.bus.trip'].sudo().create({
                                'route': route_management.id,
                                'trip_date': route_obj.trip_date,
                                'bus_id': bus_id,
                            })
                            # Link trip to search result
                            route_obj.write({'trip_id': trip.id})
                            _logger.info(f"[MBB] Created trip {trip.id} for reservation {reservation.name}")
                        else:
                            _logger.warning(f"[MBB] Could not find or create trip for reservation {reservation.name} - route management not found")

            # Mark seats as booked and link to trip
            for seat_id in selected_seats:
                seat_vals = {
                    'search_id': route_id,
                    'name': seat_id,
                    'seat_id': seat_id
                }
                if trip:
                    seat_vals['bus_id'] = trip.id
                request.env['bus.booked.seat'].sudo().create(seat_vals)

            # Send reservation emails (async to not block response)
            try:
                reservation._send_reservation_email()
                reservation._send_admin_notification_email()
                _logger.info(f"Reservation emails sent for {reservation.name}")
            except Exception as e:
                _logger.error(f"Failed to send reservation emails: {e}")
                # Don't fail the reservation if email fails

            return {
                'success': True,
                'reservation_id': reservation.id,
                'message': 'Sedadla byla úspěšně rezervována',
                'redirect_url': f'/bus-booking/confirmation/{reservation.id}'
            }

        except Exception as e:
            _logger.error(f"Error in reserve_seats: {e}")
            return {'success': False, 'message': str(e)}

    @http.route('/bus-booking/confirmation/<int:reservation_id>', type='http', auth='public', website=True)
    def show_confirmation(self, reservation_id, **kw):
        """Show reservation confirmation page"""
        try:
            reservation = request.env['modern.bus.reservation'].sudo().browse(reservation_id)
            if not reservation.exists():
                return request.redirect('/bus-booking')

            # Calculate expiry time
            now = get_prague_now()
            trip_date = reservation.route_id.trip_date
            trip_start_time = reservation.route_id.trip_start_date or 0

            # Get boarding/dropping info with times and addresses
            boarding_point = reservation.boarding_point if reservation.boarding_point else reservation.route_id.bording_from
            dropping_point = reservation.dropping_point if reservation.dropping_point else reservation.route_id.to

            boarding_point_name = boarding_point.name if boarding_point else ''
            boarding_address = ''
            boarding_time = ''
            dropping_point_name = dropping_point.name if dropping_point else ''
            dropping_address = ''
            dropping_time = ''

            # Get addresses from point_ids (sub-locations)
            if boarding_point and boarding_point.point_ids:
                boarding_address = ', '.join(boarding_point.point_ids.mapped('name'))
            if dropping_point and dropping_point.point_ids:
                dropping_address = ', '.join(dropping_point.point_ids.mapped('name'))

            # Get times from route lines
            if reservation.route_id and hasattr(reservation.route_id, 'route') and reservation.route_id.route:
                for line in reservation.route_id.route.route_line_ids:
                    if boarding_point and line.bording_from.id == boarding_point.id:
                        hours = int(line.start_times)
                        minutes = int((line.start_times - hours) * 60)
                        boarding_time = f"{hours:02d}:{minutes:02d}"
                    if dropping_point and line.to.id == dropping_point.id:
                        hours = int(line.end_times)
                        minutes = int((line.end_times - hours) * 60)
                        dropping_time = f"{hours:02d}:{minutes:02d}"

            # Fallback: use trip_start_date if no boarding_time found
            if not boarding_time and trip_start_time:
                hours = int(trip_start_time)
                minutes = int((trip_start_time - hours) * 60)
                boarding_time = f"{hours:02d}:{minutes:02d}"

            # Convert trip time to datetime (Prague timezone)
            hours = int(trip_start_time)
            minutes = int((trip_start_time - hours) * 60)
            trip_departure = datetime.datetime.combine(trip_date, datetime.time(hours, minutes), tzinfo=PRAGUE_TZ)

            # Set expiry to 3 hours before departure
            expiry_datetime = trip_departure - datetime.timedelta(hours=3)
            hours_until_departure = (trip_departure - now).total_seconds() / 3600

            # Calculate hours until expiry (3 hours before departure)
            if expiry_datetime > now:
                hours_until_expiry = (expiry_datetime - now).total_seconds() / 3600
            else:
                hours_until_expiry = 0  # Already expired

            expiry_time = expiry_datetime.strftime('%d.%m.%Y %H:%M')

            # Send confirmation email if not already sent
            self._send_reservation_email(reservation, hours_until_expiry, expiry_time)

            # Calculate correct price using Special Price (always in UAH)
            correct_price = reservation.get_correct_price()
            # Handle both selected_seats and seat_number (from dispatcher quick-sell)
            if reservation.selected_seats:
                seat_count = len(reservation.selected_seats.split(','))
            elif reservation.seat_number:
                seat_count = len(reservation.seat_number.split(','))
            else:
                seat_count = 1
            total_price = correct_price * seat_count

            return request.render('ie_bus_ticket_web.bus_booking_confirmation_template', {
                'reservation': reservation,
                'hours_until_expiry': int(hours_until_expiry),
                'expiry_time': expiry_time,
                'boarding_point_name': boarding_point_name,
                'boarding_address': boarding_address,
                'boarding_time': boarding_time,
                'dropping_point_name': dropping_point_name,
                'dropping_address': dropping_address,
                'dropping_time': dropping_time,
                'correct_price': correct_price,
                'total_price': total_price,
            })

        except Exception as e:
            _logger.error(f"Error in show_confirmation: {e}")
            return request.redirect('/bus-booking')

    @http.route('/bus-booking/back', type='http', auth='public', website=True)
    def back_to_booking(self, **kw):
        """Handle back button from checkout - return to seat selection or search"""
        route_id = request.session.get('bus_booking_route_id')

        if route_id:
            # Return to seat selection page
            return request.redirect(f'/bus-booking/book?route_id={route_id}')
        else:
            # Return to search page
            return request.redirect('/bus-booking')

    @http.route('/bus-booking/pay', type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def process_payment(self, **kw):
        """Zobrazit přehled informací před platbou"""
        _logger.info(f"=== PROCESS PAYMENT (CONFIRM PAGE): params={kw}")
        reservation_id = kw.get('reservation_id')

        if not reservation_id:
            _logger.warning("No reservation_id provided")
            return request.redirect('/bus-booking')

        try:
            reservation = request.env['modern.bus.reservation'].sudo().browse(int(reservation_id))
            if not reservation.exists():
                _logger.warning(f"Reservation {reservation_id} does not exist")
                return request.redirect('/bus-booking')

            # Check if already paid
            if reservation.status == 'paid':
                _logger.info(f"Reservation {reservation_id} is already paid, showing success page")
                return self.payment_success(reservation_id=reservation_id)

            # Připravit data pro zobrazení
            route = reservation.route_id

            # Boarding/Dropping info
            boarding_name = reservation.boarding_point.name if reservation.boarding_point else (route.bording_from.name if route and route.bording_from else '-')
            dropping_name = reservation.dropping_point.name if reservation.dropping_point else (route.to.name if route and route.to else '-')

            # Trip date
            trip_date = route.trip_date.strftime('%d.%m.%Y') if route and route.trip_date else '-'

            # Boarding time
            boarding_time = ''
            if route and route.trip_start_date:
                hours = int(route.trip_start_date)
                minutes = int((route.trip_start_date - hours) * 60)
                boarding_time = f"{hours:02d}:{minutes:02d}"

            # Seats
            seat_display = reservation.selected_seats or reservation.seat_number or 'AUTO'
            if reservation.selected_seats:
                seat_count = len(reservation.selected_seats.split(','))
            elif reservation.seat_number:
                seat_count = len(reservation.seat_number.split(','))
            else:
                seat_count = 1

            # Price
            price_per_seat = reservation.get_correct_price()
            total_amount = price_per_seat * seat_count

            # Affiliate info
            referral_code = getattr(reservation, 'referral_code', None) or ''
            banner_code = getattr(reservation, 'banner_code', None) or ''
            campaign_code = getattr(reservation, 'campaign_code', None) or ''

            # Fallback to Many2one relations
            if not referral_code and hasattr(reservation, 'affiliate_id') and reservation.affiliate_id:
                referral_code = reservation.affiliate_id.custom_code or reservation.affiliate_id.referral_code or ''
            if not banner_code and hasattr(reservation, 'affiliate_banner_id') and reservation.affiliate_banner_id:
                banner_code = reservation.affiliate_banner_id.code or ''
            if not campaign_code and hasattr(reservation, 'affiliate_campaign_id') and reservation.affiliate_campaign_id:
                campaign_code = reservation.affiliate_campaign_id.code or ''

            # Překlady pro stránku potvrzení platby
            user_lang = request.env.user.lang or 'uk_UA'
            lang_code = user_lang.split('_')[0] if user_lang else 'uk'
            
            translations = {
                'uk': {
                    'payment_confirmation': 'Підтвердження оплати',
                    'passenger': 'Пасажир',
                    'name': "Ім'я",
                    'email': 'Email',
                    'phone': 'Телефон',
                    'trip_details': 'Деталі поїздки',
                    'route': 'Маршрут',
                    'date': 'Дата',
                    'boarding': 'Посадка',
                    'seat': 'Місце',
                    'affiliate_info': 'Партнерська інформація',
                    'referral_code': 'Реферальний код',
                    'banner': 'Банер',
                    'campaign': 'Кампанія',
                    'price_per_seat': 'Ціна за місце',
                    'seat_count': 'Кількість місць',
                    'total_to_pay': 'До сплати',
                    'warning_monobank': 'Після натискання кнопки Ви будете перенаправлені на захищену сторінку оплати Monobank.',
                    'pay_btn': 'Оплатити',
                },
                'cs': {
                    'payment_confirmation': 'Potvrzení platby',
                    'passenger': 'Cestující',
                    'name': 'Jméno',
                    'email': 'Email',
                    'phone': 'Telefon',
                    'trip_details': 'Detaily cesty',
                    'route': 'Trasa',
                    'date': 'Datum',
                    'boarding': 'Nástup',
                    'seat': 'Sedadlo',
                    'affiliate_info': 'Partnerské informace',
                    'referral_code': 'Referenční kód',
                    'banner': 'Banner',
                    'campaign': 'Kampaň',
                    'price_per_seat': 'Cena za sedadlo',
                    'seat_count': 'Počet sedadel',
                    'total_to_pay': 'K úhradě',
                    'warning_monobank': 'Po kliknutí na tlačítko budete přesměrováni na zabezpečenou platební stránku Monobank.',
                    'pay_btn': 'Zaplatit',
                },
                'en': {
                    'payment_confirmation': 'Payment Confirmation',
                    'passenger': 'Passenger',
                    'name': 'Name',
                    'email': 'Email',
                    'phone': 'Phone',
                    'trip_details': 'Trip Details',
                    'route': 'Route',
                    'date': 'Date',
                    'boarding': 'Boarding',
                    'seat': 'Seat',
                    'affiliate_info': 'Affiliate Information',
                    'referral_code': 'Referral Code',
                    'banner': 'Banner',
                    'campaign': 'Campaign',
                    'price_per_seat': 'Price per seat',
                    'seat_count': 'Number of seats',
                    'total_to_pay': 'Total to pay',
                    'warning_monobank': 'After clicking the button you will be redirected to the secure Monobank payment page.',
                    'pay_btn': 'Pay',
                },
            }
            
            t = translations.get(lang_code, translations['uk'])

            return request.render('ie_bus_ticket_web.bus_booking_pay_confirm_template', {
                'reservation': reservation,
                'boarding_name': boarding_name,
                'dropping_name': dropping_name,
                'trip_date': trip_date,
                'boarding_time': boarding_time,
                'seat_display': seat_display,
                'seat_count': seat_count,
                'price_per_seat': int(price_per_seat),
                'total_amount': int(total_amount),
                'referral_code': referral_code,
                'banner_code': banner_code,
                'campaign_code': campaign_code,
                't': t,
                'lang_code': lang_code,
            })

        except Exception as e:
            _logger.error(f"Error showing payment confirm page: {e}", exc_info=True)
            return request.redirect('/bus-booking')

    @http.route('/bus-booking/pay-now', type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def process_payment_now(self, **kw):
        """Provést samotnou platbu - redirect na Monobank"""
        _logger.info(f"=== PROCESS PAYMENT NOW: params={kw}")
        reservation_id = kw.get('reservation_id')

        if not reservation_id:
            _logger.warning("No reservation_id provided")
            return request.redirect('/bus-booking')

        try:
            reservation = request.env['modern.bus.reservation'].sudo().browse(int(reservation_id))
            if not reservation.exists():
                _logger.warning(f"Reservation {reservation_id} does not exist")
                return request.redirect('/bus-booking')

            # Check if already paid
            if reservation.status == 'paid':
                _logger.info(f"Reservation {reservation_id} is already paid, showing success page")
                return self.payment_success(reservation_id=reservation_id)

            # Check if departure time from selected boarding point has passed (Prague timezone)
            now = get_prague_now()
            route = reservation.route_id
            if route:
                trip_date = route.trip_date
                trip_start_time = route.trip_start_date or 0

                if trip_date and trip_start_time:
                    # Create departure datetime from selected boarding point (Prague timezone)
                    departure_hour = int(trip_start_time)
                    departure_minute = int((trip_start_time - departure_hour) * 60)
                    departure_datetime = datetime.datetime.combine(
                        trip_date,
                        datetime.time(departure_hour, departure_minute),
                        tzinfo=PRAGUE_TZ
                    )

                    # Stop sales 5 minutes before departure from selected stop
                    sales_cutoff = departure_datetime - datetime.timedelta(minutes=5)

                    if now > sales_cutoff:
                        time_diff = now - departure_datetime
                        if time_diff.total_seconds() > 0:
                            hours_ago = int(time_diff.total_seconds() / 3600)
                            minutes_ago = int((time_diff.total_seconds() % 3600) / 60)
                            if hours_ago > 0:
                                _logger.warning(f"Reservation {reservation_id}: bus departed {hours_ago}h {minutes_ago}m ago")
                                return request.redirect(f'/bus-booking/confirmation/{reservation_id}?error=departed')
                            else:
                                _logger.warning(f"Reservation {reservation_id}: bus departed {minutes_ago} minutes ago")
                                return request.redirect(f'/bus-booking/confirmation/{reservation_id}?error=departed')
                        else:
                            minutes_until = int((departure_datetime - now).total_seconds() / 60)
                            _logger.warning(f"Reservation {reservation_id}: sales closed (departs in {minutes_until} min)")
                            return request.redirect(f'/bus-booking/confirmation/{reservation_id}?error=too_late')

            # Calculate total amount using correct price from Special Price
            # Handle both selected_seats and seat_number (from dispatcher quick-sell)
            if reservation.selected_seats:
                seat_count = len(reservation.selected_seats.split(','))
            elif reservation.seat_number:
                seat_count = len(reservation.seat_number.split(','))
            else:
                seat_count = 1

            price_per_seat = reservation.get_correct_price()
            total_amount = price_per_seat * seat_count
            _logger.info(f"Processing payment for {seat_count} seats × {price_per_seat} = {total_amount}")

            # Pokusit se o přímou platbu přes Monobank
            if 'payment.provider' in request.env:
                try:
                    monobank_provider = request.env['payment.provider'].sudo().search([
                        ('code', '=', 'monobank'),
                        ('state', '=', 'enabled')
                    ], limit=1)

                    if monobank_provider:
                        _logger.info(f"Using Monobank provider for reservation {reservation_id}")

                        # Získat callback URL
                        base_url = request.httprequest.host_url.rstrip('/')
                        callback_url = f"{base_url}/payment/monobank/notify"
                        result_url = f"{base_url}/bus-booking/payment-success?reservation_id={reservation_id}"

                        # Vytvořit platební odkaz přes Monobank
                        payment_url = monobank_provider._monobank_get_api_url(
                            amount=total_amount,
                            callback_url=callback_url,
                            result_url=result_url,
                            external_id=reservation.name,
                            partner_name=reservation.passenger_name,
                            currency_name='UAH',
                            transaction=None  # Bez transakce, přímý odkaz
                        )

                        if payment_url:
                            _logger.info(f"Monobank payment URL created: {payment_url}")
                            # Uložit do session pro callback
                            request.session['bus_reservation_id'] = reservation.id
                            # Pro externí URL použít werkzeug redirect přímo
                            if payment_url.startswith('https://') or payment_url.startswith('http://'):
                                from werkzeug.utils import redirect as werkzeug_redirect
                                return werkzeug_redirect(payment_url, code=302)
                            return request.redirect(payment_url)
                        else:
                            _logger.warning("Monobank returned empty payment URL")
                except Exception as mono_error:
                    _logger.error(f"Monobank error: {mono_error}", exc_info=True)

            # Fallback: Zkusit vytvořit sale order a použít standardní checkout
            _logger.info("Falling back to sale order method")
            try:
                sale_order = self._get_or_create_sale_order(reservation, total_amount)
                _logger.info(f"Sale order created/retrieved: {sale_order.id}")

                # Store reservation ID in session for callback
                request.session['bus_reservation_id'] = reservation.id
                request.session['sale_order_id'] = sale_order.id
                request.session['bus_booking_route_id'] = reservation.route_id.id

                # Set this as the current sale order for the website
                request.session['sale_order_id'] = sale_order.id
                request.session['website_sale_current_pl'] = sale_order.id

                # Skip cart page and go directly to payment
                _logger.info(f"=== Redirecting to payment with order {sale_order.id}")
                return request.redirect('/shop/payment')

            except Exception as sale_error:
                _logger.warning(f"Could not create sale order: {sale_error}")
                # Fallback: zobrazit confirmation stránku s možností kontaktovat dispečera
                return request.redirect(f'/bus-booking/confirmation/{reservation_id}?error=payment_unavailable')

        except Exception as e:
            _logger.error(f"Error during payment processing: {e}", exc_info=True)
            return request.redirect(f'/bus-booking/confirmation/{reservation_id}?error=payment')

    @http.route('/bus-booking/buy', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def buy_tickets(self, **kw):
        """Buy tickets - create sale order and redirect to payment"""
        try:
            route_id = int(kw.get('route_id'))
            selected_seats = kw.get('selected_seats', [])
            passenger_data = kw.get('passengers', [])

            if not all([route_id, selected_seats, passenger_data]):
                return {'success': False, 'message': 'Chybějící údaje'}

            route = request.env['ie.bus.search.result'].sudo().browse(route_id)
            if not route.exists():
                return {'success': False, 'message': 'Neplatný spoj'}
            
            # Validace: nelze nakupovat na minulé datum
            today = get_prague_today()
            if route.trip_date and route.trip_date < today:
                return {'success': False, 'message': f'Nelze nakupovat na minulé datum ({route.trip_date.strftime("%d.%m.%Y")}). Nákup je možný pouze od dnešního dne.'}

            # Check if departure time from selected boarding point has passed (Prague timezone)
            now = get_prague_now()
            trip_date = route.trip_date
            trip_start_time = route.trip_start_date or 0

            if trip_date and trip_start_time:
                # Create departure datetime from selected boarding point (Prague timezone)
                departure_hour = int(trip_start_time)
                departure_minute = int((trip_start_time - departure_hour) * 60)
                departure_datetime = datetime.datetime.combine(
                    trip_date,
                    datetime.time(departure_hour, departure_minute),
                    tzinfo=PRAGUE_TZ
                )

                # Stop sales 5 minutes before departure from selected stop
                sales_cutoff = departure_datetime - datetime.timedelta(minutes=5)

                if now > sales_cutoff:
                    time_diff = now - departure_datetime
                    if time_diff.total_seconds() > 0:
                        hours_ago = int(time_diff.total_seconds() / 3600)
                        minutes_ago = int((time_diff.total_seconds() % 3600) / 60)
                        if hours_ago > 0:
                            return {'success': False, 'message': f'Autobus již odjel před {hours_ago} hodinami. Nákup není možný.'}
                        else:
                            return {'success': False, 'message': f'Autobus již odjel před {minutes_ago} minutami. Nákup není možný.'}
                    else:
                        minutes_until = int((departure_datetime - now).total_seconds() / 60)
                        return {'success': False, 'message': f'Nákup není možný. Autobus odjíždí za {minutes_until} minut.'}

            # Create sale order
            sale_order = self._create_sale_order(route, selected_seats, passenger_data)

            return {
                'success': True,
                'order_id': sale_order.id,
                'payment_url': f'/shop/payment?order_id={sale_order.id}'
            }

        except Exception as e:
            _logger.error(f"Error in buy_tickets: {e}")
            return {'success': False, 'message': str(e)}

    def _create_sale_order(self, route, selected_seats, passenger_data):
        """Create a sale order for the booking"""
        # Create or get customer
        partner = request.env['res.partner'].sudo().search([
            ('email', '=', reservation.passenger_email)
        ], limit=1)

        if not partner:
            partner = request.env['res.partner'].sudo().create({
                'name': reservation.passenger_name,
                'email': reservation.passenger_email,
                'phone': reservation.passenger_phone,
                'street': 'Ulice 770',
                'city': 'Praha',
                'zip': '770 00',
                'country_id': request.env.ref('base.cz').id,
            })

        # Create sale order
        sale_order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': self._get_bus_ticket_product().id,
                'product_uom_qty': 1,
                'price_unit': route.price or 0,
            })],
        })

        # Update reservation with sale order
        reservation.sale_order_id = sale_order.id
        reservation.status = 'paid'

        return sale_order

    def _get_bus_ticket_product(self, from_location=None, to_location=None, price=None):
        """Get or create bus ticket product for specific route and price"""

        # If we have location and price info, create/get specific product
        if from_location and to_location and price:
            # Create unique product code based on route
            product_code = f'BUS_TICKET_{from_location.id}_{to_location.id}'
            product_name = f'Квиток: {from_location.name} → {to_location.name}'

            # Search for existing product for this route
            product = request.env['product.product'].sudo().search([
                ('default_code', '=', product_code)
            ], limit=1)

            if product:
                # Update price if changed
                if product.list_price != price:
                    product.sudo().write({'list_price': price})
                    _logger.info(f"[MBB] Updated product {product_code} price to {price}")
            else:
                # Create new product for this specific route with exact price
                product = request.env['product.product'].sudo().create({
                    'name': product_name,
                    'default_code': product_code,
                    'type': 'service',
                    'list_price': price,  # Exact price from Special Price
                    'sale_ok': True,
                    'purchase_ok': False,
                    'invoice_policy': 'order',
                })
                _logger.info(f"[MBB] Created new product {product_code} with price {price}")

            return product

        # Fallback: generic bus ticket product
        product = request.env['product.product'].sudo().search([
            ('default_code', '=', 'BUS_TICKET')
        ], limit=1)

        if not product:
            product = request.env['product.product'].sudo().create({
                'name': 'Автобусний квиток',
                'default_code': 'BUS_TICKET',
                'type': 'service',
                'list_price': 0.01,  # Symbolic price
                'sale_ok': True,
                'purchase_ok': False,
                'invoice_policy': 'order',
            })

        return product

    def _get_or_create_sale_order(self, reservation, total_amount):
        """Get or create sale order for reservation"""
        # Check if sale module is installed
        if 'sale.order' not in request.env:
            raise Exception("Sale module not installed - cannot create sale order")

        # Check if sale order already exists for this reservation
        if reservation.sale_order_id:
            return reservation.sale_order_id

        # Get or create partner
        partner = request.env['res.partner'].sudo().search([
            ('email', '=', reservation.passenger_email)
        ], limit=1)

        if not partner:
            partner = request.env['res.partner'].sudo().create({
                'name': reservation.passenger_name,
                'email': reservation.passenger_email,
                'phone': reservation.passenger_phone,
                'street': 'N/A',
                'city': 'Praha',
                'country_id': request.env.ref('base.cz').id,
            })

        # Get boarding and dropping points
        from_location = reservation.boarding_point if reservation.boarding_point else reservation.route_id.bording_from
        to_location = reservation.dropping_point if reservation.dropping_point else reservation.route_id.to

        # Calculate correct price
        price_per_seat = float(reservation.get_correct_price())

        # Get or create product specific to this route with correct price
        product = self._get_bus_ticket_product(
            from_location=from_location,
            to_location=to_location,
            price=price_per_seat
        )
        _logger.info(f"[MBB] Using product: {product.name} (code: {product.default_code}) with price {product.list_price}")

        # Get pricelist
        pricelist = request.env['product.pricelist'].sudo().search([
            ('currency_id', '=', request.env.company.currency_id.id)
        ], limit=1)

        if not pricelist:
            pricelist = request.env['product.pricelist'].sudo().create({
                'name': 'CZK Pricelist',
                'currency_id': request.env.company.currency_id.id,
            })

        # Create sale order with website context
        sale_order = request.env['sale.order'].sudo().create({
            'partner_id': partner.id,
            'partner_invoice_id': partner.id,
            'partner_shipping_id': partner.id,
            'pricelist_id': pricelist.id,
            'website_id': request.website.id if hasattr(request, 'website') else False,
            'state': 'draft',
            'require_signature': False,
            'require_payment': True,
        })

        # Add order line with correct price from reservation
        # IMPORTANT: Use get_correct_price() which takes boarding/dropping points into account
        # Handle both selected_seats and seat_number (from dispatcher quick-sell)
        if reservation.selected_seats:
            seat_count = len(reservation.selected_seats.split(','))
        elif reservation.seat_number:
            seat_count = len(reservation.seat_number.split(','))
        else:
            seat_count = 1
        price_per_seat = float(reservation.get_correct_price())  # Get price from Special Price table

        _logger.info(f"[MBB] Creating order line: {seat_count} seats × {price_per_seat} = {seat_count * price_per_seat}")

        # Create order line with forced price
        order_line = request.env['sale.order.line'].sudo().with_context(
            force_price=True
        ).create({
            'order_id': sale_order.id,
            'product_id': product.id,
            'name': f'Jízdenka: {reservation.route_id.bording_from.name} → {reservation.route_id.to.name}\nSedadla: {reservation.selected_seats}\nDatum: {reservation.route_id.trip_date}',
            'product_uom_qty': seat_count,
            'price_unit': price_per_seat,
            'discount': 0.0,
            'product_uom_id': product.uom_id.id,
        })

        # Force update the price to override any pricelist calculation
        order_line.sudo().write({
            'price_unit': price_per_seat,
            'price_reduce_taxexcl': price_per_seat,
            'price_subtotal': price_per_seat * seat_count,
        })

        # Link sale order to reservation
        reservation.sale_order_id = sale_order.id

        return sale_order

    @http.route(['/bus-booking/payment-success', '/shop/confirmation'], type='http', auth='public', website=True, csrf=False)
    def payment_success(self, **kw):
        """Handle successful payment callback"""
        _logger.info(f"=== PAYMENT SUCCESS CALLBACK: params={kw}")

        # Get reservation from session
        reservation_id = request.session.get('bus_reservation_id')
        sale_order_id = request.session.get('sale_order_id')

        if not reservation_id:
            return request.redirect('/bus-booking')

        try:
            reservation = request.env['modern.bus.reservation'].sudo().browse(int(reservation_id))
            if not reservation.exists():
                return request.redirect('/bus-booking')

            # Mark as paid
            reservation.status = 'paid'

            # Send confirmation email
            self._send_reservation_email(reservation)

            # Calculate departure info (Prague timezone for all times)
            now = get_prague_now()
            trip = None
            if reservation.route_id:
                search_result = reservation.route_id
                trip = search_result.trip_id if search_result else None

            if not trip:
                return request.redirect('/bus-booking')

            trip_date = trip.trip_date
            trip_start_time = search_result.trip_start_date if search_result else 0

            hours = int(trip_start_time)
            minutes = int((trip_start_time - hours) * 60)
            trip_departure = datetime.datetime.combine(trip_date, datetime.time(hours, minutes), tzinfo=PRAGUE_TZ)

            hours_until_departure = (trip_departure - now).total_seconds() / 3600

            # Clear session
            request.session.pop('bus_reservation_id', None)
            request.session.pop('sale_order_id', None)
            request.session.pop('website_sale_current_pl', None)

            # Calculate correct price
            correct_price = reservation.get_correct_price()
            # Handle both selected_seats and seat_number (from dispatcher quick-sell)
            if reservation.selected_seats:
                seat_count = len(reservation.selected_seats.split(','))
            elif reservation.seat_number:
                seat_count = len(reservation.seat_number.split(','))
            else:
                seat_count = 1
            total_price = correct_price * seat_count

            return request.render('ie_bus_ticket_web.bus_booking_payment_success_template', {
                'reservation': reservation,
                'hours_until_departure': int(max(0, hours_until_departure)),
                'departure_time': trip_departure.strftime('%d.%m.%Y %H:%M'),
                'correct_price': correct_price,
                'total_price': total_price,
            })

        except Exception as e:
            _logger.error(f"Error in payment_success: {e}")
            return request.redirect('/bus-booking')

    def _send_reservation_email(self, reservation, hours_until_expiry=None, expiry_time=None):
        """Send reservation confirmation email in Ukrainian with UAH pricing"""
        try:
            # Get boarding/dropping info with times
            boarding_name = reservation.boarding_point.name if reservation.boarding_point else (reservation.route_id.bording_from.name if reservation.route_id.bording_from else '-')
            boarding_address = ''
            boarding_time = ''
            dropping_name = reservation.dropping_point.name if reservation.dropping_point else (reservation.route_id.to.name if reservation.route_id.to else '-')
            dropping_address = ''
            dropping_time = ''

            if reservation.boarding_point and reservation.boarding_point.point_ids:
                boarding_address = ', '.join(reservation.boarding_point.point_ids.mapped('name'))
            if reservation.dropping_point and reservation.dropping_point.point_ids:
                dropping_address = ', '.join(reservation.dropping_point.point_ids.mapped('name'))

            # Get times from route lines
            if reservation.route_id and hasattr(reservation.route_id, 'route') and reservation.route_id.route:
                for line in reservation.route_id.route.route_line_ids:
                    if reservation.boarding_point and line.bording_from.id == reservation.boarding_point.id:
                        hours = int(line.start_times)
                        minutes = int((line.start_times - hours) * 60)
                        boarding_time = f"{hours:02d}:{minutes:02d}"
                    if reservation.dropping_point and line.to.id == reservation.dropping_point.id:
                        hours = int(line.end_times)
                        minutes = int((line.end_times - hours) * 60)
                        dropping_time = f"{hours:02d}:{minutes:02d}"

            # Fallback: use trip_start_date if no boarding_time found
            if not boarding_time and reservation.route_id and reservation.route_id.trip_start_date:
                hours = int(reservation.route_id.trip_start_date)
                minutes = int((reservation.route_id.trip_start_date - hours) * 60)
                boarding_time = f"{hours:02d}:{minutes:02d}"

            # Format boarding/dropping HTML
            boarding_info = boarding_name
            if boarding_time:
                boarding_info += f" ({boarding_time})"
            if boarding_address:
                boarding_info += f"<br><small style='color:#666;'>{boarding_address}</small>"

            dropping_info = dropping_name
            if dropping_time:
                dropping_info += f" ({dropping_time})"
            if dropping_address:
                dropping_info += f"<br><small style='color:#666;'>{dropping_address}</small>"

            # Calculate correct price (always in UAH)
            correct_price = reservation.get_correct_price()
            # Handle both selected_seats and seat_number (from dispatcher quick-sell)
            if reservation.selected_seats:
                seat_count = len(reservation.selected_seats.split(','))
            elif reservation.seat_number:
                seat_count = len(reservation.seat_number.split(','))
            else:
                seat_count = 1
            total_price = correct_price * seat_count

            # Get trip date
            trip_date = reservation.route_id.trip_date.strftime('%d.%m.%Y') if reservation.route_id and reservation.route_id.trip_date else '-'

            # Expiry info in Ukrainian
            expiry_html = ''
            if expiry_time:
                expiry_html = f'<p style="color: #856404; margin: 10px 0;"><strong>Бронювання закінчується:</strong> {expiry_time}</p>'

            mail_values = {
                'subject': f'✅ Бронювання {reservation.name} - НЕОПЛАЧЕНО - SymcheraBUS',
                'email_to': reservation.passenger_email,
                'email_from': 'rezervace@symcherabus.eu',
                'body_html': f'''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <div style="background: linear-gradient(135deg, #ff8906, #ffc107); padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                            <h1 style="color: white; margin: 0;">⏳ Бронювання створено</h1>
                        </div>

                        <div style="background: #f8f9fa; padding: 20px;">
                            <h2 style="color: #ff8906; margin-top: 0;">🚌 SymcheraBUS</h2>
                            <p>Шановний/а <strong>{reservation.passenger_name}</strong>,</p>
                            <p>Дякуємо за Ваше бронювання. Ось деталі Вашої поїздки:</p>

                            <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background: white; border-radius: 8px; overflow: hidden;">
                                <tr><td style="padding: 12px; border-bottom: 1px solid #ddd; background: #fff3e0;"><strong>📋 Номер бронювання:</strong></td><td style="padding: 12px; border-bottom: 1px solid #ddd; background: #fff3e0; font-weight: bold; color: #ff8906;">{reservation.name}</td></tr>
                                <tr><td style="padding: 12px; border-bottom: 1px solid #ddd;"><strong>👤 Ім'я:</strong></td><td style="padding: 12px; border-bottom: 1px solid #ddd;">{reservation.passenger_name}</td></tr>
                                <tr><td style="padding: 12px; border-bottom: 1px solid #ddd;"><strong>📅 Дата:</strong></td><td style="padding: 12px; border-bottom: 1px solid #ddd;">{trip_date}</td></tr>
                                <tr><td style="padding: 12px; border-bottom: 1px solid #ddd;"><strong>💺 Місце:</strong></td><td style="padding: 12px; border-bottom: 1px solid #ddd;">{reservation.selected_seats or reservation.seat_number or '-'}</td></tr>
                                <tr style="background:#e8f5e9;"><td style="padding: 12px; border-bottom: 1px solid #ddd;"><strong>🚏 Посадка:</strong></td><td style="padding: 12px; border-bottom: 1px solid #ddd;">{boarding_info}</td></tr>
                                <tr style="background:#e8f5e9;"><td style="padding: 12px; border-bottom: 1px solid #ddd;"><strong>🏁 Висадка:</strong></td><td style="padding: 12px; border-bottom: 1px solid #ddd;">{dropping_info}</td></tr>
                                <tr><td style="padding: 12px; border-bottom: 1px solid #ddd;"><strong>💰 Ціна:</strong></td><td style="padding: 12px; border-bottom: 1px solid #ddd; font-weight: bold; color: #059669;">{total_price} UAH</td></tr>
                            </table>

                            <div style="background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; border-radius: 4px;">
                                <h4 style="color: #856404; margin-top: 0;">⚠️ БРОНЮВАННЯ - НЕОПЛАЧЕНО</h4>
                                <p style="color: #856404; margin: 10px 0;">
                                    Зв'яжіться з диспетчером не пізніше ніж <strong>за 3 години до відправлення</strong>, інакше бронювання буде автоматично скасовано.
                                </p>
                                {expiry_html}
                            </div>

                            <div style="text-align: center; margin: 20px 0;">
                                <a href="https://symcherabus.eu/bus-booking/pay?reservation_id={reservation.id}"
                                   style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-size: 16px; font-weight: bold;">
                                   💳 Оплатити онлайн
                                </a>
                            </div>

                            <div style="background: #e3f2fd; padding: 15px; border-left: 4px solid #2196f3; margin: 20px 0; border-radius: 4px;">
                                <h4 style="color: #0d47a1; margin-top: 0;">📞 Контакт диспетчера:</h4>
                                <p style="color: #0d47a1; margin: 5px 0;">📞 +380673124850</p>
                                <p style="color: #0d47a1; margin: 5px 0;">📞 +420776359353</p>
                                <p style="color: #0d47a1; margin: 5px 0;">✉️ symchera@email.cz</p>
                            </div>
                        </div>

                        <div style="background: #333; padding: 15px; text-align: center; border-radius: 0 0 8px 8px;">
                            <p style="color: #999; font-size: 12px; margin: 0;">SymcheraBUS | symcherabus.eu | +380673124850 | +420776359353</p>
                        </div>
                    </div>
                ''',
            }

            mail = request.env['mail.mail'].sudo().create(mail_values)
            mail.send()

            _logger.info(f"Reservation confirmation email sent to {reservation.passenger_email}")

        except Exception as e:
            _logger.error(f"Error sending reservation email: {e}")

    # =========================================================================
    # TICKET CHECK - Kontrola jízdenky s bezpečným tokenem
    # =========================================================================

    @http.route('/bus/ticket/check/<int:reservation_id>', type='http', auth='public', website=True)
    def ticket_check(self, reservation_id, token=None, **kw):
        """
        Veřejná stránka pro kontrolu stavu jízdenky a platby.
        Přístup pouze s platným tokenem z emailu.
        """
        import hashlib
        # Najít rezervaci
        reservation = request.env['modern.bus.reservation'].sudo().browse(reservation_id)
        if not reservation.exists():
            return request.render('website.404')

        # Ověřit token
        email = reservation.passenger_email or ''
        expected_token = hashlib.sha256(f"{reservation.id}:{reservation.name}:{email}:symchera_secret".encode()).hexdigest()[:32]
        if token != expected_token:
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>❌ Neplatný přístup | SymcheraBUS</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: Arial, sans-serif; background: #fee2e2; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
                    .error-box {{ background: white; padding: 40px; border-radius: 12px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 400px; }}
                    h1 {{ color: #dc2626; }}
                    a {{ color: #f97316; }}
                </style>
            </head>
            <body>
                <div class="error-box">
                    <h1>❌ Neplatný přístup</h1>
                    <p>Tento odkaz je neplatný nebo vypršel.</p>
                    <p>Použijte prosím odkaz z vašeho emailu.</p>
                    <p><a href="https://symcherabus.eu">← Zpět na hlavní stránku</a></p>
                </div>
            </body>
            </html>
            """

        # DŮLEŽITÉ: Ověřit a opravit stav podle bankovního logu před zobrazením
        try:
            if hasattr(reservation, '_verify_and_fix_payment_status'):
                was_fixed, fix_message = reservation._verify_and_fix_payment_status()
                if was_fixed:
                    _logger.info(f"[TICKET_CHECK] Auto-fixed status for {reservation.name}: {fix_message}")
                    # Refresh reservation po opravě
                    reservation = request.env['modern.bus.reservation'].sudo().browse(reservation.id)
        except Exception as e:
            _logger.warning(f"[TICKET_CHECK] Could not verify status: {e}")

        # Získat detaily
        status_info = self._get_ticket_status_info(reservation)
        payment_info = self._get_payment_info(reservation)
        route_info = self._get_route_info(reservation)

        # Status badge
        status_color = {
            'reserved': '#f59e0b',
            'paid': '#22c55e',
            'confirmed': '#22c55e',
            'cancelled': '#ef4444',
            'expired': '#6b7280',
        }.get(reservation.status, '#6b7280')

        status_text = {
            'reserved': '📋 Rezervováno - čeká na platbu',
            'paid': '✅ Zaplaceno',
            'confirmed': '✅ Potvrzeno',
            'cancelled': '❌ Zrušeno',
            'expired': '⏱️ Vypršelo',
        }.get(reservation.status, reservation.status)

        # Platební tlačítko (pokud nezaplaceno)
        payment_button = ""
        if reservation.status in ['reserved']:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', 'https://symcherabus.eu')
            payment_link = f"{base_url}/pwa/client/pay/{reservation.id}"
            details = reservation._get_trip_details()
            price = details.get('price', 0)
            payment_button = f"""
            <div style="text-align: center; margin: 30px 0;">
                <a href="{payment_link}" style="background: linear-gradient(135deg, #f97316, #ea580c); color: white; padding: 18px 45px; text-decoration: none; border-radius: 10px; font-weight: bold; font-size: 18px; display: inline-block; box-shadow: 0 4px 15px rgba(249,115,22,0.4);">
                    💳 Zaplatit nyní - {price:.0f} ₴
                </a>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>🎫 Kontrola jízdenky {reservation.name} | SymcheraBUS</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%); min-height: 100vh; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                .card {{ background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.3); }}
                .header {{ background: linear-gradient(135deg, #f97316, #ea580c); padding: 30px; text-align: center; color: white; }}
                .header h1 {{ margin: 0 0 10px 0; font-size: 24px; }}
                .header .ticket-number {{ font-size: 32px; font-weight: bold; }}
                .status-badge {{ display: inline-block; padding: 8px 20px; border-radius: 20px; font-weight: bold; margin-top: 15px; }}
                .content {{ padding: 30px; }}
                .info-row {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }}
                .info-label {{ color: #666; }}
                .info-value {{ font-weight: 600; color: #333; }}
                .section-title {{ color: #f97316; font-size: 14px; font-weight: 600; margin: 25px 0 15px 0; text-transform: uppercase; letter-spacing: 1px; }}
                .footer {{ background: #f9fafb; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
                .footer a {{ color: #f97316; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <div class="header">
                        <h1>🚌 SymcheraBUS</h1>
                        <div class="ticket-number">{reservation.name}</div>
                        <div class="status-badge" style="background: {status_color}; color: white;">
                            {status_text}
                        </div>
                    </div>

                    <div class="content">
                        <div class="section-title">👤 Cestující</div>
                        <div class="info-row">
                            <span class="info-label">Jméno:</span>
                            <span class="info-value">{reservation.passenger_name or '—'}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Email:</span>
                            <span class="info-value">{reservation.passenger_email or '—'}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Telefon:</span>
                            <span class="info-value">{reservation.passenger_phone or '—'}</span>
                        </div>

                        <div class="section-title">🚏 Cesta</div>
                        {route_info}

                        <div class="section-title">💳 Platba</div>
                        {payment_info}

                        {payment_button}

                        {self._get_documents_section(reservation)}
                    </div>

                    <div class="footer">
                        <p>SymcheraBUS | <a href="https://symcherabus.eu">symcherabus.eu</a> | +380673124850 | +420776359353</p>
                        <p style="font-size: 12px; color: #999;">Kontrola provedena: {get_prague_now().strftime('%d.%m.%Y %H:%M')}</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    def _get_ticket_status_info(self, reservation):
        """Získá informace o stavu jízdenky"""
        return {
            'status': reservation.status,
            'created': reservation.create_date.strftime('%d.%m.%Y %H:%M') if reservation.create_date else '—',
        }

    def _get_payment_info(self, reservation):
        """Získá informace o platbě"""
        html = ""

        # Získat cenu
        details = reservation._get_trip_details()
        price = details.get('price', 0)

        # Status platby
        if reservation.status in ['paid', 'confirmed']:
            html += f"""
            <div class="info-row">
                <span class="info-label">Stav:</span>
                <span class="info-value" style="color: #22c55e;">✅ Zaplaceno</span>
            </div>
            """
        else:
            html += f"""
            <div class="info-row">
                <span class="info-label">Stav:</span>
                <span class="info-value" style="color: #f59e0b;">⏳ Čeká na platbu</span>
            </div>
            """

        html += f"""
        <div class="info-row">
            <span class="info-label">Částka:</span>
            <span class="info-value">{price:.0f} ₴</span>
        </div>
        <div class="info-row">
            <span class="info-label">Způsob:</span>
            <span class="info-value">{reservation.payment_method_detail or 'online'}</span>
        </div>
        """

        # Monobank log info
        if 'monobank.payment.log' in request.env:
            monobank_log = request.env['monobank.payment.log'].sudo().search([
                ('reservation_id', '=', reservation.id)
            ], limit=1, order='create_date desc')
            if monobank_log:
                html += f"""
                <div class="info-row">
                    <span class="info-label">Reference:</span>
                    <span class="info-value">{monobank_log.invoice_id or '—'}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Datum platby:</span>
                    <span class="info-value">{monobank_log.create_date.strftime('%d.%m.%Y %H:%M') if monobank_log.create_date else '—'}</span>
                </div>
                """

        return html

    def _get_documents_section(self, reservation):
        """Sekce s tlačítky pro stažení dokumentů"""
        if reservation.status not in ['paid', 'confirmed']:
            return ""

        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url', 'https://symcherabus.eu')

        # URL pro jízdenku
        ticket_url = f"{base_url}/bus/ticket/pdf/{reservation.id}"

        # URL pro kasový ček / příjmový doklad
        receipt_url = f"{base_url}/bus/receipt/{reservation.id}"

        # URL pro fakturu (pokud existuje)
        invoice_url = ""
        if hasattr(reservation, 'sale_order_id') and reservation.sale_order_id:
            invoices = reservation.sale_order_id.invoice_ids.filtered(lambda i: i.state == 'posted')
            if invoices:
                invoice_url = f"{base_url}/report/pdf/account.report_invoice/{invoices[0].id}"

        html = """
        <div class="section-title">📄 Dokumenty</div>
        <div style="display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; margin: 15px 0;">
        """

        html += f"""
            <a href="{ticket_url}" target="_blank" style="display: inline-block; padding: 12px 20px; background: #22c55e; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 14px;">
                🎫 Jízdenka (PDF)
            </a>
        """

        html += f"""
            <a href="{receipt_url}" target="_blank" style="display: inline-block; padding: 12px 20px; background: #6366f1; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 14px;">
                🧾 Kasovní ček
            </a>
        """

        if invoice_url:
            html += f"""
                <a href="{invoice_url}" target="_blank" style="display: inline-block; padding: 12px 20px; background: #004aad; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 14px;">
                    📋 Faktura
                </a>
            """

        html += "</div>"
        return html

    def _get_route_info(self, reservation):
        """Získá informace o trase"""
        html = ""

        boarding = reservation.boarding_point.name if hasattr(reservation, 'boarding_point') and reservation.boarding_point else '—'
        dropping = reservation.dropping_point.name if hasattr(reservation, 'dropping_point') and reservation.dropping_point else '—'

        html += f"""
        <div class="info-row">
            <span class="info-label">🚏 Nástup:</span>
            <span class="info-value">{boarding}</span>
        </div>
        <div class="info-row">
            <span class="info-label">🏁 Výstup:</span>
            <span class="info-value">{dropping}</span>
        </div>
        <div class="info-row">
            <span class="info-label">💺 Sedadlo:</span>
            <span class="info-value">{reservation.selected_seats or 'AUTO'}</span>
        </div>
        """

        # Datum jízdy
        if hasattr(reservation, 'route_id') and reservation.route_id and hasattr(reservation.route_id, 'trip_date'):
            trip_date = reservation.route_id.trip_date
            if trip_date:
                html += f"""
                <div class="info-row">
                    <span class="info-label">📅 Datum:</span>
                    <span class="info-value">{trip_date.strftime('%d.%m.%Y') if hasattr(trip_date, 'strftime') else trip_date}</span>
                </div>
                """

        return html

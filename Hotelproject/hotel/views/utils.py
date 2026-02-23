"""
Utility Views and API Endpoints
- API endpoints for admin dashboard
- Helper functions
"""

from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from hotel.models import Booking, Reservation
from hotel.views.admin import admin_login_required


@admin_login_required
@require_http_methods(["GET"])
def api_pending_bookings(request):
    """API endpoint returning count of pending bookings"""
    pending_count = Booking.objects.filter(status='Pending').count()
    return JsonResponse({
        'pending_bookings': pending_count
    })


@admin_login_required
@require_http_methods(["GET"])
def api_all_bookings(request):
    """API endpoint returning paginated pending/confirmed bookings"""
    status_filter = request.GET.get('status', 'all')
    page = int(request.GET.get('page', 1))
    per_page = 10
    
    if status_filter == 'pending':
        bookings = Booking.objects.filter(status='Pending').order_by('-created_at')
    elif status_filter == 'confirmed':
        bookings = Booking.objects.filter(status='Confirmed').order_by('-created_at')
    else:
        bookings = Booking.objects.all().order_by('-created_at')
    
    total = bookings.count()
    start = (page - 1) * per_page
    end = start + per_page
    bookings_page = bookings[start:end]
    
    data = {
        'bookings': [
            {
                'id': b.id,
                'room': str(b.room),
                'guest': str(b.guest),
                'status': b.status,
                'created_at': b.created_at.isoformat() if b.created_at else None,
            }
            for b in bookings_page
        ],
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
    }
    return JsonResponse(data)


def my_view(request):
    """Simple success view for form redirects"""
    return render(request, 'hotel/html/success.html')

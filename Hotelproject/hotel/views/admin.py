"""
Admin Dashboard and Management Views
- Admin Dashboard with Analytics
- Room, Service, Contact, User Management
- Review Management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Sum, Avg, Q
from datetime import datetime, timedelta
from functools import wraps
from django.utils import timezone
import json

from hotel.models import (
    Room, RoomCategory, Reservation, Payment, Guest, Service, UserProfile,
    Contact, RoomRating, ServiceRating, ServiceBooking, RoomImage, Booking
)


# ===== DECORATOR FOR ADMIN-ONLY ACCESS =====
def admin_login_required(view_func):
    """Decorator to check if user is admin/staff"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        try:
            profile = request.user.userprofile
        except UserProfile.DoesNotExist:
            return HttpResponseForbidden("You don't have permission to access this page.")
        if profile.role != 'Admin':
            return HttpResponseForbidden("You don't have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return wrapper


# ===== DASHBOARD VIEWS =====
@admin_login_required
def admin_dashboard(request):
    """Admin dashboard home with analytics and metrics"""
    from django.db import models
    
    # ===== REQUESTED PERIOD =====
    period_param = request.GET.get('period', '1')
    try:
        period = int(period_param)
    except ValueError:
        period = 1

    today = timezone.now().date()
    if period <= 1:
        start_date = today
    else:
        start_date = today - timedelta(days=period - 1)

    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period - 1) if period > 1 else prev_end

    # ===== ROOM STATISTICS =====
    total_rooms = Room.objects.count()
    total_rooms_prev = Room.objects.filter(created_at__lt=start_date).count()
    available_rooms = Room.objects.filter(status='Available').count()
    booked_rooms = Room.objects.filter(status='Booked').count()
    
    # ===== RESERVATION STATISTICS =====
    total_reservations = Reservation.objects.count()
    pending_reservations = Reservation.objects.filter(status='Pending').count()
    confirmed_reservations = Reservation.objects.filter(status='Confirmed').count()
    
    # ===== PAYMENT STATISTICS =====
    total_payments = Payment.objects.filter(payment_status='Completed').count()
    total_revenue = Payment.objects.filter(payment_status='Completed').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    # ===== PERIOD METRICS =====
    if period <= 1:
        guests_count = Reservation.objects.filter(check_in_date=today).count()
        revenue_count = Payment.objects.filter(
            payment_status='Completed',
            payment_date__date=today
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        active_current = Reservation.objects.filter(
            status__in=['Confirmed', 'Checked In']
        ).count()

        prev_guests = Reservation.objects.filter(check_in_date=prev_end).count()
        prev_revenue = Payment.objects.filter(
            payment_status='Completed',
            payment_date__date=prev_end
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        prev_active = Reservation.objects.filter(
            status__in=['Confirmed', 'Checked In'],
            booking_date__date=prev_end
        ).count()
    else:
        guests_count = Reservation.objects.filter(
            check_in_date__range=(start_date, today)
        ).count()
        revenue_count = Payment.objects.filter(
            payment_status='Completed',
            payment_date__date__range=(start_date, today)
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        active_current = Reservation.objects.filter(
            status__in=['Confirmed', 'Checked In'],
            booking_date__date__range=(start_date, today)
        ).count()

        prev_guests = Reservation.objects.filter(
            check_in_date__range=(prev_start, prev_end)
        ).count()
        prev_revenue = Payment.objects.filter(
            payment_status='Completed',
            payment_date__date__range=(prev_start, prev_end)
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        prev_active = Reservation.objects.filter(
            status__in=['Confirmed', 'Checked In'],
            booking_date__date__range=(prev_start, prev_end)
        ).count()

    # helper for percentage difference
    def pct(curr, prev):
        if prev == 0:
            return "100%" if curr > 0 else "0%"
        diff = ((curr - prev) / prev) * 100
        return f"{ '+' if diff >= 0 else ''}{int(diff)}%"

    total_rooms_trend = pct(total_rooms, total_rooms_prev)
    active_reservations_trend = pct(active_current, prev_active)
    guests_trend = pct(guests_count, prev_guests)
    revenue_trend = pct(revenue_count, prev_revenue)

    # determine colors for hints based on sign
    def hint_color(trend_str):
        return '#ef4444' if str(trend_str).startswith('-') else '#16a34a'

    total_rooms_trend_color = hint_color(total_rooms_trend)
    active_reservations_trend_color = hint_color(active_reservations_trend)
    guests_trend_color = hint_color(guests_trend)
    revenue_trend_color = hint_color(revenue_trend)
    
    # ===== RECENT DATA =====
    recent_reservations = Reservation.objects.select_related(
        'guest__user', 'room__category'
    ).order_by('-booking_date')[:10]
    
    recent_contacts = Contact.objects.filter(is_read=False).order_by('-created_at')[:5]
    unread_contacts = Contact.objects.filter(is_read=False)
    
    # ===== PENDING & CONFIRMED BOOKINGS =====
    pending_room_bookings = Reservation.objects.filter(status='Pending').select_related('guest__user', 'room__category').order_by('-booking_date')[:5]
    pending_service_bookings = ServiceBooking.objects.filter(status='Pending').select_related('user', 'service').order_by('-booking_date')[:5]
    
    seven_days_ago = timezone.now() - timedelta(days=7)
    confirmed_room_bookings = Reservation.objects.filter(status='Confirmed', booking_date__gte=seven_days_ago).select_related('guest__user', 'room__category').order_by('-booking_date')[:5]
    confirmed_service_bookings = ServiceBooking.objects.filter(status='Confirmed', booking_date__gte=seven_days_ago).select_related('user', 'service').order_by('-booking_date')[:5]
    
    pending_bookings = len(list(pending_room_bookings) + list(pending_service_bookings))
    confirmed_bookings = len(list(confirmed_room_bookings) + list(confirmed_service_bookings))
    total_notifications = pending_bookings + confirmed_bookings
    
    # ===== CHART DATA - Last 7 Days =====
    last_7_days = [timezone.now().date() - timedelta(days=i) for i in range(6, -1, -1)]
    reservation_counts = []
    revenue_by_day = []
    
    for day in last_7_days:
        count = Reservation.objects.filter(booking_date__date=day).count()
        revenue = Payment.objects.filter(
            payment_status='Completed',
            payment_date__date=day
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        reservation_counts.append(count)
        revenue_by_day.append(float(revenue))
    
    chart_labels = [d.strftime('%d %b') for d in last_7_days]
    
    # ===== ROOM CATEGORY DISTRIBUTION =====
    category_data = Room.objects.values('category__category_name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    category_names = [item['category__category_name'] for item in category_data]
    category_counts = [item['count'] for item in category_data]
    
    context = {
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'booked_rooms': booked_rooms,
        'total_reservations': total_reservations,
        'pending_reservations': pending_reservations,
        'confirmed_reservations': confirmed_reservations,
        'total_payments': total_payments,
        'total_revenue': total_revenue,
        'guests_today': guests_count,
        'revenue_today': revenue_count,
        'active_reservations': active_current,
        'total_rooms_trend': total_rooms_trend,
        'active_reservations_trend': active_reservations_trend,
        'guests_trend': guests_trend,
        'revenue_trend': revenue_trend,
        'total_rooms_trend_color': total_rooms_trend_color,
        'active_reservations_trend_color': active_reservations_trend_color,
        'guests_trend_color': guests_trend_color,
        'revenue_trend_color': revenue_trend_color,
        'period': period,
        'period_label': {1:'Today',7:'Last 7 days',30:'Last 30 days',365:'This year'}.get(period, f'Last {period} days'),
        'recent_reservations': recent_reservations,
        'unread_contacts': unread_contacts,
        'pending_bookings': pending_bookings,
        'pending_room_bookings': pending_room_bookings,
        'pending_service_bookings': pending_service_bookings,
        'confirmed_bookings': confirmed_bookings,
        'confirmed_room_bookings': confirmed_room_bookings,
        'confirmed_service_bookings': confirmed_service_bookings,
        'total_notifications': total_notifications,
        'reservation_counts': reservation_counts,
        'revenue_by_day': revenue_by_day,
        'chart_labels': chart_labels,
        'category_names': category_names,
        'category_counts': category_counts,
    }
    return render(request, 'hotel/admin/dashboard.html', context)


# ===== USER MANAGEMENT =====
@admin_login_required
def manage_users(request):
    """List all users for admin to manage"""
    users = User.objects.all().order_by('username')
    return render(request, 'hotel/admin/manage_users.html', {'users': users})


@admin_login_required
def add_user(request):
    """Add a new user"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        is_staff = request.POST.get('is_staff') == 'on'
        is_superuser = request.POST.get('is_superuser') == 'on'
        role = request.POST.get('role', 'Customer')
        
        # Validation
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect('manage_users')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists.")
            return redirect('manage_users')
        
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.save()
            try:
                UserProfile.objects.create(user=user, role=role)
            except Exception:
                pass
            messages.success(request, f"User '{username}' created successfully.")
        except Exception as e:
            messages.error(request, f"Error creating user: {str(e)}")
        
        return redirect('manage_users')
    
    return redirect('manage_users')


@admin_login_required
def edit_user(request, user_id):
    """Edit a user"""
    user = get_object_or_404(User, id=user_id)
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        role = request.POST.get('role')
        is_staff = True if request.POST.get('is_staff') == 'on' else False
        is_super = True if request.POST.get('is_superuser') == 'on' else False

        try:
            # ensure profile exists
            if not profile:
                profile = UserProfile(user=user, role=role or 'Customer')
            else:
                profile.role = role or profile.role
            profile.save()

            user.is_staff = is_staff
            user.is_superuser = is_super
            user.save()

            messages.success(request, f"User '{user.username}' updated successfully.")
        except Exception as e:
            messages.error(request, f"Error updating user: {str(e)}")
        
        return redirect('manage_users')

    return redirect('manage_users')


@admin_login_required
@require_http_methods(["POST"])
def delete_user(request, user_id):
    """Delete a user"""
    user = get_object_or_404(User, id=user_id)
    username = user.username
    try:
        user.delete()
        messages.success(request, f'User "{username}" deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting user: {str(e)}')
    return redirect('manage_users')


# ===== CATEGORY MANAGEMENT =====
@admin_login_required
def manage_categories(request):
    """Manage room categories"""
    categories = RoomCategory.objects.all().order_by('category_name')
    return render(request, 'hotel/admin/manage_category.html', {'categories': categories})


@admin_login_required
def add_category(request):
    """Add a new category"""
    if request.method == "POST":
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body)
                name = (data.get('category_name') or "").strip()
            except json.JSONDecodeError:
                return JsonResponse({"success": False, "error": "Invalid JSON."})
        else:
            name = (request.POST.get('category_name') or "").strip()

        if not name:
            if request.content_type == "application/json":
                return JsonResponse({"success": False, "error": "Category name is required."})
            else:
                messages.error(request, "Category name is required.")
                return redirect('manage_categories')

        # prevent duplicate name
        if RoomCategory.objects.filter(category_name__iexact=name).exists():
            msg = f'Category "{name}" already exists.'
            if request.content_type == "application/json":
                return JsonResponse({"success": False, "error": msg})
            else:
                messages.warning(request, msg)
                return redirect('manage_categories')

        RoomCategory.objects.create(category_name=name)
        
        if request.content_type == "application/json":
            return JsonResponse({"success": True, "message": f'Category "{name}" added successfully.'})
        else:
            messages.success(request, f'Category "{name}" added successfully.')
            return redirect('manage_categories')
    
    return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)


@admin_login_required
@require_http_methods(["POST"])
def delete_category(request, category_id):
    """Delete a category"""
    if request.method == 'POST':
        category = get_object_or_404(RoomCategory, id=category_id)
        category.delete()
        messages.success(request, f'Category "{category.category_name}" deleted.')
    return redirect('manage_categories')


@admin_login_required
def edit_category(request, category_id):
    """Edit a room category"""
    category = get_object_or_404(RoomCategory, id=category_id)
    
    if request.method == 'POST':
        category.category_name = request.POST.get('category_name', category.category_name)
        category.description = request.POST.get('description', getattr(category, 'description', ''))
        try:
            category.save()
            messages.success(request, f'Category "{category.category_name}" updated successfully.')
            return redirect('manage_categories')
        except Exception as e:
            messages.error(request, f'Error updating category: {str(e)}')
    
    context = {'category': category}
    return render(request, 'hotel/admin/edit_category.html', context)


# ===== ROOM MANAGEMENT =====
@admin_login_required
def manage_rooms(request):
    """Manage rooms"""
    rooms = Room.objects.all().select_related('category').order_by('room_number')
    categories = RoomCategory.objects.all()
    context = {'rooms': rooms, 'categories': categories}
    return render(request, 'hotel/admin/manage_rooms.html', context)


@admin_login_required
def add_room(request):
    """Add a new room"""
    if request.method == 'POST':
        room_number = request.POST.get('room_number')
        category_id = request.POST.get('category')
        floor = request.POST.get('floor', 1)
        max_occupancy = request.POST.get('max_occupancy', 2)
        price = request.POST.get('price')
        
        if not room_number or not category_id:
            messages.error(request, 'Room number and category are required.')
            return redirect('manage_rooms')
        
        try:
            category = RoomCategory.objects.get(id=category_id)
            room = Room.objects.create(
                room_number=room_number,
                category=category,
                floor=int(floor),
                max_occupancy=int(max_occupancy),
                price=float(price) if price else None,
                status='Available'
            )
            messages.success(request, f'Room {room_number} created successfully.')
        except RoomCategory.DoesNotExist:
            messages.error(request, 'Category not found.')
        except ValueError:
            messages.error(request, 'Invalid input values.')
        except Exception as e:
            messages.error(request, f'Error creating room: {str(e)}')
    
    return redirect('manage_rooms')


@admin_login_required
def edit_room(request, room_id):
    """Edit a room"""
    room = get_object_or_404(Room, id=room_id)
    
    if request.method == 'POST':
        room.room_number = request.POST.get('room_number', room.room_number)
        room.category_id = request.POST.get('category', room.category_id)
        room.floor = int(request.POST.get('floor', room.floor))
        room.max_occupancy = int(request.POST.get('max_occupancy', room.max_occupancy))
        price = request.POST.get('price')
        room.price = float(price) if price else None
        room.status = request.POST.get('status', room.status)
        room.amenities = request.POST.get('amenities', room.amenities)
        room.description = request.POST.get('description', room.description)
        
        # Handle image upload
        image = request.FILES.get('image')
        if image:
            room.image = image
        
        try:
            room.save()
            
            # Handle room image gallery (up to 6 images)
            for i in range(1, 7):
                image_file = request.FILES.get(f'room_image_{i}')
                alt_text = request.POST.get(f'alt_text_{i}', '')
                
                if image_file:
                    existing_image = RoomImage.objects.filter(room=room, order=i).first()
                    if existing_image:
                        existing_image.image = image_file
                        existing_image.alt_text = alt_text
                        existing_image.save()
                    else:
                        RoomImage.objects.create(
                            room=room,
                            image=image_file,
                            alt_text=alt_text,
                            order=i
                        )
            
            messages.success(request, f'Room {room.room_number} updated successfully.')
            return redirect('manage_rooms')
        except Exception as e:
            messages.error(request, f'Error updating room: {str(e)}')
    
    categories = RoomCategory.objects.all()
    context = {'room': room, 'categories': categories}
    return render(request, 'hotel/admin/edit_room.html', context)


@admin_login_required
@require_http_methods(["POST"])
def delete_room(request, room_id):
    """Delete a room"""
    room = get_object_or_404(Room, id=room_id)
    room_number = room.room_number
    
    try:
        room.delete()
        messages.success(request, f'Room {room_number} deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting room: {str(e)}')
    
    return redirect('manage_rooms')


@admin_login_required
@require_http_methods(["POST"])
def delete_room_image(request, image_id):
    """Delete a room gallery image"""
    room_image = get_object_or_404(RoomImage, id=image_id)
    room_id = room_image.room.id
    
    try:
        room_image.delete()
        messages.success(request, 'Image deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting image: {str(e)}')
    
    return redirect('manage_rooms')


# ===== SERVICE MANAGEMENT =====
@admin_login_required
def manage_services(request):
    """Manage services offered by the hotel"""
    services = Service.objects.all().order_by('-id')
    return render(request, 'hotel/admin/manage_services.html', {'services': services})


@admin_login_required
def add_service(request):
    """Add a new service"""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        price_str = request.POST.get("price", "0")
        is_active = request.POST.get("is_active") == "on"
        image = request.FILES.get("image")

        if not name:
            messages.error(request, "Service name is required.")
            return redirect("manage_services")

        try:
            price = float(price_str) if price_str else 0
            service = Service.objects.create(
                name=name,
                description=description,
                price=price,
                is_active=is_active
            )
            if image:
                service.image = image
                service.save()
            messages.success(request, f"Service '{name}' added successfully.")
        except ValueError:
            messages.error(request, "Invalid price. Please enter a number.")
        except Exception as e:
            messages.error(request, f"Error adding service: {str(e)}")
        
        return redirect("manage_services")

    return redirect("manage_services")


@admin_login_required
def edit_service(request, service_id):
    """Edit a service"""
    service = get_object_or_404(Service, id=service_id)
    
    if request.method == 'POST':
        service.name = request.POST.get('name', service.name)
        service.description = request.POST.get('description', service.description)
        price = request.POST.get('price')
        service.price = float(price) if price else service.price
        service.is_active = request.POST.get('is_active') == 'on'
        
        # Handle image upload
        image = request.FILES.get('image')
        if image:
            service.image = image
        
        try:
            service.save()
            messages.success(request, f'Service "{service.name}" updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating service: {str(e)}')
    
    return redirect('manage_services')


@admin_login_required
@require_http_methods(["POST"])
def delete_service(request, service_id):
    """Delete a service"""
    service = get_object_or_404(Service, id=service_id)
    service_name = service.name
    try:
        service.delete()
        messages.success(request, f'Service "{service_name}" deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting service: {str(e)}')
    return redirect('manage_services')


# ===== CONTACT MANAGEMENT =====
@admin_login_required
def manage_contacts(request):
    """View contact messages"""
    contacts = Contact.objects.all().order_by('-created_at')
    read_status = request.GET.get('read_status')
    if read_status == 'unread':
        contacts = contacts.filter(is_read=False)
    elif read_status == 'read':
        contacts = contacts.filter(is_read=True)
    context = {'contacts': contacts}
    return render(request, 'hotel/admin/manage_contacts.html', context)


@admin_login_required
def add_contact(request):
    """Add a contact message"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        subject = request.POST.get('subject', '')
        message = request.POST.get('message')

        if not all([name, email, message]):
            messages.error(request, 'Name, email and message are required.')
            return redirect('manage_contacts')

        try:
            Contact.objects.create(
                name=name,
                email=email,
                phone=phone or None,
                subject=subject or '',
                message=message
            )
            messages.success(request, 'Contact message saved.')
        except Exception as e:
            messages.error(request, f'Error saving contact: {str(e)}')
    
    return redirect('manage_contacts')


@admin_login_required
def edit_contact(request, contact_id):
    """Edit a contact message"""
    contact = get_object_or_404(Contact, id=contact_id)
    
    if request.method == 'POST':
        contact.name = request.POST.get('name', contact.name)
        contact.email = request.POST.get('email', contact.email)
        contact.phone = request.POST.get('phone', contact.phone)
        contact.subject = request.POST.get('subject', contact.subject)
        contact.message = request.POST.get('message', contact.message)
        contact.is_read = request.POST.get('is_read') == 'on'
        
        try:
            contact.save()
            messages.success(request, 'Contact updated successfully.')
            return redirect('manage_contacts')
        except Exception as e:
            messages.error(request, f'Error updating contact: {str(e)}')
    
    context = {'contact': contact}
    return render(request, 'hotel/admin/edit_contact.html', context)


@admin_login_required
@require_http_methods(["POST"])
def delete_contact(request, contact_id):
    """Delete a contact message"""
    contact = get_object_or_404(Contact, id=contact_id)
    try:
        contact.delete()
        messages.success(request, 'Contact deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting contact: {str(e)}')
    return redirect('manage_contacts')


@admin_login_required
@require_http_methods(["POST"])
def mark_contact_read(request, contact_id):
    """Mark contact as read"""
    contact = get_object_or_404(Contact, id=contact_id)
    contact.is_read = True
    contact.save()
    messages.success(request, "Contact marked as read.")
    return redirect('manage_contacts')


# ===== REVIEW MANAGEMENT =====
@admin_login_required
@login_required
def manage_reviews(request):
    """Manage room and service reviews"""
    room_reviews = RoomRating.objects.select_related("user", "room", "reservation").all()
    service_reviews = ServiceRating.objects.select_related("user", "service", "service_booking").all()
    
    # Combine both querysets and sort by created_at descending
    combined_reviews = list(room_reviews) + list(service_reviews)
    combined_reviews.sort(key=lambda x: x.created_at, reverse=True)

    # only show reservations that are Checked Out
    reservations = Reservation.objects.select_related("guest__user", "room").filter(status="Checked Out").order_by("-booking_date")

    return render(request, "hotel/admin/manage_reviews.html", {
        "reviews": combined_reviews,
        "reservations": reservations,
    })


@admin_login_required
@login_required
def add_room_review_admin(request):
    """Add a room review (admin)"""
    if request.method == "POST":
        reservation_id = request.POST.get("reservation")
        rating = request.POST.get("rating")
        review = request.POST.get("review", "")

        cleanliness = request.POST.get("cleanliness", 5)
        comfort = request.POST.get("comfort", 5)
        amenities = request.POST.get("amenities", 5)

        if not reservation_id:
            messages.error(request, "Please select a reservation.")
            return redirect("manage_reviews")

        reservation = get_object_or_404(Reservation, id=reservation_id)
        user = reservation.guest.user
        room = reservation.room

        # prevent duplicate
        if RoomRating.objects.filter(user=user, reservation=reservation).exists():
            messages.warning(request, "This reservation already has a review.")
            return redirect("manage_reviews")

        RoomRating.objects.create(
            user=user,
            room=room,
            reservation=reservation,
            rating=int(rating),
            review=review,
            cleanliness=int(cleanliness),
            comfort=int(comfort),
            amenities=int(amenities),
            created_at=timezone.now(),
        )

        messages.success(request, "Review added successfully.")
        return redirect("manage_reviews")

    return redirect("manage_reviews")


@admin_login_required
@login_required
def delete_review(request, review_id):
    """Delete a room or service review"""
    r = None
    try:
        r = RoomRating.objects.get(id=review_id)
    except RoomRating.DoesNotExist:
        try:
            r = ServiceRating.objects.get(id=review_id)
        except ServiceRating.DoesNotExist:
            messages.error(request, "Review not found.")
            return redirect("manage_reviews")

    if request.method == "POST":
        r.delete()
        messages.success(request, "Review deleted.")
    return redirect("manage_reviews")


@admin_login_required
@login_required
def edit_review(request, review_id):
    """Edit a room or service review"""
    r = None
    rating_type = None
    
    try:
        r = RoomRating.objects.get(id=review_id)
        rating_type = 'room'
    except RoomRating.DoesNotExist:
        try:
            r = ServiceRating.objects.get(id=review_id)
            rating_type = 'service'
        except ServiceRating.DoesNotExist:
            raise Http404("Review not found")

    if request.method == "POST":
        r.rating = int(request.POST.get("rating", r.rating))
        r.review = request.POST.get("review", r.review)
        
        if rating_type == 'room':
            r.cleanliness = int(request.POST.get("cleanliness", r.cleanliness))
            r.comfort = int(request.POST.get("comfort", r.comfort))
            r.amenities = int(request.POST.get("amenities", r.amenities))
        else:  # service
            r.quality = int(request.POST.get("quality", r.quality))
            r.timeliness = int(request.POST.get("timeliness", r.timeliness))
            r.value_for_money = int(request.POST.get("value_for_money", r.value_for_money))
        
        try:
            r.save()
            messages.success(request, "Review updated successfully.")
            return redirect("manage_reviews")
        except Exception as e:
            messages.error(request, f"Error updating review: {str(e)}")
            return redirect("manage_reviews")

    context = {'r': r, 'rating_type': rating_type}
    return render(request, "hotel/admin/edit_review.html", context)


# ===== BOOKING & PAYMENT MANAGEMENT =====
@admin_login_required
def manage_bookings(request):
    """Manage bookings/booking history"""
    room_bookings = Booking.objects.select_related('user', 'room', 'reservation').all().order_by('-booking_date')[:200]
    service_bookings = ServiceBooking.objects.select_related('user', 'service', 'reservation').all().order_by('-booking_date')[:200]
    
    return render(request, 'hotel/admin/manage_bookings.html', {
        'room_bookings': room_bookings,
        'service_bookings': service_bookings,
    })


@admin_login_required
def manage_payment(request):
    """Manage payments"""
    payments = Payment.objects.select_related(
        'reservation', 'reservation__guest', 'reservation__room',
        'service_booking', 'service_booking__user', 'service_booking__service'
    ).all().order_by('-payment_date', '-id')[:200]
    return render(request, 'hotel/admin/manage_payment.html', {'payments': payments})


@admin_login_required
def manage_service_bookings(request):
    """Admin: Manage all service bookings"""
    bookings = ServiceBooking.objects.select_related('user', 'service', 'reservation').all().order_by('-booking_date')[:500]

    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        bookings = bookings.filter(status=status_filter)

    # Optional filter by service id
    service_id = request.GET.get('service_id')
    if service_id:
        try:
            sid = int(service_id)
            bookings = bookings.filter(service__id=sid)
        except (ValueError, TypeError):
            pass

    context = {
        'bookings': bookings,
        'status_choices': ServiceBooking._meta.get_field('status').choices,
        'filtered_service_id': service_id,
    }
    return render(request, 'hotel/admin/manage_service_bookings.html', context)


@admin_login_required
@require_http_methods(["POST"])
def update_service_booking_status(request, booking_id):
    """Admin: Update service booking status"""
    booking = get_object_or_404(ServiceBooking, id=booking_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(ServiceBooking._meta.get_field('status').choices):
        booking.status = new_status
        booking.save()
        messages.success(request, f"Booking status updated to {new_status}.")
    else:
        messages.error(request, "Invalid status.")
    
    return redirect('manage_service_bookings')


# ===== REPORTS =====
@admin_login_required
def admin_reports(request):
    """Admin reports page with analytics"""
    from django.db import models
    
    period = int(request.GET.get('period', 30))
    start_date = datetime.now() - timedelta(days=period)
    
    # Revenue data
    reservations = Reservation.objects.filter(booking_date__gte=start_date)
    total_revenue = Payment.objects.filter(
        payment_status='Completed',
        payment_date__gte=start_date
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    total_bookings = reservations.count()

    # calculate previous period values for trends
    prev_start = start_date - timedelta(days=period)
    prev_end = start_date

    prev_revenue = Payment.objects.filter(
        payment_status='Completed',
        payment_date__gte=prev_start,
        payment_date__lt=prev_end
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    prev_bookings = Reservation.objects.filter(
        booking_date__gte=prev_start,
        booking_date__lt=prev_end
    ).count()

    def pct_change(current, previous):
        if previous == 0:
            return None
        return (current - previous) / previous * 100

    revenue_pct = pct_change(total_revenue, prev_revenue)
    bookings_pct = pct_change(total_bookings, prev_bookings)

    def format_pct(val):
        if val is None:
            return 'N/A'
        sign = '+' if val >= 0 else ''
        return f"{sign}{val:.1f}% from last period"

    revenue_trend = format_pct(revenue_pct)
    bookings_trend = format_pct(bookings_pct)

    # Occupancy calculation
    total_rooms = Room.objects.count()
    if total_rooms > 0:
        checked_in_today = Reservation.objects.filter(
            check_in_date__lte=datetime.now().date(),
            check_out_date__gte=datetime.now().date(),
            status__in=['Checked In', 'Confirmed']
        ).values('room').distinct().count()
        occupancy_rate = int((checked_in_today / total_rooms) * 100)
    else:
        occupancy_rate = 0
    
    # Average rating (all time)
    avg_rating = RoomRating.objects.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Top rooms (period-filtered)
    top_rooms = Room.objects.annotate(
        booking_count=Count('reservations', filter=Q(reservations__booking_date__gte=start_date)),
        total_revenue=Sum('reservations__payment__amount', filter=Q(reservations__booking_date__gte=start_date)),
        avg_rating=Avg('ratings__rating')
    ).filter(booking_count__gt=0).order_by('-total_revenue')[:5]
    
    # Top services (period-filtered)
    booking_filter = Q(user_bookings__booking_date__gte=start_date)
    top_services = Service.objects.annotate(
        usage_count=Count('user_bookings', filter=booking_filter),
        avg_rating=Avg('ratings__rating')
    ).filter(usage_count__gt=0).order_by('-usage_count')[:5]
    
    # Guest statistics (period-filtered)
    guests_checked_in = Reservation.objects.filter(status='Checked In', booking_date__gte=start_date).count()
    guests_pending = Reservation.objects.filter(status='Pending', booking_date__gte=start_date).count()
    guests_checked_out = Reservation.objects.filter(status='Checked Out', booking_date__gte=start_date).count()
    guests_cancelled = Reservation.objects.filter(status='Cancelled', booking_date__gte=start_date).count()
    
    # Revenue dates for chart
    revenue_by_date = {}
    for res in reservations:
        if hasattr(res, 'payment') and res.payment.payment_status == 'Completed':
            date_key = res.payment.payment_date.strftime('%Y-%m-%d') if res.payment.payment_date else datetime.now().strftime('%Y-%m-%d')
            revenue_by_date[date_key] = revenue_by_date.get(date_key, 0) + float(res.payment.amount)
    
    revenue_dates = json.dumps(sorted(revenue_by_date.keys()))
    revenue_values = json.dumps([revenue_by_date[d] for d in sorted(revenue_by_date.keys())])
    
    context = {
        'period': period,
        'total_revenue': f"${total_revenue:,.2f}",
        'total_bookings': total_bookings,
        'occupancy_rate': occupancy_rate,
        'avg_rating': f"{avg_rating:.1f}",
        'top_rooms': top_rooms,
        'top_services': top_services,
        'guests_checked_in': guests_checked_in,
        'guests_pending': guests_pending,
        'guests_checked_out': guests_checked_out,
        'guests_cancelled': guests_cancelled,
        'revenue_dates_json': revenue_dates,
        'revenue_values_json': revenue_values,
        'revenue_trend': revenue_trend,
        'bookings_trend': bookings_trend,
        'occupancy_trend': 'No change',
        'rating_trend': f"{avg_rating:.1f}",
    }
    return render(request, 'hotel/admin/reports.html', context)

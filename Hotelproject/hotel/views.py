from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User

from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db import models
from django.db.models import Q
from datetime import datetime, timedelta
from .models import (
    Room, RoomCategory, Reservation, Payment, Guest, 
    Contact, Service, UserProfile, Staff
)
from .forms import (
    CustomUserCreationForm, GuestForm, ReservationForm, 
    RoomFilterForm, PaymentForm, ContactForm, CustomPasswordResetForm
)
from django.middleware.csrf import get_token

from django.conf import settings
from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
# (UserProfile already imported above)
from django.db.models import Q , Count, Sum, Avg


# Decorator for admin-only access (checks UserProfile role and superuser)
def admin_login_required(view_func):
    @wraps (view_func)  
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

@admin_login_required
def manage_users(request):
    """List all users for admin to manage."""
    users = User.objects.all().order_by('username')
    return render(request, 'hotel/admin/manage_users.html', {
        'users': users
    })


@admin_login_required
def manage_categories(request):
    """Manage room categories"""
    categories = RoomCategory.objects.all().order_by('category_name')
    return render(request, 'hotel/admin/manage_category.html', {'categories': categories})


@admin_login_required
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            RoomCategory.objects.create(category_name=name)
            messages.success(request, f'Category "{name}" added.')
        else:
            messages.error(request, 'Category name is required.')
    return redirect('manage_categories')


@admin_login_required
def delete_category(request, category_id):
    if request.method == 'POST':
        category = get_object_or_404(RoomCategory, id=category_id)
        category.delete()
        messages.success(request, f'Category "{category.category_name}" deleted.')
    return redirect('manage_categories')


@admin_login_required
def manage_services(request):
    """Manage services offered by the hotel"""
    services = Service.objects.all().order_by('-id')
    return render(request, 'hotel/admin/manage_services.html', {'services': services})


@admin_login_required
def manage_bookings(request):
    """Manage bookings/booking history"""
    # Booking model may not always exist; try to import safely
    try:
        from .models import Booking
        bookings = Booking.objects.select_related('user','room','reservation').all().order_by('-booking_date')[:200]
    except Exception:
        bookings = []
    return render(request, 'hotel/admin/manage_bookings.html', {'bookings': bookings})


@admin_login_required
def manage_reviews(request):
    """Show room reviews and ratings"""
    try:
        from .models import RoomRating
        reviews = RoomRating.objects.select_related('user','room','reservation').order_by('-created_at')[:200]
    except Exception:
        reviews = []
    return render(request, 'hotel/admin/manage_reviews.html', {'reviews': reviews})


@admin_login_required
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = None

    role_choices = UserProfile.ROLE_CHOICES

    if request.method == 'POST':
        role = request.POST.get('role')
        is_staff = True if request.POST.get('is_staff') == 'on' else False
        is_super = True if request.POST.get('is_superuser') == 'on' else False

        # ensure profile exists
        if not profile:
            profile = UserProfile(user=user, role=role or 'Customer')
        else:
            profile.role = role or profile.role
        profile.save()

        user.is_staff = is_staff
        user.is_superuser = is_super
        user.save()

        messages.success(request, f"User {user.username} updated.")
        return redirect('manage_users')

    return render(request, 'hotel/admin/edit_user.html', {
        'user': user,
        'profile': profile,
        'role_choices': role_choices,
    })





# ===== AUTHENTICATION VIEWS =====
@ensure_csrf_cookie
def login_view(request):
    if request.user.is_authenticated:
        return redirect('guest_home')
    
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            # Redirect admins to dashboard, others to guest home (respect ?next=)
            try:
                profile = UserProfile.objects.get(user=user)
                if profile.role in ['Admin', 'Receptionist'] or user.is_superuser:
                    return redirect('admin_dashboard')
            except UserProfile.DoesNotExist:
                pass

            # Respect `next` GET param if present
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('guest_home')
        else:
            messages.error(request, "Invalid username or password")

    return render(request, 'hotel/html/login.html')


@ensure_csrf_cookie
def register_view(request):
    if request.user.is_authenticated:
        return redirect('guest_home')
    
    form = CustomUserCreationForm()
    guest_form = GuestForm()
    
    # Note: CSRF exempt for registration to avoid token mismatches in local/dev setup.
    # In production, remove @csrf_exempt and ensure CSRF cookie/token are correctly set.
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        guest_form = GuestForm(request.POST)
        if form.is_valid() and guest_form.is_valid():
            user = form.save()
            guest = guest_form.save(commit=False)
            guest.user = user
            guest.save()
            login(request, user)
            messages.success(request, "Account created successfully!")
            return redirect('complete_profile')
        else:
            # Do not duplicate field-level validation errors into global messages.
            # Field errors will be rendered inline by the template using `form` and `guest_form`.
            pass
    
    # Ensure a CSRF token is generated server-side and passed to the template
    csrf_token_value = get_token(request)
    return render(request, 'hotel/html/register.html', {
        'form': form,
        'guest_form': guest_form,
        'csrf_token_value': csrf_token_value,
    })


def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')


@login_required(login_url='login')
def complete_profile(request):
    """Allow users to complete their profile after registration"""
    try:
        guest = request.user.guest
    except Guest.DoesNotExist:
        guest = None

    if request.method == "POST":
        form = GuestForm(request.POST, instance=guest)
        if form.is_valid():
            guest = form.save(commit=False)
            guest.user = request.user
            guest.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('guest_home')
    else:
        form = GuestForm(instance=guest)

    return render(request, 'hotel/html/complete_profile.html', {'form': form})


# ===== HOME & GENERAL VIEWS =====
def guest_home(request):
    """Home page showing latest info (public)."""
    # Redirect to admin dashboard only if user has an admin role or is superuser
    if request.user.is_authenticated:
        is_admin_role = False
        try:
            is_admin_role = UserProfile.objects.get(user=request.user).role in ['Admin', 'Receptionist']
        except UserProfile.DoesNotExist:
            is_admin_role = False
        if is_admin_role or request.user.is_superuser:
            return redirect('admin_dashboard')

    featured_rooms = Room.objects.filter(status='Available')[:6]
    services = Service.objects.filter(is_active=True)[:6]

    user_reservations = []
    if request.user.is_authenticated:
        try:
            guest = request.user.guest
            user_reservations = Reservation.objects.filter(
                guest=guest
            ).order_by('-booking_date')[:5]
        except Guest.DoesNotExist:
            user_reservations = []

    context = {
        'featured_rooms': featured_rooms,
        'services': services,
        'user_reservations': user_reservations,
    }
    return render(request, 'hotel/html/home.html', context)


def about_view(request):
    """About page"""
    return render(request, 'hotel/html/about.html')


def service_view(request):
    """Services page"""
    services = Service.objects.filter(is_active=True)
    return render(request, 'hotel/html/service.html', {'services': services})


def contact_view(request):
    """Contact form page"""
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your message has been sent! We'll get back to you soon.")
            return redirect('service')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ContactForm()
    
    return render(request, 'hotel/html/contact.html', {'form': form})


# ===== ROOM BROWSING VIEWS =====
def room_list(request):
    """Browse available rooms with filters"""
    rooms = Room.objects.filter(status='Available')
    form = RoomFilterForm(request.GET or None)
    categories = RoomCategory.objects.all()
    # collect and sanitize selected category ids from querystring
    raw_selected = request.GET.getlist('category')
    selected_categories = []
    for v in raw_selected:
        if v is None:
            continue
        v = str(v).strip()
        if v == "":
            continue
        try:
            selected_categories.append(int(v))
        except (ValueError, TypeError):
            # ignore non-numeric values
            continue
    # template expects string ids for membership checks
    selected_categories_str = [str(x) for x in selected_categories]
    
    if form.is_valid():
        check_in = form.cleaned_data.get('check_in_date')
        check_out = form.cleaned_data.get('check_out_date')
        category = form.cleaned_data.get('category')
        max_price = form.cleaned_data.get('max_price')
        
        if check_in and check_out:
            # Filter out booked rooms
            booked_rooms = Reservation.objects.filter(
                Q(check_in_date__lt=check_out) & Q(check_out_date__gt=check_in),
                status__in=['Pending', 'Confirmed', 'Checked In']
            ).values_list('room_id', flat=True)
            rooms = rooms.exclude(id__in=booked_rooms)
        
        # If multiple category ids are provided via checkboxes, filter by those ids
        if selected_categories:
            rooms = rooms.filter(category__id__in=selected_categories)
        elif category:
            # fallback to legacy single text category match
            rooms = rooms.filter(category__category_name__icontains=category)
        
        if max_price:
            rooms = rooms.filter(category__base_price__lte=max_price)
    
    context = {
        'rooms': rooms,
        'form': form,
        'categories': categories,
        'selected_categories': selected_categories_str,
    }
    return render(request, 'hotel/html/room_list.html', context)


def room_detail(request, room_id):
    """View room details"""
    room = get_object_or_404(Room, id=room_id)
    # Split amenities string into a list for template rendering
    amenities_list = [a.strip() for a in (room.amenities or 'WiFi, AC, TV').split(',')]
    context = {
        'room': room,
        'amenities_list': amenities_list,
    }
    return render(request, 'hotel/html/room_detail.html', context)


# ===== BOOKING/RESERVATION VIEWS =====
@login_required(login_url='login')
def book_room(request, room_id):
    """Book a room"""
    room = get_object_or_404(Room, id=room_id)
    
    try:
        guest = request.user.guest
    except Guest.DoesNotExist:
        messages.error(request, "Please complete your profile before booking.")
        return redirect('complete_profile')
    
    if request.method == "POST":
        form = ReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.guest = guest
            reservation.room = room
            reservation.calculate_total_price()
            reservation.save()
            messages.success(request, "Reservation created! Please proceed with payment.")
            return redirect('payment', reservation_id=reservation.id)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ReservationForm()
    
    context = {
        'room': room,
        'form': form,
    }
    return render(request, 'hotel/html/book_room.html', context)


@login_required(login_url='login')
def my_reservations(request):
    """View user's reservations"""
    try:
        guest = request.user.guest
        reservations = guest.reservations.all()
    except Guest.DoesNotExist:
        reservations = []
    
    context = {'reservations': reservations}
    return render(request, 'hotel/html/my_reservations.html', context)


@login_required(login_url='login')
def reservation_detail(request, reservation_id):
    """View reservation details"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    # Check if user has permission to view
    if reservation.guest.user != request.user:
        messages.error(request, "You don't have permission to view this reservation.")
        return redirect('my_reservations')
    
    context = {'reservation': reservation}
    return render(request, 'hotel/html/reservation_detail.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def cancel_reservation(request, reservation_id):
    """Cancel a reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    if reservation.guest.user != request.user:
        messages.error(request, "You don't have permission to cancel this reservation.")
        return redirect('my_reservations')
    
    if reservation.status in ['Checked In', 'Checked Out', 'Cancelled']:
        messages.error(request, "This reservation cannot be cancelled.")
        return redirect('reservation_detail', reservation_id=reservation.id)
    
    reservation.status = 'Cancelled'
    reservation.save()
    messages.success(request, "Reservation cancelled successfully.")
    return redirect('my_reservations')


# ===== PAYMENT VIEWS =====
@login_required(login_url='login')
def payment(request, reservation_id):
    """Process payment for reservation"""
    reservation = get_object_or_404(Reservation, id=reservation_id)

    # permission check
    if reservation.guest.user != request.user:
        messages.error(request, "You don't have permission to access this reservation.")
        return redirect('my_reservations')

    # ✅ create or get payment object (ONE place only)
    payment_obj, created = Payment.objects.get_or_create(
        reservation=reservation,
        defaults={
            "amount": reservation.total_price,
            "payment_method": "Cash",     # default method
            "payment_status": "Pending",  # default status
        }
    )

    # ✅ if already paid
    if payment_obj.payment_status == "Paid":
        messages.info(request, "Payment already completed for this reservation.")
        return redirect('reservation_detail', reservation_id=reservation.id)

    if request.method == "POST":
        form = PaymentForm(request.POST, instance=payment_obj)
        if form.is_valid():
            payment_obj = form.save(commit=False)

            # ✅ mark paid
            payment_obj.payment_status = "Paid"
            payment_obj.transaction_id = f"TXN-{reservation.id}-{int(datetime.now().timestamp())}"
            payment_obj.save()

            # ✅ confirm reservation
            reservation.status = "Confirmed"
            reservation.save(update_fields=["status"])

            messages.success(request, "Payment completed successfully! Your reservation is confirmed.")
            return redirect('reservation_detail', reservation_id=reservation.id)
    else:
        form = PaymentForm(instance=payment_obj)

    return render(request, "hotel/html/payment.html", {
        "reservation": reservation,
        "payment": payment_obj,
        "form": form,
    })


# ===== ADMIN DASHBOARD VIEWS =====
def admin_login_required(view_func):
    """Decorator to check if user is admin/staff"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.role not in ['Admin', 'Receptionist']:
                return HttpResponseForbidden("You don't have permission to access the admin dashboard.")
        except UserProfile.DoesNotExist:
            return HttpResponseForbidden("You don't have permission to access the admin dashboard.")
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_login_required
def admin_dashboard(request):
    """Admin dashboard home"""
    total_rooms = Room.objects.count()
    available_rooms = Room.objects.filter(status='Available').count()
    total_reservations = Reservation.objects.count()
    pending_reservations = Reservation.objects.filter(status='Pending').count()
    total_payments = Payment.objects.filter(payment_status='Completed').count()
    total_revenue = Payment.objects.filter(payment_status='Completed').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    recent_reservations = Reservation.objects.order_by('-booking_date')[:10]
    recent_contacts = Contact.objects.filter(is_read=False).order_by('-created_at')[:5]
    
    booked_rooms = Room.objects.filter(status='Booked').count()
    unread_contacts = Contact.objects.filter(is_read=False)
    
    context = {
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'booked_rooms': booked_rooms,
        'total_reservations': total_reservations,
        'pending_reservations': pending_reservations,
        'total_payments': total_payments,
        'total_revenue': total_revenue,
        'recent_reservations': recent_reservations,
        'unread_contacts': unread_contacts,
    }
    return render(request, 'hotel/admin/dashboard.html', context)


@admin_login_required
def manage_reservations(request):
    """Manage all reservations"""
    reservations = Reservation.objects.all().order_by('-booking_date')
    status_filter = request.GET.get('status')
    
    if status_filter:
        reservations = reservations.filter(status=status_filter)
    # Provide guests and rooms for admin add-reservation modal
    guests = Guest.objects.select_related('user').all()
    rooms = Room.objects.all()

    context = {
        'reservations': reservations,
        'status_choices': Reservation.STATUS_CHOICES,
        'guests': guests,
        'rooms': rooms,
    }
    return render(request, 'hotel/admin/manage_reservations.html', context)


@admin_login_required
@require_http_methods(["POST"])
def add_reservation(request):
    """Admin: create a reservation"""
    guest_id = request.POST.get('guest')
    room_id = request.POST.get('room')
    check_in = request.POST.get('check_in_date')
    check_out = request.POST.get('check_out_date')
    number_of_guests = request.POST.get('number_of_guests', 1)
    status = request.POST.get('status', 'Pending')

    try:
        guest = Guest.objects.get(id=guest_id)
        room = Room.objects.get(id=room_id)
        reservation = Reservation.objects.create(
            guest=guest,
            room=room,
            check_in_date=check_in,
            check_out_date=check_out,
            number_of_guests=int(number_of_guests),
            status=status,
        )
        reservation.calculate_total_price()
        reservation.save()
        messages.success(request, f'Reservation #{reservation.id} created.')
    except Exception as e:
        messages.error(request, f'Error creating reservation: {str(e)}')
    return redirect('manage_reservations')


@admin_login_required
@require_http_methods(["POST"])
def delete_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    try:
        reservation.delete()
        messages.success(request, f'Reservation #{reservation_id} deleted.')
    except Exception as e:
        messages.error(request, f'Error deleting reservation: {str(e)}')
    return redirect('manage_reservations')


@admin_login_required
@require_http_methods(["POST"])
def update_reservation_status(request, reservation_id):
    """Update reservation status"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(Reservation.STATUS_CHOICES):
        reservation.status = new_status
        if new_status in ['Checked Out', 'Cancelled']:
            reservation.room.status = 'Available'
            reservation.room.save()
        elif new_status == 'Checked In':
            reservation.room.status = 'Booked'
            reservation.room.save()
        reservation.save()
        messages.success(request, f"Reservation status updated to {new_status}.")
    else:
        messages.error(request, "Invalid status.")
    
    return redirect('manage_reservations')


@admin_login_required
def manage_rooms(request):
    """Manage rooms"""
    rooms = Room.objects.all().select_related('category').order_by('room_number')
    categories = RoomCategory.objects.all()
    context = {'rooms': rooms, 'categories': categories}
    return render(request, 'hotel/admin/manage_rooms.html', context)


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
@require_http_methods(["POST"])
def mark_contact_read(request, contact_id):
    """Mark contact as read"""
    contact = get_object_or_404(Contact, id=contact_id)
    contact.is_read = True
    contact.save()
    messages.success(request, "Contact marked as read.")
    return redirect('manage_contacts')


# ===== NEW ENHANCED VIEWS =====

@admin_login_required
def admin_reports(request):
    """Admin reports page with analytics"""
    from django.db.models import Sum, Avg, Count
    
    period = int(request.GET.get('period', 30))
    start_date = datetime.now() - timedelta(days=period)
    
    # Revenue data
    reservations = Reservation.objects.filter(booking_date__gte=start_date)
    total_revenue = Payment.objects.filter(
        payment_status='Completed',
        payment_date__gte=start_date
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    total_bookings = reservations.count()
    
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
    
    # Average rating
    from .models import RoomRating, ServiceRating
    avg_rating = RoomRating.objects.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # Top rooms
    top_rooms = Room.objects.annotate(
        booking_count=Count('reservations'),
        total_revenue=Sum('reservations__payment__amount'),
        avg_rating=Avg('ratings__rating')
    ).filter(booking_count__gt=0).order_by('-total_revenue')[:5]
    
    # Top services
    top_services = Service.objects.annotate(
        usage_count=Count('usages'),
        avg_rating=Avg('ratings__rating')
    ).filter(usage_count__gt=0).order_by('-usage_count')[:5]
    
    # Guest statistics
    guests_checked_in = Reservation.objects.filter(status='Checked In').count()
    guests_pending = Reservation.objects.filter(status='Pending').count()
    guests_checked_out = Reservation.objects.filter(status='Checked Out').count()
    guests_cancelled = Reservation.objects.filter(status='Cancelled').count()
    
    # Revenue dates for chart
    revenue_by_date = {}
    for res in reservations:
        if hasattr(res, 'payment') and res.payment.payment_status == 'Completed':
            date_key = res.payment.payment_date.strftime('%Y-%m-%d') if res.payment.payment_date else datetime.now().strftime('%Y-%m-%d')
            revenue_by_date[date_key] = revenue_by_date.get(date_key, 0) + float(res.payment.amount)
    
    import json
    revenue_dates = json.dumps(sorted(revenue_by_date.keys()))
    revenue_values = json.dumps([revenue_by_date[d] for d in sorted(revenue_by_date.keys())])
    
    context = {
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
        'revenue_dates': revenue_dates,
        'revenue_values': revenue_values,
    }
    return render(request, 'hotel/admin/reports.html', context)


@login_required(login_url='login')
def user_profile(request):
    """User profile page"""
    try:
        guest = request.user.guest
    except Guest.DoesNotExist:
        guest = None
    
    bookings = Reservation.objects.filter(guest=guest).order_by('-check_in_date') if guest else []
    
    from .models import RoomRating, ServiceRating
    reviews = RoomRating.objects.filter(user=request.user)
    
    total_bookings = bookings.count()
    total_nights = sum((b.check_out_date - b.check_in_date).days for b in bookings if b.check_out_date and b.check_in_date) if bookings else 0
    reviews_count = reviews.count()
    
    context = {
        'guest': guest,
        'bookings': bookings,
        'reviews': reviews,
        'total_bookings': total_bookings,
        'total_nights': total_nights,
        'reviews_count': reviews_count,
    }
    return render(request, 'hotel/html/user_profile.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def update_profile(request):
    """Update user profile"""
    request.user.first_name = request.POST.get('first_name', request.user.first_name)
    request.user.last_name = request.POST.get('last_name', request.user.last_name)
    request.user.save()
    
    try:
        guest = request.user.guest
        guest.phone = request.POST.get('phone', guest.phone)
        guest.address = request.POST.get('address', guest.address)
        guest.save()
    except Guest.DoesNotExist:
        pass
    
    messages.success(request, "Profile updated successfully!")
    return redirect('user_profile')


@login_required(login_url='login')
@require_http_methods(["POST"])
def change_password(request):
    """Change user password"""
    current = request.POST.get('current_password')
    new = request.POST.get('new_password')
    confirm = request.POST.get('confirm_password')
    
    if not request.user.check_password(current):
        messages.error(request, "Current password is incorrect")
        return redirect('user_profile')
    
    if new != confirm:
        messages.error(request, "New passwords do not match")
        return redirect('user_profile')
    
    request.user.set_password(new)
    request.user.save()
    login(request, request.user)
    
    messages.success(request, "Password changed successfully!")
    return redirect('user_profile')


@login_required(login_url='login')
def rate_room(request, room_id):
    """Rate a room after checkout"""
    from .models import RoomRating
    room = get_object_or_404(Room, id=room_id)
    
    if request.method == 'POST':
        from .forms import RoomRatingForm
        form = RoomRatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.room = room
            rating.user = request.user
            rating.save()
            messages.success(request, "Thank you for your review!")
            return redirect('user_profile')
    else:
        from .forms import RoomRatingForm
        form = RoomRatingForm()
    
    context = {
        'room': room,
        'form': form,
    }
    return render(request, 'hotel/html/rate_room.html', context)


@login_required(login_url='login')
def rate_service(request, service_id):
    """Rate a service"""
    from .models import ServiceRating, ServiceBooking
    service = get_object_or_404(Service, id=service_id)
    
    if request.method == 'POST':
        from .forms import ServiceRatingForm
        form = ServiceRatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.service = service
            rating.user = request.user
            rating.save()
            messages.success(request, "Thank you for your service review!")
            return redirect('user_profile')
    else:
        from .forms import ServiceRatingForm
        form = ServiceRatingForm()
    
    context = {
        'service': service,
        'form': form,
    }
    return render(request, 'hotel/html/rate_service.html', context)

@login_required(login_url='login')
def reviews_page(request):
    from .models import RoomRating

    qs = RoomRating.objects.select_related("reservation", "room", "user").order_by("-created_at")

    summary = qs.aggregate(
        avg_rating=Avg("rating"),
        total=Count("id"),
    )

    return render(request, "hotel/html/review.html", {
        "reviews": qs,
        "avg_rating": summary["avg_rating"] or 0,
        "total_reviews": summary["total"] or 0,
    })


# ===== ROOM MANAGEMENT CRUD VIEWS =====
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
        
        try:
            room.save()
            messages.success(request, f'Room {room.room_number} updated successfully.')
            return redirect('manage_rooms')
        except Exception as e:
            messages.error(request, f'Error updating room: {str(e)}')
    
    categories = RoomCategory.objects.all()
    context = {'room': room, 'categories': categories}
    return render(request, 'hotel/admin/edit_room.html', context)


@admin_login_required
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


@admin_login_required
def add_service(request):
    """Add a new service"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        price = request.POST.get('price', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        if not name:
            messages.error(request, 'Service name is required.')
            return redirect('manage_services')
        
        try:
            Service.objects.create(
                name=name,
                description=description,
                price=float(price) if price else 0,
                is_active=is_active
            )
            messages.success(request, f'Service "{name}" added successfully.')
        except Exception as e:
            messages.error(request, f'Error adding service: {str(e)}')
    
    return redirect('manage_services')


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
        
        try:
            service.save()
            messages.success(request, f'Service "{service.name}" updated successfully.')
            return redirect('manage_services')
        except Exception as e:
            messages.error(request, f'Error updating service: {str(e)}')
    
    context = {'service': service}
    return render(request, 'hotel/admin/edit_service.html', context)


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


@admin_login_required
def add_contact(request):
    """Add a contact message"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        
        if not all([name, email, message]):
            messages.error(request, 'All fields are required.')
            return redirect('manage_contacts')
        
        try:
            Contact.objects.create(
                name=name,
                email=email,
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
def add_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        is_staff = request.POST.get('is_staff') == 'on'
        is_superuser = request.POST.get('is_superuser') == 'on'
        role = request.POST.get('role', 'staff')
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect('add_user')
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save()
        try:
            UserProfile.objects.create(user=user, role=role)
        except Exception:
            pass
        messages.success(request, f'User "{username}" created.')
        return redirect('manage_users')
    return render(request, 'hotel/admin/add_user.html')


@admin_login_required
def add_review(request):
    """Admin: Add a review"""
    rooms = Room.objects.all()
    users = User.objects.all()
    
    if request.method == 'POST':
        try:
            from .models import RoomRating
            user_id = request.POST.get('user')
            room_id = request.POST.get('room')
            rating = request.POST.get('rating')
            comment = request.POST.get('comment', '')
            
            user = User.objects.get(id=user_id)
            room = Room.objects.get(id=room_id)
            
            review = RoomRating.objects.create(
                user=user,
                room=room,
                rating=int(rating),
                comment=comment
            )
            messages.success(request, 'Review added successfully.')
            return redirect('manage_reviews')
        except Exception as e:
            messages.error(request, f'Error adding review: {str(e)}')
    
    context = {'rooms': rooms, 'users': users}
    return render(request, 'hotel/admin/add_review.html', context)


@admin_login_required
def edit_review(request, review_id):
    """Edit a review"""
    try:
        from .models import RoomRating
        review = get_object_or_404(RoomRating, id=review_id)
        rooms = Room.objects.all()
        users = User.objects.all()
        
        if request.method == 'POST':
            review.rating = request.POST.get('rating', review.rating)
            review.comment = request.POST.get('comment', review.comment)
            review.room_id = request.POST.get('room', review.room_id)
            review.save()
            messages.success(request, 'Review updated successfully.')
            return redirect('manage_reviews')
        
        context = {'review': review, 'rooms': rooms, 'users': users}
        return render(request, 'hotel/admin/edit_review.html', context)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('manage_reviews')


@admin_login_required
@require_http_methods(["POST"])
def delete_review(request, review_id):
    """Delete a review"""
    try:
        from .models import RoomRating
        review = get_object_or_404(RoomRating, id=review_id)
        review.delete()
        messages.success(request, 'Review deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting review: {str(e)}')
    return redirect('manage_reviews')


@admin_login_required
def edit_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    guests = Guest.objects.all()
    rooms = Room.objects.all()

    if request.method == 'POST':
        reservation.guest_id = request.POST.get('guest', reservation.guest_id)
        reservation.room_id = request.POST.get('room', reservation.room_id)
        reservation.check_in_date = request.POST.get('check_in_date', reservation.check_in_date)
        reservation.check_out_date = request.POST.get('check_out_date', reservation.check_out_date)
        reservation.status = request.POST.get('status', reservation.status)
        try:
            # recalc total_price if possible
            ci = reservation.check_in_date
            co = reservation.check_out_date
            if hasattr(ci, 'day') and hasattr(co, 'day') and reservation.room and getattr(reservation.room, 'price', None) is not None:
                nights = (co - ci).days
                if nights > 0:
                    reservation.total_price = float(reservation.room.price) * nights
        except Exception:
            pass
        reservation.save()
        messages.success(request, "Reservation updated successfully.")
        return redirect('manage_reservations')

    return render(request, 'hotel/admin/edit_reservation.html', {
        'reservation': reservation,
        'guests': guests,
        'rooms': rooms,
    })
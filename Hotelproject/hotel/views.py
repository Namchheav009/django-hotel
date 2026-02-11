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
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
import uuid
from .models import (
    Room, RoomCategory, Reservation, Payment, Guest, 
    Contact, Service, UserProfile, Staff, RoomRating, ServiceRating, ServiceBooking, RoomImage,
    Cart, CartItem
)
from .forms import (
    CustomUserCreationForm, GuestForm, ReservationForm, 
    RoomFilterForm, PaymentForm, ContactForm, CustomPasswordResetForm, ServiceBookingForm
)
from django.middleware.csrf import get_token
from .models import Booking
from django.utils import timezone

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
    """Add a new category"""
    if request.method == "POST":
        # Handle both form POST and JSON POST
        if request.content_type == "application/json":
            import json
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
    """Manage bookings/booking history - combines room and service bookings"""
    room_bookings = Booking.objects.select_related('user', 'room', 'reservation').all().order_by('-booking_date')[:200]
    service_bookings = ServiceBooking.objects.select_related('user', 'service', 'reservation').all().order_by('-booking_date')[:200]
    
    return render(request, 'hotel/admin/manage_bookings.html', {
        'room_bookings': room_bookings,
        'service_bookings': service_bookings,
    })


@admin_login_required
@admin_login_required
def manage_payment(request):
    """Manage payments"""
    payments = Payment.objects.select_related('reservation', 'reservation__guest', 'reservation__room').all().order_by('-payment_date', '-id')[:200]
    return render(request, 'hotel/admin/manage_payment.html', {'payments': payments})


@admin_login_required
def edit_user(request, user_id):
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

    # GET request - redirect to manage_users
    return redirect('manage_users')





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
    """View user's reservations (My Stays)"""
    try:
        guest = request.user.guest
        reservations = guest.reservations.select_related("room", "room__category").all()

        # ✅ which reservations already reviewed by this user
        from .models import RoomRating
        reviewed_res_ids = set(
            RoomRating.objects.filter(user=request.user, reservation__guest=guest)
            .values_list("reservation_id", flat=True)
        )
        
        # Get pending reservations
        pending_reservations = guest.reservations.exclude(payment__payment_status__in=['Completed', 'Refunded'])
    except Guest.DoesNotExist:
        reservations = []
        reviewed_res_ids = set()
        pending_reservations = None

    context = {
        "reservations": reservations,
        "reviewed_res_ids": reviewed_res_ids,
        "pending_reservations": pending_reservations,
    }
    return render(request, "hotel/html/my_reservations.html", context)



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
def payment(request, reservation_id=None):
    """
    Process payment for reservation(s).
    Handles both:
    - Single reservation (via reservation_id) - legacy flow
    - Multiple reservations (from session) - from confirm_information flow
    """
    # Check if multiple items payment (from confirm_information)
    if reservation_id is None:
        reservation_ids = request.session.get('checkout_reservation_ids', [])
        service_booking_ids = request.session.get('checkout_service_booking_ids', [])
        
        if not reservation_ids and not service_booking_ids:
            messages.error(request, "No reservations found. Please start from cart.")
            return redirect('view_cart')
        
        # Handle multiple items POST request
        if request.method == "POST":
            payment_method = request.POST.get('payment_method', 'Cash')
            
            if not payment_method:
                messages.error(request, "Please select a payment method.")
                return redirect('checkout_payment') if hasattr(request, 'path') else render(request, 'hotel/html/payment.html', {})
            
            try:
                # Process all reservations
                reservations = Reservation.objects.filter(id__in=reservation_ids, guest__user=request.user)
                service_bookings = ServiceBooking.objects.filter(id__in=service_booking_ids, user=request.user)
                
                for res in reservations:
                    # Create or update payment
                    payment_obj, _ = Payment.objects.get_or_create(
                        reservation=res,
                        defaults={
                            "amount": res.total_price,
                            "payment_method": payment_method,
                            "payment_status": "Completed",
                            "payment_date": timezone.now(),
                            "transaction_id": f"TXN-{res.id}-{int(datetime.now().timestamp())}"
                        }
                    )
                    
                    if payment_obj.payment_status != "Completed":
                        payment_obj.payment_status = "Completed"
                        payment_obj.payment_method = payment_method
                        payment_obj.payment_date = timezone.now()
                        payment_obj.transaction_id = f"TXN-{res.id}-{int(datetime.now().timestamp())}"
                        payment_obj.save()
                    
                    # Confirm reservation
                    res.status = "Confirmed"
                    res.save(update_fields=["status"])
                    
                    # Create booking record
                    try:
                        Booking.objects.get_or_create(
                            reservation=res,
                            defaults={
                                "user": request.user,
                                "room": res.room,
                                "booking_status": "Confirmed",
                                "confirmation_number": f"BK-{res.id}-{int(datetime.now().timestamp())}"
                            }
                        )
                    except Exception as e:
                        pass
                
                # Confirm service bookings
                for sb in service_bookings:
                    sb.status = "Confirmed"
                    sb.save(update_fields=["status"])
                
                # Clear session
                if 'checkout_reservation_ids' in request.session:
                    del request.session['checkout_reservation_ids']
                if 'checkout_service_booking_ids' in request.session:
                    del request.session['checkout_service_booking_ids']
                if 'checkout_total' in request.session:
                    del request.session['checkout_total']
                
                messages.success(request, "Payment completed successfully!")
                return redirect('payment_success')
            
            except Exception as e:
                messages.error(request, f"Payment processing error: {str(e)}")
                return redirect('view_cart')
        
        # GET request - show payment form with multiple items
        reservations = Reservation.objects.filter(id__in=reservation_ids, guest__user=request.user)
        service_bookings = ServiceBooking.objects.filter(id__in=service_booking_ids, user=request.user)
        total_amount = sum(r.total_price for r in reservations) + sum(sb.total_price for sb in service_bookings)
        
        return render(request, 'hotel/html/payment.html', {
            'reservations': reservations,
            'service_bookings': service_bookings,
            'total_amount': total_amount,
            'multiple_items': True,
        })
    
    # Single reservation flow (from reservation_detail.html)
    reservation = get_object_or_404(Reservation, id=reservation_id)

    # ✅ permission check
    if reservation.guest.user != request.user:
        messages.error(request, "You don't have permission to access this reservation.")
        return redirect('my_reservations')

    # ✅ already paid (IMPORTANT: use 'Completed', not 'Paid')
    payment_obj = Payment.objects.filter(reservation=reservation).first()
    if payment_obj and payment_obj.payment_status == "Completed":
        messages.info(request, "Payment already completed for this reservation.")
        return redirect('reservation_detail', reservation_id=reservation.id)

    if request.method == "POST":
        # Handle payment form submission
        payment_method = request.POST.get('payment_method', 'Cash')
        
        if not payment_method:
            messages.error(request, "Please select a payment method.")
            return render(request, 'hotel/html/payment.html', {
                'reservation': reservation,
                'payment_obj': payment_obj,
                'multiple_items': False,
            })
        
        try:
            # Create or update payment object
            payment_obj, _ = Payment.objects.get_or_create(
                reservation=reservation,
                defaults={
                    "amount": reservation.total_price,
                    "payment_method": payment_method,
                    "payment_status": "Completed",
                    "payment_date": timezone.now(),
                    "transaction_id": f"TXN-{reservation.id}-{int(datetime.now().timestamp())}"
                }
            )
            
            if payment_obj.payment_status != "Completed":
                payment_obj.payment_status = "Completed"
                payment_obj.payment_method = payment_method
                payment_obj.payment_date = timezone.now()
                payment_obj.transaction_id = f"TXN-{reservation.id}-{int(datetime.now().timestamp())}"
                payment_obj.save()
            
            # Confirm reservation
            reservation.status = "Confirmed"
            reservation.save(update_fields=["status"])
            
            # Create booking record
            try:
                Booking.objects.get_or_create(
                    reservation=reservation,
                    defaults={
                        "user": request.user,
                        "room": reservation.room,
                        "booking_status": "Confirmed",
                        "confirmation_number": f"BK-{reservation.id}-{int(datetime.now().timestamp())}"
                    }
                )
            except Exception as e:
                pass
            
            messages.success(request, "Payment completed successfully! Your reservation is confirmed.")
            return redirect('payment_success')
        
        except Exception as e:
            messages.error(request, f"Payment processing error: {str(e)}")
            return redirect('reservation_detail', reservation_id=reservation.id)

    # GET request - show payment form with single reservation
    if not payment_obj:
        payment_obj = Payment.objects.create(
            reservation=reservation,
            amount=reservation.total_price,
            payment_method="Cash",
            payment_status="Pending"
        )

    return render(request, 'hotel/html/payment.html', {
        'reservation': reservation,
        'payment_obj': payment_obj,
        'multiple_items': False,
    })


def payment_success(request):
    """
    Display payment success page after successful payment processing.
    Both multi-item and single-reservation flows redirect here.
    """
    return render(request, 'hotel/html/payment_success.html', {})


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
    from django.db.models import Count, Sum
    from datetime import date, timedelta
    
    # ===== ROOM STATISTICS =====
    total_rooms = Room.objects.count()
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
    
    # ===== TODAY STATISTICS =====
    today = timezone.now().date()
    guests_today = Reservation.objects.filter(
        check_in_date=today
    ).count()
    
    revenue_today = Payment.objects.filter(
        payment_status='Completed',
        payment_date__date=today
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    active_reservations = Reservation.objects.filter(
        status__in=['Confirmed', 'Checked In']
    ).count()
    
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
    
    # ===== TODAY'S OVERVIEW =====
    today_activities = []
    
    # Checkouts today
    checkouts_today = Reservation.objects.filter(
        check_out_date=today,
        status__in=['Confirmed', 'Checked In']
    ).count()
    if checkouts_today > 0:
        today_activities.append({
            'type': 'checkout',
            'title': f'{checkouts_today} guest(s) checking out',
            'subtitle': 'Prepare rooms for cleaning',
            'color': 'orange'
        })
    
    # New bookings today
    new_bookings_today = Reservation.objects.filter(
        booking_date__date=today
    ).count()
    if new_bookings_today > 0:
        today_activities.append({
            'type': 'booking',
            'title': f'{new_bookings_today} new booking(s)',
            'subtitle': 'Family suites and standard rooms',
            'color': 'blue'
        })
    
    # VIP arrivals
    vip_count = Reservation.objects.filter(
        check_in_date=today,
        total_price__gte=5000
    ).count()
    if vip_count > 0:
        today_activities.append({
            'type': 'vip',
            'title': f'{vip_count} high-value guest(s) arriving',
            'subtitle': 'Prepare premium welcome package',
            'color': 'pink'
        })
    
    # Pending payments
    pending_payments = Payment.objects.filter(
        payment_status='Pending'
    ).count()
    if pending_payments > 0:
        today_activities.append({
            'type': 'payment',
            'title': f'{pending_payments} pending payment(s)',
            'subtitle': 'Follow up with guests',
            'color': 'red'
        })
    
    context = {
        'total_rooms': total_rooms,
        'available_rooms': available_rooms,
        'booked_rooms': booked_rooms,
        'total_reservations': total_reservations,
        'pending_reservations': pending_reservations,
        'confirmed_reservations': confirmed_reservations,
        'total_payments': total_payments,
        'total_revenue': total_revenue,
        'guests_today': guests_today,
        'revenue_today': revenue_today,
        'active_reservations': active_reservations,
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
        'today_activities': today_activities,
    }
    return render(request, 'hotel/admin/dashboard.html', context)


@admin_login_required
@login_required(login_url='login')
def manage_reservations(request):
    reservations = Reservation.objects.select_related(
        "guest__user", "room__category"
    ).order_by("-booking_date")

    # 🔍 SEARCH
    search = request.GET.get("search")
    if search:
        reservations = reservations.filter(
            Q(guest__user__username__icontains=search) |
            Q(guest__user__first_name__icontains=search) |
            Q(guest__user__last_name__icontains=search) |
            Q(room__room_number__icontains=search)
        )

    # 🎯 FILTER STATUS
    status = request.GET.get("status")
    if status:
        reservations = reservations.filter(status=status)

    # 📄 PAGINATION
    paginator = Paginator(reservations, 8)  # 8 rows per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "reservations": page_obj,
        "status_choices": Reservation.STATUS_CHOICES,
        "search": search,
        "page_obj": page_obj,
    }
    return render(request, "hotel/admin/manage_reservations.html", context)

@admin_login_required
@admin_login_required
def add_reservation_page(request):
    guests = Guest.objects.select_related("user").all().order_by("user__username")
    rooms = Room.objects.select_related("category").all().order_by("room_number")
    return render(request, "hotel/admin/add-reservations.html", {
        "guests": guests,
        "rooms": rooms,
        "status_choices": Reservation.STATUS_CHOICES,
    })

@admin_login_required
@require_http_methods(["POST"])
def add_reservation(request):
    guest_id = request.POST.get("guest")
    room_id = request.POST.get("room")
    check_in = request.POST.get("check_in_date")
    check_out = request.POST.get("check_out_date")
    number_of_guests = int(request.POST.get("number_of_guests", 1))
    status = request.POST.get("status", "Pending")

    # offline guest fields
    full_name = request.POST.get("offline_full_name", "").strip()
    phone = request.POST.get("offline_phone", "").strip()
    email = request.POST.get("offline_email", "").strip()
    address = request.POST.get("offline_address", "").strip()

    if not room_id or not check_in or not check_out:
        messages.error(request, "Room and dates are required.")
        return redirect("add_reservation_page")

    ci = datetime.strptime(check_in, "%Y-%m-%d").date()
    co = datetime.strptime(check_out, "%Y-%m-%d").date()

    if co <= ci:
        messages.error(request, "Check-out must be after check-in.")
        return redirect("add_reservation_page")

    room = get_object_or_404(Room, id=room_id)

    # prevent double booking
    if Reservation.objects.filter(
        room=room,
        status__in=["Pending", "Confirmed", "Checked In"],
        check_in_date__lt=co,
        check_out_date__gt=ci
    ).exists():
        messages.error(request, "Room already booked for these dates.")
        return redirect("add_reservation_page")

    # determine guest
    if guest_id:
        guest = get_object_or_404(Guest, id=guest_id)
    else:
        if not full_name or not phone:
            messages.error(request, "Offline guest name & phone required.")
            return redirect("add_reservation_page")

        username = full_name.lower().replace(" ", "")
        if User.objects.filter(username=username).exists():
            username += str(User.objects.count() + 1)

        random_password = uuid.uuid4().hex[:20]
        user = User.objects.create_user(
            username=username,
            email=email,
            password=random_password
        )
        user.first_name = full_name
        user.save()

        guest = Guest.objects.create(
            user=user,
            phone=phone,
            address=address or "-"
        )

    reservation = Reservation.objects.create(
        guest=guest,
        room=room,
        check_in_date=ci,
        check_out_date=co,
        number_of_guests=number_of_guests,
        status=status,
        is_online_booking=False,
    )
    reservation.calculate_total_price()
    reservation.save()

    Booking.objects.create(
        user=guest.user,
        reservation=reservation,
        room=room,
        booking_status="Confirmed" if status == "Confirmed" else "Pending",
    )

    messages.success(request, "Reservation created successfully.")
    return redirect("manage_reservations")


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
    reservation = get_object_or_404(Reservation, id=reservation_id)
    new_status = request.POST.get('status')  # ✅ must match template

    if new_status in dict(Reservation.STATUS_CHOICES):
        reservation.status = new_status

        # optional: update room status
        if new_status in ['Checked Out', 'Cancelled']:
            reservation.room.status = 'Available'
            reservation.room.save(update_fields=['status'])
        elif new_status in ['Checked In', 'Confirmed']:
            reservation.room.status = 'Booked'
            reservation.room.save(update_fields=['status'])

        reservation.save(update_fields=['status'])
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

@login_required(login_url='login')
def add_room(request):
    if request.method != "POST":
        return redirect("manage_rooms")

    room_number = request.POST.get("room_number")
    category_id = request.POST.get("category")
    floor = request.POST.get("floor") or 1
    max_occupancy = request.POST.get("max_occupancy") or 2
    status = request.POST.get("status") or "Available"

    price = request.POST.get("price")
    description = request.POST.get("description")
    amenities = request.POST.get("amenities") or "WiFi, AC, TV"

    image = request.FILES.get("image")  # ✅ IMPORTANT

    # validation
    if not room_number or not category_id:
        messages.error(request, "Room number and category are required.")
        return redirect("manage_rooms")

    category = get_object_or_404(RoomCategory, id=category_id)

    # prevent duplicate
    if Room.objects.filter(room_number=room_number).exists():
        messages.error(request, f"Room {room_number} already exists.")
        return redirect("manage_rooms")

    room = Room.objects.create(
        room_number=room_number,
        category=category,
        floor=floor,
        max_occupancy=max_occupancy,
        status=status,
        amenities=amenities,
        description=description,
        image=image,          # ✅ saves image
        price=price or None,  # optional
    )

    messages.success(request, f"Room {room.room_number} added successfully.")
    return redirect("manage_rooms")



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
    try:
        guest = request.user.guest
    except Guest.DoesNotExist:
        guest = None

    bookings = Reservation.objects.filter(guest=guest).order_by('-check_in_date') if guest else []

    room_reviews = RoomRating.objects.filter(user=request.user).select_related("room")
    service_reviews = ServiceRating.objects.filter(user=request.user).select_related("service")

    total_bookings = bookings.count()
    total_nights = sum((b.check_out_date - b.check_in_date).days for b in bookings if b.check_out_date and b.check_in_date) if bookings else 0

    context = {
        'guest': guest,
        'bookings': bookings,
        'room_reviews': room_reviews,
        'service_reviews': service_reviews,
        'total_bookings': total_bookings,
        'total_nights': total_nights,
        'reviews_count': room_reviews.count() + service_reviews.count(),
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
    # Find the user's most recent reservation for this room
    reservation = Reservation.objects.filter(guest__user=request.user, room=room).order_by('-check_out_date').first()
    if not reservation:
        messages.error(request, "No reservation found for you and this room.")
        return redirect('my_reservations')

    if request.method == 'POST':
        rating_val = request.POST.get('rating')
        cleanliness = request.POST.get('cleanliness', 5)
        comfort = request.POST.get('comfort', 5)
        amenities = request.POST.get('amenities', 5)
        review_text = request.POST.get('review', '')

        try:
            RoomRating.objects.create(
                user=request.user,
                room=room,
                reservation=reservation,
                rating=int(rating_val),
                review=review_text,
                cleanliness=int(cleanliness),
                comfort=int(comfort),
                amenities=int(amenities),
            )
            messages.success(request, "Thank you for your review!")
            return redirect('user_profile')
        except Exception as e:
            messages.error(request, f"Error saving review: {str(e)}")

    # provide minimal form context expected by template
    context = {
        'reservation': reservation,
        'room': room,
        'form': {},
    }
    return render(request, 'hotel/html/rate_room.html', context)


@login_required(login_url='login')
def rate_service(request, service_id):
    """Rate a service - only for completed bookings"""
    from .models import ServiceRating, ServiceBooking
    service = get_object_or_404(Service, id=service_id)
    # find most recent COMPLETED service booking for this user & service
    service_booking = ServiceBooking.objects.filter(
        user=request.user, 
        service=service,
        status='Completed'
    ).order_by('-scheduled_date').first()
    
    if not service_booking:
        messages.error(request, "No completed service booking found for you and this service. You can only rate services after they're completed.")
        return redirect('service')

    if request.method == 'POST':
        rating_val = request.POST.get('rating')
        quality = request.POST.get('quality', 5)
        timeliness = request.POST.get('timeliness', 5)
        value_for_money = request.POST.get('value_for_money', 5)
        review_text = request.POST.get('review', '')

        try:
            ServiceRating.objects.create(
                user=request.user,
                service=service,
                service_booking=service_booking,
                rating=int(rating_val),
                review=review_text,
                quality=int(quality),
                timeliness=int(timeliness),
                value_for_money=int(value_for_money),
            )
            messages.success(request, "Thank you for your service review!")
            return redirect('user_profile')
        except Exception as e:
            messages.error(request, f"Error saving service review: {str(e)}")

    context = {
        'service': service,
        'service_booking': service_booking,
        'form': {},
    }
    return render(request, 'hotel/html/rate_service.html', context)


@login_required(login_url='login')
def book_service(request, service_id):
    """Book a service"""
    service = get_object_or_404(Service, id=service_id)
    try:
        guest = request.user.guest
    except Guest.DoesNotExist:
        messages.error(request, "Please complete your profile before booking a service.")
        return redirect('complete_profile')

    if request.method == 'POST':
        form = ServiceBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = request.user
            booking.service = service
            # calculate total price using Decimal to avoid float issues
            booking.total_price = Decimal(service.price) * Decimal(booking.quantity)
            booking.status = 'Pending'
            booking.save()

            # Prepare session for checkout flow (single service booking)
            request.session['checkout_service_booking_ids'] = [booking.id]
            # ensure reservation ids key exists (empty)
            request.session['checkout_reservation_ids'] = []
            request.session['checkout_total'] = float(booking.total_price)

            messages.success(request, f"Service '{service.name}' added to checkout. Please complete payment.")
            return redirect('checkout_payment')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ServiceBookingForm()

    context = {
        'service': service,
        'form': form,
    }
    return render(request, 'hotel/html/book_service.html', context)


@login_required(login_url='login')
@login_required(login_url='login')
def my_service_bookings(request):
    """View user's service bookings"""
    bookings = ServiceBooking.objects.filter(user=request.user).select_related('service', 'reservation').order_by('-booking_date')
    
    # Separate paid and unpaid bookings
    unpaid_bookings = []
    paid_bookings = []
    
    for booking in bookings:
        # Consider booking paid if:
        # 1) it has a direct Payment record with status 'Completed'
        # 2) OR it's attached to a Reservation that has a completed Payment
        is_paid = False
        # check direct payment on the service booking
        try:
            payment = booking.payment
            if payment and payment.payment_status == 'Completed':
                is_paid = True
        except Exception:
            is_paid = False

        # fallback: check payment on linked reservation (some older records may store payment there)
        if not is_paid and booking.reservation and hasattr(booking.reservation, 'payment'):
            try:
                res_pay = booking.reservation.payment
                if res_pay and res_pay.payment_status == 'Completed':
                    is_paid = True
            except Exception:
                is_paid = is_paid

        if is_paid:
            paid_bookings.append(booking)
        else:
            unpaid_bookings.append(booking)
    
    context = {
        'bookings': bookings,
        'unpaid_bookings': unpaid_bookings,
        'paid_bookings': paid_bookings,
    }
    return render(request, 'hotel/html/my_service_bookings.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def update_service_booking(request, booking_id):
    """Update an existing service booking"""
    booking = get_object_or_404(ServiceBooking, id=booking_id, user=request.user)
    
    scheduled_date = request.POST.get('scheduled_date')
    quantity = request.POST.get('quantity')
    notes = request.POST.get('notes')
    
    if scheduled_date:
        booking.scheduled_date = scheduled_date
    if quantity:
        try:
            booking.quantity = int(quantity)
        except (ValueError, TypeError):
            messages.error(request, "Invalid quantity.")
            return redirect('my_service_bookings')
    if notes is not None:
        booking.notes = notes
    
    booking.save()
    messages.success(request, f"Service booking for '{booking.service.name}' updated successfully.")
    return redirect('my_service_bookings')


@admin_login_required
def manage_service_bookings(request):
    """Admin: Manage all service bookings"""
    bookings = ServiceBooking.objects.select_related('user', 'service', 'reservation').all().order_by('-booking_date')[:500]

    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        bookings = bookings.filter(status=status_filter)

    # Optional filter by service id (from manage_services quick-link)
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


@login_required(login_url='login')
@require_http_methods(["POST"])
def cancel_service_booking(request, booking_id):
    """User or Admin: Cancel a service booking"""
    booking = get_object_or_404(ServiceBooking, id=booking_id)
    service_name = booking.service.name
    
    # Check if user is authorized (either owner or admin)
    is_owner = request.user == booking.user
    is_admin = hasattr(request.user, 'userprofile') and request.user.userprofile.role == 'Admin'
    
    if not (is_owner or is_admin):
        messages.error(request, "You don't have permission to cancel this booking.")
        return redirect('my_service_bookings')
    
    booking.status = 'Cancelled'
    booking.save()
    messages.success(request, f"Service booking for '{service_name}' has been cancelled.")
    
    # Redirect based on user role/context
    if is_owner and not is_admin:
        return redirect('my_service_bookings')
    else:
        return redirect('manage_service_bookings')

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
                    # Check if image already exists for this position
                    existing_image = RoomImage.objects.filter(room=room, order=i).first()
                    if existing_image:
                        existing_image.image = image_file
                        existing_image.alt_text = alt_text
                        existing_image.save()
                    else:
                        # Create new image
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
@admin_login_required
@admin_login_required
def add_user(request):
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
    
    # GET request - redirect to manage_users
    return redirect('manage_users')


@login_required
@admin_login_required
def manage_reviews(request):
    room_reviews = RoomRating.objects.select_related("user", "room", "reservation").all()
    service_reviews = ServiceRating.objects.select_related("user", "service", "service_booking").all()
    
    # Combine both querysets and sort by created_at descending
    combined_reviews = list(room_reviews) + list(service_reviews)
    combined_reviews.sort(key=lambda x: x.created_at, reverse=True)

    # only show reservations that are Checked Out (recommended)
    reservations = Reservation.objects.select_related("guest__user", "room").filter(status="Checked Out").order_by("-booking_date")

    return render(request, "hotel/admin/manage_reviews.html", {
        "reviews": combined_reviews,
        "reservations": reservations,
    })


@login_required
@admin_login_required
def add_room_review_admin(request):
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

        # prevent duplicate (your model unique_together: user + reservation)
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


@login_required
@admin_login_required
def delete_review(request, review_id):
    r = get_object_or_404(RoomRating, id=review_id)
    if request.method == "POST":
        r.delete()
        messages.success(request, "Review deleted.")
    return redirect("manage_reviews")


@login_required
@admin_login_required
def edit_review(request, review_id):
    r = get_object_or_404(RoomRating, id=review_id)

    if request.method == "POST":
        r.rating = int(request.POST.get("rating", r.rating))
        r.review = request.POST.get("review", r.review)
        r.cleanliness = int(request.POST.get("cleanliness", r.cleanliness))
        r.comfort = int(request.POST.get("comfort", r.comfort))
        r.amenities = int(request.POST.get("amenities", r.amenities))
        
        try:
            r.save()
            messages.success(request, "Review updated successfully.")
            return redirect("manage_reviews")
        except Exception as e:
            messages.error(request, f"Error updating review: {str(e)}")
            return redirect("manage_reviews")

    context = {'r': r}
    return render(request, "hotel/admin/edit_review.html", context)


@login_required(login_url='login')
def edit_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)

    if request.method == "POST":
        reservation.guest_id = request.POST.get("guest")
        reservation.room_id = request.POST.get("room")
        reservation.check_in_date = request.POST.get("check_in_date")
        reservation.check_out_date = request.POST.get("check_out_date")
        reservation.number_of_guests = request.POST.get("number_of_guests")
        reservation.status = request.POST.get("status")

        reservation.save()
        messages.success(request, "Reservation updated successfully.")
        return redirect("manage_reservations")

    context = {
        "reservation": reservation,
        "guests": Guest.objects.all(),
        "rooms": Room.objects.all(),
        "status_choices": Reservation.STATUS_CHOICES,
    }
    return render(request, "hotel/admin/edit_reservation.html", context)


# ===== CART VIEWS =====
# 
# HOTEL BOOKING 8-STEP PROCESS:
# =============================
# Step 1️⃣: Browse Items - User explores rooms/services (room_list, room_detail, service_view)
# Step 2️⃣: Add to Cart - User adds items to temporary storage (add_room_to_cart, add_service_to_cart)
# Step 3️⃣: View Cart - User reviews selected items (view_cart)
# Step 4️⃣: Checkout - System converts cart to orders (checkout) → Creates reservations/bookings
# Step 5️⃣: Select Payment Method - User chooses payment type (checkout_payment GET)
# Step 6️⃣: Process Payment - Transaction executed (checkout_payment POST)
# Step 7️⃣: Payment Confirmation - Success page shown (payment_success.html)
# Step 8️⃣: Booking Completion - Orders finalized, cart cleared, confirmations sent
#

@login_required(login_url='login')
def view_cart(request):
    """
    STEP 3️⃣: VIEW CART - Review Cart Items
    
    User reviews their selected rooms and services before checkout.
    Can modify quantities or remove items.
    Shows order summary with total amount.
    """
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    # Get pending reservations for the user
    pending_reservations = None
    try:
        guest = request.user.guest
        pending_reservations = guest.reservations.exclude(payment__payment_status__in=['Completed', 'Refunded'])
    except:
        pending_reservations = None
    
    context = {
        'cart': cart,
        'cart_items': cart.items.all(),
        'total_price': cart.get_total_price(),
        'pending_reservations': pending_reservations,
    }
    return render(request, 'hotel/html/cart.html', context)


@login_required(login_url='login')
def add_room_to_cart(request, room_id):
    """
    STEP 2️⃣: ADD ROOM TO CART
    
    Saves room with check-in/check-out dates to cart.
    Validates date range and availability.
    Stores in Cart/CartItem for logged-in user.
    """
    if request.method == 'POST':
        room = get_object_or_404(Room, id=room_id)
        check_in = request.POST.get('check_in_date')
        check_out = request.POST.get('check_out_date')
        guests = request.POST.get('number_of_guests', 1)
        
        if not check_in or not check_out:
            messages.error(request, 'Please select check-in and check-out dates.')
            return redirect('room_detail', room_id=room_id)
        
        try:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            
            if check_out_date <= check_in_date:
                messages.error(request, 'Check-out date must be after check-in date.')
                return redirect('room_detail', room_id=room_id)
            
            cart, created = Cart.objects.get_or_create(user=request.user)
            CartItem.objects.create(
                cart=cart,
                item_type='Room',
                room=room,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                number_of_guests=int(guests),
            )
            
            messages.success(request, f'{room.room_number} added to cart!')
            return redirect('view_cart')
        except Exception as e:
            messages.error(request, f'Error adding room to cart: {str(e)}')
            return redirect('room_detail', room_id=room_id)
    
    return redirect('room_detail', room_id=room_id)


@login_required(login_url='login')
def add_service_to_cart(request, service_id):
    """
    STEP 2️⃣: ADD SERVICE TO CART
    
    Saves service with quantity and schedule to cart.
    Validates quantity is positive.
    Stores in Cart/CartItem for logged-in user.
    """
    if request.method == 'POST':
        service = get_object_or_404(Service, id=service_id)
        quantity = int(request.POST.get('quantity', 1))
        scheduled_date = request.POST.get('scheduled_date')
        
        if quantity < 1:
            messages.error(request, 'Quantity must be at least 1.')
            return redirect('book_service', service_id=service_id)
        
        try:
            if scheduled_date:
                scheduled_date = datetime.strptime(scheduled_date, '%Y-%m-%d %H:%M')
            
            cart, created = Cart.objects.get_or_create(user=request.user)
            CartItem.objects.create(
                cart=cart,
                item_type='Service',
                service=service,
                service_quantity=quantity,
                scheduled_date=scheduled_date if scheduled_date else None,
            )
            
            messages.success(request, f'{service.name} added to cart!')
            return redirect('view_cart')
        except Exception as e:
            messages.error(request, f'Error adding service to cart: {str(e)}')
            return redirect('book_service', service_id=service_id)
    
    return redirect('book_service', service_id=service_id)


@login_required(login_url='login')
def remove_from_cart(request, item_id):
    """
    STEP 3️⃣: REMOVE ITEM FROM CART (Variation)
    
    Allows user to remove item from cart while reviewing.
    User stays on cart view after deletion.
    """
    cart = get_object_or_404(Cart, user=request.user)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
    messages.success(request, 'Item removed from cart.')
    return redirect('view_cart')


@login_required(login_url='login')
@require_http_methods(["POST"])
def update_cart_item_quantity(request, item_id):
    """
    STEP 3️⃣: UPDATE ITEM QUANTITY (Variation)
    
    Allows user to modify quantity of services in cart.
    For services: increase/decrease quantity
    For rooms: update number of guests or dates
    Returns JSON response for AJAX or redirects back to cart
    """
    cart = get_object_or_404(Cart, user=request.user)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    
    try:
        # For Services: Update service_quantity
        if item.item_type == 'Service':
            quantity = request.POST.get('quantity')
            action = request.POST.get('action')  # 'increment', 'decrement', or 'set'
            
            if action == 'increment':
                item.service_quantity += 1
            elif action == 'decrement':
                if item.service_quantity > 1:
                    item.service_quantity -= 1
                else:
                    messages.warning(request, 'Quantity cannot be less than 1.')
                    return redirect('view_cart')
            elif action == 'set' and quantity:
                qty = int(quantity)
                if qty < 1:
                    messages.error(request, 'Quantity must be at least 1.')
                    return redirect('view_cart')
                item.service_quantity = qty
            
            item.save()
            messages.success(request, 'Service quantity updated.')
        
        # For Rooms: Update number_of_guests or dates
        elif item.item_type == 'Room':
            action = request.POST.get('action')

            # Some forms in the template send simple 'increment'/'decrement' actions
            # with a marker `guest_action` when adjusting guests. Support those.
            if request.POST.get('guest_action'):
                if action == 'increment':
                    if item.number_of_guests < item.room.max_occupancy:
                        item.number_of_guests = (item.number_of_guests or 1) + 1
                        item.save()
                        messages.success(request, f'Updated to {item.number_of_guests} guest(s).')
                    else:
                        messages.error(request, f'Room capacity is {item.room.max_occupancy} guests.')
                        return redirect('view_cart')
                elif action == 'decrement':
                    if (item.number_of_guests or 1) > 1:
                        item.number_of_guests = (item.number_of_guests or 1) - 1
                        item.save()
                        messages.success(request, f'Updated to {item.number_of_guests} guest(s).')
                    else:
                        messages.warning(request, 'Number of guests cannot be less than 1.')
                        return redirect('view_cart')
                elif action == 'set':
                    guests = request.POST.get('number_of_guests')
                    if guests:
                        guests_int = int(guests)
                        if guests_int < 1:
                            messages.error(request, 'Number of guests must be at least 1.')
                            return redirect('view_cart')
                        if guests_int > item.room.max_occupancy:
                            messages.error(request, f'Room capacity is {item.room.max_occupancy} guests.')
                            return redirect('view_cart')
                        item.number_of_guests = guests_int
                        item.save()
                        messages.success(request, f'Updated to {guests_int} guest(s).')

            # Backwards-compatible explicit update action
            elif action == 'update_guests':
                guests = request.POST.get('number_of_guests')
                if guests:
                    guests_int = int(guests)
                    if guests_int < 1:
                        messages.error(request, 'Number of guests must be at least 1.')
                        return redirect('view_cart')
                    if guests_int > item.room.max_occupancy:
                        messages.error(request, f'Room capacity is {item.room.max_occupancy} guests.')
                        return redirect('view_cart')
                    item.number_of_guests = guests_int
                    item.save()
                    messages.success(request, f'Updated to {guests_int} guest(s).')

            elif action == 'update_dates':
                check_in = request.POST.get('check_in_date')
                check_out = request.POST.get('check_out_date')

                if check_in and check_out:
                    check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
                    check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()

                    if check_out_date <= check_in_date:
                        messages.error(request, 'Check-out date must be after check-in date.')
                        return redirect('view_cart')

                    item.check_in_date = check_in_date
                    item.check_out_date = check_out_date
                    item.save()
                    messages.success(request, 'Room dates updated.')
        
        # Return JSON if AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'item_total': float(item.get_item_total()),
                'cart_total': float(cart.get_total_price()),
            })
        
        return redirect('view_cart')
    except (ValueError, TypeError) as e:
        messages.error(request, 'Invalid input.')
        return redirect('view_cart')


@login_required(login_url='login')
def checkout(request):
    """
    STEP 4️⃣: CHECKOUT - Verify Cart & Redirect
    
    Checks cart exists and redirects to confirm_information.
    
    Flow: Cart → Confirm Information
    """
    cart = get_object_or_404(Cart, user=request.user)
    
    if not cart.items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('view_cart')
    
    if request.method == 'POST':
        # Redirect to confirmation form
        return redirect('confirm_information')
    
    context = {
        'cart': cart,
        'cart_items': cart.items.all(),
        'total_price': cart.get_total_price(),
    }
    return render(request, 'hotel/html/checkout.html', context)


@login_required(login_url='login')
def confirm_information(request):
    """
    STEP 4.5️⃣: CONFIRM INFORMATION - Collect User Details
    
    Shows form for user to confirm personal and address information.
    On submission:
    - Creates Reservation objects for rooms (status: Pending)
    - Creates ServiceBooking objects for services (status: Pending)
    - Stores booking IDs in session
    - Clears cart
    - Redirects to checkout_payment
    
    Flow: Confirm Info (GET show form) → (POST create reservations) → Payment
    """
    cart = get_object_or_404(Cart, user=request.user)
    
    if not cart.items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('view_cart')
    
    if request.method == 'POST':
        try:
            # Get form data
            full_name = request.POST.get('full_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            country = request.POST.get('country', '').strip()
            address = request.POST.get('address', '').strip()
            city = request.POST.get('city', '').strip()
            state = request.POST.get('state', '').strip()
            postal_code = request.POST.get('postal_code', '').strip()
            special_requests = request.POST.get('special_requests', '').strip()
            
            # Validate required fields
            if not all([full_name, email, phone, country, address, city, state, postal_code]):
                messages.error(request, 'All required fields must be filled.')
                return redirect('confirm_information')
            
            # Update user's guest profile
            try:
                guest = request.user.guest
            except Guest.DoesNotExist:
                guest = Guest.objects.create(user=request.user)
            
            # Update user's first/last name
            names = full_name.split(' ', 1)
            request.user.first_name = names[0]
            request.user.last_name = names[1] if len(names) > 1 else ''
            request.user.email = email
            request.user.save()
            
            # Update guest profile with address/contact info
            if hasattr(guest, 'phone_number'):
                guest.phone_number = phone
            if hasattr(guest, 'country'):
                guest.country = country
            if hasattr(guest, 'address'):
                guest.address = address
            if hasattr(guest, 'city'):
                guest.city = city
            if hasattr(guest, 'state_province'):
                guest.state_province = state
            if hasattr(guest, 'postal_code'):
                guest.postal_code = postal_code
            guest.save()
            
            # Create reservations for room items
            room_items = cart.items.filter(item_type='Room')
            reservations = []
            total_amount = 0
            
            for item in room_items:
                reservation = Reservation.objects.create(
                    guest=guest,
                    room=item.room,
                    check_in_date=item.check_in_date,
                    check_out_date=item.check_out_date,
                    number_of_guests=item.number_of_guests,
                    special_requests=special_requests,
                    status='Pending',
                    is_online_booking=True,
                )
                reservation.calculate_total_price()
                reservation.save()
                reservations.append(reservation)
                total_amount += reservation.total_price
            
            # Create service bookings for service items
            service_items = cart.items.filter(item_type='Service')
            service_bookings = []
            
            for item in service_items:
                service_booking = ServiceBooking.objects.create(
                    user=request.user,
                    service=item.service,
                    quantity=item.service_quantity,
                    total_price=item.service.price * item.service_quantity,
                    scheduled_date=item.scheduled_date if item.scheduled_date else timezone.now(),
                    status='Pending',
                )
                service_bookings.append(service_booking)
                total_amount += service_booking.total_price
            
            # Store checkout info in session
            request.session['checkout_reservation_ids'] = [r.id for r in reservations]
            request.session['checkout_service_booking_ids'] = [sb.id for sb in service_bookings]
            request.session['checkout_total'] = str(total_amount)
            
            # Clear the cart
            cart.items.all().delete()
            
            messages.success(request, 'Information confirmed. Proceed to payment.')
            # Redirect to payment with all reservations and service bookings
            return render(request, 'hotel/html/payment.html', {
                'reservations': reservations,
                'service_bookings': service_bookings,
                'total_amount': total_amount,
                'multiple_items': True,
            })
        
        except Exception as e:
            messages.error(request, f'Error during confirmation: {str(e)}')
            return redirect('confirm_information')
    
    # GET request - show form
    # Build full name from user
    full_name = f"{request.user.first_name} {request.user.last_name}".strip()
    
    try:
        guest = request.user.guest
        context = {
            'cart_items': cart.items.all(),
            'total_price': cart.get_total_price(),
            'full_name': full_name,
            'email': request.user.email,
            'phone': getattr(guest, 'phone_number', ''),
            'country': getattr(guest, 'country', ''),
            'address': getattr(guest, 'address', ''),
            'city': getattr(guest, 'city', ''),
            'state': getattr(guest, 'state_province', ''),
            'postal_code': getattr(guest, 'postal_code', ''),
            'special_requests': '',
        }
    except Guest.DoesNotExist:
        context = {
            'cart_items': cart.items.all(),
            'total_price': cart.get_total_price(),
            'full_name': full_name,
            'email': request.user.email,
            'phone': '',
            'country': '',
            'address': '',
            'city': '',
            'state': '',
            'postal_code': '',
            'special_requests': '',
        }
    
    return render(request, 'hotel/html/confirm_information.html', context)


@login_required(login_url='login')
def checkout_payment(request):
    """
    STEP 5️⃣ + STEP 6️⃣: SELECT PAYMENT METHOD & PROCESS PAYMENT
    
    GET Request (Step 5): Shows payment method selection form
    - User can choose: Cash, Card, Bank Transfer, Online
    - Displays order summary with all items and total
    
    POST Request (Step 6): Processes payment
    - Creates Payment objects for each reservation
    - Marks payment status as 'Completed'
    - Sets transaction ID and timestamp
    - Updates reservation status to 'Confirmed'
    - Creates Booking records
    - Confirms ServiceBookings
    - Clears session data
    - Redirects to payment_success view
    
    Flow: Select Method → Process → Confirm Payment
    """
    # Get reservation and service booking IDs from session
    reservation_ids = request.session.get('checkout_reservation_ids', [])
    service_booking_ids = request.session.get('checkout_service_booking_ids', [])
    
    if not reservation_ids and not service_booking_ids:
        messages.error(request, 'No items found for payment. Please start from cart.')
        return redirect('view_cart')
    
    # Get all reservations and service bookings
    reservations = Reservation.objects.filter(id__in=reservation_ids, guest__user=request.user)
    service_bookings = ServiceBooking.objects.filter(id__in=service_booking_ids, user=request.user)
    
    if not reservations.exists() and not service_bookings.exists():
        messages.error(request, 'No valid bookings found.')
        return redirect('view_cart')
    
    # Calculate total
    total_amount = sum(r.total_price for r in reservations) + sum(sb.total_price for sb in service_bookings)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'Cash')
        
        try:
            # Process payment for each reservation
            for reservation in reservations:
                payment_obj, _ = Payment.objects.get_or_create(
                    reservation=reservation,
                    defaults={
                        'amount': reservation.total_price,
                        'payment_method': payment_method,
                        'payment_status': 'Pending',
                    }
                )
                
                # Mark as completed
                payment_obj.payment_status = 'Completed'
                payment_obj.payment_date = timezone.now()
                payment_obj.transaction_id = f"TXN-{reservation.id}-{int(datetime.now().timestamp())}"
                payment_obj.payment_method = payment_method
                payment_obj.save()
                
                # Confirm reservation
                reservation.status = 'Confirmed'
                reservation.save(update_fields=['status'])
                
                # Create booking record
                booking, created = Booking.objects.get_or_create(
                    reservation=reservation,
                    defaults={
                        'user': request.user,
                        'room': reservation.room,
                        'booking_status': 'Confirmed',
                        'confirmation_number': f"BK-{reservation.id}-{int(datetime.now().timestamp())}",
                    }
                )
                if not created:
                    booking.booking_status = 'Confirmed'
                    booking.save()
            
            # Process payment for each service booking
            for service_booking in service_bookings:
                payment_obj, _ = Payment.objects.get_or_create(
                    service_booking=service_booking,
                    defaults={
                        'amount': service_booking.total_price,
                        'payment_method': payment_method,
                        'payment_status': 'Pending',
                    }
                )
                
                # Mark as completed
                payment_obj.payment_status = 'Completed'
                payment_obj.payment_date = timezone.now()
                payment_obj.transaction_id = f"SVC-{service_booking.id}-{int(datetime.now().timestamp())}"
                payment_obj.payment_method = payment_method
                payment_obj.save()
                
                # Confirm service booking
                service_booking.status = 'Confirmed'
                service_booking.save()
            
            # Clear session
            if 'checkout_reservation_ids' in request.session:
                del request.session['checkout_reservation_ids']
            if 'checkout_service_booking_ids' in request.session:
                del request.session['checkout_service_booking_ids']
            if 'checkout_total' in request.session:
                del request.session['checkout_total']
            
            messages.success(request, 'Payment completed successfully! Your bookings are confirmed.')
            return render(request, 'hotel/html/payment_success.html', {
                'reservations': reservations,
                'service_bookings': service_bookings,
                'total_amount': total_amount,
            })
        
        except Exception as e:
            messages.error(request, f'Error processing payment: {str(e)}')
            return redirect('view_cart')
    
    return render(request, 'hotel/html/payment.html', {
        'reservations': reservations,
        'service_bookings': service_bookings,
        'total_amount': total_amount,
        'multiple_items': True,
    })


@login_required(login_url='login')
def service_payment(request, booking_id):
    """Initiate payment flow for a single ServiceBooking by setting session and redirecting to checkout."""
    booking = get_object_or_404(ServiceBooking, id=booking_id, user=request.user)

    # Set session keys expected by checkout_payment
    request.session['checkout_service_booking_ids'] = [booking.id]
    # Clear reservation ids for this flow
    request.session['checkout_reservation_ids'] = []
    try:
        request.session['checkout_total'] = float(booking.total_price)
    except Exception:
        request.session['checkout_total'] = None

    return redirect('checkout_payment')


@login_required(login_url='login')
@require_http_methods(["POST"])
def payment_process(request):
    """
    STEP 5️⃣: PROCESS PAYMENT - From Confirm Information
    
    Handles payment form submission from confirm_information flow.
    Creates Payment objects, marks as completed, and redirects to success.
    
    Flow: Payment Form POST → Payment Objects Created → Success Page
    """
    try:
        payment_method = request.POST.get('payment_method', 'Card').strip()
        
        # Get reservation and service booking IDs from session
        reservation_ids = request.session.get('checkout_reservation_ids', [])
        service_booking_ids = request.session.get('checkout_service_booking_ids', [])
        
        if not reservation_ids and not service_booking_ids:
            messages.error(request, 'No bookings found. Please start over.')
            return redirect('view_cart')
        
        # Get all reservations and service bookings
        reservations = Reservation.objects.filter(id__in=reservation_ids, guest__user=request.user)
        service_bookings = ServiceBooking.objects.filter(id__in=service_booking_ids, user=request.user)
        
        if not reservations.exists() and not service_bookings.exists():
            messages.error(request, 'No bookings found.')
            return redirect('view_cart')
        
        # Create Payment objects for reservations
        for reservation in reservations:
            payment_obj, created = Payment.objects.get_or_create(
                reservation=reservation,
                defaults={
                    'amount': reservation.total_price,
                    'payment_method': payment_method,
                    'payment_status': 'Completed',
                    'transaction_id': f"TXN-{reservation.id}-{timezone.now().timestamp()}",
                }
            )
            if created:
                payment_obj.save()
            else:
                payment_obj.payment_method = payment_method
                payment_obj.payment_status = 'Completed'
                payment_obj.transaction_id = f"TXN-{reservation.id}-{timezone.now().timestamp()}"
                payment_obj.save()
            
            # Update reservation status to Confirmed
            reservation.status = 'Confirmed'
            reservation.save()
            
            # Create Booking record
            Booking.objects.get_or_create(
                reservation=reservation,
                defaults={
                    'user': request.user,
                    'room': reservation.room,
                    'booking_status': 'Confirmed',
                }
            )
        
        # Confirm service bookings
        for service_booking in service_bookings:
            service_booking.status = 'Confirmed'
            service_booking.save()
        
        # Clear session data
        if 'checkout_reservation_ids' in request.session:
            del request.session['checkout_reservation_ids']
        if 'checkout_service_booking_ids' in request.session:
            del request.session['checkout_service_booking_ids']
        if 'checkout_total' in request.session:
            del request.session['checkout_total']
        
        total_amount = sum(r.total_price for r in reservations) + sum(sb.total_price for sb in service_bookings)
        
        messages.success(request, 'Payment completed successfully! Your bookings are confirmed.')
        return render(request, 'hotel/html/payment_success.html', {
            'reservations': reservations,
            'service_bookings': service_bookings,
            'total_amount': total_amount,
        })
    
    except Exception as e:
        messages.error(request, f'Error processing payment: {str(e)}')
        return redirect('view_cart')


# ===== API ENDPOINTS =====
@admin_login_required
def api_pending_bookings(request):
    """API endpoint to get count of pending bookings"""
    pending_room_bookings = Reservation.objects.filter(status='Pending').count()
    pending_service_bookings = ServiceBooking.objects.filter(status='Pending').count()
    pending_count = pending_room_bookings + pending_service_bookings
    return JsonResponse({'pending_count': pending_count})


@admin_login_required
def api_all_bookings(request):
    """API endpoint to get all pending and confirmed bookings"""
    # Pending bookings
    pending_room_bookings = Reservation.objects.filter(status='Pending').select_related('guest__user', 'room__category').values(
        'id', 'guest__user__first_name', 'guest__user__last_name', 'room__room_number', 
        'room__category__category_name', 'check_in_date', 'status'
    ).order_by('-booking_date')[:5]
    
    pending_service_bookings = ServiceBooking.objects.filter(status='Pending').select_related('user', 'service').values(
        'id', 'user__first_name', 'user__last_name', 'service__name', 'scheduled_date', 'status'
    ).order_by('-booking_date')[:5]
    
    # Confirmed bookings from last 7 days
    seven_days_ago = timezone.now() - timedelta(days=7)
    confirmed_room_bookings = Reservation.objects.filter(status='Confirmed', booking_date__gte=seven_days_ago).select_related('guest__user', 'room__category').values(
        'id', 'guest__user__first_name', 'guest__user__last_name', 'room__room_number', 
        'room__category__category_name', 'check_in_date', 'status'
    ).order_by('-booking_date')[:5]
    
    confirmed_service_bookings = ServiceBooking.objects.filter(status='Confirmed', booking_date__gte=seven_days_ago).select_related('user', 'service').values(
        'id', 'user__first_name', 'user__last_name', 'service__name', 'scheduled_date', 'status'
    ).order_by('-booking_date')[:5]
    
    total_pending = Reservation.objects.filter(status='Pending').count() + ServiceBooking.objects.filter(status='Pending').count()
    total_confirmed = Reservation.objects.filter(status='Confirmed', booking_date__gte=seven_days_ago).count() + ServiceBooking.objects.filter(status='Confirmed', booking_date__gte=seven_days_ago).count()
    
    return JsonResponse({
        'pending_room_bookings': list(pending_room_bookings),
        'pending_service_bookings': list(pending_service_bookings),
        'confirmed_room_bookings': list(confirmed_room_bookings),
        'confirmed_service_bookings': list(confirmed_service_bookings),
        'total_pending': total_pending,
        'total_confirmed': total_confirmed,
        'total': total_pending + total_confirmed,
    })



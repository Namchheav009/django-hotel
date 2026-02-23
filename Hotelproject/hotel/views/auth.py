"""
Authentication Views
- Login, Registration, Logout
- Profile Management, Password Changes
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
from django.urls import reverse

from hotel.models import Guest, UserProfile, Reservation
from hotel.forms import CustomUserCreationForm, GuestForm


@ensure_csrf_cookie
def login_view(request):
    """User login view"""
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

    return render(request, 'hotel/login&register/login.html')


@ensure_csrf_cookie
def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('guest_home')
    
    form = CustomUserCreationForm()
    guest_form = GuestForm()
    
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
    
    # Ensure a CSRF token is generated server-side and passed to the template
    csrf_token_value = get_token(request)
    return render(request, 'hotel/login&register/register.html', {
        'form': form,
        'guest_form': guest_form,
        'csrf_token_value': csrf_token_value,
    })


def logout_view(request):
    """User logout view"""
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


@login_required(login_url='login')
def user_profile(request):
    """View user profile and bookings"""
    try:
        guest = request.user.guest
    except Guest.DoesNotExist:
        guest = None

    from hotel.models import RoomRating, ServiceRating, ServiceBooking

    bookings = Reservation.objects.filter(guest=guest).order_by('-check_in_date') if guest else []

    room_reviews = RoomRating.objects.filter(user=request.user).select_related("room")
    service_reviews = ServiceRating.objects.filter(user=request.user).select_related("service")

    # user's service bookings
    service_bookings = ServiceBooking.objects.filter(user=request.user).select_related('service', 'reservation').order_by('-booking_date')

    total_bookings = bookings.count()
    total_service_bookings = service_bookings.count()
    total_nights = sum((b.check_out_date - b.check_in_date).days for b in bookings if b.check_out_date and b.check_in_date) if bookings else 0

    # set of room ids already reviewed by the user (prevent duplicate review links)
    reviewed_rooms = set(room_reviews.values_list('room_id', flat=True))

    # allow caller to request a specific tab via query parameter
    active_tab = request.GET.get('tab', 'profile')
    if active_tab not in ('profile', 'bookings', 'reviews', 'settings'):
        active_tab = 'profile'

    context = {
        'guest': guest,
        'bookings': bookings,
        'service_bookings': service_bookings,
        'room_reviews': room_reviews,
        'service_reviews': service_reviews,
        'total_bookings': total_bookings,
        'total_nights': total_nights,
        'total_service_bookings': total_service_bookings,
        'reviews_count': room_reviews.count() + service_reviews.count(),
        'active_tab': active_tab,
        'reviewed_rooms': reviewed_rooms,
    }
    return render(request, 'hotel/html/user_profile.html', context)


@login_required(login_url='login')
def update_profile(request):
    """Update user profile"""
    if request.method == 'POST':
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
        return redirect(f"{reverse('user_profile')}?tab=profile")
    
    return redirect('user_profile')


@login_required(login_url='login')
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
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
        # keep the settings tab open after changing password
        return redirect(f"{reverse('user_profile')}?tab=settings")
    
    return redirect('user_profile')

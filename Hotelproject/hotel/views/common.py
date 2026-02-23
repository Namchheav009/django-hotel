"""
Common Views
- Home, About, Contact, Room Browsing
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from hotel.models import Room, RoomCategory, Guest, Reservation, Service
from hotel.forms import RoomFilterForm, ContactForm


def guest_home(request):
    """Home page showing featured rooms and services"""
    # Redirect to admin dashboard if user is admin
    if request.user.is_authenticated:
        from hotel.models import UserProfile
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


def room_list(request):
    """Browse available rooms with filters"""
    from django.db.models import Q
    
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
            continue
    
    # template expects string ids for membership checks
    selected_categories_str = [str(x) for x in selected_categories]
    
    if form.is_valid():
        check_in = form.cleaned_data.get('check_in_date')
        check_out = form.cleaned_data.get('check_out_date')
        category = form.cleaned_data.get('category')
        max_price = form.cleaned_data.get('max_price')
        guests = form.cleaned_data.get('guests')
        
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
            rooms = rooms.filter(price__lte=max_price)

        # Filter by requested number of guests
        if guests:
            try:
                g = int(guests)
                if g > 0:
                    rooms = rooms.filter(max_occupancy__gte=g)
            except (ValueError, TypeError):
                pass
    
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

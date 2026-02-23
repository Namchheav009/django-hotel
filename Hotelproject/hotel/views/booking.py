"""
Booking/Reservation Views
- Room booking, reservations management
- Check-in/check-out, cancellations
"""

import uuid
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator

from hotel.models import Room, Reservation, Guest, Booking, RoomRating, Payment
from hotel.forms import ReservationForm


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
        reservations = guest.reservations.select_related("room", "room__category").all()

        # which reservations already reviewed by this user
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


# ===== ADMIN RESERVATION VIEWS =====
from hotel.views.admin import admin_login_required


@admin_login_required
@login_required(login_url='login')
def manage_reservations(request):
    """Manage all reservations (admin)"""
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
def add_reservation_page(request):
    """Show form to add reservation (admin)"""
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
    """Add a new reservation (admin)"""
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
        if request.user.objects.filter(username=username).exists():
            username += str(request.user.objects.count() + 1)

        random_password = uuid.uuid4().hex[:20]
        from django.contrib.auth.models import User
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
@login_required(login_url='login')
def edit_reservation(request, reservation_id):
    """Edit a reservation"""
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


@admin_login_required
@require_http_methods(["POST"])
def update_reservation_status(request, reservation_id):
    """Update reservation status (admin)"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    new_status = request.POST.get('status')

    if new_status in dict(Reservation.STATUS_CHOICES):
        reservation.status = new_status

        # optional: update room status and associated Booking record
        if new_status in ['Checked Out', 'Cancelled']:
            reservation.room.status = 'Available'
            reservation.room.save(update_fields=['status'])
            # mark booking complete or cancelled
            try:
                book = reservation.booking
                book.booking_status = 'Completed' if new_status == 'Checked Out' else 'Cancelled'
                book.save(update_fields=['booking_status'])
            except Exception:
                pass
        elif new_status in ['Checked In', 'Confirmed']:
            reservation.room.status = 'Booked'
            reservation.room.save(update_fields=['status'])
            try:
                book = reservation.booking
                book.booking_status = 'Confirmed'
                book.save(update_fields=['booking_status'])
            except Exception:
                pass

        reservation.save(update_fields=['status'])
        messages.success(request, f"Reservation status updated to {new_status}.")
    else:
        messages.error(request, "Invalid status.")

    return redirect('manage_reservations')


@admin_login_required
@require_http_methods(["POST"])
def delete_reservation(request, reservation_id):
    """Delete a reservation (admin)"""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    try:
        reservation.delete()
        messages.success(request, f'Reservation #{reservation_id} deleted.')
    except Exception as e:
        messages.error(request, f'Error deleting reservation: {str(e)}')
    return redirect('manage_reservations')

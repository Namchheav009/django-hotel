"""
Service Views
- Service booking, reviews
- Service booking management
"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from hotel.models import Service, ServiceBooking, Guest
from hotel.forms import ServiceBookingForm


def service_view(request):
    """Services page"""
    services = Service.objects.filter(is_active=True)
    return render(request, 'hotel/html/service.html', {'services': services})


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
def my_service_bookings(request):
    """View user's service bookings"""
    bookings = ServiceBooking.objects.filter(user=request.user).select_related('service', 'reservation').order_by('-booking_date')
    
    # Separate paid and unpaid bookings
    unpaid_bookings = []
    paid_bookings = []
    
    for booking in bookings:
        is_paid = False
        # check direct payment on the service booking
        try:
            payment = booking.payment
            if payment and payment.payment_status == 'Completed':
                is_paid = True
        except Exception:
            is_paid = False

        # fallback: check payment on linked reservation
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

    # don't allow edits if payment already completed
    is_paid = False
    if hasattr(booking, 'payment') and booking.payment:
        if booking.payment.payment_status == 'Completed':
            is_paid = True
    # fallback to reservation payment for older records
    if not is_paid and booking.reservation and hasattr(booking.reservation, 'payment'):
        res_pay = booking.reservation.payment
        if res_pay and res_pay.payment_status == 'Completed':
            is_paid = True

    if is_paid:
        messages.info(request, "Cannot modify a service booking that has already been paid.")
        return redirect('my_service_bookings')

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
        # update price when quantity changes
        try:
            booking.total_price = booking.service.price * booking.quantity
        except Exception:
            pass
    if notes is not None:
        booking.notes = notes
    
    booking.save()
    messages.success(request, f"Service booking for '{booking.service.name}' updated successfully.")
    return redirect('my_service_bookings')


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
        from hotel.views.admin import admin_login_required
        return redirect('manage_service_bookings')

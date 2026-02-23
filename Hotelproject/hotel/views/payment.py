"""
Payment and Checkout Views
- Payment processing, checkout flow
- Multiple item payment handling
"""

import uuid
from datetime import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from hotel.models import (
    Reservation, Payment, Guest, ServiceBooking, Service, Booking, Cart, CartItem
)


@login_required(login_url='login')
def payment(request, reservation_id=None):
    """
    Process payment for single reservation
    - Legacy flow for individual reservations
    """
    # Single reservation flow
    reservation = get_object_or_404(Reservation, id=reservation_id)

    # ✅ permission check
    if reservation.guest.user != request.user:
        messages.error(request, "You don't have permission to access this reservation.")
        return redirect('my_reservations')

    # ✅ already paid
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
                    "transaction_id": f"TXN-{reservation.id}-{uuid.uuid4().hex[:10]}"
                }
            )
            
            if payment_obj.payment_status != "Completed":
                payment_obj.payment_status = "Completed"
                payment_obj.payment_method = payment_method
                payment_obj.payment_date = timezone.now()
                payment_obj.transaction_id = f"TXN-{reservation.id}-{uuid.uuid4().hex[:10]}"
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
    """Display payment success page"""
    return render(request, 'hotel/html/payment_success.html', {})


@login_required(login_url='login')
def checkout(request):
    """
    STEP 4️⃣: CHECKOUT - Verify Cart & Redirect
    Checks cart exists and redirects to confirm_information.
    """
    cart = get_object_or_404(Cart, user=request.user)
    
    if not cart.items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('view_cart')
    
    if request.method == 'POST':
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
    STEP 4.5️⃣: CONFIRM INFORMATION
    Collects user details and creates reservations/bookings
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
            return redirect('checkout_payment')
        
        except Exception as e:
            messages.error(request, f'Error during confirmation: {str(e)}')
            return redirect('confirm_information')
    
    # GET request - show form
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
    GET: Shows form, POST: Processes payment
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
                payment_obj.transaction_id = f"TXN-{reservation.id}-{uuid.uuid4().hex[:10]}"
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
                payment_obj.transaction_id = f"SVC-{service_booking.id}-{uuid.uuid4().hex[:10]}"
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
@require_http_methods(["POST"])
def payment_process(request):
    """Process payment from confirm information flow"""
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
                    'transaction_id': f"TXN-{reservation.id}-{uuid.uuid4().hex[:10]}",
                }
            )
            if created:
                payment_obj.save()
            else:
                payment_obj.payment_method = payment_method
                payment_obj.payment_status = 'Completed'
                payment_obj.transaction_id = f"TXN-{reservation.id}-{uuid.uuid4().hex[:10]}"
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


@login_required(login_url='login')
def service_payment(request, booking_id):
    """Initiate payment flow for a single ServiceBooking"""
    booking = get_object_or_404(ServiceBooking, id=booking_id, user=request.user)

    # Set session keys expected by checkout_payment
    request.session['checkout_service_booking_ids'] = [booking.id]
    request.session['checkout_reservation_ids'] = []
    try:
        request.session['checkout_total'] = float(booking.total_price)
    except Exception:
        request.session['checkout_total'] = None

    return redirect('checkout_payment')

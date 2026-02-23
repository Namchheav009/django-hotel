"""
Shopping Cart Views
- View, add, remove, update cart items
"""

from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone

from hotel.models import Room, Service, Cart, CartItem, Reservation


@login_required(login_url='login')
def view_cart(request):
    """View cart items"""
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
    """Add room to cart"""
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
    """Add service to cart"""
    if request.method == 'POST':
        service = get_object_or_404(Service, id=service_id)
        quantity = int(request.POST.get('quantity', 1))
        scheduled_date = request.POST.get('scheduled_date')
        
        if quantity < 1:
            messages.error(request, 'Quantity must be at least 1.')
            return redirect('book_service', service_id=service_id)

        # require date/time
        if not scheduled_date:
            messages.error(request, 'Please choose a date and time before adding to cart.')
            return redirect('book_service', service_id=service_id)
        
        try:
            # some browsers return "YYYY-MM-DDTHH:MM" (with T) others use space
            try:
                scheduled_date = datetime.strptime(scheduled_date, '%Y-%m-%d %H:%M')
            except ValueError:
                scheduled_date = datetime.strptime(scheduled_date, '%Y-%m-%dT%H:%M')

            # make aware in current timezone so comparison works
            if timezone.is_naive(scheduled_date):
                scheduled_date = timezone.make_aware(scheduled_date, timezone.get_current_timezone())

            if scheduled_date < timezone.now():
                messages.error(request, 'Scheduled date must be in the future.')
                return redirect('book_service', service_id=service_id)
            
            cart, created = Cart.objects.get_or_create(user=request.user)
            CartItem.objects.create(
                cart=cart,
                item_type='Service',
                service=service,
                service_quantity=quantity,
                scheduled_date=scheduled_date,
            )
            
            messages.success(request, f'{service.name} added to cart!')
            return redirect('view_cart')
        except ValueError:
            messages.error(request, 'Invalid date/time, please pick a valid future date.')
            return redirect('book_service', service_id=service_id)
        except Exception as e:
            messages.error(request, f'Error adding service to cart: {str(e)}')
            return redirect('book_service', service_id=service_id)
    
    return redirect('book_service', service_id=service_id)


@login_required(login_url='login')
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart = get_object_or_404(Cart, user=request.user)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
    messages.success(request, 'Item removed from cart.')
    return redirect('view_cart')


@login_required(login_url='login')
@require_http_methods(["POST"])
def update_cart_item_quantity(request, item_id):
    """Update cart item quantity or dates"""
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

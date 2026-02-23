"""
Review Views
- Rate rooms and services
- View reviews
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from hotel.models import Room, Service, Reservation, RoomRating, ServiceRating, ServiceBooking


@login_required(login_url='login')
def rate_room(request, room_id):
    """Rate a room after checkout"""
    room = get_object_or_404(Room, id=room_id)
    # Find the user's most recent reservation for this room
    reservation = Reservation.objects.filter(guest__user=request.user, room=room).order_by('-check_out_date').first()
    if not reservation:
        messages.error(request, "No reservation found for you and this room.")
        return redirect('my_reservations')

    # avoid duplicate review for same reservation
    if RoomRating.objects.filter(user=request.user, reservation=reservation).exists():
        messages.info(request, "You've already reviewed this reservation.")
        return redirect(f"{reverse('user_profile')}?tab=reviews")

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
            # user just submitted a room review, show reviews tab
            from django.urls import reverse
            return redirect(f"{reverse('user_profile')}?tab=reviews")
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

    # prevent duplicate service review on the same booking
    if ServiceRating.objects.filter(user=request.user, service_booking=service_booking).exists():
        messages.info(request, "You have already reviewed this service booking.")
        from django.urls import reverse
        return redirect(f"{reverse('user_profile')}?tab=reviews")

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
            from django.urls import reverse
            return redirect(f"{reverse('user_profile')}?tab=reviews")
        except Exception as e:
            messages.error(request, f"Error saving service review: {str(e)}")

    context = {
        'service': service,
        'service_booking': service_booking,
        'form': {},
    }
    return render(request, 'hotel/html/rate_service.html', context)


@login_required(login_url='login')
def reviews_page(request):
    """View all room reviews"""
    from django.db.models import Avg, Count
    
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

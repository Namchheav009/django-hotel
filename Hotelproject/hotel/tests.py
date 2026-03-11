from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Booking,
    Guest,
    Payment,
    Reservation,
    Room,
    RoomCategory,
    RoomRating,
    Service,
    ServiceBooking,
    ServiceRating,
    UserProfile,
)


class AdminManagementPagesTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin",
            password="pass1234",
            email="admin@example.com",
        )
        UserProfile.objects.create(user=self.admin_user, role="Admin")

        self.guest_user = User.objects.create_user(
            username="guest",
            password="pass1234",
            first_name="Guest",
            last_name="User",
            email="guest@example.com",
        )
        self.guest = Guest.objects.create(
            user=self.guest_user,
            phone="123456789",
            address="Bangkok",
        )

        self.category = RoomCategory.objects.create(category_name="Deluxe")
        self.room = Room.objects.create(
            room_number="101",
            category=self.category,
            status="Available",
            price=150,
        )
        self.reservation = Reservation.objects.create(
            guest=self.guest,
            room=self.room,
            check_in_date=timezone.now().date(),
            check_out_date=(timezone.now() + timedelta(days=2)).date(),
            status="Pending",
            total_price=300,
        )
        self.booking = Booking.objects.create(
            user=self.guest_user,
            reservation=self.reservation,
            room=self.room,
            booking_status="Pending",
            confirmation_number="CONF-101",
        )

        self.service = Service.objects.create(
            name="Spa",
            description="Spa treatment",
            price=50,
            is_active=True,
        )
        self.service_booking = ServiceBooking.objects.create(
            user=self.guest_user,
            service=self.service,
            reservation=self.reservation,
            scheduled_date=timezone.now() + timedelta(days=1),
            quantity=2,
            total_price=100,
            status="Pending",
        )

        self.payment = Payment.objects.create(
            reservation=self.reservation,
            amount=300,
            payment_method="Card",
            payment_status="Completed",
            payment_date=timezone.now(),
            transaction_id="TXN-ROOM-1",
        )
        self.service_payment = Payment.objects.create(
            service_booking=self.service_booking,
            amount=100,
            payment_method="Cash",
            payment_status="Pending",
            transaction_id="TXN-SERVICE-1",
        )

        self.room_review = RoomRating.objects.create(
            user=self.guest_user,
            room=self.room,
            reservation=self.reservation,
            rating=5,
            review="Great stay",
        )
        self.service_review = ServiceRating.objects.create(
            user=self.guest_user,
            service=self.service,
            service_booking=self.service_booking,
            rating=4,
            review="Great service",
        )

        self.client.force_login(self.admin_user)

    def test_management_pages_render(self):
        urls = [
            reverse("manage_bookings"),
            reverse("manage_payment"),
            reverse("manage_reservations"),
            reverse("manage_reviews"),
            reverse("manage_rooms"),
            reverse("manage_service_bookings"),
            reverse("manage_services"),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_update_booking_status_syncs_reservation_and_room(self):
        response = self.client.post(
            reverse("update_booking_status", args=[self.booking.id]),
            {"status": "Confirmed"},
        )

        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        self.reservation.refresh_from_db()
        self.room.refresh_from_db()

        self.assertEqual(self.booking.booking_status, "Confirmed")
        self.assertEqual(self.reservation.status, "Confirmed")
        self.assertEqual(self.room.status, "Booked")

    def test_refund_payment_syncs_linked_records(self):
        response = self.client.post(
            reverse("update_payment_status", args=[self.payment.id]),
            {"payment_status": "Refunded"},
        )

        self.assertEqual(response.status_code, 302)
        self.payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.reservation.refresh_from_db()
        self.room.refresh_from_db()

        self.assertEqual(self.payment.payment_status, "Refunded")
        self.assertEqual(self.booking.booking_status, "Cancelled")
        self.assertEqual(self.reservation.status, "Cancelled")
        self.assertEqual(self.room.status, "Available")

    def test_service_booking_status_update_works(self):
        response = self.client.post(
            reverse("update_service_booking_status", args=[self.service_booking.id]),
            {"status": "Confirmed"},
        )

        self.assertEqual(response.status_code, 302)
        self.service_booking.refresh_from_db()
        self.assertEqual(self.service_booking.status, "Confirmed")

    def test_reviews_page_contains_room_and_service_reviews(self):
        response = self.client.get(reverse("manage_reviews"))

        self.assertContains(response, "Great stay")
        self.assertContains(response, "Great service")

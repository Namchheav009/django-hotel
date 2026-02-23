# Import all views from submodules for backward compatibility
from .auth import (
    login_view, register_view, logout_view, complete_profile,
    user_profile, update_profile, change_password
)
from .admin import (
    admin_dashboard, manage_users, add_user, edit_user, delete_user,
    manage_categories, add_category, edit_category, delete_category,
    manage_rooms, add_room, edit_room, delete_room, delete_room_image,
    manage_services, add_service, edit_service, delete_service,
    manage_contacts, add_contact, edit_contact, delete_contact, mark_contact_read,
    manage_reviews, add_room_review_admin, delete_review, edit_review,
    manage_bookings, manage_payment, admin_reports,
    admin_login_required, manage_service_bookings, update_service_booking_status
)
from .booking import (
    book_room, my_reservations, reservation_detail, cancel_reservation,
    manage_reservations, add_reservation_page, add_reservation, edit_reservation, 
    update_reservation_status, delete_reservation
)
from .payment import (
    payment, payment_success, checkout, confirm_information,
    checkout_payment, payment_process, service_payment
)
from .service import (
    service_view, book_service, my_service_bookings, 
    update_service_booking, cancel_service_booking
)
from .review import (
    rate_room, rate_service, reviews_page
)
from .cart import (
    view_cart, add_room_to_cart, add_service_to_cart,
    remove_from_cart, update_cart_item_quantity
)
from .common import (
    guest_home, about_view, contact_view, room_list, room_detail
)
from .utils import (
    api_pending_bookings, api_all_bookings, my_view
)

__all__ = [
    # Auth
    'login_view', 'register_view', 'logout_view', 'complete_profile',
    'user_profile', 'update_profile', 'change_password',
    # Admin
    'admin_dashboard', 'manage_users', 'add_user', 'edit_user', 'delete_user',
    'manage_categories', 'add_category', 'edit_category', 'delete_category',
    'manage_rooms', 'add_room', 'edit_room', 'delete_room', 'delete_room_image',
    'manage_services', 'add_service', 'edit_service', 'delete_service',
    'manage_contacts', 'add_contact', 'edit_contact', 'delete_contact',
    'mark_contact_read', 'manage_reviews', 'add_room_review_admin',
    'delete_review', 'edit_review', 'manage_bookings', 'manage_payment',
    'admin_reports', 'admin_login_required', 'manage_service_bookings',
    'update_service_booking_status',
    # Booking
    'book_room', 'my_reservations', 'reservation_detail', 'cancel_reservation',
    'manage_reservations', 'add_reservation_page', 'add_reservation', 'edit_reservation',
    'update_reservation_status', 'delete_reservation',
    # Payment
    'payment', 'payment_success', 'checkout', 'confirm_information',
    'checkout_payment', 'payment_process', 'service_payment',
    # Service
    'service_view', 'book_service', 'my_service_bookings',
    'update_service_booking', 'cancel_service_booking',
    # Review
    'rate_room', 'rate_service', 'reviews_page',
    # Cart
    'view_cart', 'add_room_to_cart', 'add_service_to_cart',
    'remove_from_cart', 'update_cart_item_quantity',
    # Common
    'guest_home', 'about_view', 'contact_view', 'room_list', 'room_detail',
    # Utils
    'api_pending_bookings', 'api_all_bookings', 'my_view',
]

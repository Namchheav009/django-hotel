from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.guest_home, name='guest_home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('complete-profile/', views.complete_profile, name='complete_profile'),
    
    # General Pages
    path('about/', views.about_view, name='about'),
    path('service/', views.service_view, name='service'),
    path('contact/', views.contact_view, name='contact'),
    
    # Room Browsing
    path('rooms/', views.room_list, name='room_list'),
    path('room/<int:room_id>/', views.room_detail, name='room_detail'),
    
    # Booking
    path('book/<int:room_id>/', views.book_room, name='book_room'),
    path('my-reservations/', views.my_reservations, name='my_reservations'),
    path('reservation/<int:reservation_id>/', views.reservation_detail, name='reservation_detail'),
    path('reservation/<int:reservation_id>/cancel/', views.cancel_reservation, name='cancel_reservation'),
    
    # Payment
    path('payment/', views.payment, name='payment_checkout'),  # For multiple items from confirm_information
    path('payment/<int:reservation_id>/', views.payment, name='payment'),  # For single reservation
    path('payment-success/', views.payment_success, name='payment_success'),  # Success page after payment
    
    # Cart
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add-room/<int:room_id>/', views.add_room_to_cart, name='add_room_to_cart'),
    path('cart/add-service/<int:service_id>/', views.add_service_to_cart, name='add_service_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update-quantity/<int:item_id>/', views.update_cart_item_quantity, name='update_cart_quantity'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/confirm/', views.confirm_information, name='confirm_information'),
    path('checkout/payment-process/', views.payment_process, name='payment_process'),
    path('checkout/payment/', views.checkout_payment, name='checkout_payment'),
    
    # Admin Dashboard (all under dashboard/)
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/users/', views.manage_users, name='manage_users'),
    path('dashboard/users/add/', views.add_user, name='add_user'),
    path('dashboard/users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('dashboard/users/<int:user_id>/delete/', views.delete_user, name='delete_user'),

    path('dashboard/reservations/', views.manage_reservations, name='manage_reservations'),
    path('dashboard/reservations/add/', views.add_reservation_page, name='add_reservation_page'),
    path('dashboard/reservations/add/submit/', views.add_reservation, name='add_reservation'),
    path('dashboard/reservations/<int:reservation_id>/edit/', views.edit_reservation, name='edit_reservation'),
    path("dashboard/reservations/<int:reservation_id>/edit/",views.edit_reservation, name="edit_reservation"),
    path('dashboard/reservations/<int:reservation_id>/update-status/', views.update_reservation_status, name='update_reservation_status'),
    path('dashboard/reservations/<int:reservation_id>/delete/', views.delete_reservation, name='delete_reservation'),

    path('dashboard/rooms/', views.manage_rooms, name='manage_rooms'),
    path('dashboard/rooms/add/', views.add_room, name='add_room'),
    path('dashboard/rooms/<int:room_id>/edit/', views.edit_room, name='edit_room'),
    path('dashboard/rooms/<int:room_id>/delete/', views.delete_room, name='delete_room'),
    path('dashboard/rooms/image/<int:image_id>/delete/', views.delete_room_image, name='delete_room_image'),
    path('dashboard/categories/', views.manage_categories, name='manage_categories'),
    path('dashboard/categories/add/', views.add_category, name='add_category'),
    path('dashboard/categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    path('dashboard/categories/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('dashboard/services/add/', views.add_service, name='add_service'),
    path('dashboard/services/<int:service_id>/delete/', views.delete_service, name='delete_service'),
    path('dashboard/services/<int:service_id>/edit/', views.edit_service, name='edit_service'),
    path('dashboard/contacts/add/', views.add_contact, name='add_contact'),
    path('dashboard/contacts/<int:contact_id>/delete/', views.delete_contact, name='delete_contact'),
    path('dashboard/contacts/<int:contact_id>/edit/', views.edit_contact, name='edit_contact'),

    path('dashboard/reviews/add/', views.add_room_review_admin, name='add_review'),
    path('dashboard/reviews/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path('dashboard/reviews/<int:review_id>/edit/', views.edit_review, name='edit_review'),
    path('dashboard/services/', views.manage_services, name='manage_services'),
    path('dashboard/bookings/', views.manage_bookings, name='manage_bookings'),
    path('dashboard/payment/', views.manage_payment, name='manage_payment'),
    path('dashboard/reviews/', views.manage_reviews, name='manage_reviews'),
    path('dashboard/contacts/', views.manage_contacts, name='manage_contacts'),
    path('dashboard/contacts/<int:contact_id>/mark-read/', views.mark_contact_read, name='mark_contact_read'),

    path('dashboard/reports/', views.admin_reports, name='admin_reports'),

    
    # User Management (avoid using the 'admin/' prefix which conflicts with Django admin)
    path('dashboard/users/', views.manage_users, name='manage_users'),
    path('dashboard/users/add/', views.add_user, name='add_user'),
    path('dashboard/users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('dashboard/users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    
    # User Profile
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    
    # Ratings
    path('room/<int:room_id>/rate/', views.rate_room, name='rate_room'),
    path('service/<int:service_id>/rate/', views.rate_service, name='rate_service'),
    
    # Service Booking
    path('services/<int:service_id>/book/', views.book_service, name='book_service'),
    path('my-service-bookings/', views.my_service_bookings, name='my_service_bookings'),
    path('service-payment/<int:booking_id>/', views.service_payment, name='service_payment'),
    path('my-service-bookings/<int:booking_id>/update/', views.update_service_booking, name='update_service_booking'),
    path('dashboard/service-bookings/', views.manage_service_bookings, name='manage_service_bookings'),
    path('dashboard/service-bookings/<int:booking_id>/status/', views.update_service_booking_status, name='update_service_booking_status'),
    path('dashboard/service-bookings/<int:booking_id>/cancel/', views.cancel_service_booking, name='cancel_service_booking'),
    
    path("reviews/", views.reviews_page, name="reviews"),
    
    # API Endpoints
    path('api/pending-bookings/', views.api_pending_bookings, name='api_pending_bookings'),
    path('api/all-bookings/', views.api_all_bookings, name='api_all_bookings'),
]

from django.contrib import admin
from .models import (
    UserProfile, RoomCategory, Room, Guest, Reservation,
    Payment, Staff, Contact, Service, ServiceUsage, Booking,
    ServiceBooking, RoomRating, ServiceRating
)


# =========================
# User Profile
# =========================
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "email_verified", "created_at")
    list_filter = ("role", "email_verified", "created_at")
    search_fields = ("user__username", "user__email")
    list_select_related = ("user",)
    ordering = ("-created_at",)


# =========================
# Room Category
# =========================
@admin.register(RoomCategory)
class RoomCategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name",)
    search_fields = ("category_name",)
    ordering = ("category_name",)


# =========================
# Room
# =========================
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("room_number", "category", "status", "floor", "max_occupancy", "price")
    list_filter = ("status", "category", "floor")
    search_fields = ("room_number", "category__category_name")
    list_select_related = ("category",)
    ordering = ("room_number",)


# =========================
# Guest
# =========================
@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "id_type", "id_number")
    search_fields = ("user__username", "user__email", "phone", "id_number")
    list_select_related = ("user",)
    ordering = ("user__username",)


# =========================
# Reservation Inlines
# =========================
class ServiceUsageInline(admin.TabularInline):
    model = ServiceUsage
    extra = 0
    autocomplete_fields = ("service",)
    readonly_fields = ("usage_date",)
    fields = ("service", "quantity", "usage_date")


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    can_delete = True
    fields = ("amount", "payment_method", "payment_status", "transaction_id", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


# =========================
# Reservation
# =========================
@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "guest", "room", "check_in_date", "check_out_date", "status", "is_online_booking", "booking_date", "total_price")
    list_filter = ("status", "check_in_date", "check_out_date", "is_online_booking")
    search_fields = ("guest__user__username", "guest__user__email", "room__room_number")
    date_hierarchy = "booking_date"
    ordering = ("-booking_date",)
    list_select_related = ("guest", "guest__user", "room", "room__category")
    autocomplete_fields = ("guest", "room")

    readonly_fields = ("booking_date", "total_price")
    inlines = [ServiceUsageInline, PaymentInline]

    actions = ["recalculate_total_price"]

    def recalculate_total_price(self, request, queryset):
        for r in queryset:
            r.total_price = r.calculate_total_price()
            r.save(update_fields=["total_price"])
        self.message_user(request, f"Updated total_price for {queryset.count()} reservation(s).")
    recalculate_total_price.short_description = "Recalculate total price"


# =========================
# Payment
# =========================
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reservation", "amount", "payment_method", "payment_status", "transaction_id", "created_at")
    list_filter = ("payment_status", "payment_method", "created_at")
    search_fields = ("transaction_id", "reservation__id")
    ordering = ("-created_at",)
    list_select_related = ("reservation",)
    readonly_fields = ("created_at", "updated_at")


# =========================
# Staff
# =========================
@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "phone", "hire_date")
    list_filter = ("department", "hire_date")
    search_fields = ("user__username", "user__email", "phone")
    ordering = ("user__username",)
    list_select_related = ("user",)


# =========================
# Contact
# =========================
@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "email", "subject", "message")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


# =========================
# Service
# =========================
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "description")
    ordering = ("name",)
    readonly_fields = ("created_at",)


# =========================
# ServiceUsage
# =========================
@admin.register(ServiceUsage)
class ServiceUsageAdmin(admin.ModelAdmin):
    list_display = ("reservation", "service", "quantity", "usage_date")
    list_filter = ("usage_date", "service")
    search_fields = ("reservation__id", "service__name")
    ordering = ("-usage_date",)
    list_select_related = ("reservation", "service")
    readonly_fields = ("usage_date",)
    autocomplete_fields = ("reservation", "service")


# =========================
# Booking
# =========================
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("confirmation_number", "user", "room", "booking_status", "booking_date")
    list_filter = ("booking_status", "booking_date")
    search_fields = ("confirmation_number", "user__username", "user__email", "room__room_number")
    ordering = ("-booking_date",)
    list_select_related = ("user", "room")
    readonly_fields = ("booking_date",)


# =========================
# ServiceBooking
# =========================
@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = ("user", "service", "status", "scheduled_date", "booking_date")
    list_filter = ("status", "booking_date", "scheduled_date")
    search_fields = ("user__username", "user__email", "service__name")
    ordering = ("-booking_date",)
    list_select_related = ("user", "service")
    readonly_fields = ("booking_date",)
    autocomplete_fields = ("user", "service")


# =========================
# RoomRating
# =========================
@admin.register(RoomRating)
class RoomRatingAdmin(admin.ModelAdmin):
    list_display = ("user", "room", "rating", "cleanliness", "comfort", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("user__username", "user__email", "room__room_number")
    ordering = ("-created_at",)
    list_select_related = ("user", "room")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "room")


# =========================
# ServiceRating
# =========================
@admin.register(ServiceRating)
class ServiceRatingAdmin(admin.ModelAdmin):
    list_display = ("user", "service", "rating", "quality", "timeliness", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("user__username", "user__email", "service__name")
    ordering = ("-created_at",)
    list_select_related = ("user", "service")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user", "service")

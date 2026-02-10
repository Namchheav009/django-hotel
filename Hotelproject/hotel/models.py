from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class UserProfile(models.Model):
    id = models.AutoField(primary_key=True)
    ROLE_CHOICES = [
        ('Customer', 'Customer'),
        ('Admin', 'Admin'),
        ('Receptionist', 'Receptionist'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    preferred_room_category = models.ForeignKey('RoomCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='preferred_by_users')
    managed_by_staff = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_users')

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class RoomCategory(models.Model):
    id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name_plural = "Room Categories"

    def __str__(self):
        return self.category_name


class Room(models.Model):
    id = models.AutoField(primary_key=True)
    STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Booked', 'Booked'),
        ('Maintenance', 'Maintenance'),
    ]

    room_number = models.CharField(max_length=10, unique=True)
    category = models.ForeignKey(RoomCategory, on_delete=models.CASCADE, related_name='rooms')
    assigned_staff = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_rooms')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Available')
    floor = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_occupancy = models.IntegerField(default=2, validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], help_text="Room-specific price (leave blank to use category base price)")
    amenities = models.TextField(default="WiFi, AC, TV", help_text="Comma-separated list of amenities")
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='rooms/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['room_number']

    def __str__(self):
        return self.room_number


class RoomImage(models.Model):
    """Model to store multiple images for each room (up to 6)"""
    id = models.AutoField(primary_key=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='rooms/')
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    order = models.IntegerField(default=0, help_text="Order in gallery (1-6)")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['room', 'order']
        unique_together = ('room', 'order')

    def __str__(self):
        return f"{self.room.room_number} - Image {self.order}"


class Guest(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    id_type = models.CharField(max_length=50, blank=True, null=True, help_text="Passport, Driver License, etc.")
    id_number = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Reservation(models.Model):
    id = models.AutoField(primary_key=True)
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Checked In', 'Checked In'),
        ('Checked Out', 'Checked Out'),
        ('Cancelled', 'Cancelled'),
    ]

    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name='reservations')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reservations')
    handled_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_reservations')
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    booking_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    is_online_booking = models.BooleanField(default=True)
    number_of_guests = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    special_requests = models.TextField(blank=True, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ['-booking_date']

    def __str__(self):
        return f"{self.guest} - {self.room} ({self.check_in_date})"

    def calculate_total_price(self):
        """Calculate total price based on room category and number of nights"""
        if self.check_in_date and self.check_out_date:
            nights = (self.check_out_date - self.check_in_date).days
            if nights > 0:
                # Use room-specific price when available; otherwise default to 0
                price = self.room.price if self.room.price is not None else 0
                self.total_price = price * nights
        return self.total_price


class Payment(models.Model):
    id = models.AutoField(primary_key=True)
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('Online', 'Online'),
        ('Bank Transfer', 'Bank Transfer'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
    ]

    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    processed_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_payments')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    payment_date = models.DateTimeField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.amount} - {self.reservation}"


class Staff(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    department = models.CharField(max_length=50, blank=True, null=True)
    hire_date = models.DateField(default=timezone.now)

    def __str__(self):
        return self.user.username


class Contact(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contacts')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True, null=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    handled_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_contacts')
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.subject}"


class Service(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    icon = models.CharField(max_length=100, blank=True, null=True, help_text="Font Awesome icon class")
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    provider = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='services_provided')

    class Meta:
        verbose_name_plural = "Services"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class ServiceUsage(models.Model):
    """Track which services are used in reservations"""
    id = models.AutoField(primary_key=True)
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='services_used')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='usages')
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    usage_date = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ['reservation', 'service']

    def __str__(self):
        return f"{self.reservation} - {self.service}"


class Booking(models.Model):
    """User booking history and tracking"""
    id = models.AutoField(primary_key=True)
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Cancelled', 'Cancelled'),
        ('Completed', 'Completed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='booking')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    booking_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    booking_date = models.DateTimeField(auto_now_add=True)
    confirmation_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-booking_date']
    
    def __str__(self):
        return f"Booking {self.confirmation_number} - {self.user.username}"


class ServiceBooking(models.Model):
    """User service bookings"""
    id = models.AutoField(primary_key=True)
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_bookings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='user_bookings')
    reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='service_bookings')
    booking_date = models.DateTimeField(auto_now_add=True)
    scheduled_date = models.DateTimeField()
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-booking_date']
    
    def __str__(self):
        return f"{self.user.username} - {self.service.name} ({self.status})"


class RoomRating(models.Model):
    """User/Guest ratings for rooms"""
    id = models.AutoField(primary_key=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_ratings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='ratings')
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='room_rating')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True, null=True)
    cleanliness = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comfort = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    amenities = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'reservation']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.room.room_number} ({self.rating}/5)"


class ServiceRating(models.Model):
    """User/Guest ratings for services"""
    id = models.AutoField(primary_key=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_ratings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='ratings')
    service_booking = models.ForeignKey(ServiceBooking, on_delete=models.CASCADE, related_name='rating')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True, null=True)
    quality = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    timeliness = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    value_for_money = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'service_booking']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.service.name} ({self.rating}/5)"


class Cart(models.Model):
    """Shopping cart for users before checkout"""
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total_price(self):
        """Calculate total price of all items in cart"""
        total = sum(item.get_item_total() for item in self.items.all())
        return total

    def __str__(self):
        return f"Cart - {self.user.username}"


class CartItem(models.Model):
    """Individual items in the shopping cart"""
    ITEM_TYPE_CHOICES = [
        ('Room', 'Room'),
        ('Service', 'Service'),
    ]

    id = models.AutoField(primary_key=True)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=10, choices=ITEM_TYPE_CHOICES)
    
    # For Room bookings
    room = models.ForeignKey(Room, on_delete=models.CASCADE, null=True, blank=True, related_name='cart_items')
    check_in_date = models.DateField(null=True, blank=True)
    check_out_date = models.DateField(null=True, blank=True)
    number_of_guests = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    
    # For Service bookings
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True, related_name='cart_items')
    service_quantity = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    scheduled_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def number_of_nights(self):
        """Calculate number of nights for room bookings"""
        if self.item_type == 'Room' and self.check_in_date and self.check_out_date:
            nights = (self.check_out_date - self.check_in_date).days
            return max(1, nights)  # Minimum 1 night
        return 0

    def get_item_total(self):
        """Calculate total price for this cart item"""
        if self.item_type == 'Room' and self.room and self.check_in_date and self.check_out_date:
            nights = (self.check_out_date - self.check_in_date).days
            if nights > 0:
                price = self.room.price if self.room.price is not None else 0
                return price * nights
        elif self.item_type == 'Service' and self.service:
            return self.service.price * self.service_quantity
        return 0

    def __str__(self):
        if self.item_type == 'Room':
            return f"Cart Item - {self.room.room_number}"
        else:
            return f"Cart Item - {self.service.name}"

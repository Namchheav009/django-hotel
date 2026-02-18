from rest_framework import serializers
from .models import Room, RoomCategory, Reservation, Payment, Guest, Service, Contact


class RoomCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomCategory
        # `base_price` was removed from RoomCategory; expose existing fields only
        fields = ['id', 'category_name', 'description', 'max_occupancy', 'amenities']


class RoomSerializer(serializers.ModelSerializer):
    category = RoomCategorySerializer()

    class Meta:
        model = Room
        # include `price` so API clients receive the room-level price
        fields = ['id', 'room_number', 'category', 'status', 'floor', 'description', 'price']


class GuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guest
        fields = ['id', 'phone', 'address', 'id_type', 'id_number', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'reservation', 'amount', 'payment_method', 'payment_status', 'payment_date', 'transaction_id']


class ReservationSerializer(serializers.ModelSerializer):
    room = RoomSerializer()
    guest = GuestSerializer()
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'id', 'guest', 'room', 'check_in_date', 'check_out_date',
            'booking_date', 'status', 'number_of_guests', 'total_price',
            'special_requests', 'payment'
        ]

    def create(self, validated_data):
        reservation = Reservation.objects.create(**validated_data)
        reservation.calculate_total_price()
        reservation.save()
        return reservation


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ['id', 'name', 'description', 'price', 'icon', 'image', 'is_active']


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'name', 'email', 'phone', 'subject', 'message', 'created_at', 'is_read']

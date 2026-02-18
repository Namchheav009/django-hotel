from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Room, RoomCategory, Reservation, Payment, Service, Contact, Guest
from .serializers import (
    RoomSerializer, RoomCategorySerializer, ReservationSerializer,
    PaymentSerializer, ServiceSerializer, ContactSerializer, GuestSerializer
)
from datetime import datetime


class RoomCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RoomCategory.objects.all()
    serializer_class = RoomCategorySerializer
    permission_classes = [AllowAny]


class RoomViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Room.objects.filter(status='Available')
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'status', 'floor']
    search_fields = ['room_number', 'category__category_name']
    # `category__base_price` was removed — allow ordering by room `price` instead
    ordering_fields = ['room_number', 'price']

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get available rooms with optional date filters"""
        check_in = request.query_params.get('check_in')
        check_out = request.query_params.get('check_out')
        
        rooms = self.queryset
        
        if check_in and check_out:
            from django.db.models import Q
            booked_rooms = Reservation.objects.filter(
                Q(check_in_date__lt=check_out) & Q(check_out_date__gt=check_in),
                status__in=['Pending', 'Confirmed', 'Checked In']
            ).values_list('room_id', flat=True)
            rooms = rooms.exclude(id__in=booked_rooms)
        
        serializer = self.get_serializer(rooms, many=True)
        return Response(serializer.data)


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'room', 'check_in_date']
    ordering_fields = ['booking_date', 'check_in_date']

    def get_queryset(self):
        """Return only user's reservations"""
        try:
            guest = self.request.user.guest
            return Reservation.objects.filter(guest=guest)
        except Guest.DoesNotExist:
            return Reservation.objects.none()

    def create(self, request, *args, **kwargs):
        """Create new reservation"""
        try:
            guest = request.user.guest
        except Guest.DoesNotExist:
            return Response(
                {'detail': 'Please complete your profile first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(guest=guest)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a reservation"""
        reservation = self.get_object()
        
        if reservation.status in ['Checked In', 'Checked Out', 'Cancelled']:
            return Response(
                {'detail': 'This reservation cannot be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reservation.status = 'Cancelled'
        reservation.save()
        return Response({'status': 'Reservation cancelled'})


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only user's payments"""
        try:
            guest = self.request.user.guest
            return Payment.objects.filter(reservation__guest=guest)
        except Guest.DoesNotExist:
            return Payment.objects.none()


class ServiceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = ServiceSerializer
    permission_classes = [AllowAny]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price']


class ContactViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        """Create a contact message"""
        serializer = ContactSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

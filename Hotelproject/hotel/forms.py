from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, PasswordResetForm
from .models import Reservation, Payment, Contact, Guest


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class GuestForm(forms.ModelForm):
    class Meta:
        model = Guest
        fields = ('phone', 'address', 'id_type', 'id_number')
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter phone number'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter address'}),
            'id_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Passport, Driver License'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter ID number'}),
        }


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ('check_in_date', 'check_out_date', 'number_of_guests', 'special_requests')
        widgets = {
            'check_in_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'check_out_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'number_of_guests': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'special_requests': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Any special requests?'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in_date')
        check_out = cleaned_data.get('check_out_date')

        if check_in and check_out:
            if check_out <= check_in:
                raise forms.ValidationError("Check-out date must be after check-in date.")
            
            from datetime import date
            if check_in < date.today():
                raise forms.ValidationError("Check-in date cannot be in the past.")

        return cleaned_data


class RoomFilterForm(forms.Form):
    check_in_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    check_out_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    category = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Room category'})
    )
    max_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Max price'})
    )


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ('payment_method',)
        widgets = {
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ('name', 'email', 'phone', 'subject', 'message')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your phone (optional)'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Your message'}),
        }


class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email',
            'class': 'form-control'
        })
    )

# New Rating Forms
class RoomRatingForm(forms.Form):
    overall_rating = forms.IntegerField(
        min_value=1, max_value=5,
        widget=forms.HiddenInput()
    )
    cleanliness_rating = forms.IntegerField(
        min_value=1, max_value=5,
        widget=forms.HiddenInput()
    )
    comfort_rating = forms.IntegerField(
        min_value=1, max_value=5,
        widget=forms.HiddenInput()
    )
    amenities_rating = forms.IntegerField(
        min_value=1, max_value=5,
        widget=forms.HiddenInput()
    )
    review = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': '4',
            'placeholder': 'Share your experience (max 1000 characters)',
            'maxlength': '1000'
        })
    )


class ServiceRatingForm(forms.Form):
    overall_rating = forms.IntegerField(
        min_value=1, max_value=5,
        widget=forms.HiddenInput()
    )
    quality_rating = forms.IntegerField(
        min_value=1, max_value=5,
        widget=forms.HiddenInput()
    )
    timeliness_rating = forms.IntegerField(
        min_value=1, max_value=5,
        widget=forms.HiddenInput()
    )
    value_rating = forms.IntegerField(
        min_value=1, max_value=5,
        widget=forms.HiddenInput()
    )
    review = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': '4',
            'placeholder': 'Share your service experience (max 1000 characters)',
            'maxlength': '1000'
        })
    )
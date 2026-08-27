from django import forms
from .models import Order, Profile, Review
from django.conf import settings

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone', 'address', 'city', 'postal_code']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CartAddProductForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, max_value=settings.MAX_PURCHASE_QUANTITY, initial=1, label='Количество')

    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)

    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if self.product:
            if quantity > self.product.stock:
                raise forms.ValidationError(f'Доступно только {self.product.stock} шт.')
            if quantity > settings.MAX_PURCHASE_QUANTITY:
                raise forms.ValidationError(f'За один раз можно заказать не более {settings.MAX_PURCHASE_QUANTITY} шт.')
        return quantity
    
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'text']
        widgets = {
            'rating': forms.Select(choices=[(i, i) for i in range(1, 6)], attrs={'class': 'form-control'}),
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class OrderCreateForm(forms.ModelForm):
    payment_method = forms.ChoiceField(
        choices=[
            ('card', 'Банковская карта'),
            ('sbp', 'СБП (Система быстрых платежей)'),
            ('cash', 'Наличные при получении'),
        ],
        label='Способ оплаты',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    card_number = forms.CharField(
        label='Номер карты',
        max_length=19,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1234 5678 9012 3456'})
    )
    card_expiry = forms.CharField(
        label='Срок действия (ММ/ГГ)',
        max_length=5,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12/26'})
    )
    card_cvv = forms.CharField(
        label='CVV',
        max_length=3,
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '123'})
    )
    card_holder = forms.CharField(
        label='Имя держателя',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'MARIA IVANOVA'})
    )

    class Meta:
        model = Order
        fields = [
            'first_name', 'last_name', 'email', 
            'phone', 'address', 'city', 'postal_code'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
        }
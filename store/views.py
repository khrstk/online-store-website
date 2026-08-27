from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q, Sum, Case, When, Value, IntegerField, Count
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from urllib.parse import urlparse, parse_qs, urlencode
from datetime import datetime, timedelta

from .models import Category, Product, Cart, CartItem, Order, OrderItem, Review, Wishlist, Profile
from .forms import CartAddProductForm, OrderCreateForm, ReviewForm

import csv

def get_or_create_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    return cart

def product_list(request, category_slug=None):
    categories = Category.objects.all()
    products = Product.objects.filter(available=True)
    category = None

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        cat_ids = category.get_descendant_ids()
        products = products.filter(category__id__in=cat_ids)
    # фильтр по цене
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    # для удобного отображения товаров; доступные товары получают 1, недоступные 0
    products = products.annotate(
        in_stock_order=Case(
            When(stock__gt=0, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )
    # сортировка
    sort_by = request.GET.get('sort')
    order_by_fields = ['-in_stock_order']

    if sort_by == 'price_asc':
        order_by_fields.append('price')
    elif sort_by == 'price_desc':
        order_by_fields.append('-price')
    elif sort_by == 'name_asc':
        order_by_fields.append('name')
    elif sort_by == 'name_desc':
        order_by_fields.append('-name')
    else:
        order_by_fields.append('-created')

    products = products.order_by(*order_by_fields)
    # поиск
    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name_lower__contains=query.lower()) |
            Q(description__icontains=query) |
            Q(sku__icontains=query)
        )
    context = {
        'category': category,
        'categories': categories,
        'products': products,
        'query': query,
        'min_price': min_price,
        'max_price': max_price,
        'sort_by': sort_by,
    }
    return render(request, 'store/product_list.html', context)


def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    max_quantity = min(product.stock, settings.MAX_PURCHASE_QUANTITY)
    cart_product_form = CartAddProductForm(product=product, initial={'quantity': 1})
    review_form = ReviewForm()

    is_in_wishlist = False
    if request.user.is_authenticated:
        is_in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()

    return render(request, 'store/product_detail.html', {
        'product': product,
        'cart_product_form': cart_product_form,
        'review_form': review_form,
        'max_quantity': max_quantity,
        'global_max': settings.MAX_PURCHASE_QUANTITY,
        'is_in_wishlist': is_in_wishlist,
    })

def search_autocomplete(request):
    query = request.GET.get('q', '')
    if len(query) >= 2:
        products = Product.objects.filter(
            Q(name_lower__contains=query.lower()) |
            Q(sku__icontains=query),
            available=True
        )[:10]
        results = [{'id': p.id, 'name': p.name, 'slug': p.slug, 'price': str(p.price)} for p in products]
    else:
        results = []
    return JsonResponse({'results': results})

@require_POST
@login_required
def cart_add(request, product_id):
    cart = get_or_create_cart(request)
    product = get_object_or_404(Product, id=product_id, available=True)
    form = CartAddProductForm(request.POST)

    if form.is_valid():
        cd = form.cleaned_data
        quantity = cd['quantity']
        if quantity > product.stock:
            messages.error(request, f'Недостаточно товара "{product.name}". В наличии: {product.stock}.')
            return redirect('store:product_detail', id=product.id, slug=product.slug)
        
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, product=product,
            defaults={'quantity': quantity}
        )
        if not created:
            if cart_item.quantity + quantity > product.stock:
                messages.error(request, f'Нельзя добавить такое количество. Всего доступно: {product.stock}, в корзине уже: {cart_item.quantity}')
                return redirect('store:cart_detail')
            cart_item.quantity += quantity
            cart_item.save()
        messages.success(request, f'Товар "{product.name}" добавлен в корзину')

    return redirect('store:cart_detail')

@login_required
def cart_remove(request, product_id):
    cart = get_or_create_cart(request)
    product = get_object_or_404(Product, id=product_id)
    CartItem.objects.filter(cart=cart, product=product).delete()
    return redirect('store:cart_detail')

@login_required
def cart_detail(request):
    cart = get_or_create_cart(request)
    return render(request, 'store/cart_detail.html', {'cart': cart})

@login_required
def order_create(request):
    cart = get_or_create_cart(request)
    if cart.items.count() == 0:
        messages.warning(request, 'Ваша корзина пуста')
        return redirect('store:product_list')

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            order.save()
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    price=cart_item.product.final_price,
                    quantity=cart_item.quantity
                )
                product = cart_item.product
                product.stock -= cart_item.quantity
                product.save()
            cart.items.all().delete()
            
            payment_method = form.cleaned_data.get('payment_method')
            if payment_method == 'card':
                messages.success(request, 'Оплата банковской картой прошла успешно!')
            elif payment_method == 'sbp':
                messages.success(request, 'Оплата через СБП выполнена. Деньги списаны с вашего счёта.')
            else:
                messages.success(request, 'Заказ оформлен. Оплата наличными при получении.')
                
            return redirect('store:product_list')
    else:
        initial = {}
        if request.user.is_authenticated:
            profile, _ = Profile.objects.get_or_create(user=request.user)
            initial = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': profile.phone,
                'address': profile.address,
                'city': profile.city,
                'postal_code': profile.postal_code,
            }
        form = OrderCreateForm(initial=initial)
    return render(request, 'store/order_create.html', {'cart': cart, 'form': form})

@staff_member_required
def admin_stats(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category_id = request.GET.get('category')

    orders = Order.objects.filter(status__in=['delivered', 'shipped', 'confirmed'])

    if date_from:
        orders = orders.filter(created_at__gte=date_from)
    if date_to:
        date_to_inc = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        orders = orders.filter(created_at__lt=date_to_inc)
    else:
        if not date_to and not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            orders = orders.filter(created_at__gte=date_from)

    order_ids = orders.values_list('id', flat=True)
    order_items = OrderItem.objects.filter(order_id__in=order_ids)
    if category_id:
        order_items = order_items.filter(product__category_id=category_id)

    total_revenue = order_items.aggregate(total=Sum('price'))['total'] or 0
    total_orders = orders.count()
    avg_order = total_revenue / total_orders if total_orders else 0

    sales_by_day = order_items.values('order__created_at__date').annotate(
        day_total=Sum('price'),
        day_orders=Count('order_id', distinct=True)
    ).order_by('order__created_at__date')

    top_products = order_items.values('product__id', 'product__name', 'product__sku').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('price')
    ).order_by('-total_revenue')[:20]

    categories = Category.objects.all()

    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_order': avg_order,
        'sales_by_day': sales_by_day,
        'top_products': top_products,
        'categories': categories,
        'date_from': date_from,
        'date_to': date_to,
        'selected_category': category_id,
    }
    return render(request, 'store/admin_stats.html', context)

@staff_member_required
def export_sales_report(request):
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    category_id = request.GET.get('category')

    orders = Order.objects.filter(status__in=['delivered', 'shipped', 'confirmed'])

    if date_from:
        orders = orders.filter(created_at__gte=date_from)
    if date_to:
        date_to_inc = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        orders = orders.filter(created_at__lt=date_to_inc)
    else:
        if not date_to and not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            orders = orders.filter(created_at__gte=date_from)

    order_ids = orders.values_list('id', flat=True)
    order_items = OrderItem.objects.filter(order_id__in=order_ids)
    if category_id:
        order_items = order_items.filter(product__category_id=category_id)

    data = order_items.values(
        'product__id', 'product__sku', 'product__name', 'product__category__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('price')
    ).order_by('-total_revenue')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Артикул', 'Название товара', 'Категория', 'Количество продано', 'Выручка, руб'])

    for row in data:
        writer.writerow([
            row['product__sku'] or '',
            row['product__name'],
            row['product__category__name'] or '',
            row['total_quantity'],
            row['total_revenue'],
        ])
    return response

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('store:product_list')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def user_profile(request):
    orders = Order.objects.filter(user=request.user).annotate(
        is_delivered=Case(
            When(status='delivered', then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by('is_delivered', '-created_at')

    total_orders = orders.count()
    total_spent = orders.aggregate(total=Sum('items__price'))['total'] or 0
    wishlist_items = Wishlist.objects.filter(user=request.user)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, 'store/user_profile.html', {
        'orders': orders,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'wishlist_items': wishlist_items,
        'profile': profile,
    })

@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.author_name = request.user.first_name or request.user.username
            review.save()
            messages.success(request, 'Спасибо за ваш отзыв!')
    return redirect('store:product_detail', id=product.id, slug=product.slug)

@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wish, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        wish.delete()
        messages.info(request, f'Товар "{product.name}" удалён из избранного')
    else:
        messages.success(request, f'Товар "{product.name}" добавлен в избранное')

    next_url = request.META.get('HTTP_REFERER', reverse('store:product_list'))
    if '/profile/' in next_url:
        base_url = reverse('store:user_profile')
        next_url = f"{base_url}?tab=favorites"
    return redirect(next_url)

@login_required
def profile_edit(request):
    next_url = request.GET.get('next', reverse('store:user_profile'))
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        new_email = request.POST.get('email', '')
        if new_email and new_email != user.email:
            if User.objects.filter(email=new_email).exclude(id=user.id).exists():
                messages.error(request, 'Этот email уже используется другим пользователем.')
                return redirect(f"{reverse('store:user_profile')}?tab=profile")
            user.email = new_email
        user.save()

        profile, created = Profile.objects.get_or_create(user=user)
        profile.phone = request.POST.get('phone', '')
        profile.address = request.POST.get('address', '')
        profile.city = request.POST.get('city', '')
        profile.postal_code = request.POST.get('postal_code', '')
        profile.save()

        messages.success(request, 'Данные профиля обновлены.')
        return redirect(f"{reverse('store:user_profile')}?tab=profile")
    return redirect('store:user_profile')
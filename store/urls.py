from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),
    path('order/create/', views.order_create, name='order_create'),
    path('profile/', views.user_profile, name='user_profile'),
    path('register/', views.register, name='register'),
    path('search/autocomplete/', views.search_autocomplete, name='search_autocomplete'),
    path('product/<int:product_id>/add_review/', views.add_review, name='add_review'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('admin-stats/', views.admin_stats, name='admin_stats'),
    path('export-sales/', views.export_sales_report, name='export_sales_report'),
    path('<int:id>/<slug:slug>/', views.product_detail, name='product_detail'),
    path('<slug:category_slug>/', views.product_list, name='product_list_by_category'),
]
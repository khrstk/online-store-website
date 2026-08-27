from django.contrib import admin
from .models import Category, Product, Cart, CartItem, Order, OrderItem, ProductImage, Review, Wishlist, Profile
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget

class ProductResource(resources.ModelResource):
    category = Field(
        column_name='category__name',   
        attribute='category',       
        widget=ForeignKeyWidget(Category, field='name') 
    )
    class Meta:
        model = Product
        fields = ('name', 'price', 'stock', 'sku', 'discount', 'available', 'category')
        import_id_fields = ('sku',)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'is_main', 'alt_text', 'sort_order')

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    resource_class = ProductResource
    inlines = [ProductImageInline]
    list_display = ('name', 'price', 'stock', 'sku', 'category', 'discount', 'available')
    list_editable = ('price', 'stock', 'discount', 'available')
    list_filter = ('category', 'available')
    search_fields = ('name', 'sku')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent']
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ['parent']
    search_fields = ['name']

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'session_key', 'created_at']
    inlines = [CartItemInline]
    search_fields = ['user__username', 'session_key']

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name', 'status', 'created_at', 'get_total_cost']
    list_editable = ['status']
    inlines = [OrderItemInline]
    search_fields = ['first_name', 'last_name', 'email', 'phone']

    def get_total_cost(self, obj):
        return obj.get_total_cost()
    get_total_cost.short_description = 'Сумма заказа'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('author_name', 'product', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('author_name', 'text')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'city', 'address')
    search_fields = ('user__username', 'phone', 'city')
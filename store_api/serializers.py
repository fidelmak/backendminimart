from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Category, Product, Sale, SaleItem, StockMovement

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'phone', 'is_active', 'password', 'created_at']
        extra_kwargs = {
            'password': {'write_only': True}
        }
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            data['user'] = user
        return data

class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = '__all__'
    
    def get_products_count(self, obj):
        return obj.products.filter(is_active=True).count()

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_low_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = '__all__'

class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    
    class Meta:
        model = SaleItem
        fields = '__all__'

class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source='cashier.get_full_name', read_only=True)
    
    class Meta:
        model = Sale
        fields = '__all__'
        read_only_fields = ['sale_id', 'cashier']

class CreateSaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    
    class Meta:
        model = Sale
        fields = ['total_amount', 'discount_amount', 'tax_amount', 'final_amount', 
                 'payment_method', 'customer_name', 'customer_phone', 'notes', 'items']
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Generate sale ID
        import uuid
        sale_id = f"SALE-{uuid.uuid4().hex[:8].upper()}"
        
        sale = Sale.objects.create(
            sale_id=sale_id,
            cashier=self.context['request'].user,
            **validated_data
        )
        
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            
            # Check stock availability
            if product.stock_quantity < quantity:
                raise serializers.ValidationError(f"Insufficient stock for {product.name}")
            
            # Create sale item
            SaleItem.objects.create(sale=sale, **item_data)
            
            # Update product stock
            previous_qty = product.stock_quantity
            product.stock_quantity -= quantity
            product.save()
            
            # Create stock movement record
            StockMovement.objects.create(
                product=product,
                movement_type='sale',
                quantity=-quantity,
                previous_quantity=previous_qty,
                new_quantity=product.stock_quantity,
                reference_id=sale.sale_id,
                created_by=self.context['request'].user
            )
        
        return sale

class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = StockMovement
        fields = '__all__'
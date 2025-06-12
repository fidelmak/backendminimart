from django.shortcuts import render

# Create your views here.
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db.models import Q, Sum, Count, F  # Added F import here
from django.db import models  # Added this import
from django.utils import timezone
from datetime import datetime, timedelta
from .models import User, Category, Product, Sale, SaleItem, StockMovement
from .serializers import (
    UserSerializer, LoginSerializer, CategorySerializer, ProductSerializer,
    SaleSerializer, CreateSaleSerializer, StockMovementSerializer
)

# Authentication Views
# views.py - Updated authentication views

@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # This allows access without authentication
def login_view(request):
    """
    Direct login endpoint that doesn't require any prior authentication
    """
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({
            'success': True,
            'message': 'Login successful',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })
    return Response({
        'success': False,
        'message': 'Invalid credentials',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_view(request):
    """
    Registration endpoint that doesn't require authentication
    """
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'success': True,
            'message': 'Registration successful',
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        'success': False,
        'message': 'Registration failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def get_api_token_view(request):
    """
    Get API token without authentication (if you still need this for some endpoints)
    """
    # You can implement your API token logic here
    # For now, returning a simple token
    api_token = "your-api-token-here"  # Replace with your actual token generation logic
    
    return Response({
        'success': True,
        'token': api_token,
        'api_token': api_token,
        'access_token': api_token
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])  # This requires authentication
def logout_view(request):
    try:
        refresh_token = request.data.get("refresh")
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({
            'success': True,
            'message': 'Successfully logged out'
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Invalid token'
        }, status=status.HTTP_400_BAD_REQUEST)

# Add this to your urls.py
"""
from django.urls import path
from . import views

urlpatterns = [
    # Authentication endpoints
    path('api/auth/login/', views.login_view, name='login'),
    path('api/auth/register/', views.register_view, name='register'),
    path('api/auth/logout/', views.logout_view, name='logout'),
    path('api/api/token/', views.get_api_token_view, name='api_token'),  # If you still need this
    
    # Your other URLs...
]
"""

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'manager']

# User Management Views (Admin only)
class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated(), IsAdminUser()]
        return [permissions.IsAuthenticated()]

class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

# Category Views
class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer

class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

# Product Views
class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)
        search = self.request.query_params.get('search', None)
        category = self.request.query_params.get('category', None)
        low_stock = self.request.query_params.get('low_stock', None)
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(sku__icontains=search) | 
                Q(barcode__icontains=search)
            )
        
        if category:
            queryset = queryset.filter(category_id=category)
        
        if low_stock == 'true':
            queryset = queryset.filter(stock_quantity__lte=F('minimum_stock'))  # Changed to F
        
        return queryset.select_related('category')

class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

@api_view(['POST'])
def update_stock(request, product_id):
    try:
        product = Product.objects.get(id=product_id)
        movement_type = request.data.get('movement_type', 'adjustment')
        quantity = int(request.data.get('quantity', 0))
        notes = request.data.get('notes', '')
        
        previous_qty = product.stock_quantity
        
        if movement_type == 'purchase':
            product.stock_quantity += quantity
        elif movement_type == 'adjustment':
            product.stock_quantity = quantity
        else:
            return Response({'error': 'Invalid movement type'}, status=status.HTTP_400_BAD_REQUEST)
        
        product.save()
        
        # Create stock movement record
        StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=quantity if movement_type == 'purchase' else quantity - previous_qty,
            previous_quantity=previous_qty,
            new_quantity=product.stock_quantity,
            notes=notes,
            created_by=request.user
        )
        
        return Response({'message': 'Stock updated successfully', 'new_quantity': product.stock_quantity})
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Sales Views
class SaleListCreateView(generics.ListCreateAPIView):
    serializer_class = SaleSerializer
    
    def get_queryset(self):
        queryset = Sale.objects.all().select_related('cashier').prefetch_related('items__product')
        
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        cashier = self.request.query_params.get('cashier')
        
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        if cashier:
            queryset = queryset.filter(cashier_id=cashier)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateSaleSerializer
        return SaleSerializer

class SaleDetailView(generics.RetrieveAPIView):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer

# Stock Movement Views
class StockMovementListView(generics.ListAPIView):
    serializer_class = StockMovementSerializer
    
    def get_queryset(self):
        queryset = StockMovement.objects.all().select_related('product', 'created_by')
        product_id = self.request.query_params.get('product')
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        return queryset.order_by('-created_at')

# Dashboard Views
@api_view(['GET'])
def dashboard_stats(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Today's sales
    today_sales = Sale.objects.filter(created_at__date=today)
    today_revenue = today_sales.aggregate(total=Sum('final_amount'))['total'] or 0
    today_transactions = today_sales.count()
    
    # Weekly sales
    week_sales = Sale.objects.filter(created_at__date__gte=week_ago)
    week_revenue = week_sales.aggregate(total=Sum('final_amount'))['total'] or 0
    
    # Monthly sales
    month_revenue = Sale.objects.filter(created_at__date__gte=month_ago).aggregate(
        total=Sum('final_amount'))['total'] or 0
    
    # Low stock products - Fixed the issue here
    low_stock_count = Product.objects.filter(
        stock_quantity__lte=F('minimum_stock'),  # Changed from models.F to F
        is_active=True
    ).count()
    
    # Total products
    total_products = Product.objects.filter(is_active=True).count()
    
    # Recent sales
    recent_sales = Sale.objects.select_related('cashier').order_by('-created_at')[:5]
    
    return Response({
        'today_revenue': today_revenue,
        'today_transactions': today_transactions,
        'week_revenue': week_revenue,
        'month_revenue': month_revenue,
        'low_stock_count': low_stock_count,
        'total_products': total_products,
        'recent_sales': SaleSerializer(recent_sales, many=True).data
    })
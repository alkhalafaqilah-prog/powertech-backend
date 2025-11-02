from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from .models import Product, Cart, CartItem, Transaction
from .serializers import ProductSerializer, DetailedProductSerializer, CartSerializer, CartItemSerializer, SimpleCartSerializer, UserSerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.conf import settings
import uuid
import requests

# Create your views here.

BASE_URL = "http://localhost:5173"
# BASE_URL = settings.REACT_BASE_URL


@api_view(['GET'])
def products(request):
    products = Product.objects.all()
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)

@api_view(["GET"])
def product_detail(request, slug):
    product = Product.objects.get(slug=slug)
    serializer = DetailedProductSerializer(product)
    return Response(serializer.data)

@api_view(["POST"])
def add_item(request):
    try:
        cart_code = request.data.get("cart_code")
        product_id = request.data.get("product_id")

        cart, created =Cart.objects.get_or_create(cart_code = cart_code)
        product = Product.objects.get(id=product_id)

        cartitem, created  = CartItem.objects.get_or_create(cart=cart, product=product)
        cartitem.quantity = 1 
        cartitem.save()

        serializer = CartItemSerializer(cartitem)
        return Response({"data": serializer.data, "message": "CartItem created successfully"}, status=201)
    except Exception as e:
        return Response({"error": str(e)}, status=400)

# This method is to make sure when we refresh the page the product is still on the cart
@api_view(['GET'])
def product_in_cart(request):
    cart_code = request.query_params.get("cart_code")
    product_id = request.query_params.get("product_id")
    
    cart = Cart.objects.get(cart_code=cart_code)
    product = Product.objects.get(id=product_id)
    
    product_exists_in_cart = CartItem.objects.filter(cart=cart, product=product).exists()

    return Response({'product_in_cart': product_exists_in_cart})

@api_view(['GET'])
def get_cart_stat(request):
    cart_code = request.query_params.get("cart_code")
    cart = Cart.objects.get(cart_code=cart_code, paid=False)
    serializer = SimpleCartSerializer(cart)
    return Response(serializer.data)

@api_view(['GET'])
def get_cart(request):
    cart_code = request.query_params.get("cart_code")
    cart = Cart.objects.get(cart_code=cart_code, paid=False)
    serializer = CartSerializer(cart)
    return Response(serializer.data)

# Here we are taking only the quantity field of our cart items
@api_view(['PATCH'])
def update_quantity(request):
    try:
        cartitem_id =  request.data.get("item_id")
        quantity = request.data.get("quantity")
        quantity = int(quantity)
        cartitem = CartItem.objects.get(id=cartitem_id)
        cartitem.quantity = quantity
        cartitem.save()
        serializer = CartItemSerializer(cartitem)
        return Response({ "data":serializer.data, "message": "Cartitem updated successfully!"}, status=200)
    
    except Exception as e:
        return Response({'error': str(e)}, status=400)
    

@api_view(['POST'])
def delete_cartitem(request):
    cartitem_id = request.data.get("item_id")
    cartitem = CartItem.objects.get(id=cartitem_id)
    cartitem.delete()
    return Response({"mesaage": "Item deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_username(request):
    user = request.user 
    return Response({"username": user.username})

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_info(request):
    user = request.user 
    serializer = UserSerializer(user)
    return Response(serializer.data)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    # Check if user is logged in
    if request.user:
        try:
            # Generate a unique transaction reference
            tx_ref = str(uuid.uuid4())
            cart_code = request.data.get("cart_code")
            cart = Cart.objects.get(cart_code=cart_code)
            user = request.user 

            amount = sum([item.quantity * item.product.price for item in cart.items.all()])
            delivery_fee = Decimal("100.00")
            total_amount = amount + delivery_fee 
            currency = "SAR"
            redirect_url = f"{BASE_URL}/payment-status/"

            transaction = Transaction.objects.create(
                ref=tx_ref,
                cart=cart,
                amount=total_amount,
                currency=currency,
                user=user,
                status='pending'
            )

            flutterwave_payload = {
                "tx_ref": tx_ref,
                "amount": str(total_amount),  # Convert to string
                "currency": currency,
                "redirect_url": redirect_url,
                "customer": {
                    "email": user.email,
                    "name": user.username,
                    "phonenumber": user.phone
                },
                "customizations": {
                    "title": "Shoppit Payment"
                }
            }


            # Set up the headers for the request
            headers = {
                "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}",
                "Content-Type": "application/json"
            }


            # Make the API request to Flutterwave
            response = requests.post(
                'https://api.flutterwave.com/v3/payments',
                json=flutterwave_payload,
                headers=headers
            )

            # Check if the request was successful
            if response.status_code == 200:
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response(response.json(), status=response.status_code)
            
        except requests.exceptions.RequestException as e:
                # Log the error and return an error response
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
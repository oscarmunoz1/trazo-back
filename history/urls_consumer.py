"""
Consumer-specific URL patterns for API endpoints
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_consumer import (
    ConsumerDashboardViewSet,
    UserFavoriteViewSet,
    UserShoppingGoalViewSet
)

# Create router for consumer APIs
consumer_router = DefaultRouter()
consumer_router.register(r'dashboard', ConsumerDashboardViewSet, basename='consumer-dashboard')
consumer_router.register(r'favorites', UserFavoriteViewSet, basename='user-favorites')
consumer_router.register(r'goals', UserShoppingGoalViewSet, basename='user-goals')

urlpatterns = [
    # Consumer API endpoints
    path('consumer/', include(consumer_router.urls)),
]
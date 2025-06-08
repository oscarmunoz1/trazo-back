from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tickets', views.SupportTicketViewSet, basename='supportticket')
router.register(r'messages', views.SupportMessageViewSet, basename='supportmessage')
router.register(r'attachments', views.SupportAttachmentViewSet, basename='supportattachment')

urlpatterns = [
    path('', include(router.urls)),
] 
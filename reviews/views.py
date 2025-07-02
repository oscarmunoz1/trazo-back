from django.shortcuts import render

# Create your views here.

from rest_framework import generics, permissions, viewsets, filters
from rest_framework.response import Response

from .models import Review
from .serializers import ReviewSerializer, ListReviewSerializer


class ReviewsViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter]

    def get_serializer_class(self):
        if self.action == "list":
            return ListReviewSerializer
        else:
            return ReviewSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        
        # Handle scan_id if provided
        if "scan_id" in data:
            # If it's a web review (starts with 'web-'), remove it as it's not a real scan
            if isinstance(data["scan_id"], str) and data["scan_id"].startswith("web-"):
                data.pop("scan_id", None)
                data.pop("scan", None)
            else:
                # Otherwise, treat it as a real scan ID
                data["scan"] = data.pop("scan_id", None)
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)

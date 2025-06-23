from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, filters, mixins
from .models import Parcel, Product
from .serializers import (
    RetrieveParcelSerializer,
    CreateParcelSerializer,
    ProductListSerializer,
    ProductListOptionsSerializer,
)
from history.serializers import HistorySerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from backend.permissions import CompanyNestedViewSet
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
from common.models import GalleryImage, Gallery
from subscriptions.permissions import HasParcelCreationPermission
from rest_framework.permissions import IsAuthenticated

class ParcelViewSet(CompanyNestedViewSet, viewsets.ModelViewSet):
    queryset = Parcel.objects.all()
    filter_backends = [filters.OrderingFilter]
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated, HasParcelCreationPermission]

    def get_serializer_class(self):
        if (
            self.action == "create"
            or self.action == "update"
            or self.action == "partial_update"
        ):
            return CreateParcelSerializer
        return RetrieveParcelSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @action(detail=True, methods=["get"])
    def current_history(
        self, request, pk=None, parcel_pk=None, company_pk=None, establishment_pk=None
    ):
        establishments = self.company.establishment_set.all()
        parcel = get_object_or_404(
            Parcel,
            id=pk,
            establishment__in=establishments.all(),
        )
        current_history = parcel.current_history
        return Response(HistorySerializer(current_history).data)

    @action(detail=True, methods=["get"])
    def history(
        self, request, pk=None, parcel_pk=None, company_pk=None, establishment_pk=None
    ):
        """
        OPTIMIZED: Get parcel history using the optimized serializer to prevent USDA API calls.
        This endpoint was causing performance issues by using HistorySerializer which triggers
        expensive carbon calculations and USDA API calls.
        """
        from history.serializers import OptimizedHistoryListSerializer
        
        parcel = self.get_object()

        # Use optimized queryset to prevent N+1 queries
        histories = parcel.histories.select_related(
            'product',
            'parcel',
            'crop_type'
        ).only(
            'id', 'name', 'start_date', 'finish_date', 'published',
            'earning', 'reputation', 'qr_code', 'is_outdoor',
            'age_of_plants', 'number_of_plants', 'soil_ph', 'extra_data',
            'product__id', 'product__name',
            'parcel__id', 'parcel__name', 
            'crop_type__id', 'crop_type__name', 'crop_type__category', 'crop_type__slug'
        ).filter(published=True).order_by("-id")
        
        if parcel.current_history is not None:
            histories = histories.exclude(id=parcel.current_history.id)
        
        # Use the optimized serializer that avoids expensive operations
        return Response(
            OptimizedHistoryListSerializer(
                histories, many=True, context={'request': request}
            ).data
        )

    @action(detail=True, methods=["post"])
    def finish_history(
        self, request, pk=None, parcel_pk=None, company_pk=None, establishment_pk=None
    ):
        parcel = self.get_object()
        history_data = request.data
        images = request.FILES.getlist("album[images]")
        history = parcel.finish_current_history(history_data, images)
        if history is not None:
            return Response(HistorySerializer(history).data)
        return Response(status=400)

    # @action(detail=True, methods=["post"])
    # def update_parcel(
    #     self, request, pk=None, parcel_pk=None, company_pk=None, establishment_pk=None
    # ):
    #     import pdb

    #     pdb.set_trace()

    #     parcel = self.get_object()
    #     parsed_body = request.body
    #     print(request.FILES.getList("album"))
    #     name = request.data.get("id")
    #     images_data = request.data.get("album")
    #     images_post = request.POST.get("album")
    #     image = request.FILES.get("album")
    #     data = request.data
    #     data2 = request.POST
    #     data3 = request.data.get("album")
    #     # print(parsed_body)

    #     print("despues")

    #     print("images_data::::->>>>>>>")
    #     print(name)
    #     print(images_data)
    #     print(images_post)
    #     print(image)
    #     print(data)
    #     print(data2)
    #     print(data3)
    #     print(request)
    #     # parcel_data = request.data
    #     # serializer = CreateParcelSerializer(
    #     #     parcel, data=parcel_data, partial=True, context={"request": request}
    #     # )
    #     # if serializer.is_valid():
    #     #     serializer.save()
    #     #     return Response(serializer.data)
    #     return Response({}, status=400)

    # def partial_update(self, request, pk=None, company_pk=None, establishment_pk=None):
    #     parcel = self.get_object()
    #     parcel_data = request.data
    #     print(request.FILES)
    #     if parcel_data.get("album") is not None:
    #         album_data = parcel_data.get("album")
    #         parcel_data.pop("album")
    #     serializer = CreateParcelSerializer(
    #         parcel, data=parcel_data, partial=True, context={"request": request}
    #     )
    #     if serializer.is_valid():
    #         serializer.save()
    #         if album_data is None and album_data is not None:
    #             album = Gallery.objects.create()
    #             parcel.album = album
    #             parcel.save()
    #         if album_data is not None:
    #             print("entro1")
    #             for image_data in request.FILES:
    #                 print("entro2")
    #                 print(image_data)
    #                 print(request.FILES[image_data])
    #                 GalleryImage.objects.create(
    #                     image=request.FILES[image_data], gallery_id=1
    #                 )

    #         return Response(serializer.data)
    #     return Response(serializer.errors, status=400)

    # def update(self, request, pk=None, company_pk=None, establishment_pk=None):
    #     images_data = request.data.get("album")
    #     images_post = request.POST.get("album")
    #     image = request.FILES.get("album")
    #     data = request.data
    #     data2 = request.POST
    #     data3 = request.data.get("album")
    #     print("anntes")
    #     print(request.FILES)
    #     print("despues")

    #     print("images_data::::")
    #     print(images_data)
    #     print(images_post)
    #     print(image)
    #     print(data)
    #     print(data2)
    #     print(data3)
    #     parcel = self.get_object()
    #     parcel_data = request.data
    #     serializer = CreateParcelSerializer(
    #         parcel, data=parcel_data, partial=True, context={"request": request}
    #     )
    #     if serializer.is_valid():
    #         serializer.save()
    #         album = parcel_data.get("album")
    #         if album is not None:
    #             for image_data in album.get("images"):
    #                 parcel.album.images.create(
    #                     image=image_data.get("image"), gallery=parcel.album
    #                 )
    #         return Response(serializer.data)
    #     return Response(serializer.errors, status=400)


class ProductsViewSet(CompanyNestedViewSet, mixins.ListModelMixin):
    queryset = Product.objects.all()
    serializer_class = ProductListSerializer
    filter_backends = [filters.OrderingFilter]

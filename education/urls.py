from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EducationCategoryViewSet,
    EducationCourseViewSet,
    EducationLessonViewSet,
    FarmerQuestionAnswerViewSet
)

router = DefaultRouter()
router.register(r'categories', EducationCategoryViewSet, basename='education-categories')
router.register(r'courses', EducationCourseViewSet, basename='education-courses')
router.register(r'lessons', EducationLessonViewSet, basename='education-lessons')
router.register(r'faqs', FarmerQuestionAnswerViewSet, basename='education-faqs')

urlpatterns = [
    path('', include(router.urls)),
] 
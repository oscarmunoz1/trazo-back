from rest_framework import serializers
from .models import (
    EducationCategory,
    EducationCourse,
    EducationLesson,
    UserEducationProgress,
    EducationCertificate,
    EducationBookmark,
    FarmerQuestionAnswer
)

class EducationCategorySerializer(serializers.ModelSerializer):
    course_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = EducationCategory
        fields = ['id', 'name', 'category_type', 'description', 'icon', 'order', 'course_count']

class EducationLessonSummarySerializer(serializers.ModelSerializer):
    """Simplified lesson serializer for course listings"""
    is_completed = serializers.SerializerMethodField()
    
    class Meta:
        model = EducationLesson
        fields = ['id', 'title', 'content_type', 'duration', 'order', 'is_completed']
    
    def get_is_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserEducationProgress.objects.filter(
                user=request.user,
                lesson=obj,
                completed_at__isnull=False
            ).exists()
        return False

class EducationCourseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    lessons = EducationLessonSummarySerializer(many=True, read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    total_lessons = serializers.SerializerMethodField()
    completed_lessons = serializers.SerializerMethodField()
    
    class Meta:
        model = EducationCourse
        fields = [
            'id', 'title', 'description', 'difficulty', 'required_plan',
            'estimated_duration', 'target_crops', 'farm_size_min', 'farm_size_max',
            'is_featured', 'category_name', 'lessons', 'progress_percentage',
            'total_lessons', 'completed_lessons'
        ]
    
    def get_total_lessons(self, obj):
        return obj.lessons.filter(is_active=True).count()
    
    def get_completed_lessons(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserEducationProgress.objects.filter(
                user=request.user,
                lesson__course=obj,
                completed_at__isnull=False
            ).count()
        return 0
    
    def get_progress_percentage(self, obj):
        total = self.get_total_lessons(obj)
        completed = self.get_completed_lessons(obj)
        return int((completed / total) * 100) if total > 0 else 0

class EducationLessonSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    progress = serializers.SerializerMethodField()
    
    class Meta:
        model = EducationLesson
        fields = [
            'id', 'title', 'content_type', 'content', 'video_url',
            'duration', 'order', 'has_quiz', 'quiz_questions',
            'practical_steps', 'real_farm_example', 'cost_savings_potential',
            'time_savings_potential', 'course_title', 'progress'
        ]
    
    def get_progress(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                progress = UserEducationProgress.objects.get(
                    user=request.user,
                    lesson=obj
                )
                return UserEducationProgressSerializer(progress).data
            except UserEducationProgress.DoesNotExist:
                return None
        return None

class UserEducationProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    course_title = serializers.CharField(source='lesson.course.title', read_only=True)
    
    class Meta:
        model = UserEducationProgress
        fields = [
            'id', 'lesson', 'lesson_title', 'course_title',
            'started_at', 'completed_at', 'quiz_score', 'time_spent',
            'bookmarked', 'helpful_rating', 'feedback', 'is_completed'
        ]
        read_only_fields = ['is_completed']

class EducationCertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = EducationCertificate
        fields = [
            'id', 'course', 'course_title', 'certificate_id',
            'issued_at', 'completion_percentage', 'total_time_spent',
            'average_quiz_score'
        ]

class EducationBookmarkSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    course_title = serializers.CharField(source='lesson.course.title', read_only=True)
    
    class Meta:
        model = EducationBookmark
        fields = [
            'id', 'lesson', 'lesson_title', 'course_title',
            'created_at', 'notes'
        ]

class FarmerQuestionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FarmerQuestionAnswer
        fields = [
            'id', 'question', 'answer', 'category',
            'is_featured', 'view_count', 'helpful_votes'
        ] 
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from .models import (
    EducationCategory,
    EducationCourse, 
    EducationLesson,
    UserEducationProgress,
    EducationCertificate,
    EducationBookmark,
    FarmerQuestionAnswer
)
from .serializers import (
    EducationCategorySerializer,
    EducationCourseSerializer,
    EducationLessonSerializer,
    UserEducationProgressSerializer,
    EducationCertificateSerializer,
    EducationBookmarkSerializer,
    FarmerQuestionAnswerSerializer
)
from subscriptions.models import Subscription

class EducationCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """View categories of educational content"""
    queryset = EducationCategory.objects.filter(is_active=True)
    serializer_class = EducationCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return active categories with course counts"""
        return EducationCategory.objects.filter(is_active=True).annotate(
            course_count=Count('courses', filter=Q(courses__is_active=True))
        ).order_by('order', 'name')

class EducationCourseViewSet(viewsets.ReadOnlyModelViewSet):
    """View educational courses based on user's subscription plan"""
    queryset = EducationCourse.objects.filter(is_active=True)
    serializer_class = EducationCourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter courses based on user's subscription plan"""
        user = self.request.user
        
        # Get user's subscription plan
        user_plan = 'basic'  # default
        try:
            subscription = Subscription.objects.filter(
                user=user,
                is_active=True
            ).order_by('-created_at').first()
            
            if subscription and subscription.plan:
                if 'corporate' in subscription.plan.name.lower():
                    user_plan = 'corporate'
                elif 'standard' in subscription.plan.name.lower():
                    user_plan = 'standard'
        except:
            pass

        # Filter courses based on plan access
        queryset = EducationCourse.objects.filter(is_active=True)
        
        if user_plan == 'basic':
            queryset = queryset.filter(Q(required_plan='all') | Q(required_plan='basic'))
        elif user_plan == 'standard':
            queryset = queryset.filter(Q(required_plan__in=['all', 'basic', 'standard']))
        elif user_plan == 'corporate':
            # Corporate users have access to all courses
            pass
        else:
            # Default to basic access
            queryset = queryset.filter(Q(required_plan='all') | Q(required_plan='basic'))

        return queryset.order_by('category__order', 'order', 'title')

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured courses for the dashboard"""
        featured_courses = self.get_queryset().filter(is_featured=True)[:6]
        serializer = self.get_serializer(featured_courses, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get courses grouped by category"""
        category_id = request.query_params.get('category_id')
        if category_id:
            courses = self.get_queryset().filter(category_id=category_id)
        else:
            courses = self.get_queryset()
        
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)

class EducationLessonViewSet(viewsets.ReadOnlyModelViewSet):
    """View individual lessons within courses"""
    queryset = EducationLesson.objects.filter(is_active=True)
    serializer_class = EducationLessonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter lessons based on course access"""
        # Get courses user has access to
        course_viewset = EducationCourseViewSet()
        course_viewset.request = self.request
        accessible_courses = course_viewset.get_queryset()
        
        return EducationLesson.objects.filter(
            is_active=True,
            course__in=accessible_courses
        ).order_by('course', 'order', 'title')

    @action(detail=True, methods=['post'])
    def start_lesson(self, request, pk=None):
        """Mark lesson as started and track progress"""
        lesson = self.get_object()
        user = request.user
        
        progress, created = UserEducationProgress.objects.get_or_create(
            user=user,
            lesson=lesson,
            defaults={'started_at': timezone.now()}
        )
        
        serializer = UserEducationProgressSerializer(progress)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete_lesson(self, request, pk=None):
        """Mark lesson as completed"""
        lesson = self.get_object()
        user = request.user
        
        # Get or create progress record
        progress, created = UserEducationProgress.objects.get_or_create(
            user=user,
            lesson=lesson,
            defaults={'started_at': timezone.now()}
        )
        
        # Mark as completed if not already
        if not progress.completed_at:
            progress.completed_at = timezone.now()
            
        # Update quiz score if provided
        quiz_score = request.data.get('quiz_score')
        if quiz_score is not None:
            progress.quiz_score = min(100, max(0, int(quiz_score)))
            
        # Update time spent
        time_spent = request.data.get('time_spent', 0)
        if time_spent:
            progress.time_spent = max(progress.time_spent, int(time_spent))
            
        progress.save()
        
        # Check if course is completed and issue certificate
        self._check_course_completion(user, lesson.course)
        
        serializer = UserEducationProgressSerializer(progress)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def submit_quiz(self, request, pk=None):
        """Submit quiz answers and calculate score"""
        lesson = self.get_object()
        user = request.user
        
        if not lesson.has_quiz:
            return Response({'error': 'This lesson does not have a quiz'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        quiz_answers = request.data.get('answers', {})
        quiz_questions = lesson.quiz_questions
        
        # Calculate score
        correct_answers = 0
        total_questions = len(quiz_questions.get('questions', []))
        
        for i, question in enumerate(quiz_questions.get('questions', [])):
            correct_answer = question.get('correct_answer')
            user_answer = quiz_answers.get(str(i))
            
            if user_answer == correct_answer:
                correct_answers += 1
        
        score = int((correct_answers / total_questions) * 100) if total_questions > 0 else 0
        
        # Update progress
        progress, created = UserEducationProgress.objects.get_or_create(
            user=user,
            lesson=lesson,
            defaults={'started_at': timezone.now()}
        )
        
        progress.quiz_score = score
        progress.save()
        
        return Response({
            'score': score,
            'correct_answers': correct_answers,
            'total_questions': total_questions,
            'passed': score >= 70  # 70% passing grade
        })

    def _check_course_completion(self, user, course):
        """Check if user has completed all lessons in a course and issue certificate"""
        total_lessons = course.lessons.filter(is_active=True).count()
        completed_lessons = UserEducationProgress.objects.filter(
            user=user,
            lesson__course=course,
            completed_at__isnull=False
        ).count()
        
        if completed_lessons >= total_lessons and total_lessons > 0:
            # User completed the course
            certificate, created = EducationCertificate.objects.get_or_create(
                user=user,
                course=course,
                defaults={
                    'certificate_id': f"TRAZO-{course.id}-{user.id}-{timezone.now().strftime('%Y%m%d')}",
                    'completion_percentage': 100,
                    'total_time_spent': UserEducationProgress.objects.filter(
                        user=user, lesson__course=course
                    ).aggregate(total_time=Sum('time_spent'))['total_time'] or 0,
                    'average_quiz_score': UserEducationProgress.objects.filter(
                        user=user, lesson__course=course, quiz_score__isnull=False
                    ).aggregate(avg_score=Avg('quiz_score'))['avg_score']
                }
            )
            return certificate
        return None

class UserEducationProgressViewSet(viewsets.ModelViewSet):
    """Track user progress through educational content"""
    serializer_class = UserEducationProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return progress for current user only"""
        return UserEducationProgress.objects.filter(
            user=self.request.user
        ).order_by('-started_at')

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get progress statistics for dashboard"""
        user = request.user
        
        # Get user's accessible courses
        course_viewset = EducationCourseViewSet()
        course_viewset.request = request
        accessible_courses = course_viewset.get_queryset()
        
        total_courses = accessible_courses.count()
        total_lessons = EducationLesson.objects.filter(
            course__in=accessible_courses, is_active=True
        ).count()
        
        completed_lessons = UserEducationProgress.objects.filter(
            user=user,
            lesson__course__in=accessible_courses,
            completed_at__isnull=False
        ).count()
        
        certificates_earned = EducationCertificate.objects.filter(
            user=user,
            course__in=accessible_courses
        ).count()
        
        # Recently accessed lessons
        recent_lessons = UserEducationProgress.objects.filter(
            user=user,
            lesson__course__in=accessible_courses
        ).order_by('-started_at')[:5]
        
        return Response({
            'total_courses': total_courses,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'certificates_earned': certificates_earned,
            'completion_percentage': int((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0,
            'recent_lessons': UserEducationProgressSerializer(recent_lessons, many=True).data
        })

class EducationCertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """View earned certificates"""
    serializer_class = EducationCertificateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return certificates for current user only"""
        return EducationCertificate.objects.filter(
            user=self.request.user
        ).order_by('-issued_at')

class EducationBookmarkViewSet(viewsets.ModelViewSet):
    """Manage bookmarked lessons"""
    serializer_class = EducationBookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return bookmarks for current user only"""
        return EducationBookmark.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

    def perform_create(self, serializer):
        """Set current user when creating bookmark"""
        serializer.save(user=self.request.user)

class FarmerQuestionAnswerViewSet(viewsets.ReadOnlyModelViewSet):
    """View FAQ for farmers"""
    queryset = FarmerQuestionAnswer.objects.all()
    serializer_class = FarmerQuestionAnswerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return FAQs ordered by helpfulness"""
        return FarmerQuestionAnswer.objects.all().order_by(
            '-is_featured', '-helpful_votes', '-view_count'
        )

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured FAQs"""
        featured_faqs = self.get_queryset().filter(is_featured=True)[:10]
        serializer = self.get_serializer(featured_faqs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get FAQs by category"""
        category = request.query_params.get('category')
        if category:
            faqs = self.get_queryset().filter(category=category)
        else:
            faqs = self.get_queryset()
        
        serializer = self.get_serializer(faqs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, pk=None):
        """Mark FAQ as helpful"""
        faq = self.get_object()
        faq.helpful_votes += 1
        faq.save()
        
        return Response({'helpful_votes': faq.helpful_votes})

    def retrieve(self, request, *args, **kwargs):
        """Increment view count when FAQ is viewed"""
        faq = self.get_object()
        faq.view_count += 1
        faq.save()
        
        return super().retrieve(request, *args, **kwargs) 
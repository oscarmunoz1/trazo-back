from django.contrib import admin
from .models import (
    EducationCategory, 
    EducationCourse, 
    EducationLesson, 
    UserEducationProgress, 
    EducationCertificate, 
    EducationBookmark,
    FarmerQuestionAnswer
)

@admin.register(EducationCategory)
class EducationCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type', 'order', 'is_active', 'created_at')
    list_filter = ('is_active', 'category_type')
    search_fields = ('name', 'description')
    ordering = ('order', 'name')

class EducationLessonInline(admin.TabularInline):
    model = EducationLesson
    extra = 1
    fields = ('title', 'content_type', 'duration', 'order', 'is_active')
    ordering = ('order',)

@admin.register(EducationCourse)
class EducationCourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'required_plan', 'estimated_duration', 'is_featured', 'is_active')
    list_filter = ('category', 'difficulty', 'required_plan', 'is_featured', 'is_active')
    search_fields = ('title', 'description', 'target_crops')
    ordering = ('category', 'order', 'title')
    inlines = [EducationLessonInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'category', 'description', 'difficulty', 'required_plan')
        }),
        ('Content Details', {
            'fields': ('estimated_duration', 'order', 'is_featured', 'is_active')
        }),
        ('Target Audience', {
            'fields': ('target_crops', 'farm_size_min', 'farm_size_max'),
            'classes': ('collapse',)
        })
    )

@admin.register(EducationLesson)
class EducationLessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'content_type', 'duration', 'has_quiz', 'order', 'is_active')
    list_filter = ('content_type', 'has_quiz', 'is_active', 'course__category')
    search_fields = ('title', 'content', 'course__title')
    ordering = ('course', 'order', 'title')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('course', 'title', 'content_type', 'duration', 'order', 'is_active')
        }),
        ('Content', {
            'fields': ('content', 'video_url')
        }),
        ('Interactive Elements', {
            'fields': ('has_quiz', 'quiz_questions', 'practical_steps'),
            'classes': ('collapse',)
        }),
        ('Real-World Application', {
            'fields': ('real_farm_example', 'cost_savings_potential', 'time_savings_potential'),
            'classes': ('collapse',)
        })
    )

@admin.register(UserEducationProgress)
class UserEducationProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'is_completed', 'quiz_score', 'time_spent', 'helpful_rating', 'started_at')
    list_filter = ('completed_at', 'lesson__course__category', 'quiz_score', 'helpful_rating')
    search_fields = ('user__username', 'user__email', 'lesson__title')
    readonly_fields = ('started_at',)
    
    def is_completed(self, obj):
        return obj.is_completed
    is_completed.boolean = True

@admin.register(EducationCertificate)
class EducationCertificateAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'certificate_id', 'completion_percentage', 'total_time_spent', 'issued_at')
    list_filter = ('course__category', 'issued_at', 'completion_percentage')
    search_fields = ('user__username', 'course__title', 'certificate_id')
    readonly_fields = ('issued_at', 'certificate_id')

@admin.register(EducationBookmark)
class EducationBookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'created_at')
    list_filter = ('lesson__course__category', 'created_at')
    search_fields = ('user__username', 'lesson__title', 'notes')

@admin.register(FarmerQuestionAnswer)
class FarmerQuestionAnswerAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'is_featured', 'view_count', 'helpful_votes', 'created_at')
    list_filter = ('category', 'is_featured', 'created_at')
    search_fields = ('question', 'answer')
    ordering = ('-helpful_votes', '-view_count')
    readonly_fields = ('view_count', 'helpful_votes')
    
    fieldsets = (
        ('Question & Answer', {
            'fields': ('question', 'answer', 'category')
        }),
        ('Settings', {
            'fields': ('is_featured',)
        }),
        ('Statistics', {
            'fields': ('view_count', 'helpful_votes'),
            'classes': ('collapse',)
        })
    ) 
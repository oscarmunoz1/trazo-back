from django.db import models
from django.conf import settings
from django.utils import timezone
from company.models import Company

class EducationCategory(models.Model):
    """Categories for organizing educational content by farming topics"""
    
    CATEGORY_TYPES = [
        ('getting_started', 'Getting Started with Trazo'),
        ('carbon_tracking', 'Carbon Footprint Tracking'),
        ('iot_automation', 'IoT & Farm Automation'),
        ('sustainability', 'Sustainable Farming Practices'),
        ('consumer_engagement', 'Consumer Transparency & QR Codes'),
        ('cost_optimization', 'Cost Savings & ROI'),
        ('compliance', 'USDA Compliance & Certifications'),
        ('troubleshooting', 'Common Issues & Solutions'),
    ]
    
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=30, choices=CATEGORY_TYPES, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text='Icon class name for UI')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Education Categories'
    
    def __str__(self):
        return self.name

class EducationCourse(models.Model):
    """Comprehensive courses explaining how Trazo works for farmers"""
    
    DIFFICULTY_LEVELS = [
        ('beginner', 'Beginner - New to Trazo'),
        ('intermediate', 'Intermediate - Basic Trazo Knowledge'),
        ('advanced', 'Advanced - Expert Features'),
    ]
    
    PLAN_ACCESS = [
        ('basic', 'Basic Plan'),
        ('standard', 'Standard Plan & Above'),
        ('corporate', 'Corporate Plan Only'),
        ('all', 'All Plans'),
    ]
    
    title = models.CharField(max_length=200)
    category = models.ForeignKey(EducationCategory, on_delete=models.CASCADE, related_name='courses')
    description = models.TextField()
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS)
    required_plan = models.CharField(max_length=20, choices=PLAN_ACCESS, default='all')
    estimated_duration = models.PositiveIntegerField(help_text='Duration in minutes')
    order = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Farmer-specific content
    target_crops = models.CharField(max_length=200, blank=True, help_text='Comma-separated list of relevant crops')
    farm_size_min = models.PositiveIntegerField(blank=True, null=True, help_text='Minimum farm size in acres')
    farm_size_max = models.PositiveIntegerField(blank=True, null=True, help_text='Maximum farm size in acres')
    
    class Meta:
        ordering = ['category', 'order', 'title']
    
    def __str__(self):
        return f"{self.title} ({self.difficulty})"

class EducationLesson(models.Model):
    """Individual lessons within courses, farmer-focused content"""
    
    CONTENT_TYPES = [
        ('text', 'Text Guide'),
        ('video', 'Video Tutorial'),
        ('interactive', 'Interactive Demo'),
        ('checklist', 'Step-by-Step Checklist'),
        ('case_study', 'Real Farm Example'),
    ]
    
    course = models.ForeignKey(EducationCourse, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    content = models.TextField(help_text='Main lesson content in markdown format')
    video_url = models.URLField(blank=True, help_text='Video URL for video lessons')
    duration = models.PositiveIntegerField(help_text='Lesson duration in minutes')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Interactive elements
    has_quiz = models.BooleanField(default=False)
    quiz_questions = models.JSONField(default=dict, blank=True)
    practical_steps = models.JSONField(default=list, blank=True, help_text='Actionable steps for farmers')
    
    # Real-world relevance
    real_farm_example = models.TextField(blank=True, help_text='Real farm case study or example')
    cost_savings_potential = models.CharField(max_length=100, blank=True, help_text='e.g., "$500-1,200 annually"')
    time_savings_potential = models.CharField(max_length=100, blank=True, help_text='e.g., "2-3 hours per week"')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['course', 'order', 'title']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"

class UserEducationProgress(models.Model):
    """Track farmer progress through educational content"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lesson = models.ForeignKey(EducationLesson, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    quiz_score = models.PositiveIntegerField(blank=True, null=True, help_text='Quiz score as percentage')
    time_spent = models.PositiveIntegerField(default=0, help_text='Time spent in minutes')
    bookmarked = models.BooleanField(default=False)
    helpful_rating = models.PositiveIntegerField(blank=True, null=True, help_text='1-5 star rating')
    feedback = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['user', 'lesson']
    
    def __str__(self):
        return f"{self.user.username} - {self.lesson.title}"
    
    @property
    def is_completed(self):
        return self.completed_at is not None

class EducationCertificate(models.Model):
    """Certificates awarded for completing courses"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    course = models.ForeignKey(EducationCourse, on_delete=models.CASCADE)
    issued_at = models.DateTimeField(auto_now_add=True)
    certificate_id = models.CharField(max_length=50, unique=True)
    
    # Completion metrics
    completion_percentage = models.PositiveIntegerField()
    total_time_spent = models.PositiveIntegerField(help_text='Total time in minutes')
    average_quiz_score = models.PositiveIntegerField(blank=True, null=True)
    
    class Meta:
        unique_together = ['user', 'course']
    
    def __str__(self):
        return f"Certificate: {self.user.username} - {self.course.title}"

class EducationBookmark(models.Model):
    """Allow farmers to bookmark useful lessons"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lesson = models.ForeignKey(EducationLesson, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text='Personal notes about the lesson')
    
    class Meta:
        unique_together = ['user', 'lesson']
    
    def __str__(self):
        return f"{self.user.username} bookmarked {self.lesson.title}"

class FarmerQuestionAnswer(models.Model):
    """FAQ system for common farmer questions about Trazo"""
    
    QUESTION_CATEGORIES = [
        ('setup', 'Getting Started'),
        ('data_entry', 'Data Entry & Events'),
        ('carbon', 'Carbon Tracking'),
        ('iot', 'IoT & Automation'),
        ('qr_codes', 'QR Codes & Consumers'),
        ('billing', 'Pricing & Plans'),
        ('technical', 'Technical Issues'),
        ('compliance', 'USDA & Certifications'),
    ]
    
    question = models.CharField(max_length=300)
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=QUESTION_CATEGORIES)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    helpful_votes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-helpful_votes', '-view_count']
    
    def __str__(self):
        return self.question[:100] 
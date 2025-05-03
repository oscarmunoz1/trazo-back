from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.utils import timezone
from django.utils.html import format_html
from .models import User, WorksIn, VerificationCode
from .forms import CustomUserCreationForm, CustomUserChangeForm
from company.models import Company
from subscriptions.models import Subscription, Plan

class SubscriptionInfoListFilter(admin.SimpleListFilter):
    title = "Subscription Status"
    parameter_name = "subscription_status"
    
    def lookups(self, request, model_admin):
        return (
            ('active', 'Active'),
            ('trialing', 'Trialing'),
            ('canceled', 'Canceled'),
            ('no_subscription', 'No Subscription'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(companies__subscription__status='active')
        if self.value() == 'trialing':
            return queryset.filter(companies__subscription__status='trialing')
        if self.value() == 'canceled':
            return queryset.filter(companies__subscription__status='canceled')
        if self.value() == 'no_subscription':
            return queryset.filter(companies__subscription__isnull=True)

class RoleInline(admin.TabularInline):
    model = WorksIn
    extra = 1
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "company":
            kwargs["queryset"] = Company.objects.prefetch_related('subscription').all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

class CompanyWithSubscriptionInline(admin.TabularInline):
    model = User.companies.through
    extra = 0
    readonly_fields = ('company', 'role', 'subscription_status', 'plan_name', 'current_period_end', 'manage_subscription')
    fields = ('company', 'role', 'subscription_status', 'plan_name', 'current_period_end', 'manage_subscription')
    verbose_name = "Company & Subscription"
    verbose_name_plural = "Companies & Subscriptions"
    
    def subscription_status(self, obj):
        if hasattr(obj.company, 'subscription') and obj.company.subscription:
            status = obj.company.subscription.status
            status_classes = {
                'active': 'success',
                'trialing': 'info',
                'canceled': 'danger',
                'past_due': 'warning',
                'unpaid': 'warning',
                'incomplete': 'warning',
            }
            status_class = status_classes.get(status, 'default')
            return format_html('<span class="badge badge-{}">{}</span>', status_class, status.title())
        return format_html('<span class="badge badge-secondary">None</span>')
    subscription_status.short_description = "Status"
    
    def plan_name(self, obj):
        if hasattr(obj.company, 'subscription') and obj.company.subscription:
            return obj.company.subscription.plan.name
        return "N/A"
    plan_name.short_description = "Plan"
    
    def current_period_end(self, obj):
        if hasattr(obj.company, 'subscription') and obj.company.subscription:
            end_date = obj.company.subscription.current_period_end
            if end_date:
                return end_date.strftime('%d %b %Y')
        return "N/A"
    current_period_end.short_description = "Renewal Date"
    
    def manage_subscription(self, obj):
        if hasattr(obj.company, 'subscription') and obj.company.subscription:
            sub = obj.company.subscription
            sub_id = sub.id
            company_id = obj.company.id
            
            cancel_url = f"/admin/subscriptions/subscription/{sub_id}/change/"
            view_url = f"/admin/subscriptions/subscription/{sub_id}/change/"
            delete_url = f"/admin/subscriptions/subscription/{sub_id}/delete/"
            
            buttons = f"""
            <a href="{view_url}" class="button" style="margin-right: 5px;">View</a>
            """
            
            if sub.status in ['active', 'trialing']:
                buttons += f"""
                <a href="{cancel_url}" class="button" style="margin-right: 5px; background-color: #FFA500;">Cancel</a>
                """
            
            buttons += f"""
            <a href="{delete_url}" class="button" style="background-color: #FF4136;">Delete</a>
            """
            
            return format_html(buttons)
        
        # If no subscription exists, offer to create one
        company_id = obj.company.id
        create_url = f"/admin/subscriptions/subscription/add/?company={company_id}"
        return format_html(f'<a href="{create_url}" class="button">Create Subscription</a>')
    
    manage_subscription.short_description = "Actions"
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display_links = ["email"]
    search_fields = ("email",)
    ordering = ("email",)
    inlines = (RoleInline, CompanyWithSubscriptionInline)
    list_display = (
        "email",
        "is_staff",
        "is_active",
        "is_superuser",
        "subscription_status",
    )
    list_filter = ("email", "is_staff", "is_active", "is_superuser", "user_type", SubscriptionInfoListFilter)
    actions = ['cancel_all_subscriptions', 'reactivate_subscriptions']
    
    def subscription_status(self, obj):
        companies = obj.companies.all()
        if not companies:
            return "No Company"
        
        active_subscriptions = companies.filter(subscription__status='active').count()
        trial_subscriptions = companies.filter(subscription__status='trialing').count()
        
        if active_subscriptions:
            return format_html('<span style="color: green;">Active ({})</span>', active_subscriptions)
        if trial_subscriptions:
            return format_html('<span style="color: blue;">Trial ({})</span>', trial_subscriptions)
        return format_html('<span style="color: gray;">Inactive</span>')
    subscription_status.short_description = "Subscription"
    
    def cancel_all_subscriptions(self, request, queryset):
        """Admin action to cancel all active subscriptions for selected users"""
        cancelled_count = 0
        for user in queryset:
            companies = user.companies.all()
            for company in companies:
                try:
                    subscription = company.subscription
                    if subscription and subscription.status in ['active', 'trialing']:
                        subscription.status = 'canceled'
                        subscription.cancel_at_period_end = True
                        subscription.save()
                        cancelled_count += 1
                except Subscription.DoesNotExist:
                    continue
        
        if cancelled_count:
            messages.success(request, f'Successfully cancelled {cancelled_count} subscription(s).')
        else:
            messages.info(request, 'No active subscriptions to cancel.')
    cancel_all_subscriptions.short_description = "Cancel all subscriptions for selected users"
    
    def reactivate_subscriptions(self, request, queryset):
        """Admin action to reactivate cancelled subscriptions for selected users"""
        reactivated_count = 0
        for user in queryset:
            companies = user.companies.all()
            for company in companies:
                try:
                    subscription = company.subscription
                    if subscription and subscription.status == 'canceled':
                        subscription.status = 'active'
                        subscription.cancel_at_period_end = False
                        subscription.save()
                        reactivated_count += 1
                except Subscription.DoesNotExist:
                    continue
        
        if reactivated_count:
            messages.success(request, f'Successfully reactivated {reactivated_count} subscription(s).')
        else:
            messages.info(request, 'No cancelled subscriptions to reactivate.')
    reactivate_subscriptions.short_description = "Reactivate cancelled subscriptions for selected users"

    fieldsets = (
        # (None, {'fields': ('email', 'password')}),
        (
            ("Personal info"),
            {"fields": ("first_name", "last_name", "email", "user_type")},
        ),
        (
            ("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                    "user_type",
                ),
            },
        ),
    )

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(CustomUserAdmin, self).get_inline_instances(request, obj)


admin.site.register(User, CustomUserAdmin)
admin.site.register(VerificationCode)
admin.site.register(WorksIn)

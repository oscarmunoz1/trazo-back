from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum

from .models import (
    Plan, 
    Subscription, 
    AddOn,
    SubscriptionAddOn,
    Invoice,
    PaymentMethod
)

class SubscriptionAddOnInline(admin.TabularInline):
    model = SubscriptionAddOn
    extra = 0
    fields = ('addon', 'quantity', 'stripe_item_id', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('addon',)
    
class InvoiceInline(admin.TabularInline):
    model = Invoice
    extra = 0
    fields = ('amount', 'status', 'invoice_date', 'due_date', 'invoice_pdf')
    readonly_fields = ('created_at',)
    ordering = ('-invoice_date',)
    max_num = 5
    verbose_name = _("Recent Invoice")
    verbose_name_plural = _("Recent Invoices")

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'interval', 'is_active', 'created_at')
    list_filter = ('interval', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description', 'price', 'interval')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_price_id',),
            'classes': ('collapse',),
        }),
        ('Features', {
            'fields': ('features', 'is_active'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'plan_name', 'status', 'subscription_period', 'trial_status', 'updated_at')
    list_filter = ('status', 'plan', 'cancel_at_period_end')
    search_fields = ('company__name', 'stripe_subscription_id', 'stripe_customer_id')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [SubscriptionAddOnInline, InvoiceInline]
    
    fieldsets = (
        (None, {
            'fields': ('company', 'plan', 'status', 'cancel_at_period_end')
        }),
        ('Subscription Period', {
            'fields': ('current_period_start', 'current_period_end', 'trial_end'),
        }),
        ('Usage Metrics', {
            'fields': ('used_productions', 'used_storage_gb', 'scan_count'),
        }),
        ('Stripe Integration', {
            'fields': ('stripe_subscription_id', 'stripe_customer_id'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    @admin.display(description=_('Company'))
    def company_name(self, obj):
        return obj.company.name
    
    @admin.display(description=_('Plan'))
    def plan_name(self, obj):
        return obj.plan.name

    @admin.display(description=_('Period'))
    def subscription_period(self, obj):
        if obj.current_period_start and obj.current_period_end:
            start = obj.current_period_start.strftime('%d %b %Y')
            end = obj.current_period_end.strftime('%d %b %Y')
            return f"{start} - {end}"
        return "-"
        
    @admin.display(description=_('Trial'))
    def trial_status(self, obj):
        if obj.status != 'trialing':
            return format_html('<span style="color: gray;">-</span>')
        
        if obj.trial_end:
            days_left = (obj.trial_end.date() - obj.current_period_start.date()).days
            if days_left > 0:
                return format_html('<span style="color: green;">Active ({} days left)</span>', days_left)
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: gray;">-</span>')

@admin.register(AddOn)
class AddOnAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description', 'price', 'is_active')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_price_id',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

@admin.register(SubscriptionAddOn)
class SubscriptionAddOnAdmin(admin.ModelAdmin):
    list_display = ('subscription_company', 'addon_name', 'quantity', 'created_at')
    list_filter = ('addon', 'created_at')
    search_fields = ('subscription__company__name', 'addon__name')
    autocomplete_fields = ('subscription', 'addon')
    readonly_fields = ('created_at',)
    
    @admin.display(description=_('Company'))
    def subscription_company(self, obj):
        return obj.subscription.company.name
    
    @admin.display(description=_('Add-on'))
    def addon_name(self, obj):
        return obj.addon.name

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'amount', 'status', 'invoice_date', 'due_date', 'pdf_link')
    list_filter = ('status', 'invoice_date')
    search_fields = ('company__name', 'stripe_invoice_id')
    readonly_fields = ('created_at',)
    
    @admin.display(description=_('Company'))
    def company_name(self, obj):
        return obj.company.name
    
    @admin.display(description=_('PDF'))
    def pdf_link(self, obj):
        if obj.invoice_pdf:
            return format_html('<a href="{}" target="_blank">View PDF</a>', obj.invoice_pdf)
        return '-'

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'card_info', 'expiration', 'is_default', 'created_at')
    list_filter = ('card_brand', 'is_default', 'created_at')
    search_fields = ('company__name', 'last_4')
    readonly_fields = ('created_at',)
    
    @admin.display(description=_('Company'))
    def company_name(self, obj):
        return obj.company.name
    
    @admin.display(description=_('Card Information'))
    def card_info(self, obj):
        return f"{obj.card_brand.title()} **** {obj.last_4}"
    
    @admin.display(description=_('Expiration'))
    def expiration(self, obj):
        return f"{obj.exp_month}/{obj.exp_year}"

# Register custom admin site header and title
admin.site.site_header = 'Trazo Subscription Administration'
admin.site.site_title = 'Trazo Admin'
admin.site.index_title = 'Subscription Management'

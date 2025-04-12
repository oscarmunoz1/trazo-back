from rest_framework import serializers
from .models import Plan, Subscription, AddOn, SubscriptionAddOn, Invoice, PaymentMethod

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'slug', 'description', 'price', 'interval', 'features', 'is_active']

class AddOnSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddOn
        fields = ['id', 'name', 'slug', 'description', 'price', 'is_active']

class SubscriptionAddOnSerializer(serializers.ModelSerializer):
    addon = AddOnSerializer(read_only=True)
    
    class Meta:
        model = SubscriptionAddOn
        fields = ['id', 'addon', 'quantity']

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    addons = SubscriptionAddOnSerializer(many=True, read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'status', 'current_period_start', 'current_period_end', 
            'cancel_at_period_end', 'used_productions', 'used_storage_gb', 
            'scan_count', 'trial_end', 'addons'
        ]

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'card_brand', 'last_4', 'exp_month', 'exp_year', 'is_default']

class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ['id', 'amount', 'status', 'invoice_date', 'due_date', 'invoice_pdf'] 
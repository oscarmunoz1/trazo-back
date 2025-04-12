from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta

def send_trial_started_email(email, username, company_name, plan_name, trial_end_date):
    """Send email notifying the user their trial has started"""
    context = {
        'username': username,
        'company_name': company_name,
        'plan_name': plan_name,
        'trial_end_date': trial_end_date.strftime('%B %d, %Y'),
        'billing_url': f"{settings.FRONTEND_URL}/account/billing",
    }
    
    msg_plain = render_to_string('subscription_emails/trial_started.txt', context)
    msg_html = render_to_string('subscription_emails/trial_started.html', context)
    
    send_mail(
        f'Your {plan_name} trial for {company_name} has started',
        msg_plain,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        html_message=msg_html,
    )

def send_trial_ending_reminder(email, username, company_name, plan_name, trial_end_date, days_left):
    """Send reminder that trial is ending soon"""
    context = {
        'username': username,
        'company_name': company_name,
        'plan_name': plan_name,
        'trial_end_date': trial_end_date.strftime('%B %d, %Y'),
        'days_left': days_left,
        'billing_url': f"{settings.FRONTEND_URL}/account/billing",
    }
    
    msg_plain = render_to_string('subscription_emails/trial_ending.txt', context)
    msg_html = render_to_string('subscription_emails/trial_ending.html', context)
    
    send_mail(
        f'Your {plan_name} trial ends in {days_left} days',
        msg_plain,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        html_message=msg_html,
    )

def send_subscription_canceled_email(email, username, company_name):
    """Send email confirming subscription cancellation"""
    context = {
        'username': username,
        'company_name': company_name,
        'billing_url': f"{settings.FRONTEND_URL}/account/billing",
    }
    
    msg_plain = render_to_string('subscription_emails/subscription_canceled.txt', context)
    msg_html = render_to_string('subscription_emails/subscription_canceled.html', context)
    
    send_mail(
        f'Your subscription for {company_name} has been canceled',
        msg_plain,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        html_message=msg_html,
    )

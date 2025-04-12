import boto3
import uuid
import json
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


def send_invitation_to_user(email, link, username, email_address, user_type):
    """
    Send verification code link to the given email
    """
    params = {
        "link": link,
        "username": username,
        "email": email_address,
        "user_type": user_type,
    }

    msg_plain = render_to_string("email_verification_code/message.txt", params)
    msg_html = render_to_string("email_verification_code/message.html", params)
    subject = "Welcome to trazo, just verify your account."

    return send_mail(
        subject,
        msg_plain,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        html_message=msg_html,
    )

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import VerificationCode, User
from django.conf import settings
from smtplib import SMTPException
import logging
from .utils import send_invitation_to_user
from .constants import PRODUCER, CONSUMER
from urllib.parse import quote

logger = logging.getLogger(__name__)

import random
import string


def generate_verification_code(length=6):
    letters_and_digits = string.ascii_letters + string.digits
    return "".join(random.choice(letters_and_digits) for i in range(length)).upper()


@receiver(post_save, sender=User)
def create_verification_code(sender, instance, created, **kwargs):
    if created:
        code = generate_verification_code()
        VerificationCode.objects.create(user=instance, code=code)
        
        # Properly encode the email for URLs
        encoded_email = quote(instance.email)
        
        verification_link = ""
        user_type = int(instance.user_type)
        if user_type == PRODUCER:
            verification_link = f"{settings.BASE_APP_URL}auth/verifyemail?email={encoded_email}&code={code}"
        elif user_type == CONSUMER:
            verification_link = f"{settings.BASE_CONSUMER_URL}auth/verifyemail?email={encoded_email}&code={code}"

        # send verification code to user
        try:
            send_invitation_to_user(
                instance.email, verification_link, instance.first_name, instance.email, instance.user_type
            )
        except SMTPException as e:
            logger.error(
                f"Could not send invitation email to user: {instance.email}, Error: {e}"
            )

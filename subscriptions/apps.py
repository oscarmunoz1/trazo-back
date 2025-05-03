from django.apps import AppConfig

class SubscriptionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'subscriptions'
    verbose_name = 'Subscription Management'
    
    def ready(self):
        try:
            from subscriptions import signals, admin
        except ImportError:
            import logging
            logging.getLogger(__name__).error("Error importing subscriptions signals or admin", exc_info=True) 
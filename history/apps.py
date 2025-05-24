from django.apps import AppConfig


class HistoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "history"

    def ready(self):
        import history.signals  # Import signals to register them

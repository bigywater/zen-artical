from django.apps import AppConfig


class TechConfig(AppConfig):
    name = 'tech'

    def ready(self):
        from . import signals  # noqa: F401

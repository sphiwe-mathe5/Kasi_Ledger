from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates a superuser for CustomUser model'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        if not User.objects.filter(email='mathesphiwe@gmail.com').exists():
            User.objects.create_superuser(email='mathesphiwe@gmail.com', password='mancity1')
            self.stdout.write(self.style.SUCCESS('Superuser created successfully'))
        else:
            self.stdout.write(self.style.WARNING('Superuser already exists'))

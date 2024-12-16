# management/commands/create_subscription_plans.py
from django.core.management.base import BaseCommand
from submit.models import SubscriptionPlan

class Command(BaseCommand):
    help = 'Creates default subscription plans'

    def handle(self, *args, **kwargs):
        plans = [
            {
                'name': 'Free',
                'price': 0.00,
                'description': 'Basic features for starters',
                'features': [
                    'Basic feature 1',
                    'Basic feature 2',
                    'Limited storage'
                ]
            },
            {
                'name': 'Pro',
                'price': 299.99,  # R299.99
                'description': 'Professional features for growing businesses',
                'features': [
                    'All Free features',
                    'Pro feature 1',
                    'Pro feature 2',
                    'Increased storage'
                ]
            },
            {
                'name': 'Enterprise',
                'price': 999.99,  # R999.99
                'description': 'Advanced features for large organizations',
                'features': [
                    'All Pro features',
                    'Enterprise feature 1',
                    'Enterprise feature 2',
                    'Unlimited storage'
                ]
            }
        ]

        for plan_data in plans:
            SubscriptionPlan.objects.get_or_create(
                name=plan_data['name'],
                defaults={
                    'price': plan_data['price'],
                    'description': plan_data['description'],
                    'features': plan_data['features']
                }
            )
            self.stdout.write(f'Created/Updated {plan_data["name"]} plan')
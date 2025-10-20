# salon/utils.py
from .models import CustomerEmail

def save_customer_email(user, email, customer_name=None, source='manual', source_id=None):
    """
    Save customer email for marketing purposes
    """
    try:
        # Check if email already exists for this user
        customer_email, created = CustomerEmail.objects.get_or_create(
            user=user,
            email=email,
            defaults={
                'customer_name': customer_name,
                'source': source,
                'source_id': source_id
            }
        )
        
        # Update last contacted if email already exists
        if not created:
            customer_email.customer_name = customer_name or customer_email.customer_name
            customer_email.save()
        
        return customer_email
    except Exception as e:
        print(f"Error saving customer email: {e}")
        return None
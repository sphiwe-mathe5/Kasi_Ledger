from django.contrib.auth.base_user import BaseUserManager

class CustomUserManager(BaseUserManager):
    def create_user(self, email=None, password=None, **extra_fields):
        if not email and not extra_fields.get('phone_number'):
            raise ValueError('Either an email or phone number must be set.')

        if email:
            email = self.normalize_email(email)
            extra_fields['email'] = email

            if 'username' not in extra_fields:
                username = email.split('@')[0]
                base_username = username
                counter = 1
                while self.model.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                extra_fields['username'] = username

        elif extra_fields.get('phone_number'):
            phone = extra_fields['phone_number']
            # Use phone number as username if email isn't provided
            username = phone
            counter = 1
            while self.model.objects.filter(username=username).exists():
                username = f"{phone}{counter}"
                counter += 1
            extra_fields['username'] = username

        user = self.model(**extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        return self.create_user(email, password, **extra_fields)
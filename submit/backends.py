from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

UserModel = get_user_model()

class EmailOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = None
        if username:
            try:
                if "@" in username:  # assume email
                    user = UserModel.objects.get(email__iexact=username)
                else:  # assume phone
                    user = UserModel.objects.get(phone_number=username)
            except UserModel.DoesNotExist:
                return None

            if user and user.check_password(password):
                return user
        return None


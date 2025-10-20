from storages.backends.gcloud import GoogleCloudStorage
from django.conf import settings

class GoogleCloudMediaFileStorage(GoogleCloudStorage):
    bucket_name = settings.GS_BUCKET_NAME
    project_id = settings.GS_PROJECT_ID
    credentials = settings.GS_CREDENTIALS
    default_acl = 'publicRead'
    
    def url(self, name):
        """Returns the public URL for the file on Google Cloud Storage."""
        # Remove any leading slashes
        name = name.lstrip('/')
        return f"https://storage.googleapis.com/{self.bucket_name}/{name}"
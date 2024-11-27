# emails/models.py

from django.db import models

class EmailTemplate(models.Model):
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    filename = models.CharField(max_length=100, default='default_template.html')  # This will store the filename of the HTML template

    def __str__(self):
        return self.name

class SentEmail(models.Model):
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email to {self.recipient} at {self.sent_at}"


from django.db import models
import uuid
# Create your models here.

class Queue(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, default=uuid.uuid4) # Unik link untuk QR
    created_at = models.DateTimeField(auto_now_add=True)
    # Untuk simpan input label (contoh: "Masukkan nama anda")
    input_label = models.CharField(max_length=100, default="Masukkan nama anda")
    allow_join = models.BooleanField(default=True)       # Visitor self-sign-in
    ask_input = models.BooleanField(default=False)       # Ask for visitor input
    capacity = models.IntegerField(default=1000)         # Queue capacity
    
    WAIT_TIME_CHOICES = [
        ('AUTO', 'Automatically calculated'),
        ('HIDDEN', 'Hidden'),
    ]
    wait_time_display = models.CharField(max_length=10, choices=WAIT_TIME_CHOICES, default='AUTO')
    
    LANGUAGE_CHOICES = [
        ('AUTO', 'Auto'),
        ('EN', 'English'),
        ('MS', 'Malay'),
    ]
    status_language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='AUTO')

    def __str__(self):
        return self.name

class Visitor(models.Model):
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, related_name='visitors')
    name = models.CharField(max_length=100)
    number = models.IntegerField() # Nombor giliran (101, 102...)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    
    STATUS_CHOICES = [
        ('WAITING', 'Waiting'),
        ('SERVING', 'Serving'),
        ('COMPLETED', 'Completed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='WAITING')
    is_returned = models.BooleanField(default=False)
    is_invited = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.number}"
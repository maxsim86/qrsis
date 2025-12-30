from django.db import models
import uuid
# Create your models here.

class Queue(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, default=uuid.uuid4) # Unik link untuk QR
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Untuk simpan input label (contoh: "Masukkan nama anda")
    input_label = models.CharField(max_length=100, default="Masukkan nama anda")

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

    def __str__(self):
        return f"{self.name} - {self.number}"
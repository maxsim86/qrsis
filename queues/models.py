from django.db import models
import uuid
from django.utils.text import slugify
# Create your models here.

class Queue(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nama Barisan")
    #name = models.CharField(max_length=100)
    #slug = models.SlugField(unique=True, default=uuid.uuid4) # Unik link untuk QR
    slug = models.SlugField(unique=True, max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Untuk simpan input label (contoh: "Masukkan nama anda")
    input_label = models.CharField(max_length=100, default="Masukkan nama anda")
    allow_join = models.BooleanField(default=True)       # Visitor self-sign-in
    ask_input = models.BooleanField(default=False)       # Ask for visitor input
    capacity = models.IntegerField(default=1000)         # Queue capacity
    logo = models.ImageField(upload_to='queue_logos/', blank=True, null=True)
    video = models.FileField(upload_to='queue_videos/', blank=True, null=True)
    
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

    def save(self, *args, **kwargs):
        # Logic: Jika slug kosong, kita buat baru dari Nama
        if not self.slug:
            # Tukar nama jadi slug (contoh: "Klinik Dr. Ali" -> "klinik-dr-ali")
            base_slug = slugify(self.name)
            
            # Jika slugify gagal (contoh nama simbol pelik), guna UUID pendek
            if not base_slug:
                base_slug = str(uuid.uuid4())[:8]

            # Logic Unik: Pastikan tak ada slug yang sama
            slug = base_slug
            counter = 1
            while Queue.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Visitor(models.Model):
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, related_name='visitors')
    name = models.CharField(max_length=100)
    number = models.IntegerField() # Nombor giliran (101, 102...)
    joined_at = models.DateTimeField(auto_now_add=True)
    served_at = models.DateTimeField(null=True, blank=True)
    
    
    STATUS_CHOICES = [
        ('WAITING', 'Waiting'),
        ('SERVING', 'Serving'),
        ('COMPLETED', 'Completed'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='WAITING')
    is_returned = models.BooleanField(default=False)
    is_invited = models.BooleanField(default=False)

    SERVICE_CHOICES = [
        ('A', 'Pendaftaran'),
        ('B', 'Pembayaran'),
        ('C', 'Pertanyaan'),
    ]
    # Default 'A' supaya data lama tak rosak
    service_type = models.CharField(max_length=1, choices=SERVICE_CHOICES, default='A') 

    @property
    def service_duration(self):
        if self.served_at and self.completed_at:
            return self.completed_at - self.served_at
        return None
    
    @property
    def ticket_number(self):
        """Helper untuk paparkan nombor penuh: A001, B005"""
        return f"{self.service_type}{self.number:03d}"

    def __str__(self):
        return f"{self.name} - {self.ticket_number}"

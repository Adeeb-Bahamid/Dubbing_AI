# core/models.py
import uuid
from django.db import models

class DubbingJob(models.Model):
    # استخدام UUID كـ id فريد للـ API
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # ملفات المدخلات والمخرجات
    video_file = models.FileField(upload_to='uploaded_videos/')
    output_video = models.FileField(upload_to='outputs/', null=True, blank=True)
    
    # محددات الصوت والدبلجة
    voice_type = models.CharField(max_length=50)
    technical_mode = models.BooleanField(default=True)
    speaking_pace = models.FloatField(default=1.0)
    
    # تتبع خط الإنتاج (Pipeline Tracking)
    percentage = models.FloatField(default=0.0)
    current_step = models.IntegerField(default=0) # من 0 إلى 5
    status_text = models.CharField(max_length=255, default="Waiting in queue...")
    
    # 🚦 نظام الحالات الصارم المعتمد (Status System)
    # PENDING -> PROCESSING -> SUCCESS أو FAILED
    status = models.CharField(max_length=20, default='PENDING')
    
    # ⚠️ إدارة الأخطاء الحقيقية (Error Handling)
    error_message = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Job {self.id} - Status: {self.status} - {self.percentage}%"
    
# import uuid
# from django.db import models

# class DubbingJob(models.Model):
#     STATUS_CHOICES = [('PENDING', 'Pending'), ('PROCESSING', 'Processing'), ('SUCCESS', 'Success'), ('FAILED', 'Failed')]
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     video_input = models.FileField(upload_to='uploads/')
#     video_output = models.FileField(upload_to='outputs/', null=True, blank=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
#     error_message = models.TextField(null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
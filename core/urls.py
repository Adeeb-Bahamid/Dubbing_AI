from django.urls import path
from . import views

urlpatterns = [
    # واجهة الويب الأساسية (إذا كنت تستخدمها للمعاينة)
    path('', views.index_view, name='index'),
    
    # 🚀 رابط رفع الفيديو وبدء الـ Pipeline
    path('api/upload-video', views.upload_video_api, name='upload_video'),
    
    # 🛰️ رابط فحص الحالة الدوري (Polling) المحدث ليستقبله فلاتر بأمان
    path('api/job-status/<uuid:job_id>', views.get_job_status_api, name='job_status'),
    
    # 📥 رابط تحميل أو جلب الفيديو النهائي المدبلج
    path('api/download/<uuid:job_id>', views.download_video_api, name='download_video'),
]  # تم إغلاق القوس هنا بأمان








# from django.urls import path
# from . import views
# urlpatterns = [
#     path('', views.index_view, name='index'),
#     path('api/upload-video', views.upload_video_api, name='upload_video'),
#     path('api/status/<uuid:job_id>', views.get_job_status_api, name='job_status'),
#     path('api/download/<uuid:job_id>', views.download_video_api, name='download_video'),
# ]
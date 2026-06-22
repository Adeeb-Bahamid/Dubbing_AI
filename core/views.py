
# core/views.py
import os
import shutil
import threading
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from .models import DubbingJob
from .utils.audio_extractor import extract_audio
from .utils.transcriber import transcribe_audio
from .utils.translator import translate_segments
from .utils.synthesizer import generate_arabic_audio_track
from .utils.video_merger import merge_arabic_audio_with_stretching

def index_view(request):
    return render(request, 'index.html')


def merge_segments_into_chunks(segments, max_gap=0.8, max_duration=8.0, max_words=35):
    """
    تجميع المقاطع النصية بناءً على الطوابع الزمنية قبل الترجمة والتوليد
    لضمان اتساق مؤشرات الصوت (Indices) ومنع تداخل الكلمات.
    """
    if not segments:
        return []

    merged_chunks = []

    current_chunk = {
        'start': float(segments[0]['start']),
        'end': float(segments[0]['end']),
        'text': str(segments[0]['text']).strip()
    }

    for next_seg in segments[1:]:
        seg_start = float(next_seg['start'])
        seg_end = float(next_seg['end'])
        seg_text = str(next_seg['text']).strip()

        gap = seg_start - current_chunk['end']
        potential_duration = seg_end - current_chunk['start']
        potential_text = current_chunk['text'] + " " + seg_text
        word_count = len(potential_text.split())

        if gap <= max_gap and potential_duration <= max_duration and word_count <= max_words:
            current_chunk['end'] = seg_end
            current_chunk['text'] = potential_text
        else:
            merged_chunks.append(current_chunk)
            current_chunk = {
                'start': seg_start,
                'end': seg_end,
                'text': seg_text
            }

    merged_chunks.append(current_chunk)
    return merged_chunks



def _background_pipeline(job_id):
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', str(job_id))
    try:
        job = DubbingJob.objects.get(id=job_id)
        
        job.status = 'PROCESSING'
        job.percentage = 5.0
        job.current_step = 0
        job.status_text = "Initializing pipeline and directories..."
        job.save()
        
        os.makedirs(temp_dir, exist_ok=True)
        video_path = job.video_file.path
        
        # 1️⃣ المرحلة 0: استخراج الصوت الأصلي
        job.percentage = 15.0
        job.current_step = 0
        job.status_text = "Extracting audio tracks from video..."
        job.save()
        
        orig_audio = os.path.join(temp_dir, 'original.mp3')
        extract_audio(video_path, orig_audio)
        
        # 2️⃣ المرحلة 1: تحويل الصوت إلى نصوص عبر Groq API (Whisper)
        job.percentage = 35.0
        job.current_step = 1

        job.status_text = "Transcribing speech to text (Cloud Whisper AI)..."
        job.save()
        
        raw_segments = transcribe_audio(orig_audio)
        
        # تجميع الجمل زمنياً أولاً لتوحيد السياق والمؤشرات
        optimized_chunks = merge_segments_into_chunks(
            raw_segments,
            # max_gap=1.5,
            max_gap=0.8,
            max_duration=8.0,
            max_words=35
        )
        
        # 3️⃣ المرحلة 2: الترجمة الذكية والسياقية للـ Chunks المدمجة
        job.percentage = 55.0
        job.current_step = 2
        job.status_text = "Translating text to Arabic contextual language..."
        job.save()
        
        translated_chunks = translate_segments(optimized_chunks)
        
        # 4️⃣ المرحلة 3: توليد الأصوات العربية الـ TTS بناءً على الأجزاء المترجمة
        job.percentage = 75.0
        job.current_step = 3
        job.status_text = "Generating natural Arabic voice-over (AI TTS)..."

        job.save()
        
        generate_arabic_audio_track(translated_chunks, temp_dir)
        
        # تجهيز مسار الفيديو النهائي
        out_filename = f"dubbed_{job.id}.mp4"
        out_path = os.path.join(settings.MEDIA_ROOT, 'outputs', out_filename)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        # 5️⃣ المرحلة 4: دمج الأصوات وتمديد أجزاء الفيديو
        job.percentage = 90.0
        job.current_step = 4
        job.status_text = "Merging final Arabic audio with video tracks..."
        job.save()
        
        merge_arabic_audio_with_stretching(
            video_path=video_path, 
            translated_segments=translated_chunks, 
            audio_files_dir=temp_dir, 
            output_path=out_path
        )
        
        # 🎉 النجاح الكامل وحفظ المسار الناتج
        job.output_video = f"outputs/{out_filename}"
        job.percentage = 100.0
        job.current_step = 4
        job.status = 'SUCCESS'

        job.status_text = "Dubbing completed successfully!"
        job.save()
        
    except Exception as e:
        print(f"❌ Background Pipeline Error: {str(e)}")
        try:
            current_job = DubbingJob.objects.get(id=job_id)
            current_job.status = 'FAILED'
            current_job.status_text = "An error occurred during AI processing."
            current_job.error_message = str(e)
            current_job.save()
        except Exception as db_err:
            print(f"❌ Could not update database status: {db_err}")
            
    finally:
        # ضمان التنظيف التام للمجلد المؤقت وحماية مساحة القرص في كل الحالات
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@csrf_exempt
def upload_video_api(request):
    if request.method != 'POST': 
        return JsonResponse({'error': 'POST required'}, status=405)
    
    video_file = request.FILES.get('video')
    if not video_file: 

        return JsonResponse({'error': 'No video provided'}, status=400)
    
    job = DubbingJob.objects.create(
        video_file=video_file,
        status='PENDING',
        status_text="Waiting in queue..."
    )
    
    # threading.Thread(target=_background_pipeline, args=(str(job.id),)).start()
    worker = threading.Thread(target=_background_pipeline, args=(str(job.id),), daemon=True)
    worker.start()
    
    return JsonResponse({'job_id': str(job.id), 'status': 'PENDING'}, status=202)


def get_job_status_api(request, job_id):
    job = get_object_or_404(DubbingJob, id=job_id)
    return JsonResponse({
        'job_id': str(job.id),
        'status': job.status,
        'percentage': job.percentage,
        'current_step': job.current_step,
        'status_text': job.status_text,
        'error_message': job.error_message if job.error_message else "",
        'output_video_url': job.output_video.url if job.output_video else ""
    }, status=200)


def download_video_api(request, job_id):
    job = get_object_or_404(DubbingJob, id=job_id)
    if job.status != 'SUCCESS': 
        return JsonResponse({'error': 'Not ready'}, status=400)
    return FileResponse(open(job.output_video.path, 'rb'), content_type='video/mp4')












# #views.py
# import os
# import shutil
# import threading
# from django.http import JsonResponse, FileResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.shortcuts import render, get_object_or_404
# from django.conf import settings
# from .models import DubbingJob
# from .utils.audio_extractor import extract_audio
# from .utils.transcriber import transcribe_audio
# from .utils.translator import translate_segments
# from .utils.synthesizer import generate_arabic_audio_track
# from .utils.video_merger import merge_arabic_audio_with_stretching

# def index_view(request):
#     return render(request, 'index.html')


# def merge_translated_segments_into_chunks(translated_segments, max_gap=1.5, max_duration=8.0, max_words=35):
#     """
#     النسخة الآمنة والمصححة: تمنع الحشو الصامت وتراكم الأوقات (Time Drifting)
#     في الفيديوهات الطويلة عبر ضبط صارم لحدود البداية والنهاية.
#     """
#     if not translated_segments:
#         return []

#     merged_chunks = []
#     current_chunk = {
#         'start': float(translated_segments[0]['start']),
#         'end': float(translated_segments[0]['end']),
#         'text': str(translated_segments[0]['text']).strip()
#     }

#     for next_seg in translated_segments[1:]:
#         seg_start = float(next_seg['start'])
#         seg_end = float(next_seg['end'])
#         seg_text = str(next_seg['text']).strip()

#         gap = seg_start - current_chunk['end']
#         potential_duration = seg_end - current_chunk['start']
#         potential_text = current_chunk['text'] + " " + seg_text
#         word_count = len(potential_text.split())

#         if gap <= max_gap and potential_duration <= max_duration and word_count <= max_words:
#             current_chunk['end'] = seg_end
#             current_chunk['text'] = potential_text
#         else:
#             merged_chunks.append(current_chunk)
#             current_chunk = {
#                 'start': seg_start,
#                 'end': seg_end,
#                 'text': seg_text
#             }

#     merged_chunks.append(current_chunk)
#     return merged_chunks


# def _background_pipeline(job_id):
#     try:
#         job = DubbingJob.objects.get(id=job_id)
        
#         job.status = 'PROCESSING'
#         job.percentage = 5.0
#         job.current_step = 0
#         job.status_text = "Initializing pipeline and directories..."
#         job.save()
        
#         temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', str(job.id))
#         os.makedirs(temp_dir, exist_ok=True)
        
#         # ⚠️ تعديل: استخدام الحقل video_file المتوافق مع الموديل الجديد
#         video_path = job.video_file.path
        
#         # 1️⃣ المرحلة 0: استخراج الصوت الأصلي
#         job.percentage = 15.0
#         job.current_step = 0
#         job.status_text = "Extracting audio tracks from video..."
#         job.save()
        
#         orig_audio = os.path.join(temp_dir, 'original.wav')
#         extract_audio(video_path, orig_audio)
        
#         # 2️⃣ المرحلة 1: تحويل الصوت إلى نصوص (Whisper)
#         job.percentage = 30.0
#         job.current_step = 1
#         job.status_text = "Transcribing speech to text (Whisper AI)..."
#         job.save()
        
#         segments = transcribe_audio(orig_audio)
        
#         # 3️⃣ المرحلة 2: الترجمة الذكية
#         job.percentage = 45.0
#         job.current_step = 2
#         job.status_text = "Translating text to Arabic contextual language..."
#         job.save()
        
#         translated = translate_segments(segments)
        
#         optimized_chunks = merge_translated_segments_into_chunks(
#             translated_segments=translated,
#             max_gap=1.5,
#             max_duration=8.0,
#             max_words=35
#         )
        
#         # 4️⃣ المرحلة 3: توليد الأصوات العربية الـ TTS
#         job.percentage = 65.0
#         job.current_step = 3
#         job.status_text = "Generating natural Arabic voice-over (AI TTS)..."
#         job.save()
        
#         generate_arabic_audio_track(optimized_chunks, temp_dir)
        
#         # تجهيز مسار الفيديو النهائي
#         out_filename = f"dubbed_{job.id}.mp4"
#         out_path = os.path.join(settings.MEDIA_ROOT, 'outputs', out_filename)
#         os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
#         # 5️⃣ المرحلة 4: دمج الأصوات وتمديد أجزاء الفيديو
#         job.percentage = 85.0
#         job.current_step = 4
#         job.status_text = "Merging final Arabic audio with video tracks..."
#         job.save()
        
#         merge_arabic_audio_with_stretching(
#             video_path=video_path, 
#             translated_segments=optimized_chunks, 
#             audio_files_dir=temp_dir, 
#             output_path=out_path
#         )
        
#         # 🎉 المرحلة 5: النجاح الكامل وحفظ مسار الفيديو الناتج
#         # ⚠️ تعديل: استخدام الحقل output_video المتوافق مع الموديل الجديد
#         job.output_video = f"outputs/{out_filename}"
#         job.percentage = 100.0
#         job.current_step = 5
#         job.status = 'SUCCESS'
#         job.status_text = "Dubbing completed successfully!"
#         job.save()
        
#         shutil.rmtree(temp_dir)
        
#     except Exception as e:
#         if 'job' in locals():
#             job.status = 'FAILED'
#             job.status_text = "An error occurred during AI processing."
#             job.error_message = str(e)
#             job.save()


# @csrf_exempt
# def upload_video_api(request):
#     if request.method != 'POST': 
#         return JsonResponse({'error': 'POST required'}, status=405)
    
#     video_file = request.FILES.get('video')
#     if not video_file: 
#         return JsonResponse({'error': 'No video provided'}, status=400)
    
#     # ⚠️ تعديل: استخدام الحقل video_file المتوافق مع الموديل الجديد عند الإنشاء
#     job = DubbingJob.objects.create(
#         video_file=video_file,
#         status='PENDING',
#         status_text="Waiting in queue..."
#     )
    
#     threading.Thread(target=_background_pipeline, args=(str(job.id),)).start()
    
#     return JsonResponse({'job_id': str(job.id), 'status': 'PENDING'}, status=202)


# def get_job_status_api(request, job_id):
#     job = get_object_or_404(DubbingJob, id=job_id)
    
#     # ⚠️ تعديل: استخدام الحقل output_video.url المتوافق مع الموديل الجديد
#     return JsonResponse({
#         'job_id': str(job.id),
#         'status': job.status,
#         'percentage': job.percentage,
#         'current_step': job.current_step,
#         'status_text': job.status_text,
#         'error_message': job.error_message if job.error_message else "",
#         'output_video_url': job.output_video.url if job.output_video else ""
#     }, status=200)


# def download_video_api(request, job_id):
#     job = get_object_or_404(DubbingJob, id=job_id)
#     if job.status != 'SUCCESS': 
#         return JsonResponse({'error': 'Not ready'}, status=400)
#     # ⚠️ تعديل: استخدام الحقل output_video.path المتوافق مع الموديل الجديد
#     return FileResponse(open(job.output_video.path, 'rb'), content_type='video/mp4')







# import os
# import shutil
# import threading
# from django.http import JsonResponse, FileResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.shortcuts import render, get_object_or_404
# from django.conf import settings
# from .models import DubbingJob
# from .utils.audio_extractor import extract_audio
# from .utils.transcriber import transcribe_audio
# from .utils.translator import translate_segments
# from .utils.synthesizer import generate_arabic_audio_track
# from .utils.video_merger import merge_arabic_audio_with_stretching

# def index_view(request):
#     return render(request, 'index.html')


# def merge_translated_segments_into_chunks(translated_segments, max_gap=1.5, max_duration=8.0, max_words=35):
#     """
#     النسخة الآمنة والمصححة: تمنع الحشو الصامت وتراكم الأوقات (Time Drifting)
#     في الفيديوهات الطويلة عبر ضبط صارم لحدود البداية والنهاية.
#     """
#     if not translated_segments:
#         return []

#     merged_chunks = []
#     # أخذ نسخة عميقة ونظيفة من أول جملة
#     current_chunk = {
#         'start': float(translated_segments[0]['start']),
#         'end': float(translated_segments[0]['end']),
#         'text': str(translated_segments[0]['text']).strip()
#     }

#     for next_seg in translated_segments[1:]:
#         seg_start = float(next_seg['start'])
#         seg_end = float(next_seg['end'])
#         seg_text = str(next_seg['text']).strip()

#         # 1. حساب الفجوة الفعلية بين الجملتين
#         gap = seg_start - current_chunk['end']
        
#         # 2. حساب المدة الإجمالية في حال الدمج
#         potential_duration = seg_end - current_chunk['start']
        

#         # 3. حساب عدد كلمات النص المدمج
#         potential_text = current_chunk['text'] + " " + seg_text
#         word_count = len(potential_text.split())

#         # شروط الدمج الصارمة
#         if gap <= max_gap and potential_duration <= max_duration and word_count <= max_words:
#             # دمج آمن: تحديث التوقيت والنص معاً خطوة بخطوة
#             current_chunk['end'] = seg_end
#             current_chunk['text'] = potential_text
#         else:
#             # إذا لم تنطبق الشروط، نغلق الـ Chunk الحالي فوراً ونحفظه
#             merged_chunks.append(current_chunk)
#             # نبدأ Chunk جديد معزول تماماً بتوقيته الخاص لمنع سرقة الأوقات
#             current_chunk = {
#                 'start': seg_start,
#                 'end': seg_end,
#                 'text': seg_text
#             }

#     # حفظ آخر قطعة في الحلقة
#     merged_chunks.append(current_chunk)
#     return merged_chunks


# # 🔥 دالة التجميع الذكية مدمجة هنا كـ Helper Function لخدمة خط الإنتاج
# # def merge_translated_segments_into_chunks(translated_segments, max_gap=1.5, max_duration=8.0, max_words=35):
# #     """
# #     تحويل المنظومة إلى Chunk-based عبر دمج الجمل العربية المترجمة 
# #     بناءً على الفجوة الزمنية، الحد الأقصى للمدة، والحد الأقصى للكلمات.
# #     """
# #     if not translated_segments:
# #         return []

# #     merged_chunks = []
# #     current_chunk = translated_segments[0].copy()

# #     for next_seg in translated_segments[1:]:
# #         # 1. حساب الفجوة الزمنية بين نهاية الـ Chunk الحالي وبداية الجملة التالية
# #         gap = float(next_seg['start']) - float(current_chunk['end'])
        
# #         # 2. حساب المدة الزمنية الكلية المحتملة في حال الدمج
# #         potential_duration = float(next_seg['end']) - float(current_chunk['start'])
        
# #         # 3. حساب عدد الكلمات الإجمالي (تم تعديل المفتاح إلى 'text' ليتوافق مع translator.py الخاص بك)
# #         potential_text = current_chunk['text'] + " " + next_seg['text']
# #         word_count = len(potential_text.split())

# #         # اختبار الشروط الثلاثة الذكية لمنع انفجار الـ Chunk
# #         if gap <= max_gap and potential_duration <= max_duration and word_count <= max_words:
# #             current_chunk['end'] = next_seg['end']
# #             current_chunk['text'] = potential_text
# #         else:
# #             merged_chunks.append(current_chunk)
# #             current_chunk = next_seg.copy()

# #     merged_chunks.append(current_chunk)
# #     return merged_chunks

# def _background_pipeline(job_id):
#     try:
#         job = DubbingJob.objects.get(id=job_id)
#         job.status = 'PROCESSING'
#         job.save()
        
#         # إنشاء مجلد مؤقت لحفظ ملفات الصوت الصادرة لكل جملة (sub_0.mp3, sub_1.mp3...)
#         temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', str(job.id))
#         os.makedirs(temp_dir, exist_ok=True)
        
#         video_path = job.video_input.path
        
#         # 1️⃣ استخراج الصوت الأصلي
#         orig_audio = os.path.join(temp_dir, 'original.wav')
#         extract_audio(video_path, orig_audio)
        
#         # 2️⃣ تحويل الصوت إلى نصوص (Whisper عبر Groq)
#         segments = transcribe_audio(orig_audio)
        
#         # 3️⃣ الترجمة الذكية عبر Groq
#         translated = translate_segments(segments)
        
#         # 🔥🚀 الخطوة السحرية المضافة: عصر ودمج الجمل المترجمة إلى Chunks مكثفة وخفيفة
#         optimized_chunks = merge_translated_segments_into_chunks(
#             translated_segments=translated,
#             max_gap=1.5,
#             max_duration=8.0,
#             max_words=35
#         )
        
#         # 4️⃣ توليد الأصوات العربية بناءً على الـ Chunks المحسنة (سيوفر كمية ضخمة من الملفات والوقت!)
#         generate_arabic_audio_track(optimized_chunks, temp_dir)
        
#         # تجهيز مسار الفيديو النهائي المدبلج والممدد
#         out_filename = f"dubbed_{job.id}.mp4"
#         out_path = os.path.join(settings.MEDIA_ROOT, 'outputs', out_filename)
#         os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
#         # 5️⃣ دمج الأصوات وتمديد أجزاء الفيديو تلقائياً باستخدام التجميع الفائق المستقر
#         merge_arabic_audio_with_stretching(
#             video_path=video_path, 
#             translated_segments=optimized_chunks, # نمرر الـ chunks المحسنة هنا أيضاً
#             audio_files_dir=temp_dir, 
#             output_path=out_path
#         )
        
#         # تحديث حالة الـ Job بنجاح
#         job.video_output = f"outputs/{out_filename}"
#         job.status = 'SUCCESS'
#         job.save()
        
#         # تنظيف وحذف المجلد المؤقت لتوفير مساحة الهاردسك
#         shutil.rmtree(temp_dir)
        
#     except Exception as e:
#         if 'job' in locals():
#             job.status = 'FAILED'
#             job.error_message = str(e)
#             job.save()

# @csrf_exempt
# def upload_video_api(request):
#     if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
#     video_file = request.FILES.get('video')
#     if not video_file: return JsonResponse({'error': 'No video provided'}, status=400)
    
#     job = DubbingJob.objects.create(video_input=video_file)
    
#     # تشغيل الـ Pipeline في خيط منفصل فوراً بدلاً من Celery
#     threading.Thread(target=_background_pipeline, args=(str(job.id),)).start()
    
#     return JsonResponse({'job_id': str(job.id), 'status': 'PENDING'}, status=202)

# def get_job_status_api(request, job_id):
#     job = get_object_or_404(DubbingJob, id=job_id)
#     return JsonResponse({'job_id': str(job.id), 'status': job.status, 'error_message': job.error_message})

# def download_video_api(request, job_id):
#     job = get_object_or_404(DubbingJob, id=job_id)
#     if job.status != 'SUCCESS': return JsonResponse({'error': 'Not ready'}, status=400)
#     return FileResponse(open(job.video_output.path, 'rb'), content_type='video/mp4')





# import os
# import shutil
# import threading
# from django.http import JsonResponse, FileResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.shortcuts import render, get_object_or_404
# from django.conf import settings
# from .models import DubbingJob
# from .utils.audio_extractor import extract_audio
# from .utils.transcriber import transcribe_audio
# from .utils.translator import translate_segments
# from .utils.synthesizer import generate_arabic_audio_track
# # التعديل هنا: استدعاء الدالة المضمونة للتمديد والإبطاء من الـ merger
# # from .utils.video_merger import get_video_duration, merge_arabic_audio_with_stretching
# from .utils.video_merger import merge_arabic_audio_with_stretching

# def index_view(request):
#     return render(request, 'index.html')

# def _background_pipeline(job_id):
#     try:
#         job = DubbingJob.objects.get(id=job_id)
#         job.status = 'PROCESSING'
#         job.save()
        
#         # إنشاء مجلد مؤقت لحفظ ملفات الصوت الصادرة لكل جملة (sub_0.mp3, sub_1.mp3...)
#         temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', str(job.id))
#         os.makedirs(temp_dir, exist_ok=True)
        
#         video_path = job.video_input.path
        
#         # 1️⃣ استخراج الصوت الأصلي
#         orig_audio = os.path.join(temp_dir, 'original.wav')
#         extract_audio(video_path, orig_audio)
        
#         # 2️⃣ تحويل الصوت إلى نصوص (Whisper)
#         segments = transcribe_audio(orig_audio)
        
#         # 3️⃣ الترجمة الذكية عبر Groq (الموفرة للطلبات مع نظام الأمان)
#         translated = translate_segments(segments)
        
#         # 4️⃣ توليد الأصوات العربية الفردية لكل جملة براحتها بدون ضغط أو تسريع
#         # تذكر تأكيد دالة الـ synthesizer لتوليد الملفات في temp_dir بأسماء sub_0.mp3، sub_1.mp3...
#         generate_arabic_audio_track(translated, temp_dir)
        
#         # تجهيز مسار الفيديو النهائي المدبلج والممدد
#         out_filename = f"dubbed_{job.id}.mp4"
#         out_path = os.path.join(settings.MEDIA_ROOT, 'outputs', out_filename)
#         os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
#         # 5️⃣ السحر هنا: دمج الأصوات وتمديد أجزاء الفيديو بطيئة الحركة تلقائياً لتناسب الكلام العربي
#         merge_arabic_audio_with_stretching(
#             video_path=video_path, 
#             translated_segments=translated, 
#             audio_files_dir=temp_dir, 
#             output_path=out_path
#         )
        
#         # تحديث حالة الـ Job بنجاح
#         job.video_output = f"outputs/{out_filename}"
#         job.status = 'SUCCESS'
#         job.save()
        
#         # تنظيف وحذف المجلد المؤقت لتوفير مساحة الهاردسك
#         shutil.rmtree(temp_dir)
        
#     except Exception as e:
#         if 'job' in locals():
#             job.status = 'FAILED'
#             job.error_message = str(e)
#             job.save()

# @csrf_exempt
# def upload_video_api(request):
#     if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
#     video_file = request.FILES.get('video')
#     if not video_file: return JsonResponse({'error': 'No video provided'}, status=400)
    
#     job = DubbingJob.objects.create(video_input=video_file)
    
#     # تشغيل الـ Pipeline في خيط منفصل فوراً بدلاً من Celery
#     threading.Thread(target=_background_pipeline, args=(str(job.id),)).start()
    
#     return JsonResponse({'job_id': str(job.id), 'status': 'PENDING'}, status=202)

# def get_job_status_api(request, job_id):
#     job = get_object_or_404(DubbingJob, id=job_id)
#     return JsonResponse({'job_id': str(job.id), 'status': job.status, 'error_message': job.error_message})

# def download_video_api(request, job_id):
#     job = get_object_or_404(DubbingJob, id=job_id)
#     if job.status != 'SUCCESS': return JsonResponse({'error': 'Not ready'}, status=400)
#     return FileResponse(open(job.video_output.path, 'rb'), content_type='video/mp4')


# import os
# import shutil
# import threading
# from django.http import JsonResponse, FileResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.shortcuts import render, get_object_or_404
# from django.conf import settings
# from .models import DubbingJob
# from .utils.audio_extractor import extract_audio
# from .utils.transcriber import transcribe_audio
# from .utils.translator import translate_segments
# from .utils.synthesizer import generate_arabic_audio_track
# from .utils.video_merger import get_video_duration, merge_video_and_audio

# def index_view(request):
#     return render(request, 'index.html')

# def _background_pipeline(job_id):
#     try:
#         job = DubbingJob.objects.get(id=job_id)
#         job.status = 'PROCESSING'
#         job.save()
        
#         temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp', str(job.id))
#         os.makedirs(temp_dir, exist_ok=True)
        
#         video_path = job.video_input.path
#         duration = get_video_duration(video_path)
        
#         orig_audio = os.path.join(temp_dir, 'original.wav')
#         extract_audio(video_path, orig_audio)
        
#         segments = transcribe_audio(orig_audio)
#         translated = translate_segments(segments)
#         arabic_audio = generate_arabic_audio_track(translated, duration, temp_dir)
        
#         out_filename = f"dubbed_{job.id}.mp4"
#         out_path = os.path.join(settings.MEDIA_ROOT, 'outputs', out_filename)
#         os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
#         merge_video_and_audio(video_path, arabic_audio, out_path)
        
#         job.video_output = f"outputs/{out_filename}"
#         job.status = 'SUCCESS'
#         job.save()
#         shutil.rmtree(temp_dir)
#     except Exception as e:
#         if 'job' in locals():
#             job.status = 'FAILED'
#             job.error_message = str(e)
#             job.save()

# @csrf_exempt
# def upload_video_api(request):
#     if request.method != 'POST': return JsonResponse({'error': 'POST required'}, status=405)
#     video_file = request.FILES.get('video')
#     if not video_file: return JsonResponse({'error': 'No video provided'}, status=400)
    
#     job = DubbingJob.objects.create(video_input=video_file)
    
#     # تشغيل الـ Pipeline في خيط منفصل فوراً بدلاً من Celery
#     threading.Thread(target=_background_pipeline, args=(str(job.id),)).start()
    
#     return JsonResponse({'job_id': str(job.id), 'status': 'PENDING'}, status=202)

# def get_job_status_api(request, job_id):
#     job = get_object_or_404(DubbingJob, id=job_id)
#     return JsonResponse({'job_id': str(job.id), 'status': job.status, 'error_message': job.error_message})

# def download_video_api(request, job_id):
#     job = get_object_or_404(DubbingJob, id=job_id)
#     if job.status != 'SUCCESS': return JsonResponse({'error': 'Not ready'}, status=400)
#     return FileResponse(open(job.video_output.path, 'rb'), content_type='video/mp4')
# transcriber.py
import os
from groq import Groq
from django.conf import settings

def transcribe_audio(audio_path):
    """
    تحويل الصوت إلى نص عبر API الخاص بـ Groq بسرعة البرق وبدون استهلاك رام السيرفر.
    """
    # يستدعي المفتاح من إعدادات دجانجو (يمكنك وضعه كمتغير بيئة في سيرفر Render بأمان)
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    with open(audio_path, "rb") as audio_file:
        # إرسال الملف كاملاً في طلب واحد ذكي
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), audio_file.read()),
            model="whisper-large-v3", # أحدث وأقوى نموذج متاح مجاناً لديهم
            response_format="verbose_json", # لكي يعيد لنا الطوابع الزمنية بدقة
            language="en"
        )
    
    segments = []
    # استخراج الجمل مع أوقات البداية والنهاية تماماً كما كان يفعل النموذج المحلي
    if hasattr(transcription, 'segments'):
        for seg in transcription.segments:
            segments.append({
                'start': float(seg['start']),
                'end': float(seg['end']),
                'text': seg['text'].strip()
            })
            
    return segments


# import whisper
# import torch
# def transcribe_audio(audio_path):
#     device = "cuda" if torch.cuda.is_available() else "cpu"
#     model = whisper.load_model("base", device=device)
#     result = model.transcribe(audio_path, language="en")
#     segments = []
#     for seg in result.get('segments', []):
#         segments.append({'start': float(seg['start']), 'end': float(seg['end']), 'text': seg['text'].strip()})
#     return segments
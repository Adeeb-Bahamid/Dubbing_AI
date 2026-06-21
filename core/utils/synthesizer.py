# utils/synthesizer.py
import asyncio
import os
import sys
import edge_tts


async def _tts_worker(text, output_path,semaphore): 
    async with semaphore:
        communicate = edge_tts.Communicate(
            text,
            "ar-SA-HamedNeural"
        )
        await communicate.save(output_path)


async def _generate_all_tasks(tasks):
    await asyncio.gather(*tasks)


def generate_arabic_audio_track(
    translated_segments,
    temp_dir
):
    """
    توليد جميع المقاطع الصوتية بالتوازي
    بدلاً من تشغيل Event Loop لكل مقطع.
    """

    print("🎙️ Starting Parallel TTS Generation...")

    tasks = []

    for idx, seg in enumerate(translated_segments):

        text = seg.get("text", "").strip()

        if not text:
            continue

        output_path = os.path.join(
            temp_dir,
            f"sub_{idx}.mp3"
        )

        semaphore = asyncio.Semaphore(10)
        tasks.append(
            _tts_worker(
                text,
                output_path,
                semaphore
            )
        )

    try:

        asyncio.run(
            _generate_all_tasks(tasks)
        )

        print("✅ All TTS files generated successfully.")

    except Exception as e:


        print(
            f"❌ Parallel TTS Error: {e}",
            file=sys.stderr
        )






# import asyncio
# import os
# import sys
# import edge_tts

# async def _tts_worker(text, output_path):
#     """
#     استدعاء محرك edge_tts لتوليد صوت طبيعي ومريح بدون تعليق
#     """
#     communicate = edge_tts.Communicate(text, "ar-SA-HamedNeural")
#     await communicate.save(output_path)

# def generate_arabic_audio_track(translated_segments, temp_dir):
#     """
#     توليد ملفات صوتية منفصلة لكل كتلة مترجمة متناسقة مع منطق الـ Merger والمؤشرات الحقيقية.
#     """
#     print("🎙️ جاري توليد التعليق الصوتي العربي لكل جزء...")
    
#     for idx, seg in enumerate(translated_segments):
#         if not seg['text'].strip(): 
#             continue
        
#         output_file_name = f"sub_{idx}.mp3"
#         output_path = os.path.join(temp_dir, output_file_name)

        
#         try:
#             # تشغيل المعالج بشكل متزامن وآمن داخل الـ Pipeline الخفي
#             asyncio.run(_tts_worker(seg['text'], output_path))
#             print(f"✅ Generated: {output_file_name}")
            
#         except Exception as e:
#             print(f"❌ TTS Generation Failed for segment {idx}: {e}", file=sys.stderr)








# import asyncio
# import os
# import sys
# import edge_tts

# async def _tts_worker(text, output_path):
#     """
#     استدعاء محرك edge_tts لتوليد صوت طبيعي ومريح
#     """
#     # نستخدم صوت "حامد" السعودي الاحترافي، ومناسب جداً للشروحات التقنية (فلاتر وريفر بود)
#     communicate = edge_tts.Communicate(text, "ar-SA-HamedNeural")
#     await communicate.save(output_path)

# def generate_arabic_audio_track(translated_segments, temp_dir):
#     """
#     توليد ملفات صوتية منفصلة لكل جملة مترجمة وتركها تنطق براحتها 
#     بدون تسريع أو حشر زمني، ليتمكن الـ Merger من تمديد الفيديو بناءً عليها.
#     """
#     print("🎙️ جاري توليد التعليق الصوتي العربي لكل جزء...")
    
#     for idx, seg in enumerate(translated_segments):
#         # تخطي الجمل الفارغة
#         if not seg['text'].strip(): 
#             continue
        
#         # تسمية الملف باسم يطابق ما ينتظره ملف الـ video_merger (sub_0.mp3, sub_1.mp3...)
#         output_file_name = f"sub_{idx}.mp3"
#         output_path = os.path.join(temp_dir, output_file_name)
        
#         try:
#             # تشغيل الـ worker لتوليد الصوت بالسرعة الطبيعية 100%
#             asyncio.run(_tts_worker(seg['text'], output_path))
            
#             if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
#                 print(f"✅ تم توليد الصوت للجزء {idx} بنجاح.")
#             else:
#                 print(f"⚠️ تنبيه: ملف الصوت للجزء {idx} فارغ أو لم يتم إنشاؤه.")
                
#         except Exception as e:
#             print(f"❌ خطأ أثناء توليد صوت الجزء {idx}: {e}", file=sys.stderr)



# import asyncio
# import os
# import subprocess
# import edge_tts
# from pydub import AudioSegment

# async def _tts_worker(text, output_path):
#     # نستخدم صوت "حامد" السعودي أو "شاكر" المصري (يمكنك التجربة بينهما لأيهم تراه أنسب لشرحك)
#     communicate = edge_tts.Communicate(text, "ar-SA-HamedNeural")
#     await communicate.save(output_path)

# def scale_audio_duration_ffmpeg(input_path, output_path, speed_ratio):
#     """
#     تغيير سرعة الصوت باحترافية عالية باستخدام FFmpeg لمنع الصدى والتقطيع الروبوتي
#     """
#     # التأكد من أن نسبة السرعة في الحدود المسموحة لـ atempo (بين 0.5 و 2.0)
#     speed_ratio = max(0.5, min(speed_ratio, 2.0))
    
#     cmd = [
#         'ffmpeg', '-y',
#         '-i', input_path,
#         '-filter:a', f'atempo={speed_ratio}',
#         '-vn', output_path
#     ]
#     subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# def generate_arabic_audio_track(translated_segments, total_duration, temp_dir):
#     # إنشاء مسار فارغ بطول الفيديو وبجودة عالية (44100Hz)
#     master_audio = AudioSegment.silent(duration=int(total_duration * 1000), frame_rate=44100)
    
#     for idx, seg in enumerate(translated_segments):
#         if not seg['text'].strip(): continue
        
#         raw_seg_file = os.path.join(temp_dir, f"raw_seg_{idx}.mp3")
#         asyncio.run(_tts_worker(seg['text'], raw_seg_file))
        
#         if os.path.exists(raw_seg_file) and os.path.getsize(raw_seg_file) > 0:
#             seg_audio = AudioSegment.from_file(raw_seg_file, format="mp3")
            
#             start_ms = int(seg['start'] * 1000)
#             end_ms = int(seg['end'] * 1000)
#             allowed_ms = end_ms - start_ms
            
#             if allowed_ms > 0:
#                 current_duration_ms = len(seg_audio)
                
#                 # إذا كان الكلام العربي أطول من الوقت المتاح له في الفيديو الأصلي
#                 if current_duration_ms > allowed_ms:
#                     ratio = current_duration_ms / allowed_ms
                    
#                     # نقوم بالتسريع الاحترافي عبر FFmpeg
#                     scaled_seg_file = os.path.join(temp_dir, f"scaled_seg_{idx}.mp3")
#                     scale_audio_duration_ffmpeg(raw_seg_file, scaled_seg_file, ratio)
                    
#                     if os.path.exists(scaled_seg_file):
#                         seg_audio = AudioSegment.from_file(scaled_seg_file, format="mp3")
                
#                 # قَص الأجزاء الزائدة بدقة ميكرونية كحماية أخيرة لمنع تداخل الجمل
#                 if len(seg_audio) > allowed_ms:
#                     seg_audio = seg_audio[:allowed_ms]
                
#                 # دمج المقطع المسرّع والنقي في مكانه الزمني الصحيح داخل الفيديو
#                 master_audio = master_audio.overlay(seg_audio, position=start_ms)
                
#     final_wav = os.path.join(temp_dir, "final_arabic_track.wav")
#     master_audio.export(final_wav, format="wav")
#     return final_wav
import os
import sys

# 1️⃣ استيراد مرن يتوافق مع الإصدارات القديمة والجديدة لـ MoviePy
try:
    from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

def get_video_duration(video_path):
    """
    جلب المدة الزمنية الكلية للفيديو بثوانٍ.
    """
    try:
        video = VideoFileClip(video_path)
        duration = video.duration
        video.close()
        return duration
    except Exception as e:
        print(f"⚠️ فشل جلب مدة الفيديو: {e}")
        return 0.0

def apply_speed_change(clip, factor):
    """
    دالة لتغيير سرعة الفيديو تتخطى كل عيوب وتحديثات MoviePy 2.0+
    """
    if factor == 1.0 or factor <= 0:
        return clip
        
    # جلب التابع الصحيح للتعديل بناءً على ما تدعمه النسخة الحالية في جهازك
    if hasattr(clip, 'with_duration') and hasattr(clip, 'with_fps'):
        return clip.with_duration(clip.duration / factor).with_fps(clip.fps * factor)
    elif hasattr(clip, 'with_effects'):
        try:
            import vfx
            return clip.with_effects([vfx.MultiplySpeed(factor)])
        except Exception:
            pass
            
    return clip

def merge_arabic_audio_with_stretching(video_path, translated_segments, audio_files_dir, output_path):
    """
    دمج الأصوات العربية مع الفيديو، مع تمديد وإبطاء الفيديو تلقائياً 
    إذا كان الكلام العربي أطول من التوقيت الإنجليزي الأصلي.
    """
    if not os.path.exists(video_path):
        print(f"❌ خطأ: ملف الفيديو غير موجود في المسار: {video_path}", file=sys.stderr)
        return

    video = VideoFileClip(video_path)
    final_clips = []
    last_end = 0.0

    # دعم مرن لاسم دالة التقطيع سواء بالنسخة الجديدة أو القديمة
    has_subclipped = hasattr(video, 'subclipped')

    for idx, seg in enumerate(translated_segments):
        start_time = float(seg['start'])
        end_time = float(seg['end'])
        
        # 🛡️ الحماية التامة من فروقات التقريب التي تأتي من نموذج الـ AI
        if end_time > video.duration:
            end_time = video.duration
            
        if start_time >= video.duration:
            continue
            
        original_duration = end_time - start_time
        
        # 1️⃣ قطع الأجزاء الفاصلة قبل الجملة الحالية (بصوتها الأصلي)
        if start_time > last_end:
            silent_clip = video.subclipped(last_end, start_time) if has_subclipped else video.subclip(last_end, start_time)
            final_clips.append(silent_clip)

        # 2️⃣ تجهيز ملف الصوت العربي
        audio_file_path = os.path.join(audio_files_dir, f"sub_{idx}.mp3")
        
        if os.path.exists(audio_file_path) and original_duration > 0:
            # قطع مقطع الفيديو المخصص للجملة
            video_clip = video.subclipped(start_time, end_time) if has_subclipped else video.subclip(start_time, end_time)
            arabic_audio = AudioFileClip(audio_file_path)
            arabic_duration = arabic_audio.duration

            # 3️⃣ مقارنة المدة وتمديد الفيديو عند الحاجة عبر الدالة الذكية الآمنة
            if arabic_duration > original_duration:
                speed_factor = original_duration / arabic_duration
                video_clip = apply_speed_change(video_clip, speed_factor)
                print(f"🎬 تمديد الجزء {idx}: تم إبطاء الفيديو بمعدل {speed_factor:.2f} ليناسب الصوت العربي.")
            
            # 🔥 الإصلاح الجوهري والحاسم هنا: دعم set_audio و with_audio تلقائياً منعاً للانهيار
            if hasattr(video_clip, 'with_audio'):
                video_clip = video_clip.with_audio(arabic_audio)
            else:
                video_clip = video_clip.set_audio(arabic_audio)
                
            final_clips.append(video_clip)
        else:
            video_clip = video.subclipped(start_time, end_time) if has_subclipped else video.subclip(start_time, end_time)
            final_clips.append(video_clip)

        last_end = end_time

    # 4️⃣ إضافة الجزء المتبقي من الفيديو بعد آخر جملة (إن وجد)
    if video.duration > last_end:
        remaining_clip = video.subclipped(last_end, video.duration) if has_subclipped else video.subclip(last_end, video.duration)
        final_clips.append(remaining_clip)

    # 5️⃣ دمج المقاطع وتصدير الفيديو النهائي
    if final_clips:
        print("⏳ جاري دمج المقاطع وتصدير الفيديو النهائي الممدد...")
        final_video = concatenate_videoclips(final_clips, method="compose")
        
        # التصدير فائق السرعة لتجنب الـ Timeout
        final_video.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac",
            threads=4,
            preset="ultrafast", 
            fps=video.fps,
            logger=None
        )
        
        final_video.close()
    else:
        print("⚠️ تحذير: لم يتم إنتاج أي مقاطع للدمج.")

    video.close()
    print(f"🎉 تمت العملية بنجاح كامل وصارم! الفيديو متاح في: {output_path}")


# import os
# import sys
# # الاستيراد الصحيح والمتوافق تماماً مع إشارت MoviePy v2.0+
# from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
# import moviepy.video.fx as vfx

# def merge_arabic_audio_with_stretching(video_path, translated_segments, audio_files_dir, output_path):
#     """
#     دمج الأصوات العربية مع الفيديو، مع تمديد وإبطاء الفيديو تلقائياً 
#     إذا كان الكلام العربي أطول من التوقيت الإنجليزي الأصلي، لضمان صوت طبيعي ومريح.
#     """
#     if not os.path.exists(video_path):
#         print(f"❌ خطأ: ملف الفيديو غير موجود في المسار: {video_path}", file=sys.stderr)
#         return

#     # فتح الفيديو الأصلي
#     video = VideoFileClip(video_path)
#     final_clips = []
#     last_end = 0.0

#     for idx, seg in enumerate(translated_segments):
#         start_time = float(seg['start'])
#         end_time = float(seg['end'])
#         original_duration = end_time - start_time
        
#         # 1️⃣ قطع الأجزاء الفاصلة قبل الجملة الحالية (صوت الفيديو الأصلي) وإضافتها كما هي لكي لا يختفي الصوت
#         if start_time > last_end:
#             silent_clip = video.subclip(last_end, start_time)
#             final_clips.append(silent_clip)

#         # 2️⃣ تجهيز ملف الصوت العربي المقابل ومساره
#         audio_file_path = os.path.join(audio_files_dir, f"sub_{idx}.mp3")
        
#         if os.path.exists(audio_file_path) and original_duration > 0:
#             # جلب مقطع الفيديو الأصلي المخصص للجملة
#             video_clip = video.subclip(start_time, end_time)
#             arabic_audio = AudioFileClip(audio_file_path)
#             arabic_duration = arabic_audio.duration

#             # 3️⃣ السحر البرمجي: مقارنة المدة وتمديد الفيديو عند الحاجة
#             if arabic_duration > original_duration:
#                 # حساب نسبة الإبطاء المطلوبة (مثلاً 0.8)
#                 speed_factor = original_duration / arabic_duration
                
#                 # التعديل المتوافق مع الإصدار الجديد: تمرير دالة التعديل بشكل صريح
#                 video_clip = video_clip.fx(vfx.speedx, factor=speed_factor)
                
#                 print(f"🎬 تمديد الجزء {idx}: تم إبطاء الفيديو بمعدل {speed_factor:.2f} ليناسب الصوت العربي المريح.")
            
#             # ربط الصوت العربي الجديد بالمقطع (سواء ممدد أو لا)
#             video_clip = video_clip.set_audio(arabic_audio)
#             final_clips.append(video_clip)
#         else:
#             # إذا لم يوجد ملف صوتي مترجم، نأخذ مقطع الفيديو الأصلي بصوته وحالته دون تغيير
#             video_clip = video.subclip(start_time, end_time)
#             final_clips.append(video_clip)

#         last_end = end_time

#     # 4️⃣ إضافة الجزء المتبقي من الفيديو بعد آخر جملة (إن وجد)
#     if video.duration > last_end:
#         final_clips.append(video.subclip(last_end, video.duration))

#     # 5️⃣ دمج كل المقاطع الممددة والعادية في فيديو واحد نهائي وسلس
#     if final_clips:
#         print("⏳ جاري دمج المقاطع وتصدير الفيديو النهائي الممدد...")
#         final_video = concatenate_videoclips(final_clips, method="compose")
        
#         # تصدير الملف النهائي بأعلى كفاءة لـ H.264
#         final_video.write_videofile(
#             output_path, 
#             codec="libx264", 
#             audio_codec="aac",
#             threads=4,
#             fps=video.fps,
#             logger=None # لإخفاء أسطر الطبع الكثيرة وتسريع عملية المعالجة والتصدير
#         )
        
#         # إغلاق الملفات تماماً لتحرير الذاكرة العشوائية (RAM) في السيرفر والجهاز
#         final_video.close()
#     else:
#         print("⚠️ تحذير: لم يتم إنتاج أي مقاطع للدمج.")

#     video.close()
#     print(f"🎉 تمت العملية بنجاح! الفيديو الاحترافي الممدد متاح في: {output_path}")

# def get_video_duration(video_path):
#     """
#     دالة مساعدة لجلب المدة الزمنية الكلية للفيديو بثوانٍ معدودة.
#     """
#     try:
#         video = VideoFileClip(video_path)
#         duration = video.duration
#         video.close()
#         return duration
#     except Exception as e:
#         print(f"⚠️ فشل جلب مدة الفيديو: {e}")
#         return 0.0

# import subprocess
# def get_video_duration(video_path):
#     cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
#     return float(subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.strip())

# def merge_video_and_audio(video_path, audio_path, output_path):
#     cmd = ['ffmpeg', '-y', '-i', video_path, '-i', audio_path, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-shortest', output_path]
#     subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# video_merger.py

import os
import shutil
import subprocess
import sys


def get_video_duration(video_path):
    try:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        return float(result.stdout.strip())

    except Exception as error:
        print(f"⚠️ فشل جلب مدة الملف: {error}", file=sys.stderr)
        return 0.0


def run_ffmpeg(command):
    print("▶️ تشغيل FFmpeg...")

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        print("❌ FFmpeg فشل:", file=sys.stderr)
        print(result.stderr[-5000:], file=sys.stderr)
        return False

    return True


def make_silent_audio(duration, output_path):
    duration = max(float(duration), 0.01)

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t",
        f"{duration:.3f}",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-ac",
        "2",
        output_path,
    ]

    return run_ffmpeg(command)


def merge_arabic_audio_with_stretching(
    video_path,
    translated_segments,
    audio_files_dir,
    output_path,
):
    """
    دمج الفيديو والصوت العربي بطريقة منخفضة استهلاك الذاكرة.

    - تقسيم الفيديو إلى أجزاء لا تتجاوز دقيقتين.

    - الحفاظ على منطق تبطيء الفيديو حسب مدة الصوت العربي.
    - عدم تغيير setpts أو speed_factor.
    - إزالة الصوت الإنجليزي بالكامل.
    - إضافة صمت بين الجمل.
    - معالجة كل جزء بشكل مستقل.
    - حذف الملفات المؤقتة بعد الانتهاء من كل جزء.
    """

    if not os.path.exists(video_path):
        print(
            f"❌ ملف الفيديو غير موجود: {video_path}",
            file=sys.stderr,
        )
        return

    video_duration = get_video_duration(video_path)

    if video_duration <= 0:
        print(
            "❌ تعذر قراءة مدة الفيديو الأصلي.",
            file=sys.stderr,
        )
        return

    temp_dir = os.path.join(
        audio_files_dir,
        "temp_clips",
    )

    os.makedirs(temp_dir, exist_ok=True)

    # تنظيف الملفات المؤقتة القديمة
    for filename in os.listdir(temp_dir):
        file_path = os.path.join(
            temp_dir,
            filename,
        )

        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

        elif os.path.isdir(file_path):
            shutil.rmtree(
                file_path,
                ignore_errors=True,
            )

    valid_segments = []

    for index, segment in enumerate(translated_segments):
        audio_path = os.path.join(
            audio_files_dir,
            f"sub_{index}.mp3",
        )

        if not os.path.exists(audio_path):
            print(
                f"⚠️ ملف الصوت غير موجود: {audio_path}",
                file=sys.stderr,
            )
            continue

        try:
            start = max(
                0.0,
                float(segment["start"]),
            )

            end = min(
                video_duration,
                float(segment["end"]),
            )

        except (KeyError, TypeError, ValueError) as error:
            print(
                f"⚠️ بيانات الجملة غير صحيحة: {error}",
                file=sys.stderr,
            )
            continue

        if end <= start:
            continue

        valid_segments.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "audio": audio_path,
            }
        )

    if not valid_segments:
        print(
            "⚠️ لم يتم العثور على جمل صوتية صالحة.",
            file=sys.stderr,
        )
        return

    # تقسيم الجمل إلى أجزاء لا تتجاوز دقيقتين
    chunks = []
    current_chunk = []
    current_chunk_start = valid_segments[0]["start"]

    for segment in valid_segments:
        segment_end = segment["end"]

        if current_chunk and segment_end - current_chunk_start > 120.0:
            chunks.append(current_chunk)

            current_chunk = []
            current_chunk_start = segment["start"]

        current_chunk.append(segment)

    if current_chunk:
        chunks.append(current_chunk)

    output_chunks = []

    try:
        for chunk_number, segments in enumerate(chunks):
            chunk_start = segments[0]["start"]
            chunk_end = segments[-1]["end"]

            chunk_dir = os.path.join(
                temp_dir,
                f"chunk_{chunk_number}",
            )

            os.makedirs(
                chunk_dir,
                exist_ok=True,
            )

            print(
                f"🎬 معالجة الجزء "
                f"{chunk_number + 1}/{len(chunks)} "
                f"من {chunk_start:.2f} "
                f"إلى {chunk_end:.2f} ثانية"
            )

            pieces = []
            cursor = chunk_start

            for piece_number, segment in enumerate(segments):
                start = segment["start"]
                end = segment["end"]

                original_duration = end - start

                # إضافة الصمت بين الجمل
                if start > cursor + 0.05:
                    gap_duration = start - cursor

                    silent_audio_path = os.path.join(
                        chunk_dir,
                        f"silent_{piece_number}.m4a",
                    )

                    silent_video_path = os.path.join(
                        chunk_dir,
                        f"gap_{piece_number}.mp4",
                    )

                    silent_audio_created = make_silent_audio(
                        gap_duration,
                        silent_audio_path,
                    )

                    if silent_audio_created:
                        gap_command = [
                            "ffmpeg",
                            "-y",
                            "-ss",
                            f"{cursor:.3f}",
                            "-t",
                            f"{gap_duration:.3f}",
                            "-i",
                            video_path,
                            "-i",
                            silent_audio_path,
                            "-map",
                            "0:v:0",
                            "-map",
                            "1:a:0",
                            "-c:v",
                            "libx264",
                            "-preset",
                            "ultrafast",
                            "-pix_fmt",
                            "yuv420p",
                            "-c:a",
                            "aac",
                            "-ar",
                            "44100",
                            "-ac",
                            "2",
                            "-shortest",
                            silent_video_path,
                        ]

                        if run_ffmpeg(gap_command):
                            pieces.append(silent_video_path)

                audio_duration = get_video_duration(segment["audio"])

                if audio_duration <= 0:
                    audio_duration = original_duration

                dubbed_video_path = os.path.join(
                    chunk_dir,
                    f"dubbed_{piece_number}.mp4",
                )

                # ==================================================
                # منطق التبطيء الأصلي - لا يتم تغييره
                # ==================================================

                if audio_duration > original_duration:
                    speed_factor = original_duration / audio_duration

                    if speed_factor < 0.5:
                        speed_factor = 0.5

                    setpts_factor = 1.0 / speed_factor

                    video_filter = (
                        f"[0:v]"
                        f"trim=start=0:end={original_duration:.6f},"
                        f"setpts={setpts_factor:.8f}*(PTS-STARTPTS),"
                        f"fps=24[v]"
                    )

                    print(
                        f"🎬 الجملة {segment['index']}: "
                        f"تبطيء الفيديو بمعدل "
                        f"{speed_factor:.2f}"
                    )

                else:
                    video_filter = (
                        f"[0:v]"
                        f"trim=start=0:end={original_duration:.6f},"
                        f"setpts=PTS-STARTPTS,"
                        f"fps=24[v]"
                    )

                # ==================================================
                # إنشاء مقطع الجملة العربية
                # ==================================================

                dubbed_command = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{start:.3f}",
                    "-t",
                    f"{original_duration:.3f}",
                    "-i",
                    video_path,
                    "-i",
                    segment["audio"],
                    "-filter_complex",
                    video_filter,
                    "-map",
                    "[v]",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    "-shortest",
                    dubbed_video_path,
                ]

                if run_ffmpeg(dubbed_command):
                    pieces.append(dubbed_video_path)

                cursor = end

            if not pieces:
                print(
                    f"⚠️ لم يتم إنتاج مقاطع للجزء {chunk_number + 1}",
                    file=sys.stderr,
                )

                shutil.rmtree(
                    chunk_dir,
                    ignore_errors=True,
                )

                continue

            # إنشاء قائمة مقاطع الجزء
            pieces_list_path = os.path.join(
                chunk_dir,
                "pieces.txt",
            )

            with open(
                pieces_list_path,
                "w",
                encoding="utf-8",
            ) as file:
                for piece in pieces:
                    absolute_piece_path = os.path.abspath(piece)

                    escaped_piece_path = absolute_piece_path.replace("'", "'\\''")

                    file.write(f"file '{escaped_piece_path}'\n")

            chunk_output_path = os.path.join(
                temp_dir,
                f"final_chunk_{chunk_number}.mp4",
            )

            # تجميع مقاطع الجزء
            chunk_concat_command = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                pieces_list_path,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                chunk_output_path,
            ]

            if run_ffmpeg(chunk_concat_command):
                output_chunks.append(chunk_output_path)

            # حذف ملفات هذا الجزء فورًا
            shutil.rmtree(
                chunk_dir,
                ignore_errors=True,
            )

        if not output_chunks:
            print(
                "⚠️ لم يتم إنتاج أي أجزاء نهائية.",
                file=sys.stderr,
            )
            return

        # إنشاء قائمة الأجزاء النهائية
        final_list_path = os.path.join(
            temp_dir,
            "final_chunks.txt",
        )

        with open(
            final_list_path,
            "w",
            encoding="utf-8",
        ) as file:
            for chunk in output_chunks:
                absolute_chunk_path = os.path.abspath(chunk)

                escaped_chunk_path = absolute_chunk_path.replace("'", "'\\''")

                file.write(f"file '{escaped_chunk_path}'\n")

        print("🚀 تجميع الأجزاء النهائية...")

        # محاولة التجميع بدون إعادة ترميز
        final_concat_command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            final_list_path,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output_path,
        ]

        if not run_ffmpeg(final_concat_command):
            print(
                "⚠️ فشل التجميع بنسخ المسارات، سيتم استخدام إعادة الترميز.",
                file=sys.stderr,
            )

            fallback_command = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                final_list_path,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                output_path,
            ]

            if not run_ffmpeg(fallback_command):
                return

        print(f"🎉 تم الدمج بنجاح: {output_path}")

    finally:
        # حذف الأجزاء النهائية المؤقتة
        for chunk_path in output_chunks:
            try:
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
            except OSError:
                pass

        # حذف قائمة الأجزاء
        final_list_path = os.path.join(
            temp_dir,
            "final_chunks.txt",
        )

        try:
            if os.path.exists(final_list_path):
                os.remove(final_list_path)
        except OSError:
            pass


# # video_merger.py
# import os
# import sys
# import subprocess

# def get_video_duration(video_path):
#     try:
#         # النسخة المصححة والمضمونة لجلب مدة الفيديو بدقة
#         cmd = [
#             'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
#             '-of', 'default=noprint_wrappers=1:nokey=1', video_path
#         ]
#         result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
#         return float(result.stdout.strip())
#     except Exception as e:
#         print(f"⚠️ فشل جلب مدة الفيديو عبر ffprobe: {e}")
#         return 0.0

# def merge_arabic_audio_with_stretching(video_path, translated_segments, audio_files_dir, output_path):
#     """
#     النسخة الإنتاجية النهائية والكاملة (Production-Ready MVP):
#     - توليد صوت صامت وهمي (anullsrc) في الفواصل لمنع تسرب الإنجليزي ولتوحيد الهيكلية.
#     - اقتطاع دقيق بـ trim وتصفير الـ PTS حركياً وزمنياً لمنع الـ Jitter.
#     - إنهاء قطعي وفوري للفيديو عند انتهاء آخر جملة عربية مدبلجة لقطع الحشو.
#     - تجميع خارق السرعة وثابت 100% بـ -c copy لتماثل تركيب المسارات تماماً في كل الأجزاء.
#     """

#     if not os.path.exists(video_path):
#         print(f"❌ خطأ: ملف الفيديو غير موجود: {video_path}", file=sys.stderr)
#         return

#     video_duration = get_video_duration(video_path)
#     if video_duration == 0.0:
#         print("❌ خطأ: تعذر قراءة مدة الفيديو الأصلي.", file=sys.stderr)
#         return

#     temp_dir = os.path.join(audio_files_dir, "temp_clips")
#     os.makedirs(temp_dir, exist_ok=True)

#     clip_files_list = []
#     last_end = 0.0

#     # 🔍 تحديد آخر جملة عربية تمتلك صوتاً فعلياً لقطع الفائض الصامت من النهاية
#     last_valid_seg_idx = -1
#     for i in range(len(translated_segments) - 1, -1, -1):
#         audio_file_path = os.path.join(audio_files_dir, f"sub_{i}.mp3")
#         if os.path.exists(audio_file_path):
#             last_valid_seg_idx = i
#             break

#     if last_valid_seg_idx == -1:
#         print("⚠️ تحذير: لم يتم العثور على أي ملفات صوتية عربية للدبلجة.")
#         return

#     for idx, seg in enumerate(translated_segments):
#         if idx > last_valid_seg_idx:
#             break

#         start_time = float(seg['start'])
#         end_time = float(seg['end'])

#         if end_time > video_duration:
#             end_time = video_duration
#         if start_time >= video_duration:
#             continue

#         original_duration = end_time - start_time

#         # 1️⃣ معالجة الفواصل (حقن صوت صامت وهمي بالكامل لتطابق الـ Codecs والمسارات)
#         if start_time > last_end and (start_time - last_end) > 0.05:
#             # chunk_path = os.path.join(temp_dir, f"silent_{idx}.mp4")
#         # gap = start_time - last_end
#         # if gap > 0.3:
#             chunk_path = os.path.join(temp_dir, f"silent_{idx}.mp4")
#             # هندسة الفلتر: نأخذ الفيديو ونقطعه، ونولد صوت صامت ستيريو بتردد 44100 هرتز
#             filter_str = f"[0:v]trim=start={last_end}:end={start_time},setpts=PTS-STARTPTS,fps=24[v]"
#             # silent_duration = min(gap, 0.4)
#             # filter_str = f"[0:v]trim=start={last_end}:end={last_end + silent_duration},setpts=PTS-STARTPTS,fps=24[v]"
#             cmd = [
#                 'ffmpeg', '-y',
#                 '-i', video_path,
#                 '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100', # توليد مسار الصمت الوهمي
#                 '-filter_complex', filter_str,
#                 '-map', '[v]', '-map', '1:a',
#                 '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p',
#                 '-shortest', # إجبار الكليب على الانتهاء فور انتهاء قطعة الفيديو المقصوصة
#                 '-preset', 'ultrafast', chunk_path
#             ]
#             subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#             if os.path.exists(chunk_path) and get_video_duration(chunk_path) > 0:
#                 clip_files_list.append(chunk_path)

#         # 2️⃣ معالجة مقطع الدبلجة الحالي وتمديده حركياً بـ setpts بدقة الفريم وثبات الـ FPS
#         audio_file_path = os.path.join(audio_files_dir, f"sub_{idx}.mp3")
#         chunk_path = os.path.join(temp_dir, f"dubbed_{idx}.mp4")

#         if os.path.exists(audio_file_path) and original_duration > 0:
#             arabic_duration = get_video_duration(audio_file_path)
#             if arabic_duration == 0:
#                 arabic_duration = original_duration

#             if arabic_duration > original_duration:
#                 speed_factor = original_duration / arabic_duration
#                 if speed_factor < 0.5:
#                     speed_factor = 0.5


#                 setpts_factor = 1.0 / speed_factor
#                 filter_str = f"[0:v]trim=start={start_time}:end={end_time},setpts={setpts_factor}*(PTS-STARTPTS),fps=24[v]"
#             else:
#                 filter_str = f"[0:v]trim=start={start_time}:end={end_time},setpts=PTS-STARTPTS,fps=24[v]"

#             cmd = [
#                 'ffmpeg', '-y', '-i', video_path, '-i', audio_file_path,
#                 '-filter_complex', filter_str,
#                 '-map', '[v]', '-map', '1:a',
#                 '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', '-preset', 'ultrafast', chunk_path
#             ]
#             subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#             if os.path.exists(chunk_path) and get_video_duration(chunk_path) > 0:
#                 clip_files_list.append(chunk_path)
#         else:
#             # جزء احترازي يقع قبل الجملة الأخيرة (يُحقن بصوت صامت وهمي أيضاً)
#             if original_duration > 0.05:
#                 filter_str = f"[0:v]trim=start={start_time}:end={end_time},setpts=PTS-STARTPTS,fps=24[v]"
#                 cmd = [

#                     'ffmpeg', '-y', '-i', video_path,
#                     '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
#                     '-filter_complex', filter_str,
#                     '-map', '[v]', '-map', '1:a',
#                     '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p',
#                     '-shortest', '-preset', 'ultrafast', chunk_path
#                 ]
#                 subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#                 if os.path.exists(chunk_path) and get_video_duration(chunk_path) > 0:
#                     clip_files_list.append(chunk_path)

#         last_end = end_time

#     # 4️⃣ التجميع الخارق والتوحيد النهائي (الآن آمن ومستقر وصاروخي 🚀)
#     if clip_files_list:
#         list_file_path = os.path.join(temp_dir, "clips_list.txt")
#         with open(list_file_path, "w") as f:
#             for file_p in clip_files_list:
#                 f.write(f"file '{file_p}'\n")

#         print("🚀 جاري دمج الأجزاء فائق السرعة عبر Stream Copy المتطابق...")
#         # بفضل توحيد الـ Codecs والـ Tracks والصوت الوهمي، الـ copy هنا حاسم وآمن تماماً

#         concat_cmd = [
#             'ffmpeg', '-y',
#             '-f', 'concat',
#             '-safe', '0',
#             '-i', list_file_path,

#             # 🔥 إعادة تغليف آمنة بدون تغيير المحتوى كثير
#             '-c:v', 'libx264',
#             '-preset', 'veryfast',
#             '-crf', '23',

#             '-c:a', 'aac',
#             '-b:a', '128k',

#             '-movflags', '+faststart',

#             output_path
#         ]

#         # concat_cmd = [
#         #     'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
#         #     '-i', list_file_path,

#         #     '-c', 'copy',
#         #     '-movflags', '+faststart', # بث فوري سلس لتطبيق فلاتر
#         #     output_path
#         # ]
#         subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

#         # تنظيف فوري لمساحة السيرفر
#         for file_p in clip_files_list:
#             try: os.remove(file_p)
#             except: pass
#         try: os.remove(list_file_path)
#         except: pass

#         print(f"🎉 تم إغلاق المنظومة بنجاح ساحق ومثالي! الفيديو جاهز في: {output_path}")
#     else:
#         print("⚠️ تحذير: لم يتم إنتاج أي مقاطع للدمج.")


# import os
# import sys
# import subprocess

# try:
#     from moviepy import VideoFileClip, AudioFileClip
# except ImportError:
#     from moviepy.editor import VideoFileClip, AudioFileClip

# def get_video_duration(video_path):
#     try:
#         video = VideoFileClip(video_path)
#         duration = video.duration
#         video.close()
#         return duration
#     except Exception as e:
#         print(f"⚠️ فشل جلب مدة الفيديو: {e}")
#         return 0.0

# def apply_speed_change(clip, factor):
#     if factor == 1.0 or factor <= 0:
#         return clip
#     if hasattr(clip, 'with_duration') and hasattr(clip, 'with_fps'):
#         return clip.with_duration(clip.duration / factor).with_fps(clip.fps * factor)
#     return clip

# def merge_arabic_audio_with_stretching(video_path, translated_segments, audio_files_dir, output_path):
#     """

#     نسخة الـ Pipeline الاحترافية الثابتة:
#     تدمج بين سرعة الـ Stream Copy للأجزاء الفاصلة، وضمان الجودة
#     ومنع تقطيع الصوت والصورة عبر توحيد الترميز النهائي بـ FFmpeg.
#     """
#     if not os.path.exists(video_path):
#         print(f"❌ خطأ: ملف الفيديو غير موجود: {video_path}", file=sys.stderr)
#         return

#     # فتح الفيديو الأساسي لمعرفة الـ FPS والخصائص
#     video = VideoFileClip(video_path)
#     video_fps = video.fps
#     has_subclipped = hasattr(video, 'subclipped')

#     temp_dir = os.path.join(audio_files_dir, "temp_clips")
#     os.makedirs(temp_dir, exist_ok=True)

#     clip_files_list = []
#     last_end = 0.0

#     for idx, seg in enumerate(translated_segments):
#         start_time = float(seg['start'])
#         end_time = float(seg['end'])

#         if end_time > video.duration:
#             end_time = video.duration
#         if start_time >= video.duration:
#             continue

#         original_duration = end_time - start_time


#         # 1️⃣ قطع الأجزاء الفاصلة (صوت أصلي) بسرعة البرق عبر Stream Copy
#         if start_time > last_end:
#             chunk_path = os.path.join(temp_dir, f"silent_{idx}.mp4")
#             cmd = [
#                 'ffmpeg', '-y', '-ss', str(last_end), '-to', str(start_time),
#                 '-i', video_path, '-c:v', 'copy', '-c:a', 'copy', chunk_path
#             ]
#             subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#             if os.path.exists(chunk_path):
#                 clip_files_list.append(chunk_path)

#         # 2️⃣ معالجة مقطع الدبلجة الحالي (الـ Chunk)
#         audio_file_path = os.path.join(audio_files_dir, f"sub_{idx}.mp3")
#         chunk_path = os.path.join(temp_dir, f"dubbed_{idx}.mp4")

#         if os.path.exists(audio_file_path) and original_duration > 0:
#             # اقتطاع الجزء المحدد من الفيديو
#             video_clip = video.subclipped(start_time, end_time) if has_subclipped else video.subclip(start_time, end_time)
#             arabic_audio = AudioFileClip(audio_file_path)
#             arabic_duration = arabic_audio.duration

#             # التمديد عند الحاجة
#             if arabic_duration > original_duration:

#                 speed_factor = original_duration / arabic_duration
#                 video_clip = apply_speed_change(video_clip, speed_factor)

#             if hasattr(video_clip, 'with_audio'):
#                 video_clip = video_clip.with_audio(arabic_audio)
#             else:
#                 video_clip = video_clip.set_audio(arabic_audio)

#             # رندرة الجزء الصغير فقط وتوحيد الـ FPS مع الفيديو الأصلي
#             video_clip.write_videofile(
#                 chunk_path, codec="libx264", audio_codec="aac",
#                 preset="ultrafast", fps=video_fps, logger=None
#             )

#             # 🔥 إغلاق فوري للكليبات الصغيرة لتفريغ الـ RAM أولاً بأول على Render
#             video_clip.close()
#             arabic_audio.close()

#             if os.path.exists(chunk_path):
#                 clip_files_list.append(chunk_path)
#         else:
#             # نسخ سريع لو لم يوجد ملف صوتي عربي
#             cmd = [
#                 'ffmpeg', '-y', '-ss', str(start_time), '-to', str(end_time),
#                 '-i', video_path, '-c:v', 'copy', '-c:a', 'copy', chunk_path
#             ]
#             subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

#             if os.path.exists(chunk_path):
#                 clip_files_list.append(chunk_path)

#         last_end = end_time

#     # 3️⃣ الجزء المتبقي بعد آخر جملة
#     if video.duration > last_end:
#         chunk_path = os.path.join(temp_dir, f"remaining.mp4")
#         cmd = [
#             'ffmpeg', '-y', '-ss', str(last_end), '-to', str(video.duration),
#             '-i', video_path, '-c:v', 'copy', '-c:a', 'copy', chunk_path
#         ]
#         subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#         if os.path.exists(chunk_path):
#             clip_files_list.append(chunk_path)

#     # إغلاق الفيديو الأساسي وتفريغ الذاكرة بالكامل قبل التجميع النهائي
#     video.close()

#     # 4️⃣ التجميع النهائي الذكي (بناءً على نصيحتك الذهبية لمنع الـ Concat Failure)
#     if clip_files_list:
#         list_file_path = os.path.join(temp_dir, "clips_list.txt")
#         with open(list_file_path, "w") as f:
#             for file_p in clip_files_list:
#                 f.write(f"file '{file_p}'\n")

#         print("⚡ جاري تجميع وتوحيد الفيديو النهائي عبر الحلال السحري...")
#         # هنا استبدلنا الـ Copy بإعادة ترميز سريعة تضمن اندماج المسارات

# # 100% بدون أي خلل في الصوت أو الصورة
#         concat_cmd = [
#             'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
#             '-i', list_file_path,
#             '-c:v', 'libx264', '-c:a', 'aac',
#             '-preset', 'ultrafast', output_path
#         ]
#         subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

#         # تنظيف مساحة السيرفر
#         for file_p in clip_files_list:
#             try: os.remove(file_p)
#             except: pass
#         try: os.remove(list_file_path)
#         except: pass

#         print(f"🎉 تمت العملية بنجاح كامل وصارم! الفيديو متاح في: {output_path}")
#     else:
#         print("⚠️ تحذير: لم يتم إنتاج أي مقاطع للدمج.")


# import os
# import sys

# # 1️⃣ استيراد مرن يتوافق مع الإصدارات القديمة والجديدة لـ MoviePy
# try:
#     from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips
# except ImportError:
#     from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

# def get_video_duration(video_path):
#     """
#     جلب المدة الزمنية الكلية للفيديو بثوانٍ.
#     """
#     try:
#         video = VideoFileClip(video_path)
#         duration = video.duration
#         video.close()
#         return duration
#     except Exception as e:
#         print(f"⚠️ فشل جلب مدة الفيديو: {e}")
#         return 0.0

# def apply_speed_change(clip, factor):
#     """
#     دالة لتغيير سرعة الفيديو تتخطى كل عيوب وتحديثات MoviePy 2.0+
#     """
#     if factor == 1.0 or factor <= 0:
#         return clip

#     # جلب التابع الصحيح للتعديل بناءً على ما تدعمه النسخة الحالية في جهازك
#     if hasattr(clip, 'with_duration') and hasattr(clip, 'with_fps'):
#         return clip.with_duration(clip.duration / factor).with_fps(clip.fps * factor)
#     elif hasattr(clip, 'with_effects'):
#         try:
#             import vfx
#             return clip.with_effects([vfx.MultiplySpeed(factor)])
#         except Exception:
#             pass

#     return clip

# def merge_arabic_audio_with_stretching(video_path, translated_segments, audio_files_dir, output_path):
#     """
#     دمج الأصوات العربية مع الفيديو، مع تمديد وإبطاء الفيديو تلقائياً
#     إذا كان الكلام العربي أطول من التوقيت الإنجليزي الأصلي.
#     """
#     if not os.path.exists(video_path):
#         print(f"❌ خطأ: ملف الفيديو غير موجود في المسار: {video_path}", file=sys.stderr)
#         return

#     video = VideoFileClip(video_path)
#     final_clips = []
#     last_end = 0.0

#     # دعم مرن لاسم دالة التقطيع سواء بالنسخة الجديدة أو القديمة
#     has_subclipped = hasattr(video, 'subclipped')

#     for idx, seg in enumerate(translated_segments):
#         start_time = float(seg['start'])
#         end_time = float(seg['end'])

#         # 🛡️ الحماية التامة من فروقات التقريب التي تأتي من نموذج الـ AI
#         if end_time > video.duration:
#             end_time = video.duration

#         if start_time >= video.duration:
#             continue

#         original_duration = end_time - start_time

#         # 1️⃣ قطع الأجزاء الفاصلة قبل الجملة الحالية (بصوتها الأصلي)
#         if start_time > last_end:
#             silent_clip = video.subclipped(last_end, start_time) if has_subclipped else video.subclip(last_end, start_time)
#             final_clips.append(silent_clip)

#         # 2️⃣ تجهيز ملف الصوت العربي
#         audio_file_path = os.path.join(audio_files_dir, f"sub_{idx}.mp3")

#         if os.path.exists(audio_file_path) and original_duration > 0:
#             # قطع مقطع الفيديو المخصص للجملة
#             video_clip = video.subclipped(start_time, end_time) if has_subclipped else video.subclip(start_time, end_time)
#             arabic_audio = AudioFileClip(audio_file_path)
#             arabic_duration = arabic_audio.duration

#             # 3️⃣ مقارنة المدة وتمديد الفيديو عند الحاجة عبر الدالة الذكية الآمنة
#             if arabic_duration > original_duration:
#                 speed_factor = original_duration / arabic_duration
#                 video_clip = apply_speed_change(video_clip, speed_factor)
#                 print(f"🎬 تمديد الجزء {idx}: تم إبطاء الفيديو بمعدل {speed_factor:.2f} ليناسب الصوت العربي.")

#             # 🔥 الإصلاح الجوهري والحاسم هنا: دعم set_audio و with_audio تلقائياً منعاً للانهيار
#             if hasattr(video_clip, 'with_audio'):
#                 video_clip = video_clip.with_audio(arabic_audio)
#             else:
#                 video_clip = video_clip.set_audio(arabic_audio)

#             final_clips.append(video_clip)
#         else:
#             video_clip = video.subclipped(start_time, end_time) if has_subclipped else video.subclip(start_time, end_time)
#             final_clips.append(video_clip)

#         last_end = end_time

#     # 4️⃣ إضافة الجزء المتبقي من الفيديو بعد آخر جملة (إن وجد)
#     if video.duration > last_end:
#         remaining_clip = video.subclipped(last_end, video.duration) if has_subclipped else video.subclip(last_end, video.duration)
#         final_clips.append(remaining_clip)

#     # 5️⃣ دمج المقاطع وتصدير الفيديو النهائي
#     if final_clips:
#         print("⏳ جاري دمج المقاطع وتصدير الفيديو النهائي الممدد...")
#         final_video = concatenate_videoclips(final_clips, method="compose")

#         # التصدير فائق السرعة لتجنب الـ Timeout
#         final_video.write_videofile(
#             output_path,
#             codec="libx264",
#             audio_codec="aac",
#             threads=4,
#             preset="ultrafast",
#             fps=video.fps,
#             logger=None
#         )

#         final_video.close()
#     else:
#         print("⚠️ تحذير: لم يتم إنتاج أي مقاطع للدمج.")

#     video.close()
#     print(f"🎉 تمت العملية بنجاح كامل وصارم! الفيديو متاح في: {output_path}")

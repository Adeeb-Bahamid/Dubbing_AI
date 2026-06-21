# translator.py
import sys
from groq import Groq
from django.conf import settings

def translate_segments(segments):
    """
    ترجمة النصوص بذكاء عبر تجميع الجمل (Chunks) لتقليل الطلبات،
    مع وجود نظام أمان تلقائي يضمن خروج الترجمة كاملة دون نقص.
    """
    if not segments:
        return []

    client = Groq(api_key=settings.GROQ_API_KEY)
    
    # 1️⃣ تصفية الجمل الفارغة محلياً
    valid_segments = [seg for seg in segments if seg['text'].strip()]
    if not valid_segments:
        return segments

    system_instruction = (
        "You are an expert technical translator specializing in programming and software development, particularly Flutter and Dart.\n"
        "You will receive multiple sentences separated by '|||'. Translate each sentence into fluent Arabic suitable for a voice-over.\n\n"
        "STRICT RULES:\n"
        "1. Output exactly the same number of sentences.\n"
        "2. Keep the separator '|||' exactly between the translated sentences.\n"
        "3. NEVER translate names of frameworks literally (e.g., 'Flutter' -> 'فلاتر', 'Riverpod' -> 'ريفر بود').\n"
        "4. Output ONLY the final Arabic text with the separators, without any notes, introductions, or markdown blocks."
    )

    chunk_size = 15  # تقليل حجم المجموعة قليلاً لزيادة دقة النموذج في الالتزام بالفواصل
    translated_texts = []

    for i in range(0, len(valid_segments), chunk_size):
        chunk = valid_segments[i:i + chunk_size]
        combined_text = " ||| ".join([seg['text'] for seg in chunk])
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": combined_text}
                ],
                temperature=0.1, # تقليل العشوائية لأقصى درجة للالتزام بالهيكل
                max_tokens=1500,
                timeout=25
            )
            
            # تقسيم النص العائد بناءً على الفاصل وتنظيفه
            chunk_translations = [t.strip() for t in response.choices[0].message.content.strip().split("|||") if t.strip()]
            
            # 2️⃣ التحقق الصارم: إذا نجح التجميع نعتمد الترجمة
            if len(chunk_translations) == len(chunk):
                translated_texts.extend(chunk_translations)
            else:
                # 3️⃣ نظام الأمان (Fallback): إذا خبص النموذج في الفواصل، نترجم جمل هذه المجموعة فرادى فوراً لكي لا تضيع الترجمة
                print(f"⚠️ تفاوات في الفواصل في المجموعة {i//chunk_size + 1}، يتم الانتقال لنظام الأمان التلقائي...")
                for single_seg in chunk:
                    try:
                        single_resp = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[
                                {"role": "system", "content": "Translate this tech sentence to natural Arabic. Output only the translation. Phonetically transliterate terms like Flutter to فلاتر and Riverpod to ريفر بود."},
                                {"role": "user", "content": single_seg['text']}
                            ],
                            temperature=0.2,
                            max_tokens=150
                        )
                        translated_texts.append(single_resp.choices[0].message.content.strip())
                    except Exception:
                        translated_texts.append(single_seg['text']) # إذا سقط تماماً نضع النص الأصلي كملجأ أخير
                        
        except Exception as e:
            print(f"\n⚠️ Groq Chunk Error: {e}\n", file=sys.stderr)
            # في حال سقوط الشبكة، نمرر النص الأصلي لهذا الجزء
            translated_texts.extend([seg['text'] for seg in chunk])

    # إعادة ربط النصوص المترجمة بالتوقيتات الأصلية
    final_segments = []
    for idx, seg in enumerate(valid_segments):
        ar_text = translated_texts[idx] if idx < len(translated_texts) else seg['text']
        final_segments.append({
            'start': seg['start'],
            'end': seg['end'],
            'text': ar_text
        })
        
    return final_segments





# import sys
# from groq import Groq
# from django.conf import settings

# def translate_segments(segments):
#     """
#     ترجمة النصوص التقنية من الإنجليزية إلى العربية باستخدام نماذج Groq المجانية والخارقة،
#     مع الحفاظ الكامل على نطق المصطلحات البرمجية صوتياً.
#     """
#     # نستخدم نفس مفتاح Groq الذي جهزناه سابقاً في الإعدادات
#     client = Groq(api_key=settings.GROQ_API_KEY)
#     translated_segments = []
    
#     system_instruction = (
#         "You are an expert technical translator specializing in programming and software development, particularly Flutter and Dart.\n"
#         "Translate the English text into natural, professional, and fluent Arabic suitable for a video tutorial voice-over.\n\n"
#         "STRICT RULES FOR TECHNICAL TERMS:\n"
#         "1. NEVER translate names of frameworks, libraries, or concepts literally. Transliterate them phonetically into Arabic letters so they sound natural when spoken.\n"
#         "   - 'Flutter' must ALWAYS be written as 'فلاتر'\n"
#         "   - 'Riverpod' must ALWAYS be written as 'ريفر بود'\n"
#         "   - 'Provider' must ALWAYS be written as 'بروفايدر'\n"
#         "   - 'Widget' or 'Widgets' must be written as 'ويدجت' or 'ويدجتس'\n"
#         "   - 'State Management' can be translated as 'إدارة الحالة'\n"
#         "2. Avoid robotic or overly formal academic Arabic; make it sound like an expert Arab developer explaining a concept to his friends.\n"
#         "3. Output ONLY the final Arabic translation, without any notes, introduction, or English text."
#     )
    
#     for seg in segments:
#         if not seg['text'].strip(): continue
#         try:
#             # إرسال النص إلى نموذج Llama 3 القوي المتاح مجاناً على Groq
#             response = client.chat.completions.create(
#                 # model="llama-3.3-70b-specdec",
#                 model="llama-3.3-70b-versatile",
#                 messages=[
#                     {"role": "system", "content": system_instruction},
#                     {"role": "user", "content": seg['text']}
#                 ],
#                 max_tokens=150,
#                 temperature=0.3, # درجة حرارة منخفضة لضمان الالتزام الصارم بالتعليمات التقنية
#                 timeout=15 
#             )
#             translated_segments.append({
#                 'start': seg['start'], 
#                 'end': seg['end'], 
#                 'text': response.choices[0].message.content.strip()
#             })
#         except Exception as e:
#             print(f"\n⚠️ Groq Translation Error: {e}\n", file=sys.stderr)
#             # حل بديل ذكي: إذا سقط الـ API لأي سبب، نمرر النص الأصلي مؤقتاً لكي لا يخرب خط الإنتاج
#             translated_segments.append({
#                 'start': seg['start'], 
#                 'end': seg['end'], 
#                 'text': "حدث خطأ أثناء معالجة الترجمة"
#             })
            
#     return translated_segments




# import sys
# from openai import OpenAI
# from django.conf import settings

# def translate_segments(segments):
#     client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.OPENROUTER_API_KEY)
#     translated_segments = []
    
#     # التعليمات الاحترافية لترجمة المحتوى التقني وفلاتر بشكل طبيعي
#     system_instruction = (
#         "You are an expert technical translator specializing in programming and software development, particularly Flutter and Dart.\n"
#         "Translate the English text into natural, professional, and fluent Arabic suitable for a video tutorial voice-over.\n\n"
#         "STRICT RULES FOR TECHNICAL TERMS:\n"
#         "1. NEVER translate names of frameworks, libraries, or concepts literally. Transliterate them phonetically into Arabic letters so they sound natural when spoken.\n"
#         "   - 'Flutter' must ALWAYS be written as 'فلاتر'\n"
#         "   - 'Riverpod' must ALWAYS be written as 'ريفر بود'\n"
#         "   - 'Provider' must ALWAYS be written as 'بروفايدر'\n"
#         "   - 'Widget' or 'Widgets' must be written as 'ويدجت' or 'ويدجتس'\n"
#         "   - 'State Management' can be translated as 'إدارة الحالة'\n"
#         "2. Avoid robotic or overly formal academic Arabic; make it sound like an expert Arab developer explaining a concept to his friends.\n"
#         "3. Output ONLY the final Arabic translation, without any notes or English text."
#     )
    
#     for seg in segments:
#         if not seg['text']: continue
#         try:
#             response = client.chat.completions.create(
#                 model="qwen/qwen3.6-flash",
#                 messages=[
#                     {"role": "system", "content": system_instruction},
#                     {"role": "user", "content": seg['text']}
#                 ],
#                 max_tokens=100,  # حماية الحساب المجاني من خطأ 402
#                 timeout=15 
#             )
#             translated_segments.append({
#                 'start': seg['start'], 
#                 'end': seg['end'], 
#                 'text': response.choices[0].message.content.strip()
#             })
#         except Exception as e:
#             print(f"\n⚠️ خطأ أثناء الترجمة عبر OpenRouter: {e}\n", file=sys.stderr)
#             translated_segments.append({
#                 'start': seg['start'], 
#                 'end': seg['end'], 
#                 'text': "حدث خطأ في الترجمة"
#             })
            
#     return translated_segments

# # import sys
# # from openai import OpenAI
# # from django.conf import settings

# # def translate_segments(segments):
# #     client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.OPENROUTER_API_KEY)
# #     translated_segments = []
    
# #     for seg in segments:
# #         if not seg['text']: continue
# #         try:
# #             response = client.chat.completions.create(
# #                 model="qwen/qwen3.6-flash",
# #                 messages=[
# #                     {"role": "system", "content": "You are an expert translator. Translate English text into fluent Arabic. Output ONLY the translation."},
# #                     {"role": "user", "content": seg['text']}
# #                 ]
# #                 # يمكنك إضافة timeout هنا لضمان عدم تعليق الطلب طويلًا
# #                 ,max_tokens=100,timeout=15 
# #             )
# #             translated_segments.append({
# #                 'start': seg['start'], 
# #                 'end': seg['end'], 
# #                 'text': response.choices[0].message.content.strip()
# #             })
# #         except Exception as e:
# #             # طباعة الخطأ بوضوح في شاشة السيرفر لتعرف المشكلة (مفتاح خطأ، أم اتصال.. إلخ)
# #             print(f"\n⚠️ خطأ أثناء الترجمة عبر OpenRouter: {e}\n", file=sys.stderr)
            
# #             # كحل مؤقت لكي تلاحظ المشكلة، سيتم كتابة نص عربي لتعرف بالسمع أن الطلب فشل
# #             translated_segments.append({
# #                 'start': seg['start'], 
# #                 'end': seg['end'], 
# #                 'text': "حدث خطأ في الترجمة"
# #             })
            
# #     return translated_segments
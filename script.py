import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية للنسخة الثانية ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')

DB_FILE = "last_news_id.txt"
SOURCE_CHANNEL = 'CastleInfoiq'  # القناة المستهدفة بالمراقبة

def is_work_time():
    """فحص وقت العمل بتوقيت العراق (UTC+3) من 9 صباحاً إلى 11 مساءً"""
    # توقيت جرينتش الحالي + 3 ساعات لتوقيت العراق
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def clean_news_text(text):
    """تنظيف المنشور وحذف التوقيع والروابط نهائياً لفيسبوك نظيف"""
    if not text:
        return ""
    
    # 1. حذف التوقيع الصريح (تم إصلاح الـ Regex هنا بوضع \- لحل مشكلة bad character range)
    text = re.sub(r'اشتـ*رك الآن\s*[:\-\s]*', '', text)
    
    # 2. حذف روابط التليجرام أو أي روابط أخرى لضمان عدم خروج المتابع من الفيسبوك
    text = re.sub(r'http\S+|t\.me\/\S+|@\S+', '', text)
    
    # 3. تنظيف الأسطر الفارغة المتكررة الناتجة عن حذف التوقيع
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    
    return text.strip()

def post_to_facebook(message, photo_path=None):
    """نشر النصوص والصور بالطريقة الآمنة (تحميل، رفع كملف، تدمير ذاتي)"""
    try:
        if photo_path and os.path.exists(photo_path):
            # إذا كان المنشور يحتوي على صورة (يتم رفعها كملف حقيقي)
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            payload = {'caption': message, 'access_token': FB_PAGE_TOKEN}
            with open(photo_path, 'rb') as img_file:
                files = {'source': img_file}
                r = requests.post(url, data=payload, files=files, timeout=25)
        else:
            # إذا كان المنشور نصي فقط
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
            payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
            r = requests.post(url, data=payload, timeout=15)
            
        if r.status_code == 200:
            print("✅ Facebook: تم النشر بنجاح")
            return True
        else:
            print(f"❌ Facebook Error: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ FB Connection Error: {e}")
        return False

def main():
    # 1. فحص وقت العمل أولاً قبل أي إجراء
    if not is_work_time():
        print("🌙 خارج وقت العمل المحدد (9 صباحاً - 11 مساءً بتوقيت العراق). تم إيقاف الدورة لحفظ الجهد.")
        return

    # إنشاء ملف التاريخ إذا لم يكن موجوداً
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    try:
        # سحب البيانات من صفحة القناة
        res = requests.get(f"https://t.me/s/{SOURCE_CHANNEL}", timeout=15)
        items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*>(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
        
        for item in reversed(items[-5:]):
            # تخطي الفيديوهات لعدم حدوث مشاكل في مساحة السيرفر
            if 'tgme_widget_message_video' in item:
                continue
            
            # 1. استخراج النص الأصلي للمنشور
            msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
            raw_text = ""
            if msg_match:
                raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip()
            
            # 2. استخراج رابط الصورة إن وجد
            photo_match = re.search(r'background-image:\s*url\(\s*[\'"]?(.*?)[\'"]?\s*\)', item)
            photo_url = photo_match.group(1) if photo_match else None
            
            # تخطي المواد الفارغة تماماً
            if not raw_text and not photo_url:
                continue
            
            # تحديد البصمة لمنع التكرار
            sig = raw_text[:80] if raw_text else (photo_url[-80:] if photo_url else "")
            if not sig or sig in history:
                continue
            
            # تنظيف النص من التواقيع والروابط الخارجية
            clean_text = clean_news_text(raw_text)
            
            # 3. معالجة وتحميل الصورة مؤقتاً داخل الحاوية
            local_photo_path = None
            if photo_url:
                try:
                    img_res = requests.get(photo_url, timeout=12)
                    if img_res.status_code == 200:
                        local_photo_path = "temp_castle_img.jpg"
                        with open(local_photo_path, "wb") as img_f:
                            img_f.write(img_res.content)
                        print("📸 تم سحب الصورة مؤقتاً وجاهزة للرفع...")
                except Exception as img_err:
                    print(f"⚠️ فشل في تحميل الصورة مؤقتاً: {img_err}")
            
            # 4. النشر الفعلي على صفحة الفيسبوك
            print(f"🚀 جاري نقل المنشور من @{SOURCE_CHANNEL} إلى الفيسبوك...")
            success = post_to_facebook(clean_text, local_photo_path)
            
            # 5. التدمير الذاتي للملف فوراً بعد محاولة النشر للحفاظ على مساحة السيرفر صفر دائماً
            if local_photo_path and os.path.exists(local_photo_path):
                os.remove(local_photo_path)
                print("🗑️ تم حذف الصورة المؤقتة بنجاح (استهلاك المساحة الحالية: 0)")
            
            if success:
                # تسجيل المنشور في التاريخ لعدم تكراره
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(sig + "\n")
                history.append(sig)
                
                time.sleep(10)
                break
                
    except Exception as e:
        print(f"⚠️ خطأ عام أثناء تشغيل الدورة: {e}")

if __name__ == "__main__":
    main()

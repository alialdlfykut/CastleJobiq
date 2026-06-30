import os
import re
import requests
import time

# --- الإعدادات الأساسية ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_TOKEN = os.getenv('FB_TOKEN')
DB_FILE = "job_history.txt"
SOURCE_CHANNEL = 'CastleJobiq'

def clean_news_text(text):
    if not text: return ""
    # تنظيف النص من روابط التوقيع
    text = re.sub(r'📍\s*للمزيد\s*اشترك\s*معنا:\s*\n?https://t\.me/CastleJobiq', '', text)
    return text.strip()

def post_comment(post_id, comment_text):
    """دالة لنشر تعليق على منشور محدد"""
    try:
        url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
        payload = {'message': comment_text, 'access_token': FB_TOKEN}
        r = requests.post(url, data=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"⚠️ خطأ في التعليق: {e}")
        return False

def post_to_facebook(message, full_message, image_url=None):
    """نشر المنشور الأساسي والحصول على الـ ID الخاص به للتعليق"""
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos" if image_url else f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {'caption' if image_url else 'message': message, 'access_token': FB_TOKEN}
        
        if image_url:
            img_data = requests.get(image_url).content
            with open('temp_job_img.jpg', 'wb') as handler: handler.write(img_data)
            files = {'source': open('temp_job_img.jpg', 'rb')}
            r = requests.post(url, data=payload, files=files, timeout=25)
        else:
            r = requests.post(url, data=payload, timeout=15)
            
        if r.status_code == 200:
            post_id = r.json().get('id') or r.json().get('post_id')
            # بعد نجاح النشر، نقوم بنشر التعليق الكامل
            if post_id:
                time.sleep(2) # انتظار بسيط قبل التعليق
                post_comment(post_id, full_message)
            return True
        return False
    except Exception as e:
        print(f"⚠️ خطأ في النشر: {e}")
        return False

def main():
    if not os.path.exists(DB_FILE): open(DB_FILE, 'w').close()
    with open(DB_FILE, 'r', encoding='utf-8') as f: history = f.read().splitlines()

    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(f"https://t.me/s/{SOURCE_CHANNEL}", headers=headers, timeout=15)
    
    items = re.findall(r'data-post="[^"\/]+/(\d+)"(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
    
    for msg_id, item in reversed(items[-5:]):
        if msg_id.strip() in history: continue
        
        msg_match = re.search(r'class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
        raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip() if msg_match else ""
        full_text = clean_news_text(raw_text)
        
        # استخراج أول سطرين فقط
        lines = [line for line in full_text.split('\n') if line.strip()]
        short_text = "\n".join(lines[:2]) + "\n\n.... عرض المزيد" if len(lines) > 2 else full_text
        
        img_match = re.search(r'background-image:url\(\'([^\']+)\'\)', item)
        img_url = None
        if img_match:
            temp_url = img_match.group(1)
            if 'telegram.org/img/emoji/' not in temp_url:
                img_url = 'https:' + temp_url if temp_url.startswith('//') else temp_url
        
        if post_to_facebook(short_text, full_text, img_url):
            print(f"✅ تم نشر المنشور {msg_id} مع التعليق")
            with open(DB_FILE, 'a', encoding='utf-8') as f: f.write(msg_id + "\n")
            time.sleep(5)

if __name__ == "__main__":
    main()

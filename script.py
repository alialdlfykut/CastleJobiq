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
    text = re.sub(r'📍\s*للمزيد\s*اشترك\s*معنا:\s*\n?https://t\.me/CastleJobiq', '', text)
    return text.strip()

def post_to_facebook(message, image_url=None):
    try:
        if image_url:
            img_data = requests.get(image_url).content
            with open('temp_job_img.jpg', 'wb') as handler: handler.write(img_data)
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            files = {'source': open('temp_job_img.jpg', 'rb')}
            payload = {'caption': message, 'access_token': FB_TOKEN}
            r = requests.post(url, data=payload, files=files, timeout=25)
        else:
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
            payload = {'message': message, 'access_token': FB_TOKEN}
            r = requests.post(url, data=payload, timeout=15)
            
        if r.status_code == 200:
            return True
        else:
            print(f"⚠️ خطأ في فيسبوك: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بفيسبوك: {e}")
        return False

def main():
    if not os.path.exists(DB_FILE): 
        open(DB_FILE, 'w').close()
        print("📁 تم إنشاء ملف السجل.")
        
    with open(DB_FILE, 'r', encoding='utf-8') as f: 
        history = f.read().splitlines()

    print(f"🔍 جاري فحص القناة: {SOURCE_CHANNEL}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(f"https://t.me/s/{SOURCE_CHANNEL}", headers=headers, timeout=15)
    except Exception as e:
        print(f"❌ فشل الاتصال بالتليجرام: {e}")
        return

    # التعديل هنا: استخدام regex أكثر مرونة لالتقاط المنشورات
    items = re.findall(r'data-post="[^"\/]+/(\d+)"(.*?)class="tgme_widget_message_text', res.text, re.DOTALL)
    
    if not items:
        print("⚠️ لم يتم العثور على أي منشورات. قد يكون هناك تحديث في هيكل القناة.")
        return

    print(f"✅ تم العثور على {len(items)} منشور. جاري الفحص...")
    
    new_posts_found = False
    for msg_id, item in reversed(items[-10:]): # فحص آخر 10 منشورات
        if msg_id.strip() in history: 
            continue
        
        new_posts_found = True
        print(f"🆕 منشور جديد تم العثور عليه: {msg_id}")
        
        # استخراج النص
        msg_match = re.search(r'>(.*?)</div>', item, re.DOTALL)
        raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip() if msg_match else ""
        clean_text = clean_news_text(raw_text)
        
        # استخراج الصورة
        img_match = re.search(r'background-image:url\(\'([^\']+)\'\)', item)
        img_url = None
        if img_match:
            temp_url = img_match.group(1)
            if 'telegram.org/img/emoji/' not in temp_url:
                img_url = 'https:' + temp_url if temp_url.startswith('//') else temp_url
        
        if post_to_facebook(clean_text, img_url):
            print(f"✅ تم نشر المنشور {msg_id}")
            with open(DB_FILE, 'a', encoding='utf-8') as f: f.write(msg_id + "\n")
            time.sleep(5)
        else:
            print(f"❌ فشل نشر المنشور {msg_id}")

    if not new_posts_found:
        print("ℹ️ لا توجد منشورات جديدة للنشر.")

if __name__ == "__main__":
    main()

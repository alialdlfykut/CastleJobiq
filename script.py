import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_TOKEN = os.getenv('FB_TOKEN')
LINKEDIN_TOKEN = os.getenv('LINKEDIN_TOKEN') # أضف هذا في GitHub Secrets
DB_FILE = "job_history.txt"
SOURCE_CHANNEL = 'CastleJobiq'

def clean_news_text(text):
    if not text: return ""
    text = re.sub(r'📍\s*للمزيد\s*اشترك\s*معنا:\s*\n?https://t\.me/CastleJobiq', '', text)
    return text.strip()

# --- دالة النشر على فيسبوك ---
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
        return r.status_code == 200
    except Exception as e:
        print(f"⚠️ خطأ في فيسبوك: {e}")
        return False

# --- دالة النشر على لينكد إن ---
def post_to_linkedin(message):
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        # جلب URN الخاص بك
        user_data = requests.get("https://api.linkedin.com/v2/me", headers=headers).json()
        user_urn = user_data["id"]
        
        payload = {
            "author": f"urn:li:person:{user_urn}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": message},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        r = requests.post("https://api.linkedin.com/v2/ugcPosts", headers=headers, json=payload)
        return r.status_code == 201
    except Exception as e:
        print(f"⚠️ خطأ في لينكد إن: {e}")
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
        clean_text = clean_news_text(raw_text)
        
        img_match = re.search(r'background-image:url\(\'([^\']+)\'\)', item)
        img_url = 'https:' + img_match.group(1) if img_match and 'telegram.org/img/emoji/' not in img_match.group(1) else None
        
        # التنفيذ المتوازي
        fb_success = post_to_facebook(clean_text, img_url)
        li_success = post_to_linkedin(clean_text)
        
        if fb_success or li_success:
            print(f"✅ تم معالجة المنشور {msg_id} (FB: {fb_success}, LI: {li_success})")
            with open(DB_FILE, 'a', encoding='utf-8') as f: f.write(msg_id + "\n")
            time.sleep(5)

if __name__ == "__main__":
    main()

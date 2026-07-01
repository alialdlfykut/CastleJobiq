import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_TOKEN = os.getenv('FB_TOKEN')
LINKEDIN_TOKEN = os.getenv('LINKEDIN_TOKEN')
LINKEDIN_URN = os.getenv('LINKEDIN_URN')  # اختياري: إذا مو موجود، نجيبه تلقائياً من /v2/userinfo
DB_FILE = "job_history.txt"
SOURCE_CHANNEL = 'CastleJobiq'


def clean_news_text(text):
    if not text:
        return ""
    text = re.sub(r'📍\s*للمزيد\s*اشترك\s*معنا:\s*\n?https://t\.me/CastleJobiq', '', text)
    return text.strip()


def check_env_vars():
    """فحص أولي للمتغيرات المطلوبة حتى ما يفشل السكربت بمنتصف التنفيذ بصمت"""
    missing = []
    if not FB_PAGE_ID: missing.append('FB_PAGE_ID')
    if not FB_TOKEN: missing.append('FB_TOKEN')
    if missing:
        print(f"🚨 متغيرات بيئة ناقصة: {', '.join(missing)} — تأكد من GitHub Secrets.")
        return False
    if not LINKEDIN_TOKEN:
        print("ℹ️ LINKEDIN_TOKEN غير موجود — بيتم تخطي النشر على لينكدإن (فيسبوك بس راح يشتغل).")
    return True


# --- دالة النشر على فيسبوك ---
def post_to_facebook(message, image_url=None):
    temp_path = 'temp_job_img.jpg'
    try:
        if image_url:
            img_res = requests.get(image_url, timeout=15)
            if img_res.status_code != 200:
                print(f"⚠️ فشل تحميل الصورة من {image_url} — status: {img_res.status_code}")
                image_url = None  # نكمل بدون صورة بدل ما نفشل كلياً
            else:
                with open(temp_path, 'wb') as handler:
                    handler.write(img_res.content)

        if image_url:
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            with open(temp_path, 'rb') as img_file:
                files = {'source': img_file}
                payload = {'caption': message, 'access_token': FB_TOKEN}
                r = requests.post(url, data=payload, files=files, timeout=25)
        else:
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
            payload = {'message': message, 'access_token': FB_TOKEN}
            r = requests.post(url, data=payload, timeout=15)

        if r.status_code == 200:
            print(f"✅ فيسبوك: نُشر بنجاح — post id: {r.json().get('id') or r.json().get('post_id')}")
            return True
        else:
            # هذا أهم سطر بكل الملف — يطلعلك السبب الحقيقي من فيسبوك نفسه
            print(f"❌ فيسبوك رفض النشر — status: {r.status_code} — الرد: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ استثناء أثناء النشر على فيسبوك: {e}")
        return False
    finally:
        # نحذف الصورة المؤقتة بكل الحالات (نجاح أو فشل) حتى ما تتراكم على مساحة الـ runner
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_err:
                print(f"⚠️ ماكدرت أحذف الصورة المؤقتة: {cleanup_err}")


# --- دوال النشر على لينكدإن (Posts API الجديد + OpenID userinfo) ---
def get_linkedin_urn(headers):
    """/v2/me صارت مقيدة الصلاحيات؛ /v2/userinfo هو البديل الحديث (OpenID Connect)"""
    try:
        r = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers, timeout=15)
        if r.status_code == 200:
            sub = r.json().get("sub")
            print(f"ℹ️ تم جلب LinkedIn URN تلقائياً: {sub}")
            return sub
        else:
            print(f"❌ فشل جلب /v2/userinfo — status: {r.status_code} — الرد: {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ استثناء أثناء جلب LinkedIn userinfo: {e}")
        return None


def post_to_linkedin(message):
    try:
        headers = {
            "Authorization": f"Bearer {LINKEDIN_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202405",
        }

        urn = LINKEDIN_URN or get_linkedin_urn(headers)
        if not urn:
            print("🚨 ماكدر أجيب LinkedIn URN — تأكد إن التوكن عنده صلاحية openid/profile، أو خزن LINKEDIN_URN يدوياً بالـ Secrets.")
            return False

        # Posts API الجديد (/rest/posts) بدل ugcPosts القديم المهجور
        payload = {
            "author": f"urn:li:person:{urn}",
            "commentary": message,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False
        }
        r = requests.post("https://api.linkedin.com/rest/posts", headers=headers, json=payload, timeout=15)

        if r.status_code == 201:
            print(f"✅ لينكدإن: نُشر بنجاح — post id: {r.headers.get('x-restli-id', 'غير معروف')}")
            return True
        else:
            print(f"❌ لينكدإن رفض النشر — status: {r.status_code} — الرد: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ استثناء أثناء النشر على لينكدإن: {e}")
        return False


def main():
    if not check_env_vars():
        return

    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'w').close()
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(f"https://t.me/s/{SOURCE_CHANNEL}", headers=headers, timeout=15)

    items = re.findall(r'data-post="[^"\/]+/(\d+)"(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
    print(f"📡 تم العثور على {len(items)} منشور من @{SOURCE_CHANNEL} (قبل فلترة التكرار)")

    if not items:
        print("🚨 ماكو منشورات انكشفت من صفحة تليجرام! غالباً بنية الـ HTML تغيرت — راجع الـ regex.")
        return

    for msg_id, item in reversed(items[-5:]):
        if msg_id.strip() in history:
            continue

        msg_match = re.search(r'class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
        raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip() if msg_match else ""
        clean_text = clean_news_text(raw_text)

        if not clean_text:
            print(f"⚠️ المنشور {msg_id} ماله نص واضح — تخطي.")
            continue

        img_match = re.search(r"background-image:url\('([^']+)'\)", item)
        img_url = 'https:' + img_match.group(1) if img_match and 'telegram.org/img/emoji/' not in img_match.group(1) else None

        print(f"🔄 معالجة المنشور {msg_id}...")
        fb_success = post_to_facebook(clean_text, img_url)
        li_success = post_to_linkedin(clean_text) if LINKEDIN_TOKEN else False

        if fb_success or li_success:
            print(f"📌 تم معالجة المنشور {msg_id} (FB: {fb_success}, LI: {li_success})")
            with open(DB_FILE, 'a', encoding='utf-8') as f:
                f.write(msg_id + "\n")
            time.sleep(5)
        else:
            print(f"⏭️ فشل النشر بكلا المنصتين للمنشور {msg_id} — بيبقى بالسجل عشان يعاد المحاولة بالتشغيلة الجاية.")


if __name__ == "__main__":
    main()

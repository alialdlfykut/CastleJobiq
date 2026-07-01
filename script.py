import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_TOKEN = os.getenv('FB_TOKEN')
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
                print(f"🗑️ تم حذف الصورة المؤقتة ({temp_path}) بعد الاستخدام.")
            except Exception as cleanup_err:
                print(f"⚠️ ماكدرت أحذف الصورة المؤقتة: {cleanup_err}")


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

    skipped_count = 0
    for msg_id, item in reversed(items[-5:]):
        if msg_id.strip() in history:
            skipped_count += 1
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

        if fb_success:
            print(f"📌 تم نشر المنشور {msg_id} على فيسبوك بنجاح")
            with open(DB_FILE, 'a', encoding='utf-8') as f:
                f.write(msg_id + "\n")
            time.sleep(5)
        else:
            print(f"⏭️ فشل النشر على فيسبوك للمنشور {msg_id} — بيبقى بالسجل عشان يعاد المحاولة بالتشغيلة الجاية.")

    if skipped_count == len(items[-5:]):
        print(f"ℹ️ آخر {skipped_count} منشور موجودين مسبقاً بـ {DB_FILE} — ماكو شي جديد للنشر بهاي التشغيلة.")


if __name__ == "__main__":
    main()

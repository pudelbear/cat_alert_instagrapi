from instagrapi import Client
from datetime import datetime, timedelta
import os, glob, shutil, time

# -------------------------------
# 🔧 Einstellungen
# -------------------------------
CAPTURE_DIR = "captures"
POSTED_DIR = "posted"
MAX_IMAGES = 10  # Instagram erlaubt maximal 10 pro Album

# Login-Daten (oder via ENV)
USERNAME = os.getenv("INSTAGRAM_USER", "")
PASSWORD = os.getenv("INSTAGRAM_PASS", "")

# -------------------------------
# 🔐 Instagram-Login
# -------------------------------
cl = Client()
try:
    cl.login(USERNAME, PASSWORD)
    print("✅ Erfolgreich bei Instagram eingeloggt.")
except Exception as e:
    print(f"❌ Login fehlgeschlagen: {e}")
    exit(1)

# -------------------------------
# 📸 Bilder der letzten 12h finden
# -------------------------------
def get_images_last_12h():
    cutoff = datetime.now() - timedelta(hours=12)
    images = []
    for path in sorted(glob.glob(os.path.join(CAPTURE_DIR, "*.jpg"))):
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if mtime > cutoff:
            images.append(path)

    if not images:
        return []

    if len(images) > MAX_IMAGES:
        print(f"⚠️ {len(images)} Bilder gefunden, nur die neuesten {MAX_IMAGES} werden gepostet.")
        images = images[-MAX_IMAGES:]

    return images

# -------------------------------
# 📤 Diashow posten
# -------------------------------
def post_slideshow(images):
    if not images:
        print("Keine neuen Bilder in den letzten 12 Stunden.")
        return

    caption = f"🐾 Katzenalarm der letzten 12 Stunden ({datetime.now():%d.%m.%Y %H:%M})"

    try:
        print(f"📤 Starte Upload von {len(images)} Bildern ...")
        cl.album_upload(images, caption)
        print(f"✅ Erfolgreich gepostet: {len(images)} Bilder.")

        # Nach dem Posten: Bilder verschieben
        for img in images:
            shutil.move(img, os.path.join(POSTED_DIR, os.path.basename(img)))
        print("📦 Bilder verschoben nach 'posted/'.")
    except Exception as e:
        print(f"❌ Fehler beim Posten: {e}")
        print("⏳ Versuche erneut in 2 Minuten ...")
        time.sleep(120)
        try:
            cl.album_upload(images, caption)
            print("✅ Zweiter Versuch erfolgreich.")
            for img in images:
                shutil.move(img, os.path.join(POSTED_DIR, os.path.basename(img)))
        except Exception as e2:
            print(f"🚫 Zweiter Versuch fehlgeschlagen: {e2}")

# -------------------------------
# 🕒 Hauptprogramm
# -------------------------------
if __name__ == "__main__":
    images = get_images_last_12h()
    post_slideshow(images)

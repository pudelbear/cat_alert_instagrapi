import cv2
import threading
import time
import os
import traceback
from datetime import datetime
from ultralytics import YOLO

# -------------------------------
# 🔧 Einstellungen
# -------------------------------
RTSP_URL1 = os.getenv("RTSP_URL1", "")
RTSP_URL2 = os.getenv("RTSP_URL2", "")
CAPTURE_DIR = "/app/captures"
MODEL_PATH = "/root/.cache/torch/hub/checkpoints/yolov8n.pt"
FRAME_INTERVAL = 10       # alle 10 Sekunden ein Frame prüfen
TARGET_SIZE = 1080        # Instagram-Quadratgröße
RECONNECT_DELAY = 5       # Sekunden warten vor Reconnect
PING_INTERVAL = 60        # alle 60 s Statusmeldung

os.makedirs(CAPTURE_DIR, exist_ok=True)

# -------------------------------
# 🧠 YOLOv8-Modell laden
# -------------------------------
print("📦 Lade YOLOv8-Modell ...")
model = YOLO(MODEL_PATH)
print("✅ YOLOv8 geladen.")

# -------------------------------
# 🆕 Kamera-Leser-Klasse (nicht-blockierend)
# -------------------------------
class CameraStream:
    """Liest RTSP-Frames in eigenem Thread und hält das letzte gültige Bild bereit."""
    def __init__(self, url, name):
        self.url = url
        self.name = name
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def open(self):
        rtsp_tcp = (
            f"{self.url}&rtsp_transport=tcp" if "?" in self.url else f"{self.url}?rtsp_transport=tcp"
        )
        cap = cv2.VideoCapture(rtsp_tcp, cv2.CAP_FFMPEG)
        if cap.isOpened():
            print(f"✅ Kamera verbunden: {self.name}")
        else:
            print(f"⚠️ Fehler beim Öffnen von {self.name}, neuer Versuch in {RECONNECT_DELAY}s ...")
        return cap

    def update(self):
        """Liest Frames kontinuierlich. Kein Abbruch bei Fehlern."""
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                self.cap = self.open()
                time.sleep(RECONNECT_DELAY)
                continue

            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.frame = frame
            else:
                # kein Frame erhalten, kurz warten statt reconnecten
                time.sleep(0.5)

    def read(self):
        """Gibt das letzte bekannte Frame zurück (oder None)."""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

# -------------------------------
# 🖼️ Katze zuschneiden (1080x1080)
# -------------------------------
def crop_to_cat(frame, boxes):
    h, w, _ = frame.shape
    for box in boxes:
        cls_id = int(box.cls[0].item())
        label = model.names.get(cls_id, "")
        if label == "cat":
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            crop_size = min(w, h, max(x2 - x1, y2 - y1) * 2)
            x1c = max(0, cx - crop_size // 2)
            y1c = max(0, cy - crop_size // 2)
            x2c = min(w, x1c + crop_size)
            y2c = min(h, y1c + crop_size)
            cropped = frame[y1c:y2c, x1c:x2c]
            return cv2.resize(cropped, (TARGET_SIZE, TARGET_SIZE), interpolation=cv2.INTER_AREA)
    return cv2.resize(frame, (TARGET_SIZE, TARGET_SIZE), interpolation=cv2.INTER_AREA)

# -------------------------------
# 📸 YOLO-Verarbeitung (nutzt CameraStream)
# -------------------------------
def process_camera(stream: CameraStream):
    print(f"🔗 Starte Analyse für {stream.name}")
    last_ping = time.time()

    while True:
        try:
            frame = stream.read()
            if frame is None:
                # Kein Frame -> einfach warten, nicht reconnecten
                time.sleep(1)
                continue

            results = model.predict(frame, imgsz=640, verbose=False)
            for r in results:
                boxes = [b for b in r.boxes if model.names[int(b.cls[0].item())] == "cat"]
                if boxes:
                    cropped = crop_to_cat(frame, boxes)
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"{stream.name}_cat_{timestamp}.jpg"
                    filepath = os.path.join(CAPTURE_DIR, filename)
                    cv2.imwrite(filepath, cropped)
                    print(f"📸 Katze erkannt ({stream.name}) → {filename}")
                    time.sleep(5)
                    break

            if time.time() - last_ping > PING_INTERVAL:
                print(f"✅ Kamera {stream.name} aktiv ({datetime.now():%H:%M:%S})")
                last_ping = time.time()

            time.sleep(FRAME_INTERVAL)

        except Exception as e:
            print(f"💥 Fehler in {stream.name}: {e}")
            traceback.print_exc()
            time.sleep(RECONNECT_DELAY)

# -------------------------------
# 🚀 Hauptprogramm
# -------------------------------
if __name__ == "__main__":
    print("🐾 Starte 24/7 Katzenüberwachung (robuster Stream-Modus)")

    streams = []
    if RTSP_URL1:
        streams.append(CameraStream(RTSP_URL1, "cam1"))
    if RTSP_URL2:
        streams.append(CameraStream(RTSP_URL2, "cam2"))

    if not streams:
        print("❌ Keine RTSP-URLs angegeben! Bitte RTSP_URL1/2 in docker-compose setzen.")
        exit(1)

    # Starte je einen Analyse-Thread pro Kamera
    for s in streams:
        t = threading.Thread(target=process_camera, args=(s,), daemon=True)
        t.start()

    # Hauptprozess aktiv halten
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("🛑 Beende alle Streams ...")
        for s in streams:
            s.stop()

import cv2
import win32gui
import win32con
import win32api
import numpy as np
import time
import os
import pickle
from insightface.app import FaceAnalysis

# ─────────────────────────────────────────────
#  CONFIGURAZIONE ULTRA-SENSITIVE
# ─────────────────────────────────────────────
SOGLIA_ALLARME        = 5        # Scatta dopo circa 0.2 secondi di errore
DURATA_SCHERMO_NERO   = 3.0
SOGLIA_BOCCIATO_S     = 20.0
EXIT_PIN              = "2026"
TEMPO_LIMITE_PIN      = 5.0      # Finestra di 5 secondi per il PIN
WINDOW_NAME           = "SISTEMA_ANTIPLAGIO"
ENCODING_FILE         = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_profile_v48.pkl")

try:
    _app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
    _app.prepare(ctx_id=0, det_size=(640, 640))
except Exception as e:
    print(f"Errore: {e}"); exit(1)

cap = cv2.VideoCapture(0)
screen_w = win32api.GetSystemMetrics(0)
screen_h = win32api.GetSystemMetrics(1)
cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
hwnd_main = win32gui.FindWindow(None, WINDOW_NAME)

def mostra_f():
    win32gui.ShowWindow(hwnd_main, win32con.SW_SHOW)
    win32gui.SetWindowPos(hwnd_main, win32con.HWND_TOPMOST, 0,0, screen_w, screen_h, win32con.SWP_SHOWWINDOW)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

def nascondi_f(): win32gui.ShowWindow(hwnd_main, win32con.SW_HIDE)

# ─────────────────────────────────────────────
#  LOGICA PIN TEMPORIZZATA (PROGRAMMA ATTIVO)
# ─────────────────────────────────────────────
def prova_uscita_temporizzata():
    win_pin = "SBLOCCO RAPIDO"
    cv2.namedWindow(win_pin, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_pin, 400, 200)
    hwnd_pin = win32gui.FindWindow(None, win_pin)
    win32gui.SetWindowPos(hwnd_pin, win32con.HWND_TOPMOST, screen_w//2-200, screen_h//2-100, 400, 200, win32con.SWP_SHOWWINDOW)
    win32gui.SetForegroundWindow(hwnd_pin)
    
    t_inizio = time.time()
    input_pin = ""
    
    while (time.time() - t_inizio) < TEMPO_LIMITE_PIN:
        tempo_rimasto = max(0, TEMPO_LIMITE_PIN - (time.time() - t_inizio))
        img = np.full((200, 400, 3), (15, 15, 15), dtype=np.uint8)
        
        # Barra del tempo residuo
        w_barra = int((tempo_rimasto / TEMPO_LIMITE_PIN) * 400)
        cv2.rectangle(img, (0, 0), (w_barra, 5), (0, 255, 255), -1)
        
        cv2.putText(img, "INSERISCI PIN:", (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        cv2.putText(img, "*" * len(input_pin), (30, 140), cv2.FONT_HERSHEY_TRIPLEX, 1.5, (0,255,0), 3)
        
        cv2.imshow(win_pin, img)
        k = cv2.waitKey(1) & 0xFF
        if k == 13 and input_pin == EXIT_PIN:
            cap.release(); cv2.destroyAllWindows(); exit(0)
        elif k in (8, 127): input_pin = input_pin[:-1]
        elif chr(k).isdigit() and len(input_pin) < 4: input_pin += chr(k)
        if k == 27: break
        
    cv2.destroyWindow(win_pin)

# ─────────────────────────────────────────────
#  ANALISI LOGICA (ESTREMA)
# ─────────────────────────────────────────────
def analizza_situazione(frame, profile):
    faces = _app.get(frame)
    if not faces: return "NESSUN_VOLTO", None

    f = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0]) * (x.bbox[3]-x.bbox[1]))
    bbox = f.bbox # [x1, y1, x2, y2]
    
    # Rapporto Altezza/Larghezza Volto (Misura la mascella cadente)
    ratio_facciale = (bbox[3] - bbox[1]) / (bbox[2] - bbox[0])

    # 1. Identità
    emb = f.embedding / np.linalg.norm(f.embedding)
    is_owner = np.dot(emb, profile['emb']) >= 0.50 # Molto severo

    # 2. Posa (Limiti rigidissimi: 20 gradi di tolleranza)
    testa_ok = True
    if f.pose is not None:
        p, y, r = f.pose
        if abs(y) > 22 or abs(p) > 18: testa_ok = False 

    # 3. Bocca (Confronto con Enrollment a riposo)
    # Se il volto è più lungo del 5% rispetto alla calibrazione, la bocca è aperta
    soglia_allungamento = profile['ratio_riposo'] * 1.05 
    bocca_aperta = ratio_facciale > soglia_allungamento

    return {
        "ok": is_owner and testa_ok and not bocca_aperta,
        "motivo": "ID ERRATO" if not is_owner else ("MOVIMENTO TESTA" if not testa_ok else "BOCCA APERTA")
    }, f

# ─────────────────────────────────────────────
#  ENROLLMENT (FRONTALE PERFETTO)
# ─────────────────────────────────────────────
def enrollment():
    print("Avvio Enrollment...")
    while True:
        ret, frame = cap.read()
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0,0), (w, 80), (0,0,0), -1)
        cv2.putText(frame, "GUARDA FISSO - BOCCA CHIUSA - [SPAZIO]", (20, 50), 
                    cv2.FONT_HERSHEY_TRIPLEX, 0.7, (0,255,0), 2)
        cv2.imshow(WINDOW_NAME, frame); mostra_f()
        
        if cv2.waitKey(1) & 0xFF == 32:
            faces = _app.get(frame)
            if faces:
                f = faces[0]
                dati = {
                    'emb': f.embedding / np.linalg.norm(f.embedding),
                    'ratio_riposo': (f.bbox[3]-f.bbox[1]) / (f.bbox[2]-f.bbox[0])
                }
                with open(ENCODING_FILE, "wb") as file: pickle.dump(dati, file)
                return dati

# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────
profile = enrollment() if not os.path.exists(ENCODING_FILE) else pickle.load(open(ENCODING_FILE, "rb"))
contatore_errori = 0
errore_continuo_t = None
stato_bocciato = False
black_screen_fino = 0

while True:
    ret, frame = cap.read()
    if not ret: break
    adesso = time.time()

    if stato_bocciato:
        mostra_f()
        img = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
        cv2.putText(img, "BOCCIATO", (screen_w//2-300, screen_h//2), cv2.FONT_HERSHEY_TRIPLEX, 5, (0,0,255), 10)
        cv2.imshow(WINDOW_NAME, img)
        if cv2.waitKey(1) & 0xFF == 27: prova_uscita_temporizzata()
        continue

    res, _ = analizza_situazione(frame, profile)
    err_attivo = (res == "NESSUN_VOLTO" or not res["ok"])

    if err_attivo:
        contatore_errori += 1
        if errore_continuo_t is None: errore_continuo_t = adesso
        if (adesso - errore_continuo_t) >= SOGLIA_BOCCIATO_S: stato_bocciato = True
    else:
        contatore_errori = max(0, contatore_errori - 1)
        if contatore_errori == 0: errore_continuo_t = None

    if adesso < black_screen_fino:
        mostra_f()
        img = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
        cv2.putText(img, "RIPRENDI POSIZIONE", (screen_w//2-400, screen_h//2), cv2.FONT_HERSHEY_TRIPLEX, 2, (255,255,255), 4)
        cv2.imshow(WINDOW_NAME, img)
        if cv2.waitKey(1) & 0xFF == 27: prova_uscita_temporizzata()
        continue

    if contatore_errori >= SOGLIA_ALLARME:
        black_screen_fino = adesso + DURATA_SCHERMO_NERO
        contatore_errori = 0
        continue

    nascondi_f()
    if cv2.waitKey(1) & 0xFF == 27:
        prova_uscita_temporizzata()
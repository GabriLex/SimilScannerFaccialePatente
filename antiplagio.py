"""
╔══════════════════════════════════════════════════════════╗
║          SISTEMA ANTIPLAGIO  v1.3  —  Portable          ║
║     Riconoscimento facciale AI per sessioni d'esame     ║
╚══════════════════════════════════════════════════════════╝

Architettura:
  GUI (tkinter)  →  processo principale
  Worker (OpenCV + InsightFace)  →  subprocess self-relaunch
  Comunicazione  →  stdout pipe UTF-8

Uso portable: copia la cartella ovunque e avvia SistemaAntiplagio.exe
"""

import sys
import os

# ── Cartella base (funziona sia da .py che da EXE PyInstaller) ────────────
def _get_base() -> str:
    if getattr(sys, "frozen", False):
        # onefile: sys.executable è nella cartella temp _MEIxxx,
        # sys.argv[0] è il percorso del vero EXE originale
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(os.path.abspath(__file__))

def _get_bundle() -> str:
    """Cartella dei file embedded (models, ico) — dentro _MEIxxx con onefile."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS          # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))

BUNDLE = _get_bundle()

BASE        = _get_base()
PROFILES    = os.path.join(BASE, "profiles")
SETTINGS_F  = os.path.join(BASE, "settings.pkl")
WINDOW_CV   = "SISTEMA_ANTIPLAGIO"
WORKER_FLAG = "--_ap_worker"
DONE_TOKEN  = "__DONE__"

os.makedirs(PROFILES, exist_ok=True)

# ── Default settings ──────────────────────────────────────────────────────
CFG_DEFAULTS = {
    "exit_pin":            "2026",
    "soglia_allarme":      5,
    "durata_schermo_nero": 3.0,
    "soglia_bocciato_s":   20.0,
    "tempo_limite_pin":    5.0,
    "identita_threshold":  0.50,
    "yaw_max":             22.0,
    "pitch_max":           18.0,
    "bocca_sensibilita":   1.02,
}

def cfg_load() -> dict:
    import pickle
    if os.path.exists(SETTINGS_F):
        try:
            s = pickle.load(open(SETTINGS_F, "rb"))
            d = CFG_DEFAULTS.copy(); d.update(s); return d
        except Exception:
            pass
    return CFG_DEFAULTS.copy()

def cfg_save(c: dict):
    import pickle
    pickle.dump(c, open(SETTINGS_F, "wb"))

def profiles_list() -> list:
    import glob
    return sorted([
        os.path.splitext(os.path.basename(f))[0]
        for f in glob.glob(os.path.join(PROFILES, "*.pkl"))
    ])

def profile_path(name: str) -> str:
    return os.path.join(PROFILES, f"{name}.pkl")

def find_icon() -> str | None:
    # Cerca nei due posti possibili: cartella EXE reale e bundle onefile
    for folder in [BASE, BUNDLE]:
        for name in ["icon.ico"] + sorted(os.listdir(folder)):
            fp = os.path.join(folder, name)
            if os.path.isfile(fp) and name.lower().endswith(".ico"):
                return fp
    return None


# ═════════════════════════════════════════════════════════════════════════════
#  WORKER  ─  gira nel processo figlio, comunica via stdout
# ═════════════════════════════════════════════════════════════════════════════
def run_worker(mode: str, profile_name: str, cfg: dict):
    import io, time, pickle
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace")

    def emit(msg: str):
        print(msg, flush=True)

    # ── import pesanti ────────────────────────────────────────────────────
    import cv2
    import numpy as np

    try:
        import win32gui, win32con, win32api
        W32 = True
    except ImportError:
        W32 = False

    try:
        from insightface.app import FaceAnalysis
        import insightface
        # Con onefile i modelli sono nel bundle (BUNDLE/.insightface)
        # o, se già scaricati, in BASE/.insightface
        # Proviamo BASE prima (cartella dell'EXE reale, portable)
        _model_root = os.path.join(BASE, ".insightface")
        if not os.path.isdir(_model_root):
            # fallback al bundle onefile
            _model_root = os.path.join(BUNDLE, ".insightface")
        if not os.path.isdir(_model_root):
            # fallback default insightface (~/.insightface)
            _model_root = None
        if _model_root:
            insightface.utils.storage.BASE_REPO_URL  # touch module
            import insightface.utils.storage as _ifs
            _ifs.BASE_REPO_URL = _ifs.BASE_REPO_URL  # no-op, solo import
            os.environ["INSIGHTFACE_HOME"] = os.path.dirname(_model_root)
        fa = FaceAnalysis(name="buffalo_sc",
                          providers=["CPUExecutionProvider"])
        fa.prepare(ctx_id=0, det_size=(640, 640))
    except Exception as e:
        emit(f"ERRORE InsightFace: {e}"); return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        emit("ERRORE: webcam non trovata."); return

    SW = win32api.GetSystemMetrics(0) if W32 else 1920
    SH = win32api.GetSystemMetrics(1) if W32 else 1080

    # ── crea finestra e acquisisci hwnd ───────────────────────────────────
    cv2.namedWindow(WINDOW_CV, cv2.WINDOW_NORMAL)
    cv2.imshow(WINDOW_CV, np.zeros((480, 640, 3), dtype=np.uint8))
    cv2.waitKey(1)

    hwnd = None
    if W32:
        for _ in range(20):
            hwnd = win32gui.FindWindow(None, WINDOW_CV)
            if hwnd: break
            time.sleep(0.05)

    def fullscreen():
        if W32 and hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST,
                                  0, 0, SW, SH, win32con.SWP_SHOWWINDOW)
            cv2.setWindowProperty(WINDOW_CV, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN)

    def hide():
        if W32 and hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

    def set_cv_icon(target_hwnd):
        """Imposta l'icona .ico su una finestra Win32 (OpenCV)."""
        if not (W32 and target_hwnd):
            return
        ico = find_icon()
        if not ico:
            return
        try:
            import ctypes
            LR_LOADFROMFILE = 0x10
            LR_DEFAULTSIZE  = 0x40
            IMAGE_ICON      = 1
            WM_SETICON      = 0x0080
            ICON_SMALL      = 0
            ICON_BIG        = 1
            hicon = ctypes.windll.user32.LoadImageW(
                None, ico, IMAGE_ICON, 0, 0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if hicon:
                ctypes.windll.user32.SendMessageW(
                    target_hwnd, WM_SETICON, ICON_SMALL, hicon)
                ctypes.windll.user32.SendMessageW(
                    target_hwnd, WM_SETICON, ICON_BIG,   hicon)
        except Exception:
            pass

    # Applica icona alla finestra principale OpenCV
    set_cv_icon(hwnd)

    # ─────────────────────────────────────────────────────────────────────
    #  ENROLLMENT
    # ─────────────────────────────────────────────────────────────────────
    if mode == "enrollment":
        emit(f"Enrollment '{profile_name}' | SPAZIO=salva  ESC=annulla")
        while True:
            ret, frm = cap.read()
            if not ret: continue
            frm = cv2.flip(frm, 1)
            h, w = frm.shape[:2]

            faces = fa.get(frm)
            ok = bool(faces)
            for f in faces:
                x1,y1,x2,y2 = [int(v) for v in f.bbox]
                cv2.rectangle(frm,(x1,y1),(x2,y2),(0,220,0),2)

            # overlay
            overlay = frm.copy()
            cv2.rectangle(overlay,(0,0),(w,90),(0,0,0),-1)
            cv2.addWeighted(overlay,0.65,frm,0.35,0,frm)
            cv2.putText(frm, f"ENROLLMENT: {profile_name}",
                        (14,34), cv2.FONT_HERSHEY_DUPLEX, 0.8,
                        (255,255,255), 1, cv2.LINE_AA)
            col = (0,220,0) if ok else (0,60,220)
            txt = "Volto OK — premi SPAZIO" if ok else "Nessun volto rilevato..."
            cv2.putText(frm, txt, (14,70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2, cv2.LINE_AA)
            cv2.putText(frm, "SPAZIO = salva   ESC = annulla",
                        (14, h-14), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (170,170,170), 1, cv2.LINE_AA)

            fullscreen()
            cv2.imshow(WINDOW_CV, frm)
            k = cv2.waitKey(1) & 0xFF

            if k == 32 and faces:
                f = faces[0]
                data = {
                    "nome":         profile_name,
                    "emb":          f.embedding / np.linalg.norm(f.embedding),
                    "ratio_riposo": (f.bbox[3]-f.bbox[1])/(f.bbox[2]-f.bbox[0]),
                }
                pickle.dump(data, open(profile_path(profile_name),"wb"))
                emit(f"ENROLLMENT_DONE:{profile_name}")
                break
            elif k == 27:
                emit("Enrollment annullato.")
                break
        cap.release(); cv2.destroyAllWindows(); return

    # ─────────────────────────────────────────────────────────────────────
    #  MONITORAGGIO
    # ─────────────────────────────────────────────────────────────────────
    pfile = profile_path(profile_name)
    if not os.path.exists(pfile):
        emit(f"ERRORE: profilo '{profile_name}' non trovato."); return

    profile = pickle.load(open(pfile,"rb"))
    emit(f"Monitoraggio attivo — profilo: {profile_name}")

    count     = 0
    err_t     = None
    bocciato  = False
    blk_fine  = 0

    def analizza(frm):
        faces = fa.get(frm)
        if not faces:
            return {"ok":False,"motivo":"NESSUN VOLTO"}, None
        f    = max(faces, key=lambda x:(x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
        bbox = f.bbox
        ratio= (bbox[3]-bbox[1])/(bbox[2]-bbox[0])
        emb  = f.embedding/np.linalg.norm(f.embedding)
        own  = float(np.dot(emb, profile["emb"])) >= cfg["identita_threshold"]
        head = True
        if f.pose is not None:
            p,y,r = f.pose
            if abs(y)>cfg["yaw_max"] or abs(p)>cfg["pitch_max"]: head=False
        mouth= ratio > profile["ratio_riposo"]*cfg["bocca_sensibilita"]
        mot  = ("ID ERRATO" if not own else
                "MOVIMENTO TESTA" if not head else
                "BOCCA APERTA" if mouth else "OK")
        return {"ok": own and head and not mouth, "motivo": mot}, f

    def pin_screen() -> bool:
        WP = "SBLOCCO RAPIDO"
        cv2.namedWindow(WP, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WP, 420, 210)
        if W32:
            hp = win32gui.FindWindow(None, WP)
            if not hp:
                # fallback: aspetta un frame
                cv2.waitKey(1)
                hp = win32gui.FindWindow(None, WP)
            if hp:
                win32gui.SetWindowPos(hp, win32con.HWND_TOPMOST,
                    SW//2-210, SH//2-105, 420, 210, win32con.SWP_SHOWWINDOW)
                win32gui.SetForegroundWindow(hp)
                set_cv_icon(hp)
        t0, inp = time.time(), ""
        LIM = cfg["tempo_limite_pin"]
        while (time.time()-t0) < LIM:
            tr  = max(0, LIM-(time.time()-t0))
            img = np.full((210,420,3),(12,12,12),dtype=np.uint8)
            cv2.rectangle(img,(0,0),(int((tr/LIM)*420),5),(0,200,255),-1)
            cv2.putText(img,"INSERISCI PIN:",(30,80),
                        cv2.FONT_HERSHEY_SIMPLEX,0.9,(220,220,220),2)
            cv2.putText(img,"*"*len(inp),(30,155),
                        cv2.FONT_HERSHEY_TRIPLEX,1.6,(0,220,0),3)
            cv2.imshow(WP, img)
            k = cv2.waitKey(1) & 0xFF
            if k==13 and inp==cfg["exit_pin"]:
                cv2.destroyWindow(WP); return True
            elif k in (8,127): inp=inp[:-1]
            elif 0<=k<=127 and chr(k).isdigit() and len(inp)<4: inp+=chr(k)
            if k==27: break
        cv2.destroyWindow(WP); return False

    while True:
        ret, frm = cap.read()
        if not ret: break
        frm  = cv2.flip(frm, 1)
        now  = time.time()

        # BOCCIATO
        if bocciato:
            fullscreen()
            img = np.zeros((SH,SW,3),dtype=np.uint8)
            cv2.putText(img,"BOCCIATO",(SW//2-320,SH//2),
                        cv2.FONT_HERSHEY_TRIPLEX,5,(0,0,200),10,cv2.LINE_AA)
            cv2.putText(img,"ESC = inserisci PIN per uscire",
                        (SW//2-290,SH//2+110),cv2.FONT_HERSHEY_SIMPLEX,
                        1,(150,150,150),2,cv2.LINE_AA)
            cv2.imshow(WINDOW_CV, img)
            if cv2.waitKey(1)&0xFF==27 and pin_screen(): break
            continue

        res, _ = analizza(frm)
        err = not res["ok"]

        if err:
            count += 1
            if err_t is None: err_t = now
            if (now-err_t) >= cfg["soglia_bocciato_s"]:
                bocciato = True; emit("BOCCIATO")
        else:
            count = max(0, count-1)
            if count==0: err_t = None

        # BLACK SCREEN
        if now < blk_fine:
            fullscreen()
            img = np.zeros((SH,SW,3),dtype=np.uint8)
            cv2.putText(img,"RIPRENDI POSIZIONE",
                        (SW//2-440,SH//2),cv2.FONT_HERSHEY_TRIPLEX,
                        2,(240,240,240),4,cv2.LINE_AA)
            cv2.putText(img,res["motivo"],
                        (SW//2-200,SH//2+100),cv2.FONT_HERSHEY_SIMPLEX,
                        1.3,(0,80,255),3,cv2.LINE_AA)
            cv2.imshow(WINDOW_CV, img)
            if cv2.waitKey(1)&0xFF==27 and pin_screen(): break
            continue

        if count >= cfg["soglia_allarme"]:
            blk_fine = now + cfg["durata_schermo_nero"]
            count = 0
            continue

        hide()
        if cv2.waitKey(1)&0xFF==27 and pin_screen(): break

    cap.release(); cv2.destroyAllWindows()
    emit("Sessione terminata.")


# ═════════════════════════════════════════════════════════════════════════════
#  GUI  ─  processo principale
# ═════════════════════════════════════════════════════════════════════════════

def run_gui():
    import json, subprocess, threading
    import tkinter as tk
    from tkinter import messagebox
    import queue as Q

    ICO  = find_icon()
    DARK = dict(
        bg="#0c0c12", bg2="#12121c", bg3="#1a1a28",
        top="#06060e", brd="#1c2c88",
        blu="#1a4fff", blu_h="#3a6aff", blu_d="#0a1f66",
        red="#bb0018", red_h="#e00020", red_d="#3a0008",
        txt="#d8e0ff", txt2="#5868aa", stbg="#080810",
        wht="#ffffff",
    )
    LIGHT = dict(
        bg="#f2f4fb", bg2="#e4e8f6", bg3="#ffffff",
        top="#15205a", brd="#1a4fff",
        blu="#1a4fff", blu_h="#0033cc", blu_d="#c5d3ff",
        red="#bb0018", red_h="#8a0012", red_d="#ffd6da",
        txt="#0d1040", txt2="#3a4a99", stbg="#dde3f8",
        wht="#ffffff",
    )

    # ─────────────────────────────────────────────────────────────────────
    #  Applica icona — funzione standalone, nessun patch globale
    # ─────────────────────────────────────────────────────────────────────
    def apply_icon(win):
        if not ICO:
            return
        try:
            win.iconbitmap(ICO)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    #  Dialog tematizzato — rimpiazza askstring e askyesno
    # ─────────────────────────────────────────────────────────────────────
    def _make_dialog(parent, title, T):
        """Crea un Toplevel tematizzato, centrato sul parent."""
        d = tk.Toplevel(parent)
        d.title(title)
        d.configure(bg=T["bg"])
        d.resizable(False, False)
        d.transient(parent)
        # Icona subito, senza after()
        apply_icon(d)
        # Centra (aggiornamento prima di mostrare)
        d.withdraw()
        return d

    def _show_dialog(d, parent):
        """Posiziona e mostra il dialog."""
        d.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width()  // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        dw = d.winfo_reqwidth()
        dh = d.winfo_reqheight()
        d.geometry(f"{dw}x{dh}+{pw - dw//2}+{ph - dh//2}")
        d.deiconify()
        d.lift()
        d.focus_force()
        d.grab_set()

    def ask_string(parent, title, prompt, T):
        """Dialog di input tematizzato. Restituisce stringa o None."""
        result = [None]
        d = _make_dialog(parent, title, T)

        tk.Label(d, text=prompt, font=("Segoe UI", 10),
                 fg=T["txt"], bg=T["bg"],
                 wraplength=320, justify="left",
                 anchor="w"
                 ).pack(fill="x", padx=20, pady=(18, 6))

        var = tk.StringVar()
        ent = tk.Entry(d, textvariable=var,
                       font=("Consolas", 10),
                       bg=T["bg3"], fg=T["txt"],
                       insertbackground=T["blu"],
                       relief="flat", bd=0,
                       highlightthickness=1,
                       highlightbackground=T["brd"],
                       highlightcolor=T["blu"],
                       width=34)
        ent.pack(padx=20, pady=(0, 14))

        row = tk.Frame(d, bg=T["bg"])
        row.pack(fill="x", padx=20, pady=(0, 16))

        def _ok(ev=None):
            v = var.get().strip()
            result[0] = v if v else None
            d.grab_release()
            d.destroy()

        def _cancel(ev=None):
            d.grab_release()
            d.destroy()

        def _btn(parent, txt, bg, bh, fg, cmd):
            b = tk.Button(parent, text=txt,
                          font=("Consolas", 9, "bold"),
                          fg=fg, bg=bg,
                          activeforeground=fg, activebackground=bh,
                          relief="flat", bd=0, cursor="hand2",
                          command=cmd, padx=16, pady=5)
            b.bind("<Enter>", lambda e: b.configure(bg=bh))
            b.bind("<Leave>", lambda e: b.configure(bg=bg))
            return b

        _btn(row, "Annulla", T["bg2"],  T["bg3"],  T["txt"], _cancel).pack(side="right", padx=(4, 0))
        _btn(row, "OK",      T["blu"],  T["blu_h"], T["wht"], _ok    ).pack(side="right")

        d.bind("<Return>", _ok)
        d.bind("<Escape>", _cancel)

        _show_dialog(d, parent)
        ent.focus_set()
        parent.wait_window(d)
        return result[0]

    def ask_yesno(parent, title, msg, T):
        """Dialog si/no tematizzato. Restituisce True/False."""
        result = [False]
        d = _make_dialog(parent, title, T)

        tk.Label(d, text=msg, font=("Segoe UI", 10),
                 fg=T["txt"], bg=T["bg"],
                 wraplength=320, justify="left",
                 anchor="w"
                 ).pack(fill="x", padx=20, pady=(18, 16))

        row = tk.Frame(d, bg=T["bg"])
        row.pack(fill="x", padx=20, pady=(0, 16))

        def _yes(ev=None):
            result[0] = True
            d.grab_release(); d.destroy()

        def _no(ev=None):
            d.grab_release(); d.destroy()

        def _btn(par, txt, bg, bh, fg, cmd):
            b = tk.Button(par, text=txt,
                          font=("Consolas", 9, "bold"),
                          fg=fg, bg=bg,
                          activeforeground=fg, activebackground=bh,
                          relief="flat", bd=0, cursor="hand2",
                          command=cmd, padx=16, pady=5)
            b.bind("<Enter>", lambda e: b.configure(bg=bh))
            b.bind("<Leave>", lambda e: b.configure(bg=bg))
            return b

        _btn(row, "No",  T["bg2"], T["bg3"],  T["txt"], _no ).pack(side="right", padx=(4,0))
        _btn(row, "Si",  T["red"], T["red_h"], T["wht"], _yes).pack(side="right")

        d.bind("<Return>", _yes)
        d.bind("<Escape>", _no)

        _show_dialog(d, parent)
        parent.wait_window(d)
        return result[0]

    def show_error(parent, title, msg, T):
        """Dialog errore tematizzato."""
        d = _make_dialog(parent, title, T)

        tk.Frame(d, bg=T["red"], height=3).pack(fill="x")
        tk.Label(d, text=msg, font=("Segoe UI", 10),
                 fg=T["txt"], bg=T["bg"],
                 wraplength=320, justify="left",
                 anchor="w"
                 ).pack(fill="x", padx=20, pady=(16, 12))

        row = tk.Frame(d, bg=T["bg"])
        row.pack(fill="x", padx=20, pady=(0, 16))
        b = tk.Button(row, text="OK",
                      font=("Consolas", 9, "bold"),
                      fg=T["wht"], bg=T["red"],
                      activeforeground=T["wht"],
                      activebackground=T["red_h"],
                      relief="flat", bd=0, cursor="hand2",
                      command=lambda: (d.grab_release(), d.destroy()),
                      padx=18, pady=5)
        b.bind("<Enter>", lambda e: b.configure(bg=T["red_h"]))
        b.bind("<Leave>", lambda e: b.configure(bg=T["red"]))
        b.pack(side="right")
        d.bind("<Return>", lambda e: (d.grab_release(), d.destroy()))
        d.bind("<Escape>", lambda e: (d.grab_release(), d.destroy()))

        _show_dialog(d, parent)
        parent.wait_window(d)

    def show_warn(parent, title, msg, T):
        """Dialog avviso tematizzato."""
        d = _make_dialog(parent, title, T)

        tk.Frame(d, bg=T["blu"], height=3).pack(fill="x")
        tk.Label(d, text=msg, font=("Segoe UI", 10),
                 fg=T["txt"], bg=T["bg"],
                 wraplength=320, justify="left",
                 anchor="w"
                 ).pack(fill="x", padx=20, pady=(16, 12))

        row = tk.Frame(d, bg=T["bg"])
        row.pack(fill="x", padx=20, pady=(0, 16))
        b = tk.Button(row, text="OK",
                      font=("Consolas", 9, "bold"),
                      fg=T["wht"], bg=T["blu"],
                      activeforeground=T["wht"],
                      activebackground=T["blu_h"],
                      relief="flat", bd=0, cursor="hand2",
                      command=lambda: (d.grab_release(), d.destroy()),
                      padx=18, pady=5)
        b.bind("<Enter>", lambda e: b.configure(bg=T["blu_h"]))
        b.bind("<Leave>", lambda e: b.configure(bg=T["blu"]))
        b.pack(side="right")
        d.bind("<Return>", lambda e: (d.grab_release(), d.destroy()))
        d.bind("<Escape>", lambda e: (d.grab_release(), d.destroy()))

        _show_dialog(d, parent)
        parent.wait_window(d)

    # ════════════════════════════════════════════════════════════════════
    class App(tk.Tk):
        F1 = "Consolas"
        F2 = "Segoe UI"
        P  = 18

        def __init__(self):
            super().__init__()
            self.title("Sistema Antiplagio v1.3")
            self.resizable(True, True)
            self.protocol("WM_DELETE_WINDOW", self._quit)

            self._dark = True
            self._T    = DARK
            self._cfg  = cfg_load()
            self._proc = None
            self._q    = Q.Queue()
            self._rec  = False
            self._reg  = {}

            # Icona root — default= propaga ai dialogs nativi come fallback
            if ICO:
                try: self.iconbitmap(default=ICO)
                except Exception: pass
            # Applica anche direttamente
            self.after(0,   lambda: apply_icon(self))
            self.after(400, lambda: apply_icon(self))

            self._build()
            self._profiles_reload()
            self._poll()
            self.update_idletasks()
            self.after(80, self._autofit)

        # ── autofit ───────────────────────────────────────────────────────
        def _autofit(self):
            self.update_idletasks()
            need = (self._body.winfo_reqheight() +
                    self._top.winfo_reqheight() +
                    self._sbar.winfo_reqheight() +
                    self._bot.winfo_reqheight() + 10)
            h = min(need, int(self.winfo_screenheight() * 0.92))
            self.geometry(f"640x{h}")
            self.minsize(600, min(h, 680))
            self.update_idletasks()
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))

        # ── tag ───────────────────────────────────────────────────────────
        def _t(self, w, *tags):
            for t in tags: self._reg.setdefault(t, []).append(w)
            return w

        # ── repaint ───────────────────────────────────────────────────────
        def _paint(self):
            T = self._T
            for tag, col in [
                ("bg",T["bg"]),("bg2",T["bg2"]),("bg3",T["bg3"]),
                ("top",T["top"]),("stbg",T["stbg"]),
                ("brd",T["brd"]),("cnv",T["bg"]),
            ]:
                for w in self._reg.get(tag, []):
                    try: w.configure(bg=col)
                    except Exception: pass
            for tag, col in [
                ("txt",T["txt"]),("txt2",T["txt2"]),("blu_fg",T["blu"]),
            ]:
                for w in self._reg.get(tag, []):
                    try: w.configure(fg=col)
                    except Exception: pass
            for w in self._reg.get("lb", []):
                try: w.configure(bg=T["bg3"],fg=T["txt"],
                                 selectbackground=T["blu"],
                                 selectforeground=T["wht"])
                except Exception: pass
            for w in self._reg.get("ent", []):
                try: w.configure(bg=T["bg3"],fg=T["txt"],
                                 insertbackground=T["blu"],
                                 highlightbackground=T["brd"],
                                 highlightcolor=T["blu"])
                except Exception: pass
            for w in self._reg.get("scr", []):
                try: w.configure(bg=T["bg2"],troughcolor=T["bg3"],
                                 activebackground=T["blu"])
                except Exception: pass
            _bm = {
                "B":  (T["blu"],  T["blu_h"],T["wht"]),
                "Bd": (T["blu_d"],T["blu"],  T["txt"]),
                "R":  (T["red"],  T["red_h"],T["wht"]),
                "Rd": (T["red_d"],T["red"],  T["txt"]),
            }
            for bk,(bg,bh,fg) in _bm.items():
                for w in self._reg.get(f"btn{bk}", []):
                    try:
                        w.configure(bg=bg,fg=fg,
                                    activebackground=bh,activeforeground=fg)
                        w._bl=bg; w._bh=bh
                    except Exception: pass
            lbl = "Modalita Chiara" if self._dark else "Modalita Scura"
            try: self._tbtn.configure(text=lbl)
            except Exception: pass
            if not self._rec:
                try: self._rlbl.configure(fg=T["red_d"])
                except Exception: pass

        def _toggle(self):
            self._dark = not self._dark
            self._T = DARK if self._dark else LIGHT
            self.configure(bg=self._T["bg"])
            self._paint()

        # ── hover ─────────────────────────────────────────────────────────
        @staticmethod
        def _hov(b):
            b.bind("<Enter>", lambda e: b.configure(bg=b._bh))
            b.bind("<Leave>", lambda e: b.configure(bg=b._bl))

        # ── factory pulsante ──────────────────────────────────────────────
        def _btn(self, par, txt, bk, cmd, px=12, py=6,
                 side=None, fill=None):
            T = self._T
            _bm = {
                "B":  (T["blu"],  T["blu_h"],T["wht"]),
                "Bd": (T["blu_d"],T["blu"],  T["txt"]),
                "R":  (T["red"],  T["red_h"],T["wht"]),
                "Rd": (T["red_d"],T["red"],  T["txt"]),
            }
            bg,bh,fg = _bm.get(bk,(T["bg2"],T["bg3"],T["txt"]))
            b = tk.Button(par, text=txt,
                          font=(self.F1,9,"bold"),
                          fg=fg,bg=bg,
                          activeforeground=fg,activebackground=bh,
                          relief="flat",bd=0,cursor="hand2",
                          command=cmd,padx=px,pady=py)
            b._bl=bg; b._bh=bh
            self._hov(b)
            self._t(b,f"btn{bk}")
            if fill:   b.pack(fill=fill,pady=(4,0))
            elif side: b.pack(side=side,padx=(0,4),pady=3)
            return b

        # ── separatore ────────────────────────────────────────────────────
        def _sep(self):
            T = self._T
            f = tk.Frame(self._body,bg=T["brd"],height=1)
            f.pack(fill="x",padx=self.P,pady=(12,6))
            self._t(f,"brd")

        # ── heading ───────────────────────────────────────────────────────
        def _head(self, title, sub=None):
            T = self._T
            l = tk.Label(self._body,text=title,
                         font=(self.F1,11,"bold"),
                         fg=T["blu"],bg=T["bg"],anchor="w")
            l.pack(anchor="w",padx=self.P,pady=(14,0))
            self._t(l,"blu_fg","bg")
            if sub:
                s = tk.Label(self._body,text=sub,
                             font=(self.F2,8),
                             fg=T["txt2"],bg=T["bg"],anchor="w")
                s.pack(anchor="w",padx=self.P,pady=(1,0))
                self._t(s,"txt2","bg")

        # ══════════════════════════════════════════════════════════════════
        #  BUILD
        # ══════════════════════════════════════════════════════════════════
        def _build(self):
            T = self._T
            self.configure(bg=T["bg"])

            # topbar
            top = tk.Frame(self,bg=T["top"])
            top.pack(fill="x",side="top")
            self._t(top,"top"); self._top=top

            tk.Frame(top,bg=T["red"],width=5).pack(side="left",fill="y")

            tc = tk.Frame(top,bg=T["top"])
            tc.pack(side="left",padx=(12,0),fill="y")
            self._t(tc,"top")

            lm = tk.Label(tc,text="SISTEMA ANTIPLAGIO",
                          font=(self.F1,13,"bold"),fg=T["wht"],bg=T["top"])
            lm.pack(anchor="w",pady=(12,0))
            self._t(lm,"top")

            ls = tk.Label(tc,text="v1.3  —  Riconoscimento Facciale AI",
                          font=(self.F2,8),fg=T["txt2"],bg=T["top"])
            ls.pack(anchor="w",pady=(0,12))
            self._t(ls,"txt2","top")

            rt = tk.Frame(top,bg=T["top"])
            rt.pack(side="right",padx=12,fill="y")
            self._t(rt,"top")

            self._rlbl = tk.Label(rt,text="● REC",
                                  font=(self.F1,9,"bold"),
                                  fg=T["red_d"],bg=T["top"])
            self._rlbl.pack(side="right",padx=(10,0),pady=16)
            self._t(self._rlbl,"top")

            self._tbtn = tk.Button(
                rt,text="Modalita Chiara",
                font=(self.F2,8,"bold"),
                fg=T["txt"],bg=T["blu_d"],
                activeforeground=T["wht"],activebackground=T["blu"],
                relief="flat",bd=0,cursor="hand2",
                command=self._toggle,padx=10,pady=4)
            self._tbtn._bl=T["blu_d"]; self._tbtn._bh=T["blu"]
            self._hov(self._tbtn)
            self._tbtn.pack(side="right",pady=16)
            self._t(self._tbtn,"btnBd")

            # accent line
            al=tk.Frame(self,bg=T["blu"],height=2)
            al.pack(fill="x",side="top")
            self._t(al,"brd")

            # status bar
            sb=tk.Frame(self,bg=T["stbg"])
            sb.pack(fill="x",side="top")
            self._t(sb,"stbg"); self._sbar=sb
            self.sv=tk.StringVar(value="Pronto.")
            sl=tk.Label(sb,textvariable=self.sv,
                        font=(self.F2,8),fg=T["txt2"],bg=T["stbg"],
                        anchor="w",padx=self.P,pady=5)
            sl.pack(fill="x")
            self._t(sl,"txt2","stbg")
            tk.Frame(self,bg=T["brd"],height=1).pack(fill="x",side="top")

            # bottom bar
            tk.Frame(self,bg=T["brd"],height=1).pack(fill="x",side="bottom")
            bot=tk.Frame(self,bg=T["top"])
            bot.pack(fill="x",side="bottom")
            self._t(bot,"top"); self._bot=bot

            be=tk.Button(bot,text="  ESCI  ",
                         font=(self.F1,9,"bold"),fg=T["wht"],bg=T["red"],
                         activeforeground=T["wht"],activebackground=T["red_h"],
                         relief="flat",bd=0,cursor="hand2",
                         command=self._quit,padx=14,pady=6)
            be._bl=T["red"]; be._bh=T["red_h"]
            self._hov(be)
            be.pack(side="left",padx=self.P,pady=8)
            self._t(be,"btnR")

            ht=tk.Label(bot,
                text="bocca_sensibilita: 1.02=massima  |  1.05=tollerante",
                font=(self.F2,7),fg=T["txt2"],bg=T["top"])
            ht.pack(side="right",padx=self.P)
            self._t(ht,"txt2","top")

            # canvas scrollabile
            wrap=tk.Frame(self,bg=T["bg"])
            wrap.pack(fill="both",expand=True,side="top")
            wrap.grid_rowconfigure(0,weight=1)
            wrap.grid_columnconfigure(0,weight=1)
            self._t(wrap,"bg")

            self._canvas=tk.Canvas(wrap,bg=T["bg"],
                                   highlightthickness=0,bd=0)
            vs=tk.Scrollbar(wrap,orient="vertical",
                            command=self._canvas.yview)
            self._canvas.configure(yscrollcommand=vs.set)
            self._canvas.grid(row=0,column=0,sticky="nsew")
            vs.grid(row=0,column=1,sticky="ns")
            self._t(self._canvas,"cnv","bg")
            self._t(vs,"scr")

            self._body=tk.Frame(self._canvas,bg=T["bg"])
            self._t(self._body,"bg")
            self._wid=self._canvas.create_window(
                (0,0),window=self._body,anchor="nw")

            self._canvas.bind("<Configure>",
                lambda e: self._canvas.itemconfig(self._wid,width=e.width))
            self._body.bind("<Configure>",
                lambda e: self._canvas.configure(
                    scrollregion=self._canvas.bbox("all")))
            self.bind_all("<MouseWheel>",
                lambda e: self._canvas.yview_scroll(
                    int(-1*(e.delta/120)),"units"))

            self._sec_profiles()
            self._sep()
            self._sec_session()
            self._sep()
            self._sec_settings()
            sp=tk.Frame(self._body,bg=T["bg"],height=16)
            sp.pack(); self._t(sp,"bg")

        # ── sezione profili ───────────────────────────────────────────────
        def _sec_profiles(self):
            T=self._T
            self._head("PROFILI SALVATI",
                       "Seleziona il profilo da usare per il monitoraggio")

            lb_b=tk.Frame(self._body,bg=T["brd"])
            lb_b.pack(fill="x",padx=self.P,pady=(8,0))
            self._t(lb_b,"brd")
            lb_i=tk.Frame(lb_b,bg=T["bg3"])
            lb_i.pack(fill="x",padx=1,pady=1)
            self._t(lb_i,"bg3")

            vs=tk.Scrollbar(lb_i,orient="vertical",
                            bg=T["bg2"],troughcolor=T["bg3"],
                            activebackground=T["blu"])
            self.lb=tk.Listbox(lb_i,font=(self.F1,11),height=4,
                               bg=T["bg3"],fg=T["txt"],
                               selectbackground=T["blu"],
                               selectforeground=T["wht"],
                               relief="flat",bd=0,activestyle="none",
                               yscrollcommand=vs.set)
            vs.config(command=self.lb.yview)
            self.lb.pack(side="left",fill="both",expand=True)
            vs.pack(side="right",fill="y")
            self._t(self.lb,"lb"); self._t(vs,"scr")

            pr=tk.Frame(self._body,bg=T["bg"])
            pr.pack(fill="x",padx=self.P,pady=(6,0))
            self._t(pr,"bg")
            self._btn(pr,"Nuovo Enrollment","B", self._enrollment,px=14,side="left")
            self._btn(pr,"Rinomina",        "Bd",self._rinomina,  side="left")
            self._btn(pr,"Elimina",         "R", self._elimina,   px=14,side="left")
            self._btn(pr,"Aggiorna",        "Rd",self._profiles_reload,side="left")

        # ── sezione sessione ──────────────────────────────────────────────
        def _sec_session(self):
            T=self._T
            self._head("CONTROLLO SESSIONE",
                       "Usa il profilo selezionato sopra")

            sr=tk.Frame(self._body,bg=T["bg"])
            sr.pack(fill="x",padx=self.P,pady=(10,0))
            sr.columnconfigure(0,weight=1); sr.columnconfigure(1,weight=1)
            self._t(sr,"bg")

            for col,(txt,bk,cmd) in enumerate([
                ("  ▶  AVVIA  ","B",self._start),
                ("  ■  FERMA  ","R",self._stop),
            ]):
                bg = T["blu"] if bk=="B" else T["red"]
                bh = T["blu_h"] if bk=="B" else T["red_h"]
                b=tk.Button(sr,text=txt,
                            font=(self.F1,10,"bold"),
                            fg=T["wht"],bg=bg,
                            activeforeground=T["wht"],activebackground=bh,
                            relief="flat",bd=0,cursor="hand2",
                            command=cmd,pady=12)
                b._bl=bg; b._bh=bh
                self._hov(b)
                b.grid(row=0,column=col,sticky="ew",
                       padx=(0,4) if col==0 else (4,0))
                self._t(b,f"btn{bk}")

        # ── sezione impostazioni ──────────────────────────────────────────
        def _sec_settings(self):
            T=self._T
            self._head("IMPOSTAZIONI SENSIBILITA'")

            frm=tk.Frame(self._body,bg=T["bg2"])
            frm.pack(fill="x",padx=self.P,pady=(8,0))
            frm.columnconfigure(1,weight=1)
            self._t(frm,"bg2")

            tk.Frame(frm,bg=T["brd"],height=1).grid(
                row=0,column=0,columnspan=2,
                sticky="ew",padx=6,pady=(6,4))

            self._flds={}
            ROWS=[
                ("PIN di uscita",            "exit_pin",            str),
                ("Soglia allarme (frame)",    "soglia_allarme",      int),
                ("Durata schermo nero (s)",   "durata_schermo_nero", float),
                ("Bocciato dopo (s)",         "soglia_bocciato_s",   float),
                ("Finestra PIN (s)",          "tempo_limite_pin",    float),
                ("Similarita' minima (0-1)",  "identita_threshold",  float),
                ("Yaw max (gradi)",           "yaw_max",             float),
                ("Pitch max (gradi)",         "pitch_max",           float),
                ("Sensibilita' bocca",        "bocca_sensibilita",   float),
            ]
            for i,(lbl,key,typ) in enumerate(ROWS):
                rb="bg2" if i%2==0 else "bg3"
                lw=tk.Label(frm,text=lbl,font=(self.F2,9),
                            fg=T["txt2"],bg=T[rb],anchor="w")
                lw.grid(row=i+1,column=0,padx=(8,4),pady=4,sticky="ew")
                self._t(lw,"txt2",rb)

                var=tk.StringVar(value=str(self._cfg[key]))
                ent=tk.Entry(frm,textvariable=var,
                             font=(self.F1,9),
                             bg=T["bg3"],fg=T["txt"],
                             insertbackground=T["blu"],
                             relief="flat",bd=0,
                             highlightthickness=1,
                             highlightbackground=T["brd"],
                             highlightcolor=T["blu"],
                             width=16)
                ent.grid(row=i+1,column=1,padx=(0,8),pady=4,sticky="ew")
                self._t(ent,"ent")
                self._flds[key]=(var,typ)

            tk.Frame(frm,bg=T["brd"],height=1).grid(
                row=len(ROWS)+1,column=0,columnspan=2,
                sticky="ew",padx=6,pady=(4,6))

            bs=tk.Button(self._body,
                         text="  SALVA IMPOSTAZIONI  ",
                         font=(self.F1,9,"bold"),
                         fg=T["txt"],bg=T["blu_d"],
                         activeforeground=T["wht"],activebackground=T["blu"],
                         relief="flat",bd=0,cursor="hand2",
                         command=self._save_cfg,pady=8)
            bs._bl=T["blu_d"]; bs._bh=T["blu"]
            self._hov(bs)
            bs.pack(fill="x",padx=self.P,pady=(10,0))
            self._t(bs,"btnBd")

        # ══════════════════════════════════════════════════════════════════
        #  PROFILI
        # ══════════════════════════════════════════════════════════════════
        def _profiles_reload(self):
            self.lb.delete(0,tk.END)
            for p in profiles_list():
                self.lb.insert(tk.END,"  "+p)
            if self.lb.size(): self.lb.selection_set(0)

        def _selected(self):
            sel=self.lb.curselection()
            if not sel:
                show_warn(self,"Nessuna selezione",
                          "Seleziona un profilo dalla lista.",self._T)
                return None
            return self.lb.get(sel[0]).strip()

        def _enrollment(self):
            name=ask_string(self,"Nuovo Profilo",
                            "Nome del profilo (es. Mario Rossi):",self._T)
            if not name: return
            for c in r'\/:*?"<>|': name=name.replace(c,"_")
            if os.path.exists(profile_path(name)):
                if not ask_yesno(self,"Sovrascrivere?",
                        f"'{name}' esiste. Sovrascrivere?",self._T):
                    return
            self._launch("enrollment",name)

        def _start(self):
            name=self._selected()
            if not name: return
            if not os.path.exists(profile_path(name)):
                show_error(self,"Profilo mancante",
                    f"Profilo '{name}' non trovato.\n"
                    "Esegui prima Enrollment.",self._T)
                return
            self._launch("monitor",name)

        def _stop(self):
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                self._proc=None
                self._status("Processo fermato.")
                self._blink_stop()
            else:
                self._status("Nessun processo in esecuzione.")

        def _rinomina(self):
            name=self._selected()
            if not name: return
            new=ask_string(self,"Rinomina",
                           f"Nuovo nome per '{name}':",self._T)
            if not new: return
            try:
                os.rename(profile_path(name),profile_path(new))
                self._profiles_reload()
                self._status(f"'{name}' → '{new}'")
            except Exception as e:
                show_error(self,"Errore",str(e),self._T)

        def _elimina(self):
            name=self._selected()
            if not name: return
            if ask_yesno(self,"Elimina",
                    f"Eliminare '{name}'?\nOperazione irreversibile.",self._T):
                try:
                    os.remove(profile_path(name))
                    self._profiles_reload()
                    self._status(f"Profilo '{name}' eliminato.")
                except Exception as e:
                    show_error(self,"Errore",str(e),self._T)

        # ══════════════════════════════════════════════════════════════════
        #  SUBPROCESS
        # ══════════════════════════════════════════════════════════════════
        def _launch(self,mode,name):
            if self._proc and self._proc.poll() is None:
                self._status("Un processo e' gia' attivo — fermalo prima.")
                return
            exe=sys.executable
            script=os.path.abspath(__file__)
            cmd=(
                [exe,WORKER_FLAG,mode,name,json.dumps(self._cfg)]
                if getattr(sys,"frozen",False) else
                [exe,script,WORKER_FLAG,mode,name,json.dumps(self._cfg)]
            )
            self._proc=subprocess.Popen(
                cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                encoding="utf-8",errors="replace",bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            threading.Thread(target=self._reader,
                             args=(self._proc,),daemon=True).start()
            self._status(f"'{mode}' avviato — profilo: {name}")
            self._blink_start()

        def _reader(self,proc):
            try:
                for line in proc.stdout:
                    line=line.strip()
                    if line: self._q.put(line)
            except Exception: pass
            self._q.put(DONE_TOKEN)

        def _poll(self):
            try:
                while True:
                    msg=self._q.get_nowait()
                    if msg==DONE_TOKEN:
                        self._proc=None
                        self._profiles_reload()
                        self._blink_stop()
                    elif msg.startswith("ENROLLMENT_DONE:"):
                        pn=msg.split(":",1)[1]
                        self._status(f"Profilo '{pn}' salvato.")
                        self._profiles_reload()
                        items=[self.lb.get(i).strip()
                               for i in range(self.lb.size())]
                        if pn in items:
                            idx=items.index(pn)
                            self.lb.selection_clear(0,tk.END)
                            self.lb.selection_set(idx)
                            self.lb.see(idx)
                    else:
                        self._status(msg)
            except Q.Empty: pass
            self.after(200,self._poll)

        # ── REC ───────────────────────────────────────────────────────────
        def _blink_start(self):
            self._rec=True; self._blink()

        def _blink_stop(self):
            self._rec=False
            try: self._rlbl.configure(fg=self._T["red_d"])
            except Exception: pass

        def _blink(self):
            if not self._rec: return
            T=self._T
            nxt=T["red"] if self._rlbl.cget("fg")!=T["red"] else T["red_d"]
            self._rlbl.configure(fg=nxt)
            self.after(600,self._blink)

        # ── misc ──────────────────────────────────────────────────────────
        def _status(self,msg):
            self.sv.set(msg); self.update_idletasks()

        def _save_cfg(self):
            try:
                for k,(v,t) in self._flds.items():
                    self._cfg[k]=t(v.get())
                cfg_save(self._cfg)
                self._status("Impostazioni salvate.")
            except ValueError as e:
                show_error(self,"Valore non valido",str(e),self._T)

        def _quit(self):
            self._stop(); self.destroy()

    App().mainloop()


#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if WORKER_FLAG in sys.argv:
        import json
        idx  = sys.argv.index(WORKER_FLAG)
        try:
            mode    = sys.argv[idx+1]
            profile = sys.argv[idx+2]
            cfg     = json.loads(sys.argv[idx+3])
        except (IndexError, json.JSONDecodeError) as e:
            print(f"ERRORE argomenti worker: {e}", flush=True)
            sys.exit(1)
        run_worker(mode, profile, cfg)
    else:
        run_gui()

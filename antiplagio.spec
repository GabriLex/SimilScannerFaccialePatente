# antiplagio.spec — ONE FILE portable
# Uso: pyinstaller antiplagio.spec --clean --noconfirm
import glob, os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# ── Icona ──────────────────────────────────────────────────────────────────
_ico = next(
    (f for f in [os.path.join(SPECPATH,"icon.ico")]
               + glob.glob(os.path.join(SPECPATH,"*.ico"))
     if os.path.isfile(f)), None)

# ── Dati AI ────────────────────────────────────────────────────────────────
iface = collect_data_files("insightface")
onnx  = collect_dynamic_libs("onnxruntime")
extra = [(_ico, ".")] if _ico else []

# ── Modelli InsightFace pre-scaricati ──────────────────────────────────────
_mdir = os.path.join(SPECPATH, ".insightface")
model_datas = []
if os.path.isdir(_mdir):
    for root, dirs, files in os.walk(_mdir):
        for fname in files:
            src = os.path.join(root, fname)
            rel = os.path.relpath(os.path.dirname(src), SPECPATH)
            model_datas.append((src, rel))
    print(f"[spec] Bundling {len(model_datas)} model files")

a = Analysis(
    ["antiplagio.py"],
    pathex=[SPECPATH],
    binaries=onnx,
    datas=iface + extra + model_datas,
    hiddenimports=[
        "insightface","insightface.app",
        "insightface.model_zoo","insightface.utils",
        "onnxruntime","cv2","numpy",
        "win32gui","win32con","win32api",
        "tkinter","tkinter.messagebox","tkinter.simpledialog",
    ],
    hookspath=[], runtime_hooks=[],
    excludes=[], cipher=block_cipher, noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="SistemaAntiplagio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # ── UPX DISABILITATO sui file AI/ONNX per evitare corruzione ──────────
    upx=False,
    upx_exclude=[
        "*.onnx",           # modelli InsightFace
        "*.so",             # librerie native
        "onnxruntime*.dll", # runtime ONNX
        "opencv*.dll",      # OpenCV
        "*.pyd",            # estensioni Python
    ],
    runtime_tmpdir=None,
    console=False,
    icon=_ico,
)

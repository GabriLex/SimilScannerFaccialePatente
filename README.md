# 🎓 Sistema Antiplagio v1.3
### Simulatore Biometrico Anti-Plagio per Esercitazione Esame Patente

---

## ⚠️ Disclaimer Importante

**QUESTO SOFTWARE È UN FAC-SIMILE A SCOPO DIMOSTRATIVO E DIDATTICO.**
Sebbene simuli le logiche di controllo biometrico, **NON** è un software ufficiale, non è certificato dalle autorità competenti e **NON** garantisce alcuna integrità legale o tecnica durante un esame reale.
L'interfaccia grafica e le soglie di errore sono ricostruzioni a scopo di test.
Lo sviluppatore non si assume alcuna responsabilità per l'uso improprio di questo codice in contesti di esame ufficiali.

---

## 💻 Requisiti di Sistema

### Hardware
| Componente | Requisito Minimo | Consigliato |
|---|---|---|
| Webcam | 720p | 1080p |
| Processore | Intel i5 7ª gen / AMD Ryzen 5 2000 | i7 / Ryzen 7 |
| RAM | 8 GB | 16 GB |
| Sistema Operativo | Windows 10 | Windows 11 |

> **Nota:** Il blocco finestre tramite `pywin32` richiede **esclusivamente Windows**.

### Software
- **Python** 3.10 o superiore
- Driver webcam correttamente installati e non occupati da altre applicazioni (Teams, Zoom, Skype, ecc.)

---

## 🚀 Installazione e Avvio

### Versione Python (sviluppo)
```bash
# 1. Installa le dipendenze
pip install -r requirements.txt

# 2. Avvia il programma
python antiplagio.py
```

### Versione Portable EXE (distribuzione)
1. Copia `SistemaAntiplagio.exe` in qualsiasi cartella
2. Affianca il file `icon.ico` nella stessa cartella
3. Avvia `SistemaAntiplagio.exe` — nessuna installazione Python richiesta

> **Prima esecuzione:** se i modelli AI non sono inclusi nell'EXE, verranno scaricati automaticamente da internet (~200 MB).

### Build EXE da sorgente
```bash
# Esegui il file batch incluso
build.bat
```
Il bat installa le dipendenze, scarica i modelli AI, compila e produce un singolo `SistemaAntiplagio.exe` nella cartella `dist\`.

---

## 🖥️ Interfaccia Grafica

Il programma si avvia con un pannello di controllo grafico con **modalità scura e chiara** selezionabili dal pulsante in alto a destra.

### Sezioni del pannello

**PROFILI SALVATI**
Gestione dei profili biometrici. Puoi creare più profili (uno per esaminando), selezionare quello attivo, rinominarlo o eliminarlo.

| Pulsante | Funzione |
|---|---|
| Nuovo Enrollment | Registra un nuovo profilo facciale |
| Rinomina | Rinomina il profilo selezionato |
| Elimina | Elimina definitivamente il profilo selezionato |
| Aggiorna | Ricarica la lista profili dalla cartella |

**CONTROLLO SESSIONE**
- **▶ AVVIA** — Avvia il monitoraggio con il profilo selezionato
- **■ FERMA** — Interrompe il processo in corso

**IMPOSTAZIONI SENSIBILITÀ**
Tutti i parametri di controllo sono configurabili dalla GUI e vengono salvati automaticamente in `settings.pkl`.

---

## 🔒 Logica di Controllo e Sicurezza

### 1. Primo Avvio — Enrollment

Al primo utilizzo (o per un nuovo esaminando) è necessaria la calibrazione biometrica:

1. Clicca **Nuovo Enrollment** e inserisci il nome del profilo
2. La webcam si apre a schermo intero
3. Posizionati **frontalmente** alla camera
4. Mantieni la **bocca chiusa** e lo **sguardo fisso**
5. Premi **SPAZIO** per registrare il profilo

Il profilo viene salvato nella cartella `profiles/` come file `.pkl` con il nome scelto.

### 2. Monitoraggio Attivo

Una volta avviato, il sistema monitora costantemente tre parametri:

| Controllo | Descrizione | Penalità |
|---|---|---|
| **Identità** | Verifica che il candidato corrisponda al profilo registrato | Black screen |
| **Posizione testa** | Rileva rotazioni eccessive o sguardi laterali | Black screen |
| **Apertura bocca** | Rileva se la bocca supera la soglia di riposo | Black screen |

Quando tutto è regolare la finestra di monitoraggio rimane **nascosta** — visibile solo in caso di anomalia.

### 3. Schermo Nero (Black Screen)

Se viene rilevata un'anomalia per il numero di frame configurato (default: 5), compare uno schermo nero con il messaggio **"RIPRENDI POSIZIONE"** per la durata configurata (default: 3 secondi).

### 4. Stato BOCCIATO

Se le irregolarità persistono in modo continuo per il tempo configurato (default: **20 secondi**), il sistema entra in blocco permanente e mostra la schermata **BOCCIATO**.

### 5. Uscita dal Programma

| Azione | Effetto |
|---|---|
| **ESC** | Apre la finestra di sblocco PIN |
| PIN corretto entro il tempo limite | Chiude il programma |
| PIN errato o tempo scaduto | La finestra si chiude, il monitoraggio riprende |

---

## ⚙️ Impostazioni Configurabili

| Parametro | Default | Descrizione |
|---|---|---|
| PIN di uscita | `2026` | Codice per uscire dal monitoraggio |
| Soglia allarme (frame) | `5` | Frame consecutivi di errore prima del black screen |
| Durata schermo nero (s) | `3.0` | Secondi di black screen per ogni anomalia |
| Bocciato dopo (s) | `20.0` | Secondi di errore continuo per il blocco definitivo |
| Finestra PIN (s) | `5.0` | Tempo disponibile per inserire il PIN |
| Similarità minima | `0.50` | Soglia cosine similarity per il riconoscimento identità |
| Yaw max (gradi) | `22.0` | Rotazione orizzontale testa massima consentita |
| Pitch max (gradi) | `18.0` | Inclinazione verticale testa massima consentita |
| Sensibilità bocca | `1.02` | Moltiplicatore ratio facciale — `1.02` = max sensibilità, `1.05` = tollerante |

---

## 📁 Struttura File

```
SistemaAntiplagio/
│
├── SistemaAntiplagio.exe   ← EXE portable (dopo la build)
├── antiplagio.py           ← Sorgente principale
├── antiplagio.spec         ← Configurazione build PyInstaller
├── build.bat               ← Script di compilazione
├── icon.ico                ← Icona del programma
├── requirements.txt        ← Dipendenze Python
│
├── profiles/               ← Profili biometrici (creata automaticamente)
│   ├── Mario Rossi.pkl
│   └── ...
│
├── settings.pkl            ← Impostazioni salvate (creato automaticamente)
└── .insightface/           ← Modelli AI (scaricati al primo avvio)
    └── models/
        └── buffalo_sc/
```

---

## 💡 Note Tecniche

### Architettura
Il programma usa due processi separati:
- **Processo principale** — GUI tkinter (pannello di controllo)
- **Processo figlio** — OpenCV + InsightFace (monitoraggio webcam)

La comunicazione avviene tramite pipe stdout UTF-8, eliminando i conflitti tra tkinter e OpenCV su Windows.

### Reset Profilo
Per eliminare un profilo, usa il pulsante **Elimina** nel pannello, oppure cancella manualmente il file `.pkl` corrispondente dalla cartella `profiles/`.

### Modelli AI
Il riconoscimento facciale usa il modello **buffalo_sc** di InsightFace su CPU. Nessuna GPU necessaria.

### Dipendenze
```
opencv-python
pywin32
numpy
insightface
onnxruntime
pyinstaller
```

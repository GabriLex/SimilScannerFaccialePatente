

---
⚠️ DISCLAIMER IMPORTANTE
ATTENZIONE: Questo software è un FAC-SIMILE a scopo dimostrativo e didattico. Sebbene simuli le logiche di controllo biometrico, NON è un software ufficiale, non è certificato dalle autorità competenti e NON garantisce alcuna integrità legale o tecnica durante un esame reale.

L'interfaccia grafica e le soglie di errore sono ricostruzioni a scopo di test. Lo sviluppatore non si assume alcuna responsabilità per l'uso improprio di questo codice in contesti di esame ufficiali.

**Simil Sistema Anti-Plagio usato per Esami Patente**

Software di monitoraggio in tempo reale che utilizza una basilare intelligenza artificiale per simulare il software usato nei test teorici. Rileva automaticamente il volto del candidato, la posizione della testa e l'apertura della bocca con soglie di sensibilità estrema.

---

## 💻 Requisiti di Sistema

### Hardware
* **Webcam:** Risoluzione minima 720p (consigliata 1080p).
* **Processore:** Intel i5 7gen / AMD Ryzen 5 2000 o superiore (per analisi fluida a 30fps).
* **RAM:** Almeno 8GB.
* **Sistema Operativo:** Windows 10/11 (necessario per il blocco finestre `pywin32`).

### Software
* **Python:** Versione 3.10 o superiore.
* **Driver:** Fotocamera correttamente installata e non occupata da altre app (es. Teams/Zoom).

---

## 🚀 Installazione e Avvio

1. **Clona o scarica** la cartella del progetto.
2. **Apri il terminale** (CMD o PowerShell) nella cartella del software.
3. **Installa le librerie** necessarie eseguendo:
   ```bash
   pip install -r requirements.txt
   ```
4. **Avvia il software**:
   ```bash
   python test_patente.py
   ```

---

## 🔒 Controllo e Sicurezza

### Primo Avvio (Enrollment)
Al primo avvio il sistema richiederà la calibrazione:
* Guarda fisso la camera con la bocca chiusa.
* Premi **SPAZIO** per scattare e salvare il tuo profilo biometrico.

### Comandi Operativi
* **ESC**: Richiama la finestra di sblocco (PIN).
* **PIN di Uscita**: `2026`
* **Tempo Limite PIN**: Hai **5 secondi** per inserire il PIN, dopodiché il sistema torna in modalità monitoraggio forzato.

### Stato "BOCCIATO"
Se il sistema rileva irregolarità (testa girata, bocca aperta o volto non corrispondente) per un totale di **20 secondi**, il software bloccherà permanentemente la sessione dichiarando l'utente bocciato.

---

> **Nota:** Per resettare il profilo utente e rifare la calibrazione, elimina il file `user_profile_v48.pkl` dalla cartella principale.

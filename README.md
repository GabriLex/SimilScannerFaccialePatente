

---

# 🚗 SimilScannerFaccialePatente
**Simulatore Biometrico Anti-Plagio per Esercitazione Esame Patente**

---

### ⚠️ DISCLAIMER IMPORTANTE
**QUESTO SOFTWARE È UN FAC-SIMILE A SCOPO DIMOSTRATIVO E DIDATTICO.** Sebbene simuli le logiche di controllo biometrico, **NON è un software ufficiale**, non è certificato dalle autorità competenti e **NON garantisce alcuna integrità legale o tecnica** durante un esame reale.  
L'interfaccia grafica e le soglie di errore sono ricostruzioni a scopo di test. Lo sviluppatore non si assume alcuna responsabilità per l'uso improprio di questo codice in contesti di esame ufficiali.

---

## 💻 Requisiti di Sistema

### **Hardware**
* **Webcam:** Risoluzione minima 720p (consigliata 1080p).
* **Processore:** Intel i5 7ª gen / AMD Ryzen 5 2000 o superiore (per analisi fluida a 30fps).
* **RAM:** Almeno 8GB.
* **Sistema Operativo:** Windows 10/11 (necessario per il blocco finestre tramite `pywin32`).

### **Software**
* **Python:** Versione 3.10 o superiore.
* **Driver:** Fotocamera correttamente installata e non occupata da altre applicazioni (es. Teams, Zoom, Skype).

---

## 🚀 Installazione e Avvio

1.  **Scarica** la cartella del progetto.
2.  **Apri il terminale** (CMD o PowerShell) nella cartella del software.
3.  **Installa le librerie** necessarie eseguendo:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Avvia il software**:
    ```bash
    python test_patente.py
    ```

---

## 🔒 Logica di Controllo e Sicurezza

### **1. Primo Avvio (Enrollment)**
Al primo avvio il sistema richiede una calibrazione biometrica:
* Posizionati frontalmente alla camera.
* Mantieni la **bocca chiusa** e lo sguardo fisso.
* Premi **SPAZIO** per scattare e salvare il tuo profilo.

### **2. Comandi Operativi e PIN**
* **Tasto ESC**: Richiama la finestra di sblocco per uscire dal programma.
* **PIN di Uscita**: `2026`
* **Tempo Limite PIN**: Hai **5 secondi** per inserire il codice. Se il tempo scade, la finestra si chiude automaticamente e il monitoraggio riprende forzatamente.

### **3. Stato "BOCCIATO"**
Il software monitora costantemente:
* **Identità**: Verifica che il candidato sia lo stesso registrato.
* **Posizione Testa**: Rileva rotazioni eccessive o sguardi laterali.
* **Apertura Bocca**: Rileva se la bocca viene aperta oltre la soglia di riposo.

> **⚠️ Penalità:** Se le irregolarità persistono per un totale di **20 secondi**, il sistema entra in blocco permanente e dichiara l'utente **BOCCIATO**.

---

### 💡 Note Tecniche
* **Reset Profilo:** Per rifare la calibrazione o cambiare utente, elimina il file con estensione `.pkl` (es. `user_profile_v48.pkl`) dalla cartella principale.

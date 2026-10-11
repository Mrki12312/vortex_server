from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import math
import sqlite3
import datetime
import urllib.parse

app = Flask(__name__)
CORS(app)  # Omogućava nesmetanu komunikaciju između telefona i servera

# Tvoje centralne matematičke konstante za Vortex proračun
BAZA_KRUGA = 2 * math.pi
ZAKRIVLJENJE = 0.5

def inicijalizuj_globalnu_bazu():
    """Kreira bazu podataka i tabele za skenirane artikle i porudžbine"""
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    
    # Tabela 1: Pamti sve cene koje su aplikacije sa telefona u pozadini skenirale sa interneta
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skenirano_trziste (
            artikal_id TEXT PRIMARY KEY,
            ime TEXT,
            nadjena_cena REAL,
            sajt_izvora TEXT,
            vreme_skena DATETIME
        )
    """)
    
    # Tabela 2: Čuva informacije o kupcima koji su kupili preko anđeo čuvar pop-up prozora
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mreza_porudzbina (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proizvod_ime TEXT,
            cena REAL,
            kupac_ime TEXT,
            telefon TEXT,
            status TEXT,
            vreme_porudzbine DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# ======================================================================
# API ENDPOINT 1: Mobilna aplikacija konstantno šalje sirove podatke ovde
# ======================================================================
@app.route("/api/vortex-background-sync", methods=["POST"])
def pozadinska_sinhronizacija():
    podaci = request.json
    if not podaci:
        return jsonify({"akcija": "nastavi_skeniranje", "razlog": "prazan_paket"})
        
    ime_artikla = podaci.get("ime_proizvoda", "").strip()
    cena_na_ekranu = float(podaci.get("cena", 0))
    sajt = podaci.get("sajt", "Mobilni Uređaj")
    
    # Ako je aplikacija pokupila prazan tekst ili nevalidne podatke, preskačemo
    if not ime_artikla or len(ime_artikla) < 5:
        return jsonify({"akcija": "nastavi_skeniranje"})
        
    artikal_id = f"ART_{abs(hash(ime_artikla)) % 1000000}"
    trenutno_vreme = datetime.datetime.now()
    
    # 1. Automatski skladištimo podatak koji je kupac skenirao za nas (izgradnja tvoje baze)
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, vreme_skena)
        VALUES (?, ?, ?, ?, ?)
    """, (artikal_id, ime_artikla, cena_na_ekranu, sajt, trenutno_vreme))
    conn.commit()
    conn.close()
    
    print(f"[VORTEX MREŽA] Skener uhvatio: '{ime_artikla[:40]}...' | Cena na internetu: {cena_na_ekranu} RSD")
    
    # 2. LOGIKA ZA ANĐELA ČUVARA (Presretanje sa boljom cenom):
    # Primenjujemo tvoj matematički model da spustimo cenu za 15% (dropship na nuli/minimalnoj marži)
    vortex_cena = round(cena_na_ekranu * 0.85, 2) 
    usteda = round(cena_na_ekranu - vortex_cena, 2)
    
    # Nalažemo telefonu da trenutno prekine korisnika i izbaci Pop-up prozor jer imamo uštedu
    return jsonify({
        "akcija": "PRESRRETNI_I_POKAZI_POPUP",
        "ime": ime_artikla[:50],  # Skraćujemo naziv da lepo stane u prozor na telefonu
        "cena": vortex_cena,
        "usteda": usteda,
        "artikal_id": artikal_id
    })

# ======================================================================
# API ENDPOINT 2: Kada kupac unese podatke u pop-up na telefonu i klikne Kupi
# ======================================================================
@app.route("/api/vortex-mobilna-porudzbina", methods=["POST"])
def mobilna_porudzbina():
    podaci = request.json
    if not podaci:
        return jsonify({"status": "greska", "poruka": "Podaci nisu primljeni."})
        
    proizvod_ime = podaci.get("ime")
    cena = podaci.get("cena")
    kupac_ime = podaci.get("kupac")
    telefon = podaci.get("telefon")
    
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO mreza_porudzbina (proizvod_ime, cena, kupac_ime, telefon, status)
        VALUES (?, ?, ?, ?, 'Novo / Čeka dropship slanje')
    """, (proizvod_ime, cena, kupac_ime, telefon))
    conn.commit()
    conn.close()
    
    print(f"[VORTEX PRODAJA] ⚡ NOVAC JE LEGAO! Kupac {kupac_ime} je naručio '{proizvod_ime}' za {cena} RSD!")
    return jsonify({"status": "uspeh", "poruka": "Hvala vam! Vaš novčanik je uspešno sačuvan."})

# ======================================================================
# RUTA 3: Tvoja administratorska kontrolna tabla (Da vidiš šta se skenira i poručuje)
# ======================================================================
@app.route("/")
def administrativni_panel():
    conn = sqlite3.connect("vortex_network.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Izvlačimo najnovije skenirane podatke sa svih telefona
    cursor.execute("SELECT * FROM skenirano_trziste ORDER BY vreme_skena DESC LIMIT 20")
    skenovi = cursor.fetchall()
    
    # Izvlačimo sve pristigle porudžbine od kupaca
    cursor.execute("SELECT * FROM mreza_porudzbina ORDER BY vreme_porudzbine DESC")
    porudzbine = cursor.fetchall()
    
    conn.close()
    
    # Vraćamo tekstualni pregled baze direktno u pretraživač radi lakšeg praćenja
    return f"""
    <html>
    <head><title>Vortex Kontrolni Centar</title></head>
    <body style="font-family: Arial; padding: 30px; background: #111; color: #eee;">
        <h1>⚡ Vortex Globalni Kontrolni Centar</h1>
        <hr style="border-color: #333;">
        
        <div style="display: flex; gap: 30px;">
            <div style="flex: 1; background: #222; padding: 20px; border-radius: 8px;">
                <h2>🛒 Pristigle Porudžbine (Dropship sa terena)</h2>
                <ul>
                    {"".join([f"<li><b>{p['kupac_ime']}</b> ({p['telefon']}) - {p['proizvod_ime']} za <span style='color:#27ae60'>{p['cena']} RSD</span> [{p['status']}]</li>" for p in porudzbine]) if porudzbine else "<li>Nema novih porudžbina za sada.</li>"}
                </ul>
            </div>
            
            <div style="flex: 1; background: #222; padding: 20px; border-radius: 8px;">
                <h2>📡 Uživo Skeniranje Tržišta (Mreža Korisnika)</h2>
                <ul>
                    {"".join([f"<li>Artikal: {s['ime'][:40]}... | Cena na netu: {s['nadjena_cena']} RSD ({s['vreme_skena']})</li>" for s in skenovi]) if skenovi else "<li>Čeka se prvi pozadinski signal sa telefona...</li>"}
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    import os
    inicijalizuj_globalnu_bazu()
    
    # Klaud servisi sami dodeljuju PORT, ako ga nema (lokalno), koristi se 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)

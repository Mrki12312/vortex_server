from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os
from vortex_engine import izvuci_univerzalni_sku, izracunaj_vortex_cenu

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def inicijalizuj_globalnu_bazu():
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skenirano_trziste (
            artikal_id TEXT PRIMARY KEY,
            ime TEXT,
            nadjena_cena REAL,
            sajt_izvora TEXT,
            link_proizvoda TEXT,
            vreme_skena DATETIME
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mreza_porudzbina (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proizvod_ime TEXT,
            cena REAL,
            kupac_ime TEXT,
            telefon TEXT,
            status TEXT,
            link_naruceno TEXT,
            link_jeftinije TEXT,
            vreme_porudzbine DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

@app.route("/api/vortex-background-sync", methods=["POST"])
def pozadinska_sinhronizacija():
    podaci = request.json
    if not podaci:
        return jsonify({"akcija": "nastavi_skeniranje"})
        
    ime_artikla = podaci.get("ime_proizvoda", "").strip()
    cena_na_ekranu = float(podaci.get("cena", 0))
    sajt = podaci.get("sajt", "Skener")
    trenutni_link = podaci.get("link", "")
    
    if not ime_artikla or cena_na_ekranu == 0:
        return jsonify({"akcija": "nastavi_skeniranje"})
        
    # Izvlačenje čiste šifre modela
    sku_kod = izvuci_univerzalni_sku(ime_artikla)
    artikal_id = f"SKU_{sku_kod}"
    trenutno_vreme = datetime.datetime.now()
    
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    
    # Upis u bazu pod jedinstvenim SKU-om
    cursor.execute("""
        INSERT OR REPLACE INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (artikal_id, ime_artikla, cena_na_ekranu, sajt, trenutni_link, trenutno_vreme))
    conn.commit()
    
    # Pretraga jeftinije alternative za isti taj SKU
    cursor.execute("""
        SELECT nadjena_cena, sajt_izvora, link_proizvoda FROM skenirano_trziste 
        WHERE artikal_id = ? AND sajt_izvora != ? AND nadjena_cena < ?
        ORDER BY nadjena_cena ASC LIMIT 1
    """, (artikal_id, sajt, cena_na_ekranu))
    
    nadjena_jeftinija_ponuda = cursor.fetchone()
    conn.close()
    
    if nadjena_jeftinija_ponuda:
        cena_jeftinijeg = nadjena_jeftinija_ponuda[0]
        link_jeftinijeg = nadjena_jeftinija_ponuda[2]
        
        proracun = izracunaj_vortex_cenu(cena_na_ekranu, cena_jeftinijeg)
        if proracun["validno"]:
            return jsonify({
                "akcija": "PRESRRETNI_I_POKAZI_POPUP",
                "ime": ime_artikla[:50],
                "cena": proracun["vortex_cena"],
                "usteda": proracun["usteda"],
                "link_jeftinije": link_jeftinijeg
            })
            
    return jsonify({"akcija": "nastavi_skeniranje"})

@app.route("/api/vortex-mobilna-porudzbina", methods=["POST"])
def mobilna_porudzbina():
    podaci = request.json
    if not podaci: return jsonify({"status": "greska"})
    
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO mreza_porudzbina (proizvod_ime, cena, kupac_ime, telefon, status, link_naruceno, link_jeftinije)
        VALUES (?, ?, ?, ?, 'Novo / Čeka slanje', ?, ?)
    """, (podaci.get("ime"), podaci.get("cena"), podaci.get("kupac"), podaci.get("telefon"), podaci.get("link_naruceno"), podaci.get("link_jeftinije")))
    conn.commit()
    conn.close()
    return jsonify({"status": "uspeh"})

@app.route("/")
def administrativni_panel():
    conn = sqlite3.connect("vortex_network.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM skenirano_trziste ORDER BY vreme_skena DESC LIMIT 20")
    skenovi = cursor.fetchall()
    cursor.execute("SELECT * FROM mreza_porudzbina ORDER BY vreme_porudzbine DESC")
    porudzbine = cursor.fetchall()
    conn.close()
    
    porudzbine_html = "".join([f"<li>👤 <b>{p['kupac_ime']}</b> ({p['telefon']}) - {p['proizvod_ime']} za <span style='color:#27ae60'>{p['cena']} RSD</span><br>🔵 <a href='{p['link_naruceno']}' target='_blank' style='color:#0084ff;'>Skuplji link</a> | 🔴 <a href='{p['link_jeftinije']}' target='_blank' style='color:#ff4d4d; font-weight:bold;'>Kupi ovde (Jeftinije)</a></li>" for p in porudzbine]) if porudzbine else "<li>Nema novih porudžbina.</li>"
    skenovi_html = "".join([f"<li>📡 SKU: {s['artikal_id']} | <a href='{s['link_proizvoda']}' target='_blank' style='color:#aaa;'>{s['ime'][:40]}...</a> | <b>{s['nadjena_cena']} RSD</b> ({s['sajt_izvora']})</li>" for s in skenovi]) if skenovi else "<li>Čeka se signal...</li>"
    
    return f"""
    <html>
    <head><title>Vortex Kontrolni Centar</title></head>
    <body style="font-family: Arial; padding: 30px; background: #111; color: #eee;">
        <h1>⚡ Vortex Globalni Kontrolni Centar</h1>
        <hr style="border-color: #333;">
        <div style="display: flex; gap: 30px;">
            <div style="flex: 1; background: #222; padding: 20px; border-radius: 8px;"><h2>🛒 Pristigle Porudžbine</h2><ul>{porudzbine_html}</ul></div>
            <div style="flex: 1; background: #222; padding: 20px; border-radius: 8px;"><h2>📡 Uživo Skeniranje Tržišta</h2><ul>{skenovi_html}</ul></div>
        </div>
    </body>
    </html>
    """
# DODAJ OVO NA VRH APP.PY MEĐU OSTALE IMPORTE:
import threading
import time
from vortex_robot import pokreni_masovno_rudarenje

def pozadinski_tajmer_robota():
    """Funkcija koja se izvršava u posebnoj niti i pokreće robota na svakih 6 sati"""
    # Puštamo server da se prvo upali (pauza 30 sekundi)
    time.sleep(30)
    while True:
        try:
            pokreni_masovno_rudarenje()
        except Exception as e:
            print(f"[VORTEX TAJMER EROR] Robot je naišao na prepreku: {e}")
        
        # Pauza od 6 sati (6 sati * 60 minuta * 60 sekundi) pre sledećeg skeniranja
        time.sleep(21600)

# ULAZNA TAČKA ZA POKRETANJE
if __name__ == "__main__":
    inicijalizuj_globalnu_bazu()
    
    # Pokrećemo robota u pozadinskoj niti da ne bi usporavao rad tvog sajta na Renderu
    nit_robota = threading.Thread(target=pozadinski_tajmer_robota, daemon=True)
    nit_robota.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)

if __name__ == "__main__":
    inicijalizuj_globalnu_bazu()
    app.run(debug=False, host="0.0.0.0", port=5000)

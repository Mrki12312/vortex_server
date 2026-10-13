from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

BAZA_NAME = "vortex_network_v4.db"

def inicijalizuj_globalnu_bazu():
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skenirano_trziste (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artikal_id TEXT,
            ime TEXT,
            nadjena_cena REAL,
            sajt_izvora TEXT,
            link_proizvoda TEXT,
            vreme_skena DATETIME
        )
    """)
    conn.commit()
    conn.close()

@app.route("/api/vortex-upis-cena", methods=["POST"])
def upis_cena_iz_ekstenzije():
    podaci = request.json
    if not podaci: 
        return jsonify({"status": "greska"})
        
    artikal_id = podaci.get("artikal_id", "SKU_NEPOZNAT")
    ime_artikla = podaci.get("ime_proizvoda", "Nepoznat naziv")
    cena = float(podaci.get("cena", 0))
    sajt = podaci.get("sajt", "Nepoznat sajt")
    link = podaci.get("link", "")
    
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (artikal_id, ime_artikla, cena, sajt, link, datetime.datetime.now()))
    conn.commit()
    conn.close()
    return jsonify({"status": "uspeh"})

@app.route("/")
def administrativni_panel():
    conn = sqlite3.connect(BAZA_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM skenirano_trziste ORDER BY vreme_skena DESC LIMIT 40")
    skenovi = cursor.fetchall()
    conn.close()
    
    skenovi_html = "".join([f"<li>📡 <b>SKU: {s['artikal_id']}</b> | <a href='{s['link_proizvoda']}' target='_blank' style='color:#aaa;text-decoration:none;'>{s['ime'][:50]}...</a> | <b style='color:#2ecc71;'>{s['nadjena_cena']} RSD</b> ({s['sajt_izvora']})</li>" for s in skenovi]) if skenovi else "<li>Čeka se prvi signal sa mreže...</li>"
    
    return f"""
    <html>
    <head><title>Vortex Kontrolni Centar</title></head>
    <body style="font-family: Arial, sans-serif; padding: 30px; background: #111; color: #eee;">
        <h1>⚡ Vortex Globalno Skladište Podataka</h1>
        <hr style="border-color: #333; margin-bottom: 25px;">
        <div style="background: #222; padding: 20px; border-radius: 8px; border: 1px solid #333;">
            <h2>📡 Skeniranje Tržišta uživo</h2>
            <ul>{skenovi_html}</ul>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    inicijalizuj_globalnu_bazu()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

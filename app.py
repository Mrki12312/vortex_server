from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os
import re

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

BAZA_NAME = "vortex_network_v4.db"

def inicijalizuj_globalnu_bazu():
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    # Tabela za uživo skeniranje kupaca
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
    # Tabela za tvoje jeftinije dropship proizvode koje unosiš ručno
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dropship_ponude (
            sku_kod TEXT PRIMARY KEY,
            jeftinija_cena REAL,
            link_nabavke TEXT
        )
    """)
    # Tabela za porudžbine kupaca preko pop-up prozora
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
        
    # Izvlačenje čiste šifre modela (SKU)
    tekst = ime_artikla.upper()
    skovi_sablon = re.findall(r'\b[A-Z0-9-]{4,15}\b', tekst)
    sku_kod = "NEPOZNAT"
    if skovi_sablon:
        for stavka in skovi_sablon:
            if any(c.isdigit() for c in stavka):
                sku_kod = stavka
                break
                
    artikal_id = f"SKU_{sku_kod}"
    
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    
    # Beležimo posetu kupca u bazu
    cursor.execute("""
        INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (artikal_id, ime_artikla, cena_na_ekranu, sajt, trenutni_link, datetime.datetime.now()))
    conn.commit()
    
    # PROVERA: Tražimo da li ti u bazi imaš unetu jeftiniju dropship alternativu za ovaj SKU
    cursor.execute("SELECT jeftinija_cena, link_nabavke FROM dropship_ponude WHERE sku_kod = ?", (sku_kod,))
    ponuda = cursor.fetchone()
    conn.close()
    
    if ponuda and cena_na_ekranu > ponuda[0]:
        cena_nabavke = ponuda[0]
        link_nabavke = ponuda[1]
        
        # Računamo cenu sa popustom za kupca (srednja cena) i osiguravamo ti maržu
        cena_kupca = round((cena_na_ekranu + cena_nabavke) / 2, 2)
        if cena_kupca < (cena_nabavke * 1.15):
            cena_kupca = round(cena_nabavke * 1.15, 2)
            
        usteda = round(cena_na_ekranu - cena_kupca, 2)
        
        if usteda > 100:
            return jsonify({
                "akcija": "PRESRRETNI_I_POKAZI_POPUP",
                "ime": ime_artikla[:50],
                "cena": cena_kupca,
                "usteda": usteda,
                "link_jeftinije": link_nabavke
            })
            
    return jsonify({"akcija": "nastavi_skeniranje"})

@app.route("/api/vortex-dodaj-ponudu", methods=["POST"])
def dodaj_ponudu_rucno():
    """Ruta preko koje unosiš svoje jeftine dropship proizvode u bazu"""
    podaci = request.json
    sku = podaci.get("sku", "").strip().upper()
    cena = float(podaci.get("cena", 0))
    link = podaci.get("link", "").strip()
    
    if not sku or cena == 0 or not link:
        return jsonify({"status": "greska", "poruka": "Nevažeći podaci"})
        
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO dropship_ponude (sku_kod, jeftinija_cena, link_nabavke)
        VALUES (?, ?, ?)
    """, (sku, cena, link))
    conn.commit()
    conn.close()
    return jsonify({"status": "uspeh", "poruka": f"SKU {sku} uspesno povezan sa jeftinijom cenom!"})

@app.route("/api/vortex-mobilna-porudzbina", methods=["POST"])
def mobilna_porudzbina():
    podaci = request.json
    if not podaci: return jsonify({"status": "greska"})
    conn = sqlite3.connect(BAZA_NAME)
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
    conn = sqlite3.connect(BAZA_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM skenirano_trziste ORDER BY vreme_skena DESC LIMIT 15")
    skenovi = cursor.fetchall()
    cursor.execute("SELECT * FROM mreza_porudzbina ORDER BY vreme_porudzbine DESC")
    porudzbine = cursor.fetchall()
    conn.close()
    
    porudzbine_html = "".join([f"<li>👤 <b>{p['kupac_ime']}</b> ({p['telefon']}) - {p['proizvod_ime']} za <span style='color:#2ecc71'>{p['cena']} RSD</span><br>🔵 <a href='{p['link_naruceno']}' target='_blank'>Skuplji sajt</a> | 🔴 <a href='{p['link_jeftinije']}' target='_blank' style='font-weight:bold;color:#ff4d4d;'>Kupi na Amazonu/Aliju</a></li>" for p in porudzbine]) if porudzbine else "<li>Nema novih porudžbina.</li>"
    skenovi_html = "".join([f"<li>📡 SKU: {s['artikal_id']} | <a href='{s['link_proizvoda']}' target='_blank' style='color:#aaa;text-decoration:none;'>{s['ime'][:40]}...</a> | <b>{s['nadjena_cena']} RSD</b> ({s['sajt_izvora']})</li>" for s in skenovi]) if skenovi else "<li>Čeka se prvi signal...</li>"
    
    return f"""
    <html>
    <head><title>Vortex Kontrolni Centar</title></head>
    <body style="font-family: Arial, sans-serif; padding: 30px; background: #111; color: #eee;">
        <h1>⚡ Vortex Globalni Kontrolni Centar</h1>
        <hr style="border-color: #333; margin-bottom: 25px;">
        
        <!-- FORMA ZA RUČNI UNOS DROPSHIP PONUDA -->
        <div style="background: #1c1c24; padding: 20px; border-radius: 8px; border: 1px solid #0084ff; margin-bottom: 30px; max-width: 500px;">
            <h3>➕ Dodaj Jeftiniji Proizvod sa Amazona / AliExpressa</h3>
            <input type="text" id="ins-sku" placeholder="Šifra modela (npr. MDF3930)" style="width:100%; padding:8px; margin-bottom:10px; background:#222; color:#fff; border:1px solid #444;">
            <input type="number" id="ins-cena" placeholder="Nabavna cena u DINARIMA (npr. 1200)" style="width:100%; padding:8px; margin-bottom:10px; background:#222; color:#fff; border:1px solid #444;">
            <input type="text" id="ins-link" placeholder="Link do Amazona ili AliExpressa" style="width:100%; padding:8px; margin-bottom:15px; background:#222; color:#fff; border:1px solid #444;">
            <button onclick="posaljiPonudu()" style="width:100%; background:#0084ff; color:#fff; padding:10px; border:none; font-weight:bold; cursor:pointer;">Poveži sa Vortex Mrežom</button>
        </div>

        <div style="display: flex; gap: 30px;">
            <div style="flex: 1; background: #222; padding: 20px; border-radius: 8px; border: 1px solid #333;"><h2>🛒 Pristigle Porudžbine</h2><ul>{porudzbine_html}</ul></div>
            <div style="flex: 1; background: #222; padding: 20px; border-radius: 8px; border: 1px solid #333;"><h2>📡 Uživo Skeniranje Tržišta</h2><ul>{skenovi_html}</ul></div>
        </div>

        <script>
        function posaljiPonudu() {{
            let s = document.getElementById('ins-sku').value;
            let c = document.getElementById('ins-cena').value;
            let l = document.getElementById('ins-link').value;
            if(!s || !c || !l) {{ alert('Popuni sva polja!'); return; }}
            fetch('/api/vortex-dodaj-ponudu', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ sku: s, cena: c, link: l }})
            }}).then(res => res.json()).then(d => {{ alert(data.poruka); window.location.reload(); }});
        }}
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    inicijalizuj_globalnu_bazu()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

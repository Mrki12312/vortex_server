from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os
from vortex_engine import izvuci_univerzalni_sku

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

BAZA_NAME = "vortex_network_v2.db"

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
    if not podaci: return jsonify({"akcija": "nastavi_skeniranje"})
        
    ime_artikla = podaci.get("ime_proizvoda", "").strip()
    cena_na_ekranu = float(podaci.get("cena", 0))
    sajt = podaci.get("sajt", "Skener")
    trenutni_link = podaci.get("link", "")
    
    if not ime_artikla or cena_na_ekranu == 0:
        return jsonify({"akcija": "nastavi_skeniranje"})
        
    sku_kod = izvuci_univerzalni_sku(ime_artikla)
    artikal_id = f"SKU_{sku_kod}"
    trenutno_vreme = datetime.datetime.now()
    
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (artikal_id, ime_artikla, cena_na_ekranu, sajt, trenches_link, trenches_vreme))
    conn.commit()
    
    cursor.execute("""
        SELECT nadjena_cena, sajt_izvora, link_proizvoda FROM skenirano_trziste 
        WHERE artikal_id = ? AND sajt_izvora != ? AND sajt_izvora NOT LIKE 'amazon.com%' AND nadjena_cena < ?
        ORDER BY nadjena_cena ASC LIMIT 1
    """, (artikal_id, sajt, cena_na_ekranu))
    
    nadjena_jeftinija_ponuda = cursor.fetchone()
    conn.close()
    
    if nadjena_jeftinija_ponuda:
        return jsonify({
            "akcija": "PRESRRETNI_I_POKAZI_POPUP",
            "ime": ime_artikla[:50],
            "cena": round(nadjena_jeftinija_ponuda[0] * 1.15, 2),
            "usteda": round(cena_na_ekranu - (nadjena_jeftinija_ponuda[0] * 1.15), 2),
            "link_jeftinije": nadjena_jeftinija_ponuda[2]
        })
    return jsonify({"akcija": "nastavi_skeniranje"})

@app.route("/api/vortex-probudi-robota", methods=["GET"])
def probudi_pozadinskog_robota():
    from vortex_robot import pokreni_masovno_rudarenje
    # Pokrećemo funkciju koja odmah šalje nalog Scrape.do servisu i zatvara stranicu bez čekanja
    izvestaj = pokreni_masovno_rudarenje()
    return jsonify({"status": "zahtev_poslat_proksiju", "detalji": izvestaj})

# NOVI WEBHOOK ENDPOINT: Ovde Scrape.do direktno ubacuje podatke u bazu kada završi sa Amazonom
@app.route("/api/vortex-webhook", methods=["POST"])
def vortex_webhook_prijem():
    try:
        from bs4 import BeautifulSoup
        html_sadrzaj = request.data.decode("utf-8")
        artikal_id = request.args.get("artikal_id", "SKU_NEPOZNAT")
        
        supa = BeautifulSoup(html_sadrzaj, "html.parser")
        kartica = supa.find("div", {"data-component-type": "s-search-result"})
        
        if kartica:
            element_cene = kartica.find(class_="a-price-whole")
            element_linka = kartica.find("a", class_="a-link-normal s-no-outline")
            element_naslova = kartica.find("h2")
            
            if element_cene and element_linka and element_naslova:
                ceo_deo = "".join(c for c in element_cene.get_text() if c.isdigit())
                cena_rsd = round(float(ceo_deo or 0) * 108.0, 2)
                puni_link = "https://amazon.com" + element_linka["href"]
                ime_sa_amazona = element_naslova.get_text().strip()
                
                conn = sqlite3.connect(BAZA_NAME)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, ime_sa_amazona[:100], cena_rsd, "amazon.com (Vortex Robot)", puni_link, datetime.datetime.now()))
                conn.commit()
                conn.close()
                return "OK", 200
        
        # Ako nije nađeno, upisujemo status direktno na panel
        conn = sqlite3.connect(BAZA_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (artikal_id, "Artikal trenutno nije na stanju na Amazonu", 0, "amazon.com (Nema rezultata)", "https://amazon.com", datetime.datetime.now()))
        conn.commit()
        conn.close()
        return "Nema rezultata", 200
    except Exception as e:
        return str(e), 500

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

if __name__ == "__main__":
    inicijalizuj_globalnu_bazu()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

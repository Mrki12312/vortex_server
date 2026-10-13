from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import datetime
import os
import re
import requests
import urllib.parse
from bs4 import BeautifulSoup

app = Flask(__name__)
# CORS je potpuno otvoren za stabilnu komunikaciju sa ekstenzijom
CORS(app, resources={r"/*": {"origins": "*"}})

BAZA_NAME = "vortex_network_v3.db"
API_TOKEN = "bbf0475d54b54e9cad14c084f462da7152b49164592"

# ======================================================================
# JEZGRO 1: LOGIKA INTEGRISANOG VORTEX MOTORA
# ======================================================================

def lokalni_izvuci_sku(ime_artikla):
    """Izvlači jedinstvenu šifru modela (SKU) iz naziva artikla"""
    if not ime_artikla:
        return "NEPOZNAT_MODEL"
    tekst = ime_artikla.upper()
    skovi_sablon = re.findall(r'\b[A-Z0-9]{3,12}\b', tekst)
    if skovi_sablon:
        for stavka in skovi_sablon:
            if any(c.isdigit() for c in stavka):
                return stavka
    stop_reci = {"SET", "SLIKA", "DELA", "PODNA", "LAMPA", "CRNA", "MODERNA", "ANANAS", "GIGATRON", "BIGBANG"}
    reci = [rec for rec in tekst.split() if rec not in stop_reci and len(rec) > 2]
    if reci:
        return reci
    return "NEPOZNAT_MODEL"

def lokalni_izracunaj_vortex_cenu(cena_trenutna, cena_najniza_baza):
    """Računa fer cenu sa popustom za kupca i ugrađuje tvoj dropship profit"""
    srednja_cena = round((cena_trenutna + cena_najniza_baza) / 2, 2)
    minimalna_tvoja_cena = cena_najniza_baza * 1.10
    
    if srednja_cena < minimalna_tvoja_cena:
        srednja_cena = round(minimalna_tvoja_cena, 2)
        
    usteda = round(cena_trenutna - srednja_cena, 2)
    return {
        "vortex_cena": srednja_cena,
        "usteda": usteda,
        "validno": usteda > 0
    }

# ======================================================================
# JEZGRO 2: LOGIKA INTEGRISANOG AMAZON ROBOTA (SCRAPER-A)
# ======================================================================

def lokalni_amazon_skreper(pun_naziv, artikal_id):
    """Direktni robot sa Scrape.do tunelom koji garantovano prolazi zaštitu"""
    siguran_naziv = urllib.parse.quote(pun_naziv)
    target_url = f"https://amazon.com{siguran_naziv}"
    api_url = f"https://scrape.do{API_TOKEN}&url={target_url}"
    
    print(f"[VORTEX ROBOT] Pokrećem API sken na Amazonu za: {pun_naziv[:30]}")
    
    try:
        odgovor = requests.get(api_url, timeout=25)
        trenutno_vreme = datetime.datetime.now()
        
        if odgovor.status_code != 200:
            return f"API greška: status {odgovor.status_code}"
            
        supa = BeautifulSoup(odgovor.text, "html.parser")
        kartica = supa.find("div", {"data-component-type": "s-search-result"})
        
        conn = sqlite3.connect(BAZA_NAME)
        cursor = conn.cursor()
        
        if kartica:
            element_cene = kartica.find(class_="a-price-whole")
            element_centi = kartica.find(class_="a-price-fraction")
            element_linka = kartica.find("a", class_="a-link-normal s-no-outline")
            element_naslova = kartica.find("h2")
            
            if element_cene and element_linka and element_naslova:
                ceo_deo = "".join(c for c in element_cene.get_text() if c.isdigit())
                centi_deo = "".join(c for c in element_centi.get_text() if c.isdigit()) if element_centi else "00"
                
                cena_dolar = float(f"{ceo_deo or 0}.{centi_deo}")
                cena_rsd = round(cena_dolar * 108.0, 2)
                puni_link = "https://amazon.com" + element_linka["href"]
                ime_sa_amazona = element_naslova.get_text().strip()
                
                cursor.execute("""
                    INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, ime_sa_amazona[:100], cena_rsd, "amazon.com (Vortex Robot)", puni_link, trenutno_vreme))
                conn.commit()
                conn.close()
                return f"Uspeh! Upisana cena sa Amazona: {cena_rsd} RSD"
        
        # Ako nema poklapanja na Amazonu, upisujemo status da znaš da je robot pokrenut
        cursor.execute("""
            INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (artikal_id, "Artikal trenutno nije pronadjen na Amazonu", 0, "amazon.com (Nema na stanju)", target_url, trenutno_vreme))
        conn.commit()
        conn.close()
        return "Nije pronađeno na Amazonu."
        
    except Exception as e:
        return f"Krah robota: {str(e)}"

# ======================================================================
# JEZGRO 3: KONEKCIJA BAZE I INICIJALIZACIJA
# ======================================================================

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
# ======================================================================
# JEZGRO 4: FLASK RUTING I KONTROLNI PANEL
# ======================================================================

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
        
    sku_kod = lokalni_izvuci_sku(ime_artikla)
    artikal_id = f"SKU_{sku_kod}"
    trenutno_vreme = datetime.datetime.now()
    
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (artikal_id, ime_artikla, cena_na_ekranu, sajt, trenutni_link, trenutno_vreme))
    conn.commit()
    
    cursor.execute("""
        SELECT nadjena_cena, link_proizvoda FROM skenirano_trziste 
        WHERE artikal_id = ? AND sajt_izvora != ? AND sajt_izvora NOT LIKE 'amazon.com%' AND nadjena_cena < ?
        ORDER BY nadjena_cena ASC LIMIT 1
    """, (artikal_id, sajt, cena_na_ekranu))
    
    nadjena_jeftinija_ponuda = cursor.fetchone()
    conn.close()
    
    if nadjena_jeftinija_ponuda:
        cena_jeftinijeg, link_jeftinijeg = nadjena_jeftinija_ponuda
        proracun = lokalni_izracunaj_vortex_cenu(cena_na_ekranu, cena_jeftinijeg)
        if proracun["validno"]:
            return jsonify({
                "akcija": "PRESRRETNI_I_POKAZI_POPUP",
                "ime": ime_artikla[:50],
                "cena": proracun["vortex_cena"],
                "usteda": proracun["usteda"],
                "link_jeftinije": link_jeftinijeg
            })
    return jsonify({"akcija": "nastavi_skeniranje"})

@app.route("/api/vortex-probudi-robota", methods=["GET"])
def probudi_pozadinskog_robota():
    """Ruta koja direktno pokreće integrisanog robota nad poslednjim artiklom"""
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT artikal_id, ime FROM skenirano_trziste 
        WHERE sajt_izvora != 'amazon.com (Vortex Robot)' 
        AND sajt_izvora NOT LIKE 'amazon.com%'
        ORDER BY vreme_skena DESC LIMIT 1
    """)
    artikal = cursor.fetchone()
    conn.close()
    
    if not artikal:
        return jsonify({"status": "greska", "poruka": "Baza je prazna. Skeniraj nesto!"})
        
    artikal_id, pun_naziv = artikal
    reci = pun_naziv.split()
    skraceni_naziv = " ".join(reci[:3]) if len(reci) > 3 else pun_naziv
    
    # Pokrećemo skrepera direktno unutar ovog zahteva (sinhrono)
    izvestaj_rada = lokalni_amazon_skreper(skraceni_naziv, artikal_id)
    return jsonify({"status": "robot_izvrsio_zadatak", "izvestaj": izvestaj_rada})

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
    
    porudzbine_html = "".join([f"<li>👤 <b>{p['kupac_ime']}</b> ({p['telefon']}) - {p['proizvod_ime']} za <span style='color:#27ae60'>{p['cena']} RSD</span><br>🔵 <a href='{p['link_naruceno']}' target='_blank' style='color:#0084ff;text-decoration:none;'>Skuplji link</a> | 🔴 <a href='{p['link_jeftinije']}' target='_blank' style='color:#ff4d4d;font-weight:bold;text-decoration:none;'>Kupi ovde (Jeftinije)</a></li>" for p in porudzbine]) if porudzbine else "<li>Nema novih porudžbina.</li>"
    skenovi_html = "".join([f"<li>📡 SKU: {s['artikal_id']} | <a href='{s['link_proizvoda']}' target='_blank' style='color:#aaa;text-decoration:none;'>{s['ime'][:40]}...</a> | <b>{s['nadjena_cena']} RSD</b> ({s['sajt_izvora']})</li>" for s in skenovi]) if skenovi else "<li>Čeka se signal...</li>"
    
    return f"""
    <html>
    <head><title>Vortex Kontrolni Centar</title></head>
    <body style="font-family: Arial, sans-serif; padding: 30px; background: #111; color: #eee;">
        <h1>⚡ Vortex Globalni Kontrolni Centar</h1>
        <hr style="border-color: #333; margin-bottom: 25px;">
        <div style="display: flex; gap: 30px;">
            <div style="flex: 1; background: #222; padding: 20px; border-radius: 8px; border: 1px solid #333;"><h2>🛒 Pristigle Porudžbine</h2><ul>{porudzbine_html}</ul></div>
            <div style="flex: 1; background: #222; padding: 20px; border-radius: 8px; border: 1px solid #333;"><h2>📡 Uživo Skeniranje Tržišta</h2><ul>{skenovi_html}</ul></div>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    inicijalizuj_globalnu_bazu()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

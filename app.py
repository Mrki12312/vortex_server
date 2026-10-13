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
CORS(app, resources={r"/*": {"origins": "*"}})

BAZA_NAME = "vortex_network_v3.db"
API_TOKEN = "bbf0475d54b54e9cad14c084f462da7152b49164592"

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

@app.route("/api/vortex-background-sync", methods=["POST"])
def pozadinska_sinhronizacija():
    podaci = request.json
    if not podaci: return jsonify({"akcija": "nastavi_skeniranje"})
    
    ime_artikla = podaci.get("ime_proizvoda", "").strip()
    cena_na_ekranu = float(podaci.get("cena", 0))
    sajt = podaci.get("sajt", "Skener")
    trenutni_link = podaci.get("link", "")
    
    if not ime_artikla or cena_na_ekranu == 0: return jsonify({"akcija": "nastavi_skeniranje"})
    
    # Izvlačenje SKU oznake preko čistog teksta
    tekst = ime_artikla.upper()
    skovi_sablon = re.findall(r'\b[A-Z0-9]{3,12}\b', tekst)
    sku_kod = "NEPOZNAT"
    if skovi_sablon:
        for stavka in skovi_sablon:
            if any(c.isdigit() for c in stavka):
                sku_kod = stavka
                break
                
    artikal_id = f"SKU_{sku_kod}"
    
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (artikal_id, ime_artikla, cena_na_ekranu, sajt, trenutni_link, datetime.datetime.now()))
    conn.commit()
    conn.close()
    return jsonify({"akcija": "nastavi_skeniranje", "artikal_id": artikal_id})

@app.route("/api/vortex-probudi-robota", methods=["GET"])
def probudi_pozadinskog_robota():
    """
    Ova ruta se izvršava za 0.1 sekundu! Ona samo prosleđuje nalog Scrape.do mreži
    zajedno sa tvojim Webhook linkom i odmah oslobađa Render server čekanja.
    """
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT artikal_id, ime FROM skenirano_trziste WHERE sajt_izvora != 'amazon.com (Vortex Robot)' ORDER BY vreme_skena DESC LIMIT 1")
    artikal = cursor.fetchone()
    conn.close()
    
    if not artikal: return jsonify({"status": "baza_prazna"})
    
    artikal_id, pun_naziv = artikal
    reci = pun_naziv.split()
    skraceni_naziv = " ".join(reci[:3]) if len(reci) > 3 else pun_naziv
    
    siguran_naziv = urllib.parse.quote(skraceni_naziv)
    target_url = f"https://amazon.com{siguran_naziv}"
    
    # Generišemo tvoj lični Webhook URL koji Scrape.do mora da pozove na kraju
    webhook_url = f"https://onrender.com{artikal_id}"
    siguran_webhook = urllib.parse.quote(webhook_url)
    
    # Šaljemo nalog Scrape.do servisu i stavljamo mu do znanja gde da vrati gotov HTML
    api_url = f"https://scrape.do{API_TOKEN}&url={target_url}&callback={siguran_webhook}"
    
    try:
        requests.get(api_url, timeout=5) # Kratak zahtev, ne čekamo Amazon
        return jsonify({"status": "Vortex nalog uspesno delegiran Scrape.do mrezi! Cekam povratni paket..."})
    except Exception as e:
        return jsonify({"status": "greska_pri_slanju", "detalji": str(e)})

# KAPIJA ZA PRIJEM PODATAKA IZ SCRAPE.DO MREŽE
@app.route("/api/vortex-webhook", methods=["POST"])
def vortex_webhook_prijem():
    """Ovde Scrape.do samostalno ubacuje HTML kod sa Amazona kada završi pretragu"""
    try:
        html_sadrzaj = request.data.decode("utf-8")
        artikal_id = request.args.get("artikal_id", "SKU_NEPOZNAT")
        
        supa = BeautifulSoup(html_sadrzaj, "html.parser")
        kartica = supa.find("div", {"data-component-type": "s-search-result"})
        
        conn = sqlite3.connect(BAZA_NAME)
        cursor = conn.cursor()
        
        if kartica:
            element_cene = kartica.find(class_="a-price-whole")
            element_linka = kartica.find("a", class_="a-link-normal s-no-outline")
            element_naslova = kartica.find("h2")
            
            if element_cene and element_linka and element_naslova:
                ceo_deo = "".join(c for c in element_cene.get_text() if c.isdigit())
                cena_rsd = round(float(ceo_deo or 0) * 108.0, 2)
                puni_link = "https://amazon.com" + element_linka["href"]
                ime_sa_amazona = element_naslova.get_text().strip()
                
                cursor.execute("""
                    INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, ime_sa_amazona[:100], cena_rsd, "amazon.com (Vortex Robot)", puni_link, datetime.datetime.now()))
                conn.commit()
        else:
            # Ako Amazon nema taj pojam, beležimo to na panelu da znamo ishod
            cursor.execute("""
                INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (artikal_id, "Ovaj model trenutno ne postoji na Amazonu", 0, "amazon.com (Nema poklapanja)", "https://amazon.com", datetime.datetime.now()))
            conn.commit()
            
        conn.close()
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route("/")
def administrativni_panel():
    conn = sqlite3.connect(BAZA_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM skenirano_trziste ORDER BY vreme_skena DESC LIMIT 20")
    skenovi = cursor.fetchall()
    conn.close()
    skenovi_html = "".join([f"<li>📡 SKU: {s['artikal_id']} | <a href='{s['link_proizvoda']}' target='_blank' style='color:#aaa;text-decoration:none;'>{s['ime'][:40]}...</a> | <b>{s['nadjena_cena']} RSD</b> ({s['sajt_izvora']})</li>" for s in skenovi]) if skenovi else "<li>Čeka se prvi signal...</li>"
    return f"<html><body style='font-family:Arial;padding:30px;background:#111;color:#eee;'><h1>⚡ Vortex Globalni Kontrolni Centar</h1><hr style='border-color:#333;'><ul>{skenovi_html}</ul></body></html>"

if __name__ == "__main__":
    inicijalizuj_globalnu_bazu()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

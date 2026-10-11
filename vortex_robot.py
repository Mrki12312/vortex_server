import sqlite3
import datetime
import requests
import urllib.parse
from bs4 import BeautifulSoup

# ZAMENI OVDE: Stavi svoj pravi token koji si uzeo sa Scrape.do sajta
API_TOKEN = "bbf0475d54b54e9cad14c084f462da7152b49164592"

def pokreni_amazon_skreper_za_proizvod(pun_naziv, artikal_id):
    """
    Profesionalni robot koji koristi Scrape.do API kako bi 100% zaobišao 
    Amazonovu zaštitu (CAPTCHA) i bezbedno doneo cenu u bazu.
    """
    # Čistimo naziv proizvoda za URL pretragu
    siguran_naziv = urllib.parse.quote(pun_naziv)
    target_url = f"https://amazon.com{siguran_naziv}"
    
    # Kreiramo API URL preko Scrape.do servisa
    api_url = f"https://scrape.do{API_TOKEN}&url={target_url}"
    
    print(f"[VORTEX ROBOT] Šaljem bezbedan API zahtev za: {pun_naziv[:30]}...")
    
    try:
        # Scrape.do preuzima na sebe rotaciju proksija i rešavanje zaštite
        odgovor = requests.get(api_url, timeout=30)
        
        if odgovor.status_code != 200:
            print(f"[VORTEX ROBOT GRESKA] API je vratio status: {odgovor.status_code}")
            return False
            
        supa = BeautifulSoup(odgovor.text, "html.parser")
        
        # Tražimo prvu glavnu karticu proizvoda u Amazon rezultatima
        kartica = supa.find("div", {"data-component-type": "s-search-result"})
        
        if kartica:
            element_cene = kartica.find(class_="a-price-whole")
            element_centi = kartica.find(class_="a-price-fraction")
            element_linka = kartica.find("a", class_="a-link-normal s-no-outline")
            element_naslova = kartica.find("h2")
            
            if element_cene and element_linka and element_naslova:
                # Izvlačenje i čišćenje cifara
                ceo_deo = "".join(c for c in element_cene.get_text() if c.isdigit())
                centi_deo = "".join(c for c in element_centi.get_text() if c.isdigit()) if element_centi else "00"
                
                if not ceo_deo: ceo_deo = "0"
                
                cena_dolar = float(f"{ceo_deo}.{centi_deo}")
                cena_rsd = round(cena_dolar * 108.0, 2) # Pretvaranje dolara u dinare
                
                puni_link = "https://amazon.com" + element_linka["href"]
                ime_sa_amazona = element_naslova.get_text().strip()
                
                trenutno_vreme = datetime.datetime.now()
                
                # Upisujemo bezbedno u SQLite bazu podataka na serveru
                conn = sqlite3.connect("vortex_network.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, ime_sa_amazona[:100], cena_rsd, "amazon.com (Vortex Robot)", puni_link, trenutno_vreme))
                conn.commit()
                conn.close()
                
                print(f"[VORTEX ROBOT] USPEH! API uspešno zaobišao odbranu. {artikal_id} upisan za {cena_rsd} RSD.")
                return True
        else:
            print("[VORTEX ROBOT] Amazon rezultati su stigli, ali nema direktnog poklapanja za ovaj proizvod.")
            
    except Exception as e:
        print(f"[VORTEX ROBOT EROR] Problem pri komunikaciji sa API-jem: {e}")
    return False

def pokreni_masovno_rudarenje():
    """Uzima poslednji skenirani artikal i preko API-ja traži cenu na Amazonu"""
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT artikal_id, ime FROM skenirano_trziste 
        WHERE sajt_izvora != 'amazon.com (Vortex Robot)' 
        ORDER BY vreme_skena DESC LIMIT 1
    """)
    artikal = cursor.fetchone()
    conn.close()
    
    if not artikal:
        print("[VORTEX ROBOT] Baza prazna, nema artikala za pretragu.")
        return
        
    artikal_id, pun_naziv = artikal
    reci = pun_naziv.split()
    # Uzimamo prve 4 reči (Brend i Model) jer to daje najbolji rezultat na Amazonu
    skraceni_naziv = " ".join(reci[:4]) if len(reci) > 4 else pun_naziv
    
    pokreni_amazon_skreper_za_proizvod(skraceni_naziv, artikal_id)

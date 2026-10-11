import sqlite3
import datetime
import requests
import urllib.parse
from bs4 import BeautifulSoup

ZAGLAVLJA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://google.com"
}

def pokreni_amazon_skreper_za_proizvod(pun_naziv, artikal_id):
    """
    Napredni robot koji pretražuje Amazon koristeći puni naziv proizvoda 
    kako bi izbegao nasumične rezultate i pogodio pravu alternativu.
    """
    # Čistimo naziv za URL (menjamo razmake u %20)
    siguran_naziv = urllib.parse.quote(pun_naziv)
    url_pretrage = f"https://amazon.com{siguran_naziv}"
    
    try:
        odgovor = requests.get(url_pretrage, headers=ZAGLAVLJA, timeout=12)
        if odgovor.status_code != 200:
            print(f"[VORTEX ROBOT] Amazon je privremeno odbio pristup (Status: {odgovor.status_code})")
            return False
            
        supa = BeautifulSoup(odgovor.text, "html.parser")
        
        # Tražimo prvu glavnu karticu proizvoda na Amazonu
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
                cena_rsd = round(cena_dolar * 108.0, 2) # Pretvaranje u dinare
                
                puni_link = "https://amazon.com" + element_linka["href"]
                ime_sa_amazona = element_naslova.get_text().strip()
                
                trenutno_vreme = datetime.datetime.now()
                
                # Upisujemo bezbedno u SQLite bazu pod originalnim ID-em
                conn = sqlite3.connect("vortex_network.db")
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, ime_sa_amazona[:100], cena_rsd, "amazon.com (Vortex Robot)", puni_link, trenutno_vreme))
                conn.commit()
                conn.close()
                
                print(f"[VORTEX ROBOT] USPEH! Pronađena alternativa za {artikal_id} za {cena_rsd} RSD.")
                return True
        else:
            print(f"[VORTEX ROBOT] Amazon nije vratio direktne rezultate za upit: {pun_naziv[:30]}")
            
    except Exception as e:
        print(f"[VORTEX ROBOT EROR] Problem pri skeniranju: {e}")
    return False

def pokreni_masovno_rudarenje():
    """Prolazi kroz poslednje skenirane artikle i traži njihove nazive na Amazonu"""
    print("[VORTEX ROBOT] Pokrećem masovno rudarenje...")
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    
    # Uzimamo naziv i ID poslednjih artikala koje su skenirali korisnici, a koji nisu sa Amazona
    cursor.execute("""
        SELECT artikal_id, ime FROM skenirano_trziste 
        WHERE sajt_izvora != 'amazon.com (Vortex Robot)' 
        ORDER BY vreme_skena DESC LIMIT 5
    """)
    artikli = cursor.fetchall()
    conn.close()
    
    if not artikli:
        print("[VORTEX ROBOT] Nema artikala u bazi za osvežavanje.")
        return
        
    for artikal in artikli:
        artikal_id, pun_naziv = artikal
        # Skraćujemo naziv na optimalne prve 4 reči kako bi Amazon pretraga bila uspešna (Brend + Model)
        reci = pun_naziv.split()
        skraceni_naziv_za_pretragu = " ".join(reci[:4]) if len(reci) > 4 else pun_naziv
        
        print(f"[VORTEX ROBOT] Tražim na Amazonu: {skraceni_naziv_za_pretragu}")
        pokreni_amazon_skreper_za_proizvod(skraceni_naziv_za_pretragu, artikal_id)

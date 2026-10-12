import sqlite3
import datetime
import requests
import urllib.parse
from bs4 import BeautifulSoup

# Tvoj aktivni Scrape.do token
API_TOKEN = "bbf0475d54b54e9cad14c084f462da7152b49164592"
BAZA_NAME = "vortex_network_v2.db"

def pokreni_amazon_skreper_za_proizvod(pun_naziv, artikal_id):
    """
    Profesionalni robot koji koristi tvoj Scrape.do token za bezbedno
    zaobilaženje Amazon zaštite. Uzima ime sa Ananasa, pronalazi cenu na Amazonu
    i ispisuje je na tvoju kontrolnu tablu.
    """
    # Čistimo naziv proizvoda za URL pretragu
    siguran_naziv = urllib.parse.quote(pun_naziv)
    target_url = f"https://amazon.com{siguran_naziv}"
    
    # Ispravna struktura Scrape.do API linka za pretragu tekstualnih pojmova
    api_url = f"https://scrape.do{API_TOKEN}&url={target_url}"
    
    print(f"[VORTEX ROBOT] Pokrećem API pretragu na Amazonu za: {pun_naziv[:30]}...")
    
    try:
        odgovor = requests.get(api_url, timeout=30)
        if odgovor.status_code != 200:
            print(f"[VORTEX ROBOT GRESKA] Scrape.do je vratio status: {odgovor.status_code}")
            return False
            
        supa = BeautifulSoup(odgovor.text, "html.parser")
        
        # POPRAVLJENO: Koristi se BeautifulSoup .find() umesto JS selektora
        kartica = supa.find("div", {"data-component-type": "s-search-result"})
        
        if kartica:
            element_cene = kartica.find(class_="a-price-whole")
            element_centi = kartica.find(class_="a-price-fraction")
            element_linka = kartica.find("a", class_="a-link-normal s-no-outline")
            element_naslova = kartica.find("h2")
            
            if element_cene and element_linka and element_naslova:
                # Izvlačenje i čišćenje cifara iz teksta
                ceo_deo = "".join(c for c in element_cene.get_text() if c.isdigit())
                centi_deo = "".join(c for c in element_centi.get_text() if c.isdigit()) if element_centi else "00"
                
                if not ceo_deo: 
                    ceo_deo = "0"
                
                cena_dolar = float(f"{ceo_deo}.{centi_deo}")
                cena_rsd = round(cena_dolar * 108.0, 2)  # Automatska konverzija u dinare
                
                puni_link = "https://amazon.com" + element_linka["href"]
                ime_sa_amazona = element_naslova.get_text().strip()
                trenutno_vreme = datetime.datetime.now()
                
                # Upisujemo direktno u tabelu na tvojoj kontrolnoj tabli
                conn = sqlite3.connect(BAZA_NAME)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, ime_sa_amazona[:100], cena_rsd, "amazon.com (Vortex Robot)", puni_link, trenutno_vreme))
                conn.commit()
                conn.close()
                
                print(f"[VORTEX ROBOT] USPEH! Model {artikal_id} upisan sa Amazona za {cena_rsd} RSD.")
                return True
        else:
            print("[VORTEX ROBOT UPOZORENJE] Stranica uspešno učitana, ali Amazon nije vratio direktnu karticu proizvoda.")
            
    except Exception as e:
        print(f"[VORTEX ROBOT EROR] Problem pri čitanju podataka: {e}")
    return False

def pokreni_masovno_rudarenje():
    """Čita poslednji artikal koji je poslala ekstenzija i pokreće upit ka Amazonu"""
    conn = sqlite3.connect(BAZA_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT artikal_id, ime FROM skenirano_trziste 
        WHERE sajt_izvora != 'amazon.com (Vortex Robot)' 
        ORDER BY vreme_skena DESC LIMIT 1
    """)
    artikal = cursor.fetchone()
    conn.close()
    
    if not artikal:
        print("[VORTEX ROBOT] Baza je prazna. Prvo pogledaj neki artikal na Ananasu sa uključenom ekstenzijom!")
        return
        
    artikal_id, pun_naziv = artikal
    reci = pun_naziv.split()
    # Uzimamo prve 4 reči (brend i oznaku) za maksimalno čistu pretragu na Amazonu
    skraceni_naziv = " ".join(reci[:4]) if len(reci) > 4 else pun_naziv
    pokreni_amazon_skreper_za_proizvod(skraceni_naziv, artikal_id)

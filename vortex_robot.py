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
    Profesionalni robot koji preko Scrape.do zaobilazi zaštitu Amazona.
    Ako ne nađe proizvod, upisuje obaveštenje na panel.
    """
    siguran_naziv = urllib.parse.quote(pun_naziv)
    target_url = f"https://amazon.com{siguran_naziv}"
    api_url = f"https://scrape.do{API_TOKEN}&url={target_url}"
    
    print(f"[VORTEX ROBOT] Pokrećem API pretragu na Amazonu za: {pun_naziv[:30]}")
    
    try:
        odgovor = requests.get(api_url, timeout=30)
        trenutno_vreme = datetime.datetime.now()
        
        if odgovor.status_code != 200:
            return False
            
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
                
                if not ceo_deo: ceo_deo = "0"
                
                cena_dolar = float(f"{ceo_deo}.{centi_deo}")
                cena_rsd = round(cena_dolar * 108.0, 2)
                
                puni_link = "https://amazon.com" + element_linka["href"]
                ime_sa_amazona = element_naslova.get_text().strip()
                
                cursor.execute("""
                    INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, ime_sa_amazona[:100], cena_rsd, "amazon.com (Vortex Robot)", puni_link, trenutno_vreme))
                conn.commit()
                print(f"[VORTEX ROBOT] USPEH! Model {artikal_id} dodat sa Amazona.")
            else:
                # Ako elementi cene nisu ispravni
                cursor.execute("""
                    INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, f"Greška u formatu cene za: {pun_naziv[:20]}", 0, "amazon.com (Nema Cene)", target_url, trenutno_vreme))
                conn.commit()
        else:
            # SLUČAJ KADA AMAZON NEMA TAJ ARTIKAL: Upisujemo obaveštenje na panel
            cursor.execute("""
                INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (artikal_id, f"Proizvod nije lociran na američkom tržištu", 0, "amazon.com (Nema na stanju)", target_url, trenutno_vreme))
            conn.commit()
            print("[VORTEX ROBOT] Amazon nema ovaj proizvod u ponudi.")
            
        conn.close()
        return True
    except Exception as e:
        print(f"[VORTEX ROBOT GRESKA] Greška: {e}")
    return False

def pokreni_masovno_rudarenje():
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
        return
        
    artikal_id, pun_naziv = artikal
    reci = pun_naziv.split()
    # Uzimamo prve 3 reči (čist brend) jer to drastično povećava šansu da Amazon izbaci bilo kakav rezultat
    skraceni_naziv = " ".join(reci[:3]) if len(reci) > 3 else pun_naziv
    pokreni_amazon_skreper_za_proizvod(skraceni_naziv, artikal_id)

import sqlite3
import datetime
import requests
import urllib.parse
from bs4 import BeautifulSoup

API_TOKEN = "bbf0475d54b54e9cad14c084f462da7152b49164592"
BAZA_NAME = "vortex_network_v2.db"

def pokreni_amazon_skreper_za_proizvod(pun_naziv, artikal_id):
    siguran_naziv = urllib.parse.quote(pun_naziv)
    target_url = f"https://amazon.com{siguran_naziv}"
    api_url = f"https://scrape.do{API_TOKEN}&url={target_url}"
    
    try:
        odgovor = requests.get(api_url, timeout=30)
        trenutno_vreme = datetime.datetime.now()
        
        if odgovor.status_code != 200:
            return f"Greška proksija: status {odgovor.status_code}"
            
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
                return f"Uspeh! Upisana cena {cena_rsd} RSD za model {artikal_id}"
            else:
                cursor.execute("""
                    INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (artikal_id, f"Format cene nevažeći za: {pun_naziv[:20]}", 0, "amazon.com (Nema Cene)", target_url, trenutno_vreme))
                conn.commit()
                conn.close()
                return "Artikal nađen, ali struktura cene na Amazonu je nečitljiva."
        else:
            cursor.execute("""
                INSERT INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (artikal_id, "Proizvod nije lociran na američkom tržištu", 0, "amazon.com (Nema na stanju)", target_url, trenutno_vreme))
            conn.commit()
            conn.close()
            return "Amazon je vratio praznu stranicu za ovaj pojam."
            
    except Exception as e:
        return f"Sistemski prekid rada robota: {str(e)}"

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
        return "Baza podataka na serveru je potpuno prazna."
        
    artikal_id, pun_naziv = artikal
    reci = pun_naziv.split()
    skraceni_naziv = " ".join(reci[:3]) if len(reci) > 3 else pun_naziv
    
    return pokreni_amazon_skreper_za_proizvod(skraceni_naziv, artikal_id)

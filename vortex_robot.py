import sqlite3
import datetime
import requests
from bs4 import BeautifulSoup
from vortex_engine import izvuci_univerzalni_sku

# Koristimo stabilna User-Agent zaglavlja da nas Amazon ne bi blokirao
ZAGLAVLJA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

def pokreni_amazon_skreper_za_sku(sku_kod):
    """
    Pozadinski robot koji samostalno pretražuje Amazon preko šifre modela,
    izvlači cenu, pretvara je u RSD i skladišti u bazu podataka.
    """
    url_pretrage = f"https://amazon.com{sku_kod}"
    
    try:
        odgovor = requests.get(url_pretrage, headers=ZAGLAVLJA, timeout=10)
        if odgovor.status_code != 200:
            print(f"[VORTEX ROBOT] Amazon je blokirao zahtev za SKU: {sku_kod}")
            return False
            
        supa = BeautifulSoup(odgovor.text, "html.parser")
        
        # Pronalaženje elemenata na Amazon stranici rezultata
        element_cene = supa.find(class_="a-price-whole")
        element_centi = supa.find(class_="a-price-fraction")
        element_linka = supa.find(class_="a-link-normal s-no-outline")
        element_naslova = supa.find("h2")
        
        if element_cene and element_linka and element_naslova:
            # ISPRAVLJENO: Čist Python način za uklanjanje svega što nisu cifre
            ceo_deo = "".join(c for c in element_cene.get_text() if c.isdigit())
            centi_deo = "".join(c for c in element_centi.get_text() if c.isdigit()) if element_centi else "00"
            
            if not ceo_deo:
                ceo_deo = "0"
                
            cena_dolar = float(f"{ceo_deo}.{centi_deo}")
            cena_rsd = round(cena_dolar * 108.0, 2) # Preračunavanje u dinare
            
            puni_link = "https://amazon.com" + element_linka["href"]
            ime_proizvoda = element_naslova.get_text().strip()
            
            # Skladištenje u lokalnu bazu podataka na serveru
            artikal_id = f"SKU_{sku_kod}"
            trenutno_vreme = datetime.datetime.now()
            
            conn = sqlite3.connect("vortex_network.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (artikal_id, ime_proizvoda, cena_rsd, "amazon.com (Vortex Robot)", puni_link, trenutno_vreme))
            conn.commit()
            conn.close()
            
            print(f"[VORTEX ROBOT] Uspeh! Model {sku_kod} lociran na Amazonu za {cena_rsd} RSD.")
            return True
            
    except Exception as e:
        print(f"[VORTEX ROBOT EROR] Greška pri skeniranju modela {sku_kod}: {e}")
        
    return False

def pokreni_masovno_rudarenje():
    """Prolazi kroz sve šifre koje su korisnici ikada skenirali i ažurira Amazon cene"""
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT artikal_id FROM skenirano_trziste WHERE sajt_izvora != 'amazon.com (Vortex Robot)'")
    artikli = cursor.fetchall()
    conn.close()
    
    if not artikli:
        print("[VORTEX ROBOT] Baza je trenutno prazna. Čekam prvi signal sa ekstenzije...")
        return
        
    print(f"[VORTEX ROBOT] Započinjem osvežavanje tržišta za {len(artikli)} modela...")
    for artikal in artikli:
        sku = artikal[0].replace("SKU_", "")
        pokreni_amazon_skreper_za_sku(sku)

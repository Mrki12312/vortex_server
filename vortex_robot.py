import sqlite3
import requests
import urllib.parse

API_TOKEN = "bbf0475d54b54e9cad14c084f462da7152b49164592"
BAZA_NAME = "vortex_network_v2.db"

def pokreni_amazon_skreper_za_proizvod(pun_naziv, artikal_id):
    siguran_naziv = urllib.parse.quote(pun_naziv)
    target_url = f"https://amazon.com{siguran_naziv}"
    
    # Kreiramo povratni link (Webhook) koji vodi pravo u našu aplikaciju na Renderu
    webhook_url = f"https://onrender.com{artikal_id}"
    siguran_webhook = urllib.parse.quote(webhook_url)
    
    # Šaljemo asinhroni zahtev: Scrape.do će sam izvršiti pretragu i vratiti podatke na naš Webhook
    api_url = f"https://scrape.do{API_TOKEN}&url={target_url}&callback={siguran_webhook}"
    
    try:
        odgovor = requests.get(api_url, timeout=15)
        if odgovor.status_code == 200 or odgovor.status_code == 202:
            return f"Zahtev za model {artikal_id} uspešno delegiran Scrape.do mreži."
        else:
            return f"Proksi odbio delegaciju: status {odgovor.status_code}"
    except Exception as e:
        return f"Greška pri slanju naloga: {str(e)}"

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
        return "Baza je prazna, nema artikala."
        
    artikal_id, pun_naziv = artikal
    reci = pun_naziv.split()
    skraceni_naziv = " ".join(reci[:3]) if len(reci) > 3 else pun_naziv
    
    return pokreni_amazon_skreper_za_proizvod(skraceni_naziv, artikal_id)

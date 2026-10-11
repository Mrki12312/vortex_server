import sqlite3
import datetime
from vortex_engine import izvuci_univerzalni_sku

def unesi_jeftinu_robu_u_vortex_bazu(ime_artikla, cena_u_dolarima, link_izvora):
    """
    Ova skripta simulira rad tvog robota koji puni bazu jeftinim cenama sa Amazona.
    Pretvara dolare u dinare i upisuje artikle pod istim SKU kodom.
    """
    sku_kod = izvuci_univerzalni_sku(ime_artikla)
    artikal_id = f"SKU_{sku_kod}"
    
    # Preračunavamo dolare u dinare (1 USD = 108 RSD)
    cena_u_rsd = round(cena_u_dolarima * 108.0, 2)
    vreme_unosa = datetime.datetime.now()
    
    conn = sqlite3.connect("vortex_network.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO skenirano_trziste (artikal_id, ime, nadjena_cena, sajt_izvora, link_proizvoda, vreme_skena)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (artikal_id, ime_artikla, cena_u_rsd, "amazon.com (Vortex Robot)", link_izvora, vreme_unosa))
    
    conn.commit()
    conn.close()
    print(f"[ROBOT] Uspešno uneta jeftina alternativa! Model: {sku_kod} | Cena: {cena_u_rsd} RSD")

# POKRETANJE SIMULACIJE ROBOTA ZA TVOJU SLIKU:
if __name__ == "__main__":
    # Robot unosi da se ta ista slika (sa istom šifrom modela MDF3930295) nalazi na Amazonu za samo 4 dolara (oko 430 RSD)
    unesi_jeftinu_robu_u_vortex_bazu(
        ime_artikla="Wallity Set slika MDF3930295 3 Dela Black Canvas",
        cena_u_dolarima=4.00,
        link_izvora="https://amazon.com"
    )

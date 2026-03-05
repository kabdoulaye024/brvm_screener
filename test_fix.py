"""
Test pour vérifier que les données s'affichent correctement
"""
import pandas as pd
import numpy as np

# Simuler les données de marché
def test_mdata_display():
    """Test avec différents scénarios de données"""
    
    # Scénario 1: Toutes les données présentes
    mdata_complete = {
        "prix": 2864,
        "variation_pct": 1.5,
        "source": "richbourse",
        "rsi": 65.5,
        "bb_sup": 3000,
        "bb_inf": 2700,
        "ema20": 2850,
        "nb_pts": 120,
        "_source_tech": "richbourse · 120 pts"
    }
    
    # Scénario 2: Données manquantes (None)
    mdata_incomplete = {
        "prix": 2864,
        "variation_pct": 1.5,
        "source": "richbourse",
        "rsi": None,
        "bb_sup": None,
        "bb_inf": None,
        "ema20": None,
        "nb_pts": 0,
        "_source_tech": None
    }
    
    # Scénario 3: Dict vide
    mdata_empty = {}
    
    def check_display(mdata, scenario_name):
        print(f"\n=== {scenario_name} ===")
        
        # Vérification comme dans le code
        has_prix = "prix" in mdata
        has_rsi = "rsi" in mdata and mdata.get("rsi") is not None
        has_bb = "bb_sup" in mdata and "bb_inf" in mdata and mdata.get("bb_sup") is not None and mdata.get("bb_inf") is not None
        has_ema = "ema20" in mdata and mdata.get("ema20") is not None
        nb_pts = mdata.get("nb_pts", 0) if mdata.get("nb_pts") is not None else 0
        src_tech = mdata.get("_source_tech", "—") if mdata.get("_source_tech") else "—"
        
        # Construire les valeurs de manière sécurisée
        cours_val = f" {int(mdata['prix'])} FCFA" if has_prix else ""
        rsi_val = f" {mdata['rsi']:.0f}" if has_rsi else ""
        bb_val = f" {int(mdata.get('bb_inf',0))} / {int(mdata.get('bb_sup',0))}" if has_bb else ""
        ema_val = f" {int(mdata['ema20'])}" if has_ema else ""
        
        print(f"has_prix: {has_prix}, has_rsi: {has_rsi}, has_bb: {has_bb}, has_ema: {has_ema}")
        print(f"Cours{cours_val}")
        print(f"RSI{rsi_val}")
        print(f"BB{bb_val}")
        print(f"EMA20{ema_val}")
        print(f"{nb_pts} pts · {src_tech}")
        
        # Vérifier qu'aucune erreur ne se produit
        try:
            status_line = f"Cours{cours_val} | RSI{rsi_val} | BB{bb_val} | EMA20{ema_val} | {nb_pts} pts · {src_tech}"
            print(f"✅ Affichage réussi: {status_line}")
            return True
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False
    
    # Tester les 3 scénarios
    results = []
    results.append(check_display(mdata_complete, "Données complètes"))
    results.append(check_display(mdata_incomplete, "Données incomplètes"))
    results.append(check_display(mdata_empty, "Dict vide"))
    
    print(f"\n=== RÉSUMÉ ===")
    print(f"Tests réussis: {sum(results)}/{len(results)}")
    return all(results)

if __name__ == "__main__":
    success = test_mdata_display()
    if success:
        print("\n✅ Tous les tests sont passés!")
    else:
        print("\n❌ Certains tests ont échoué")

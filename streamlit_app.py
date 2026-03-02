import streamlit as st 
import pandas as pd
import numpy as np
import sqlite3
import json
import requests
from io import BytesIO, StringIO
from datetime import datetime, date
import warnings
warnings.filterwarnings("ignore")

# pandas-ta optionnel — fallback calcul manuel si non installé
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

# ==========================================================
# CONFIGURATION
# ==========================================================
st.set_page_config(page_title="Screener BRVM", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; }
    .stApp { background-color: #0d1117; color: #e6edf3; }
    div[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 16px 20px; margin: 8px 0; }
    .card-green  { border-left: 4px solid #3fb950; }
    .card-blue   { border-left: 4px solid #79c0ff; }
    .card-yellow { border-left: 4px solid #d29922; }
    .card-red    { border-left: 4px solid #f85149; }
    .alert-red    { background: #2d1b1b; border: 1px solid #f85149; border-radius: 8px; padding: 13px 17px; margin: 8px 0; color: #ffa198; font-weight: 600; }
    .alert-yellow { background: #2d2500; border: 1px solid #d29922; border-radius: 8px; padding: 13px 17px; margin: 8px 0; color: #e3b341; font-weight: 600; }
    .alert-green  { background: #1b2d1b; border: 1px solid #3fb950; border-radius: 8px; padding: 13px 17px; margin: 8px 0; color: #7ee787; font-weight: 600; }
    .alert-estimated { background: #1a1f2e; border: 1px solid #79c0ff; border-radius: 8px; padding: 12px 16px; margin: 8px 0; color: #a5d6ff; }
    .alert-info { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; margin: 8px 0; color: #8b949e; }
    .ratio-box { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 10px 14px; margin: 4px 0; font-family: 'IBM Plex Mono', monospace; font-size: 0.88em; }
    .filter-block { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 14px 18px; margin: 6px 0; }
    .label-small { color: #8b949e; font-size: 0.78em; }
    .stButton>button { background: #238636; color: white; border: none; border-radius: 6px; font-family: 'IBM Plex Mono', monospace; font-weight: 600; width: 100%; padding: 10px; }
    .stButton>button:hover { background: #2ea043; }
    .tooltip-text { color: #8b949e; font-size: 0.77em; font-style: italic; margin: -4px 0 6px 0; }
    .section-header { font-family: 'IBM Plex Mono', monospace; font-size: 0.8em; color: #8b949e; text-transform: uppercase; letter-spacing: 2px; border-bottom: 1px solid #30363d; padding-bottom: 6px; margin: 18px 0 10px 0; }
    .badge-estimated { display: inline-block; background: #1f3a5f; color: #79c0ff; border: 1px solid #79c0ff; border-radius: 10px; padding: 1px 8px; font-size: 0.72em; font-weight: 700; margin-left: 6px; vertical-align: middle; }
    .badge-annuel { display: inline-block; background: #1b2d1b; color: #3fb950; border: 1px solid #3fb950; border-radius: 10px; padding: 1px 8px; font-size: 0.72em; font-weight: 700; margin-left: 6px; vertical-align: middle; }
    .badge-auto { display: inline-block; background: #1b2b1b; color: #3fb950; border: 1px solid #3fb950; border-radius: 10px; padding: 1px 8px; font-size: 0.72em; font-weight: 700; margin-left: 6px; vertical-align: middle; }
    .badge-manual { display: inline-block; background: #2d2500; color: #d29922; border: 1px solid #d29922; border-radius: 10px; padding: 1px 8px; font-size: 0.72em; font-weight: 700; margin-left: 6px; vertical-align: middle; }
    .form-divider { border: none; border-top: 1px solid #30363d; margin: 16px 0; }
    .saved-chip { display: inline-block; background: #1f3a5f; color: #79c0ff; border: 1px solid #79c0ff; border-radius: 12px; padding: 2px 10px; font-size: 0.75em; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SESSION STATE
# ==========================================================
for key, val in [
    ("actions", []),
    ("secteur_sel", "Télécommunications"),
    ("periode_sel", "Annuel complet (2024 ou 2025)"),
    ("annee_sel", "2025"),
    ("marche_cache", {}),       # cache cours brvm.org
    ("marche_cache_date", None),
]:
    if key not in st.session_state:
        st.session_state[key] = val

# ==========================================================
# RÉFÉRENTIELS
# ==========================================================
PER_SECTORIELS = {
    "Télécommunications":                   10.11,
    "Consommation discrétionnaire":         72.48,
    "Services Financiers":                  11.08,
    "Consommation de base (hors Unilever)": 14.80,
    "Industriels":                          22.23,
    "Énergie":                              17.63,
    "Services Publics":                     17.65,
}
PER_CAP_SCORE    = {s: min(p, 25) for s, p in PER_SECTORIELS.items()}
SECTEUR_BANCAIRE = "Services Financiers"

TAUX_DCF_SECTEUR = {
    "Télécommunications":                   0.11,
    "Consommation discrétionnaire":         0.13,
    "Services Financiers":                  0.11,
    "Consommation de base (hors Unilever)": 0.12,
    "Industriels":                          0.14,
    "Énergie":                              0.13,
    "Services Publics":                     0.11,
}

SAISONNALITE_S1 = {
    "Télécommunications":                   0.50,
    "Consommation discrétionnaire":         0.45,
    "Services Financiers":                  0.48,
    "Consommation de base (hors Unilever)": 0.48,
    "Industriels":                          0.45,
    "Énergie":                              0.52,
    "Services Publics":                     0.50,
}

BENCH_BANQUE = {
    "cout_risque_max":    0.03,
    "cout_risque_cible":  0.01,
    "credits_depots_min": 0.60,
    "credits_depots_max": 1.00,
    "credits_depots_opt": 0.80,
    "roe_cible":          0.15,
    "marge_nette_cible":  0.20,
}

COULEURS = {
    "🟢 FORT ACHAT":                       "#3fb950",
    "🔵 ACHAT":                            "#79c0ff",
    "🟡 SURVEILLER":                       "#d29922",
    "🟡 SURVEILLER (prix > cible Graham)": "#d29922",
    "🟠 ALLÉGER":                          "#ffa657",
    "🔴 SORTIR":                           "#f85149",
    "🔴 HORS MARGE — Ne pas acheter":      "#f85149",
    "🔴 BLOQUÉ — RSI surachat":            "#f85149",
    "🔴 BLOQUÉ — Prix > BB supérieure":    "#f85149",
}

HEADERS_HTTP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# Tickers officiels richbourse.com (pour valider les saisies)
# Format : ticker BRVM standard (ex: SNTS, SGBC, BOAC…)
RICHBOURSE_BASE = "https://www.richbourse.com"

# ==========================================================
# BASE DE DONNÉES SQLITE — Persistance fondamentaux
# ==========================================================
DB_PATH = "fondamentaux_brvm.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fondamentaux (
            ticker            TEXT PRIMARY KEY,
            secteur           TEXT,
            periode           TEXT,
            annee             TEXT,
            est_banque        INTEGER DEFAULT 0,
            -- Commun
            nombre_actions    REAL,
            dividende         REAL,
            bpa_prec          REAL,
            capitaux_propres  REAL,
            -- Standard seulement
            resultat          REAL,
            total_actif       REAL,
            dettes_totales    REAL,
            stabilite_bpa     TEXT,
            -- Bancaire seulement
            pnb               REAL,
            resultat_b        REAL,
            encours_credits   REAL,
            depots_clientele  REAL,
            -- Metadata
            maj_at            TEXT,
            notes             TEXT
        )
    """)
    conn.commit()
    return conn

def save_fondamentaux(ticker, data: dict):
    conn = get_db()
    data["ticker"]  = ticker.upper()
    data["maj_at"]  = datetime.now().strftime("%Y-%m-%d %H:%M")
    cols   = ", ".join(data.keys())
    placeh = ", ".join(["?" for _ in data])
    vals   = list(data.values())
    conn.execute(
        f"INSERT OR REPLACE INTO fondamentaux ({cols}) VALUES ({placeh})",
        vals
    )
    conn.commit()
    conn.close()

def load_fondamentaux(ticker: str) -> dict | None:
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM fondamentaux WHERE ticker = ?",
            (ticker.upper(),)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None

def list_tickers_sauvegardes() -> list[str]:
    try:
        conn = get_db()
        rows = conn.execute("SELECT ticker, secteur, maj_at FROM fondamentaux ORDER BY maj_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def delete_fondamentaux(ticker: str):
    conn = get_db()
    conn.execute("DELETE FROM fondamentaux WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    conn.close()

# ==========================================================
# SCRAPING — richbourse.com (source principale)
# ==========================================================
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

import re as _re


@st.cache_data(ttl=1800, show_spinner=False)  # cache 30 min
def fetch_cours_richbourse(ticker: str) -> dict:
    """
    Scrape le cours actuel + variation depuis la page palmares de richbourse.com.
    URL : richbourse.com/common/variation/index  (tableau HTML)
    Retourne dict: {prix, variation_pct, volume} ou {}
    """
    url = f"{RICHBOURSE_BASE}/common/variation/index"
    try:
        resp = requests.get(url, headers=HEADERS_HTTP, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        tk = ticker.upper()
        for df in tables:
            df.columns = [str(c).strip().lower() for c in df.columns]
            # Cherche la colonne ticker/code + cours
            col_tk  = next((c for c in df.columns if any(k in c for k in ["ticker","code","valeur","action"])), None)
            col_px  = next((c for c in df.columns if any(k in c for k in ["cours","clôture","dernier","close"])), None)
            col_var = next((c for c in df.columns if any(k in c for k in ["variation","var","évolution","%"])), None)
            if col_tk and col_px:
                row = df[df[col_tk].astype(str).str.upper().str.strip() == tk]
                if not row.empty:
                    def clean_num(v):
                        return float(str(v).replace(" ","").replace(",",".").replace("\xa0","").replace("%","").strip())
                    prix_val = clean_num(row[col_px].values[0])
                    var_val  = clean_num(row[col_var].values[0]) if col_var else 0.0
                    return {"prix": prix_val, "variation_pct": var_val}
    except Exception:
        pass
    return {}


@st.cache_data(ttl=600, show_spinner=False)  # cache 10 min — indicateurs frais
def fetch_tech_richbourse(ticker: str) -> dict:
    """
    Scrape la page de prévision/synthèse richbourse.com qui expose
    les indicateurs techniques déjà calculés en texte HTML.

    URL : richbourse.com/common/prevision-boursiere/synthese/TICKER

    Extrait :
      - RSI 14 (valeur numérique)
      - Position par rapport aux BB (au-dessus sup / en-dessous inf / dans les bandes)
      - EMA20 (depuis historique si nécessaire)
      - Variation 1 semaine
      - Tendance + confiance
    """
    if not HAS_BS4:
        return {"source_tech": "manuel", "_erreur": "beautifulsoup4 non installé"}

    url = f"{RICHBOURSE_BASE}/common/prevision-boursiere/synthese/{ticker.upper()}"
    try:
        resp = requests.get(url, headers=HEADERS_HTTP, timeout=15)
        if resp.status_code != 200:
            return {"source_tech": "manuel"}

        soup = BeautifulSoup(resp.text, "html.parser")
        texte = soup.get_text(" ", strip=True)

        result = {"source_tech": "auto_synthese"}

        # ── RSI ─────────────────────────────────────────────
        m_rsi = _re.search(r"RSI\s*14\s*jours\s*est\s*de\s*([\d,\.]+)\s*%", texte, _re.IGNORECASE)
        if m_rsi:
            result["rsi"] = float(m_rsi.group(1).replace(",", "."))

        # ── Bollinger — position qualitative ────────────────
        if "au-dessus de la bande supérieure" in texte.lower() or "bande supérieure de bollinger" in texte.lower():
            result["bb_position"] = "above_sup"
        elif "en-dessous de la bande inférieure" in texte.lower() or "bande inférieure de bollinger" in texte.lower():
            result["bb_position"] = "below_inf"
        else:
            result["bb_position"] = "inside"

        # ── EMA20 — position qualitative ────────────────────
        if "au-dessus de leur moyenne mobile à 20" in texte.lower():
            result["ema20_position"] = "above"
        elif "en-dessous de leur moyenne mobile à 20" in texte.lower():
            result["ema20_position"] = "below"
        else:
            result["ema20_position"] = "unknown"

        # ── Tendance ─────────────────────────────────────────
        m_tend = _re.search(r"Tendance\s*[àa]\s*court\s*terme\s*:\s*(\w+)", texte, _re.IGNORECASE)
        m_conf = _re.search(r"indice de confiance de\s*([\d,\.]+)\s*%", texte, _re.IGNORECASE)
        if m_tend:
            result["tendance"] = m_tend.group(1).capitalize()
        if m_conf:
            result["confiance_tendance"] = float(m_conf.group(1).replace(",", "."))

        return result

    except Exception as e:
        return {"source_tech": "manuel", "_erreur": str(e)}


@st.cache_data(ttl=3600, show_spinner=False)  # cache 1h
def fetch_historique_richbourse(ticker: str, nb_jours: int = 120) -> pd.DataFrame:
    """
    Scrape l'historique des cours depuis richbourse.com.
    URL : richbourse.com/common/variation/historique/TICKER

    Utilisé pour calculer EMA20, BB numériques et variation 1 semaine
    quand la page synthèse ne donne que des valeurs qualitatives.
    """
    url = f"{RICHBOURSE_BASE}/common/variation/historique/{ticker.upper()}"
    try:
        resp = requests.get(url, headers=HEADERS_HTTP, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        for df in tables:
            df.columns = [str(c).strip().lower() for c in df.columns]
            col_date  = next((c for c in df.columns if any(k in c for k in ["date","séance","jour"])), None)
            col_close = next((c for c in df.columns if any(k in c for k in ["cours","clôture","close","normal"])), None)
            if col_date and col_close:
                df2 = df[[col_date, col_close]].copy()
                df2.columns = ["date", "close"]
                df2["date"]  = pd.to_datetime(df2["date"], errors="coerce", dayfirst=True)
                df2["close"] = pd.to_numeric(
                    df2["close"].astype(str).str.replace("\xa0","").str.replace(" ","").str.replace(",","."),
                    errors="coerce"
                )
                df2 = df2.dropna().sort_values("date").tail(nb_jours).reset_index(drop=True)
                if len(df2) >= 10:
                    return df2
    except Exception:
        pass
    return pd.DataFrame()


def calcul_indicateurs_numeriques(df_hist: pd.DataFrame) -> dict:
    """
    Calcule RSI(14), BB(20,2), EMA(20) en Python pur depuis l'historique.
    Utilisé en complément de fetch_tech_richbourse pour les valeurs numériques des BB.
    """
    if df_hist.empty or len(df_hist) < 14:
        return {}

    close = df_hist["close"].values.astype(float)
    n = len(close)

    # EMA20
    k = 2 / 21
    ema = [close[0]]
    for i in range(1, n):
        ema.append(close[i] * k + ema[-1] * (1 - k))
    ema20_val = ema[-1]

    # RSI14
    deltas = np.diff(close)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    if len(gains) >= 14:
        ag, al = np.mean(gains[:14]), np.mean(losses[:14])
        for i in range(14, len(gains)):
            ag = (ag * 13 + gains[i]) / 14
            al = (al * 13 + losses[i]) / 14
        rs = ag / al if al > 0 else 100
        rsi_val = 100 - (100 / (1 + rs))
    else:
        rsi_val = 50.0

    # BB(20,2)
    if n >= 20:
        win    = close[-20:]
        bb_mid = np.mean(win)
        bb_std = np.std(win, ddof=1)
        bb_sup = bb_mid + 2 * bb_std
        bb_inf = bb_mid - 2 * bb_std
    else:
        bb_mid = close[-1]; bb_sup = close[-1]*1.05; bb_inf = close[-1]*0.95

    var_1s = ((close[-1] / close[-6]) - 1) * 100 if n >= 6 else 0.0

    return {
        "rsi":    round(rsi_val, 1),
        "ema20":  round(ema20_val, 0),
        "bb_sup": round(bb_sup, 0),
        "bb_inf": round(bb_inf, 0),
        "bb_mid": round(bb_mid, 0),
        "var_1s": round(var_1s, 2),
        "nb_pts": n,
    }


def get_marche_data(ticker: str) -> dict:
    """
    Pipeline de collecte données :
      1. Cours actuel  ← richbourse.com/common/variation/index
      2. Indicateurs   ← richbourse.com/common/prevision-boursiere/synthese/TICKER
                          (RSI et positions qualitatives BB/EMA déjà calculés)
      3. Valeurs num.  ← historique + calcul Python (BB sup/inf en FCFA, var_1s)
    Retourne dict unifié.
    """
    tk = ticker.upper().strip()
    result = {}

    # 1. Cours du jour
    cours = fetch_cours_richbourse(tk)
    result.update(cours)

    # 2. Indicateurs depuis page synthèse (RSI numérique, BB position, tendance)
    tech_synth = fetch_tech_richbourse(tk)
    result.update(tech_synth)

    # 3. Historique pour valeurs numériques BB / EMA / var_1s
    df_hist = fetch_historique_richbourse(tk)
    if not df_hist.empty:
        indics = calcul_indicateurs_numeriques(df_hist)
        # On garde le RSI de la synthèse (plus précis, calculé par richbourse)
        # mais on prend les valeurs numériques BB/EMA depuis l'historique
        for k_ind, v_ind in indics.items():
            if k_ind == "rsi" and "rsi" in result:
                continue  # priorité RSI synthèse
            result[k_ind] = v_ind
        result["source_tech"] = "auto"
    elif "rsi" in result:
        result["source_tech"] = "auto_synthese_only"

    return result


# ==========================================================
# HELPERS — Calculs financiers
# ==========================================================
def extrapoler_annuel(resultat, periode, secteur):
    saison = SAISONNALITE_S1.get(secteur, 0.50)
    if periode == "9 mois (T1+T2+T3)":
        return (resultat / 3) * 4, f"9M × 4/3 ({resultat:.0f}M × 1.333)", "Élevée"
    elif periode == "Semestriel (S1 — 6 mois)":
        return resultat / saison, f"S1 ÷ {saison:.2f} (saisonnalité {secteur})", "Modérée"
    else:
        return resultat, "Données annuelles complètes", "Annuelle"

def badge_donnees(confiance):
    if confiance == "Annuelle":
        return "<span class='badge-annuel'>✅ Données annuelles</span>"
    elif confiance == "Élevée":
        return "<span class='badge-estimated'>⚠️ ESTIMÉ — 9M</span>"
    else:
        return "<span class='badge-estimated'>⚠️ ESTIMÉ — S1</span>"

def get_signal(score, upside_val, survalue_b, sous_marge_b, f_rsi, f_bb, var1s):
    if f_rsi:        return "🔴 BLOQUÉ — RSI surachat"
    if f_bb:         return "🔴 BLOQUÉ — Prix > BB supérieure"
    if survalue_b:   return "🔴 HORS MARGE — Ne pas acheter"
    if sous_marge_b: return "🟡 SURVEILLER (prix > cible Graham)"
    if score >= 0.65 and upside_val > 25 and var1s >= -2: return "🟢 FORT ACHAT"
    elif score >= 0.50 and upside_val > 15:                return "🔵 ACHAT"
    elif score >= 0.40 and upside_val > 5:                 return "🟡 SURVEILLER"
    elif score < 0.35 or upside_val < -15:                 return "🔴 SORTIR"
    else:                                                  return "🟠 ALLÉGER"

def valeur_intrinseque_dcf(bpa, croissance_bpa, taux):
    g1 = min(max(croissance_bpa / 100, -0.10), 0.20)
    g2, r = 0.03, taux
    flux = sum(bpa * (1 + g1) ** t / (1 + r) ** t for t in range(1, 6))
    vt   = (bpa * (1 + g1) ** 5 * (1 + g2)) / (r - g2) / (1 + r) ** 5
    return flux + vt


# ==========================================================
# SIDEBAR
# ==========================================================
st.sidebar.markdown("## ⚙️ Paramètres")

mode = st.sidebar.radio("Mode d'affichage", ["🟢 Mode Simple", "🔬 Mode Expert"])
mode_simple = mode == "🟢 Mode Simple"

st.sidebar.markdown("---")
if mode_simple:
    W_VALUE, W_QUALITY, W_MOMENTUM = 0.35, 0.40, 0.25
    st.sidebar.info("Mode Simple : les chiffres bruts suffisent. Ratios calculés automatiquement.")
else:
    st.sidebar.markdown("### Pondérations")
    W_VALUE    = st.sidebar.slider("Value",    0.1, 0.6, 0.30, 0.05)
    W_QUALITY  = st.sidebar.slider("Quality",  0.1, 0.6, 0.40, 0.05)
    W_MOMENTUM = st.sidebar.slider("Momentum", 0.1, 0.6, 0.30, 0.05)
    T = W_VALUE + W_QUALITY + W_MOMENTUM
    W_VALUE /= T; W_QUALITY /= T; W_MOMENTUM /= T

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔒 Discipline de prix (Graham)")
MARGE_SECURITE = st.sidebar.slider("Marge de sécurité (%)", 5, 30, 20, 5) / 100

if not mode_simple:
    st.sidebar.markdown("### 📐 DCF")
    taux_dcf_suggere = TAUX_DCF_SECTEUR.get(st.session_state.secteur_sel, 0.12)
    st.sidebar.caption(f"Taux suggéré pour **{st.session_state.secteur_sel}** : {taux_dcf_suggere*100:.0f}%")
    TAUX_ACTUA = st.sidebar.slider("Taux d'actualisation DCF (%)", 8, 20,
                                   int(taux_dcf_suggere * 100), 1) / 100
else:
    TAUX_ACTUA = TAUX_DCF_SECTEUR.get(st.session_state.secteur_sel, 0.12)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📡 Seuils techniques")
RSI_SURACHAT = st.sidebar.slider("RSI — surachat", 60, 80, 70, 5)
RSI_SURVENTE = st.sidebar.slider("RSI — survente", 20, 40, 30, 5)

st.sidebar.markdown("---")
# ── Tickers sauvegardés ────────────────────────────────────
sauvegardes = list_tickers_sauvegardes()
if sauvegardes:
    st.sidebar.markdown("### 💾 Fondamentaux sauvegardés")
    for s in sauvegardes[:10]:
        st.sidebar.markdown(
            f"<span style='color:#79c0ff;font-family:IBM Plex Mono;font-size:0.85em'>"
            f"**{s['ticker']}**</span> "
            f"<span style='color:#8b949e;font-size:0.78em'>{s['secteur'][:20]}</span><br>"
            f"<span style='color:#3d4a5c;font-size:0.72em'>màj {s['maj_at']}</span>",
            unsafe_allow_html=True
        )
    if len(sauvegardes) > 10:
        st.sidebar.caption(f"… et {len(sauvegardes)-10} autres")
    st.sidebar.markdown("---")

if st.sidebar.button("🗑️ Vider le screener (session)"):
    st.session_state.actions = []
    st.rerun()

# Export DB
if sauvegardes and st.sidebar.button("⬇️ Exporter fondamentaux (JSON)"):
    conn = get_db()
    all_rows = conn.execute("SELECT * FROM fondamentaux").fetchall()
    conn.close()
    data_export = [dict(r) for r in all_rows]
    st.sidebar.download_button(
        "Télécharger JSON",
        json.dumps(data_export, ensure_ascii=False, indent=2),
        "fondamentaux_brvm.json",
        mime="application/json"
    )

# Import DB
uploaded_json = st.sidebar.file_uploader("📥 Importer fondamentaux (JSON)", type="json", key="json_import")
if uploaded_json:
    try:
        data_import = json.loads(uploaded_json.read())
        for row in data_import:
            ticker_imp = row.pop("ticker", None)
            if ticker_imp:
                save_fondamentaux(ticker_imp, row)
        st.sidebar.success(f"✅ {len(data_import)} titres importés")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erreur import : {e}")


# ==========================================================
# EN-TÊTE
# ==========================================================
st.title("⬡ Screener BRVM v2")
st.caption("Cours automatiques (brvm.org) • Indicateurs techniques calculés • Fondamentaux persistants (SQLite) • Graham + DCF")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Analyser un titre", "📊 Tableau de bord", "💾 Fondamentaux sauvegardés", "📖 Méthodologie"])


# ==========================================================
# TAB 1 — FORMULAIRE INTERACTIF
# ==========================================================
with tab1:

    # ── SECTION 1 : Identification ─────────────────────────
    st.markdown("<div class='section-header'>1 — Identification & Contexte</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        titre = st.text_input("Nom / Ticker", placeholder="ex: SNTS, SGBCI…", key="titre_input")
    with c2:
        secteur = st.selectbox("Secteur", list(PER_SECTORIELS.keys()), key="secteur_input")
        st.session_state.secteur_sel = secteur
    with c3:
        periode_donnees = st.selectbox(
            "Période disponible",
            ["Annuel complet (2024 ou 2025)", "9 mois (T1+T2+T3)", "Semestriel (S1 — 6 mois)"],
            key="periode_input"
        )
        st.session_state.periode_sel = periode_donnees
    with c4:
        annee_donnees = st.selectbox("Exercice", ["2025", "2024", "2023"], key="annee_input")
        st.session_state.annee_sel = annee_donnees

    est_banque   = (secteur == SECTEUR_BANCAIRE)
    per_cible    = PER_SECTORIELS[secteur]
    taux_suggere = TAUX_DCF_SECTEUR[secteur]

    # ── Récupération automatique des données de marché ─────
    marche_data   = {}
    source_tech   = "manuel"
    fetch_status  = ""

    if titre and len(titre) >= 2:
        with st.spinner(f"⏳ Chargement des données de marché pour **{titre.upper()}**…"):
            marche_data = get_marche_data(titre.strip())
            source_tech = marche_data.get("source_tech", "manuel")

        if "prix" in marche_data:
            fetch_status = "auto_prix"
        if source_tech == "auto":
            fetch_status = "auto_full"

    # ── Fondamentaux sauvegardés ───────────────────────────
    fond_saved = None
    if titre and len(titre) >= 2:
        fond_saved = load_fondamentaux(titre.strip())

    # Indicateur de statut en temps réel
    info_cols = st.columns(4)
    with info_cols[0]:
        st.markdown(f"""<div class="filter-block">
        <div class="label-small">PER cible sectoriel</div>
        <b style="font-family:'IBM Plex Mono';font-size:1.2em">{per_cible:.2f}x</b>
        </div>""", unsafe_allow_html=True)
    with info_cols[1]:
        st.markdown(f"""<div class="filter-block">
        <div class="label-small">Taux DCF suggéré</div>
        <b style="font-family:'IBM Plex Mono';font-size:1.2em;color:#79c0ff">{taux_suggere*100:.0f}%</b>
        </div>""", unsafe_allow_html=True)
    with info_cols[2]:
        src = marche_data.get("source_tech", "manuel")
        if src == "auto":
            msg, col = "✅ richbourse.com — cours + RSI + BB + EMA auto", "#3fb950"
        elif src == "auto_synthese_only":
            msg, col = "⚡ richbourse.com — RSI/BB/tendance (pas historique)", "#3fb950"
        elif "prix" in marche_data:
            msg, col = "⚡ Cours chargé — indicateurs à saisir", "#d29922"
        elif titre and len(titre) >= 2:
            msg, col = "⚠️ Données auto non disponibles — saisie manuelle", "#d29922"
        else:
            msg, col = "Saisissez un ticker pour charger les données", "#8b949e"
        st.markdown(f"""<div class="filter-block">
        <div class="label-small">Données de marché</div>
        <b style="font-size:0.82em;color:{col}">{msg}</b>
        </div>""", unsafe_allow_html=True)
    with info_cols[3]:
        if fond_saved:
            maj = fond_saved.get("maj_at", "?")
            st.markdown(f"""<div class="filter-block">
            <div class="label-small">Fondamentaux sauvegardés</div>
            <b style="font-size:0.82em;color:#79c0ff">✅ Pré-rempli — màj {maj}</b>
            </div>""", unsafe_allow_html=True)
        else:
            badge_b = "🏦 Formulaire bancaire actif" if est_banque else "📋 Formulaire standard"
            col_b   = "#79c0ff" if est_banque else "#8b949e"
            st.markdown(f"""<div class="filter-block">
            <div class="label-small">Mode saisie</div>
            <b style="font-size:0.85em;color:{col_b}">{badge_b}</b>
            </div>""", unsafe_allow_html=True)

    if fond_saved:
        st.markdown(f"""<div class="alert-info">
        💾 Fondamentaux trouvés pour <b>{titre.upper()}</b> (màj {fond_saved.get('maj_at','?')}).
        Le formulaire est pré-rempli. Modifiez les champs mis à jour puis cliquez <b>Analyser</b>.
        </div>""", unsafe_allow_html=True)

    st.markdown("<hr class='form-divider'>", unsafe_allow_html=True)

    if periode_donnees != "Annuel complet (2024 ou 2025)":
        annee_bilan_ref = str(int(annee_donnees) - 1) if annee_donnees != "2024" else "2024"
        msg_bilan = (f"Crédits et dépôts : référez-vous au bilan {annee_bilan_ref}."
                     if est_banque
                     else f"Capitaux propres, total actif, dettes : référez-vous au bilan {annee_bilan_ref}.")
        st.markdown(f"""<div class="alert-estimated">
        📅 <b>Publication intermédiaire détectée</b> — {msg_bilan}
        Le résultat saisi sera extrapolé automatiquement.
        </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    # FORMULAIRE DE SAISIE
    # ══════════════════════════════════════════════════════════
    # Valeurs par défaut : priorité fond_saved, sinon valeurs neutres
    def fd(key, default):
        """Récupère valeur sauvegardée ou défaut."""
        if fond_saved and key in fond_saved and fond_saved[key] is not None:
            return fond_saved[key]
        return default

    with st.form("saisie_titre", clear_on_submit=True):

        # Cours — pré-rempli depuis fetch automatique si dispo
        prix_defaut = marche_data.get("prix", 1000.0)
        prix_label  = f"💰 Prix actuel (FCFA)"
        if "prix" in marche_data:
            var_affich = marche_data.get('variation_pct', 0)
            signe = "+" if var_affich >= 0 else ""
            prix_label = f"💰 Prix actuel (FCFA) — {signe}{var_affich:.2f}% aujourd'hui ✅"

        prix = st.number_input(prix_label, min_value=1.0, value=float(prix_defaut),
                               help="Cours chargé automatiquement depuis brvm.org (ou saisi manuellement).")

        # ── Section 2 : Fondamentaux ────────────────────────
        if est_banque:
            st.markdown("<div class='section-header'>2 — Données bancaires</div>", unsafe_allow_html=True)
            st.markdown("""<div class="alert-estimated">
            🏦 <b>Secteur bancaire — saisie simplifiée</b><br>
            <span style="font-size:0.88em">Données disponibles dans les publications BRVM. Pré-rempli si déjà sauvegardé.</span>
            </div>""", unsafe_allow_html=True)

            label_rn = {
                "Annuel complet (2024 ou 2025)": "Résultat net annuel (millions FCFA)",
                "9 mois (T1+T2+T3)":            "Résultat net 9 mois (millions FCFA)",
                "Semestriel (S1 — 6 mois)":     "Résultat net S1 (millions FCFA)",
            }[periode_donnees]

            st.markdown("**📊 Compte de résultat**")
            bc1, bc2 = st.columns(2)
            with bc1:
                pnb = st.number_input("PNB — Produit Net Bancaire (millions FCFA)",
                                      min_value=1.0, value=fd("pnb", 5000.0))
                st.markdown("<div class='tooltip-text'>📍 Compte de résultat → Produit Net Bancaire</div>", unsafe_allow_html=True)
            with bc2:
                resultat_saisi_b = st.number_input(label_rn, value=fd("resultat_b", 800.0))
                st.markdown("<div class='tooltip-text'>📍 Compte de résultat → Résultat net</div>", unsafe_allow_html=True)

            st.markdown("**🏦 Bilan**")
            bc3, bc4 = st.columns(2)
            with bc3:
                encours_credits = st.number_input("Encours crédits à la clientèle (millions FCFA)",
                                                  min_value=1.0, value=fd("encours_credits", 30000.0))
                st.markdown("<div class='tooltip-text'>📍 Bilan → Créances sur la clientèle</div>", unsafe_allow_html=True)
            with bc4:
                depots_clientele = st.number_input("Dépôts de la clientèle (millions FCFA)",
                                                   min_value=1.0, value=fd("depots_clientele", 40000.0))
                st.markdown("<div class='tooltip-text'>📍 Bilan → Dettes envers la clientèle</div>", unsafe_allow_html=True)

            st.markdown("**📌 Données complémentaires**")
            bx1, bx2, bx3 = st.columns(3)
            with bx1:
                nombre_actions_b   = st.number_input("Nombre d'actions (millions)", min_value=0.001, value=fd("nombre_actions", 10.0))
            with bx2:
                capitaux_propres_b = st.number_input("Capitaux propres (millions FCFA)", min_value=1.0, value=fd("capitaux_propres", 8000.0))
                st.markdown("<div class='tooltip-text'>📍 Bilan → Capitaux propres</div>", unsafe_allow_html=True)
            with bx3:
                dividende_b = st.number_input("Dividende par action (FCFA)", min_value=0.0, value=fd("dividende", 0.0))
                bpa_prec_b  = st.number_input("BPA année précédente (FCFA)", value=fd("bpa_prec", 80.0))

        else:
            st.markdown("<div class='section-header'>2A — Compte de résultat</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='tooltip-text'>📍 Rapport {annee_donnees} — {periode_donnees}</div>", unsafe_allow_html=True)

            label_rn_std = {
                "Annuel complet (2024 ou 2025)": "Résultat net annuel (millions FCFA)",
                "9 mois (T1+T2+T3)":            "Résultat net 9 mois (millions FCFA)",
                "Semestriel (S1 — 6 mois)":     "Résultat net S1 (millions FCFA)",
            }[periode_donnees]

            s1, s2, s3 = st.columns(3)
            with s1:
                resultat_saisi = st.number_input(label_rn_std, value=fd("resultat", 500.0))
                nombre_actions = st.number_input("Nombre d'actions (millions)", min_value=0.001, value=fd("nombre_actions", 10.0))
            with s2:
                dividende  = st.number_input("Dividende par action (FCFA)", min_value=0.0, value=fd("dividende", 0.0))
                bpa_prec   = st.number_input("BPA année précédente (FCFA)", value=fd("bpa_prec", 80.0))
            with s3:
                if not mode_simple:
                    stabilite_bpa = st.selectbox("Régularité bénéfices (3-5 ans)",
                                                 ["Stable", "Volatil", "Exceptionnel"],
                                                 index=["Stable","Volatil","Exceptionnel"].index(fd("stabilite_bpa","Stable")))
                else:
                    stabilite_bpa = "Stable"

            if periode_donnees != "Annuel complet (2024 ou 2025)":
                annee_bilan_ref_std = str(int(annee_donnees) - 1) if annee_donnees != "2024" else "2024"
                source_bilan = f"Bilan {annee_bilan_ref_std}"
            else:
                source_bilan = f"Bilan {annee_donnees}"

            st.markdown(f"<div class='section-header'>2B — Bilan ({source_bilan})</div>", unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                capitaux_propres = st.number_input("Capitaux propres (millions FCFA)", min_value=1.0, value=fd("capitaux_propres", 2000.0))
            with b2:
                total_actif = st.number_input("Total actif (millions FCFA)", min_value=1.0, value=fd("total_actif", 5000.0))
            with b3:
                dettes_totales = st.number_input("Dettes financières (millions FCFA)", min_value=0.0, value=fd("dettes_totales", 1000.0))

        # ── Section 3 : Indicateurs techniques ─────────────
        st.markdown("<div class='section-header'>3 — Indicateurs techniques</div>", unsafe_allow_html=True)

        # Affichage statut source technique
        src = marche_data.get("source_tech", "manuel")
        if src in ("auto", "auto_synthese_only"):
            bb_pos = marche_data.get("bb_position", "unknown")
            ema_pos = marche_data.get("ema20_position", "unknown")
            tendance = marche_data.get("tendance", "")
            confiance_t = marche_data.get("confiance_tendance", 0)
            details = []
            if bb_pos == "above_sup":   details.append("🔴 Prix > BB sup")
            elif bb_pos == "below_inf": details.append("🟢 Prix < BB inf")
            else:                       details.append("✅ Dans BB")
            if ema_pos == "above":  details.append("↗ au-dessus EMA20")
            elif ema_pos == "below": details.append("↘ en-dessous EMA20")
            if tendance:            details.append(f"Tendance : {tendance} ({confiance_t:.0f}%)")
            st.markdown(f"""<div class="alert-green">
            ✅ <b>Indicateurs richbourse.com</b> — RSI calculé + signaux BB/EMA<br>
            <span style="font-size:0.88em">{" &nbsp;|&nbsp; ".join(details)}</span>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="alert-yellow">
            ⚠️ <b>Saisie manuelle requise</b> — richbourse.com non disponible.<br>
            <span style="font-size:0.85em">Saisir depuis TradingView ou richbourse.com/common/mouvements/technique/TICKER</span>
            </div>""", unsafe_allow_html=True)

        t1, t2, t3, t4 = st.columns(4)
        with t1:
            st.markdown("**📈 Bollinger Bands (20,2)**")
            bb_sup_def = marche_data.get("bb_sup", 1100.0)
            bb_inf_def = marche_data.get("bb_inf", 900.0)
            bb_sup = st.number_input("BB supérieure (FCFA)", min_value=1.0, value=float(bb_sup_def))
            bb_inf = st.number_input("BB inférieure (FCFA)", min_value=1.0, value=float(bb_inf_def))
        with t2:
            st.markdown("**📊 EMA 20**")
            ema20_def = marche_data.get("ema20", 980.0)
            var1s_def = marche_data.get("var_1s", 0.0)
            ema20  = st.number_input("EMA20 (FCFA)", min_value=1.0, value=float(ema20_def))
            var_1s = st.number_input("Variation 1 semaine (%)", min_value=-30.0, max_value=30.0, value=float(var1s_def))
        with t3:
            st.markdown("**🌡️ RSI (14)**")
            rsi_def = marche_data.get("rsi", 50.0)
            rsi = st.number_input("RSI", min_value=0.0, max_value=100.0, value=float(rsi_def))
            st.markdown(f"""<div class="filter-block">
            <div class="label-small">Seuils actifs</div>
            Surachat : <b style="color:#f85149">> {RSI_SURACHAT}</b><br>
            Survente  : <b style="color:#3fb950">< {RSI_SURVENTE}</b>
            </div>""", unsafe_allow_html=True)
        with t4:
            st.markdown(f"""<div class="filter-block" style="margin-top:28px">
            <div class="label-small">Marge de sécurité</div>
            <b style="font-size:1.3em;font-family:'IBM Plex Mono'">{MARGE_SECURITE*100:.0f}%</b>
            </div>
            <div class="filter-block">
            <div class="label-small">Taux DCF utilisé</div>
            <b style="font-size:1.3em;font-family:'IBM Plex Mono'">{TAUX_ACTUA*100:.0f}%</b>
            </div>""", unsafe_allow_html=True)

        # ── Options de sauvegarde ───────────────────────────
        st.markdown("<hr class='form-divider'>", unsafe_allow_html=True)
        save_fond = st.checkbox("💾 Sauvegarder les fondamentaux pour ce ticker", value=True,
                                help="Les données fondamentales (résultats, bilan) seront sauvegardées "
                                     "et pré-remplies automatiquement lors de la prochaine analyse.")

        submitted = st.form_submit_button("🔍 Analyser ce titre", use_container_width=True)

    # ==========================================================
    # CALCULS
    # ==========================================================
    if submitted and titre:

        if any(a["Titre"] == titre.upper() for a in st.session_state.actions):
            st.error(f"⚠️ '{titre.upper()}' est déjà dans le screener.")
            st.stop()

        per_cible_score = PER_CAP_SCORE[secteur]

        # ── Extrapolation & ratios ──────────────────────────
        if est_banque:
            resultat_annuel, methode_extrapol, confiance = extrapoler_annuel(
                resultat_saisi_b, periode_donnees, secteur)
            nombre_actions   = nombre_actions_b
            capitaux_propres = capitaux_propres_b
            dividende        = dividende_b
            bpa_prec         = bpa_prec_b
            stabilite_bpa    = "Stable"
            total_actif      = encours_credits + depots_clientele
        else:
            resultat_annuel, methode_extrapol, confiance = extrapoler_annuel(
                resultat_saisi, periode_donnees, secteur)

        donnees_estimees = confiance != "Annuelle"
        bpa          = resultat_annuel / nombre_actions
        valeur_book  = capitaux_propres / nombre_actions
        per          = prix / bpa if bpa > 0 else 99
        pbr          = prix / valeur_book if valeur_book > 0 else 99
        div_yield    = dividende / prix if prix > 0 else 0
        croissance_bpa = ((bpa - bpa_prec) / abs(bpa_prec) * 100) if bpa_prec != 0 else 0

        # ── Valeur intrinsèque ──────────────────────────────
        graham_number   = np.sqrt(max(22.5 * bpa * valeur_book, 0)) if bpa > 0 else 0
        fair_value_comp = bpa * per_cible if bpa > 0 else 0
        fair_value_dcf  = valeur_intrinseque_dcf(bpa, croissance_bpa, TAUX_ACTUA) if bpa > 0 else 0

        if graham_number > 0 and fair_value_dcf > 0:
            vi = graham_number * 0.40 + fair_value_comp * 0.35 + fair_value_dcf * 0.25
        elif graham_number > 0:
            vi = graham_number * 0.50 + fair_value_comp * 0.50
        else:
            vi = fair_value_comp

        prix_cible = vi * (1 - MARGE_SECURITE)
        upside     = (prix_cible / prix - 1) * 100
        survalue   = prix > vi
        sous_marge = prix > prix_cible and not survalue

        # ── Scores ─────────────────────────────────────────
        score_per = np.clip(per_cible_score / per, 0, 1) if per > 0 else 0
        score_pbr = np.clip(1.5 / pbr, 0, 1)
        score_dy  = np.clip(div_yield / 0.08, 0, 1)
        value_score = score_per * 0.40 + score_pbr * 0.35 + score_dy * 0.25

        if est_banque:
            b = BENCH_BANQUE
            roe            = (resultat_annuel / capitaux_propres) * 100
            marge_nette_b  = resultat_annuel / pnb if pnb > 0 else 0
            score_marge    = np.clip(marge_nette_b / b["marge_nette_cible"], 0, 1)
            credits_depots = encours_credits / depots_clientele if depots_clientele > 0 else 0
            ecart_opt      = abs(credits_depots - b["credits_depots_opt"])
            score_cd       = np.clip(1 - ecart_opt / 0.40, 0, 1)
            score_roe_b    = np.clip(roe / (b["roe_cible"] * 100), 0, 1)
            quality_score  = score_marge * 0.45 + score_cd * 0.30 + score_roe_b * 0.25
            dette_cp = roa = None
        else:
            roe       = (resultat_annuel / capitaux_propres) * 100
            roa       = (resultat_annuel / total_actif) * 100
            dette_cp  = dettes_totales / capitaux_propres
            bonus_stab = {"Stable": 0.20, "Volatil": 0.0, "Exceptionnel": 0.30}[stabilite_bpa]
            quality_score = (
                np.clip(roe / 25, 0, 1)         * 0.35 +
                np.clip(roa / 12, 0, 1)         * 0.30 +
                np.clip(1 - dette_cp / 3, 0, 1) * 0.25 +
                bonus_stab                      * 0.10
            )
            marge_nette_b = credits_depots = None

        mom_fond       = np.clip(croissance_bpa / 30, -1, 1)
        mom_prix       = np.clip(var_1s / 10, -1, 1)
        momentum_score = mom_fond * 0.60 + mom_prix * 0.40
        score_final    = W_VALUE * value_score + W_QUALITY * quality_score + W_MOMENTUM * momentum_score

        # ── Technique ──────────────────────────────────────
        filtre_rsi    = rsi > RSI_SURACHAT
        filtre_bb_sup = prix > bb_sup
        bb_pct        = ((prix - bb_inf) / (bb_sup - bb_inf) * 100) if (bb_sup - bb_inf) > 0 else 50
        ecart_ma      = (prix / ema20 - 1) * 100
        rsi_survente  = rsi < RSI_SURVENTE

        signal = get_signal(score_final, upside, survalue, sous_marge,
                            filtre_rsi, filtre_bb_sup, var_1s)

        # ── Sauvegarde fondamentaux ─────────────────────────
        if save_fond:
            fond_dict = {
                "secteur": secteur, "periode": periode_donnees, "annee": annee_donnees,
                "est_banque": 1 if est_banque else 0,
                "nombre_actions": nombre_actions, "dividende": dividende,
                "bpa_prec": bpa_prec, "capitaux_propres": capitaux_propres,
            }
            if est_banque:
                fond_dict.update({
                    "pnb": pnb, "resultat_b": resultat_saisi_b,
                    "encours_credits": encours_credits, "depots_clientele": depots_clientele,
                })
            else:
                fond_dict.update({
                    "resultat": resultat_saisi, "total_actif": total_actif,
                    "dettes_totales": dettes_totales, "stabilite_bpa": stabilite_bpa,
                })
            save_fondamentaux(titre.strip(), fond_dict)

        # ══════════════════════════════════════════════════════
        # AFFICHAGE RÉSULTAT
        # ══════════════════════════════════════════════════════
        st.markdown("---")
        badge_src = "<span class='badge-auto'>✅ AUTO brvm.org</span>" if "prix" in marche_data else "<span class='badge-manual'>⚠️ Manuel</span>"
        badge_bq  = " <span style='background:#1f3a5f;color:#79c0ff;border:1px solid #79c0ff;border-radius:10px;padding:1px 8px;font-size:0.72em;font-weight:700'>🏦 BANCAIRE</span>" if est_banque else ""

        st.markdown(
            f"### {titre.upper()} {badge_donnees(confiance)} {badge_src}{badge_bq}",
            unsafe_allow_html=True
        )
        if save_fond:
            st.markdown("<div style='color:#79c0ff;font-size:0.82em'>💾 Fondamentaux sauvegardés.</div>",
                        unsafe_allow_html=True)

        if donnees_estimees:
            st.markdown(f"""<div class="alert-estimated">
            ⚠️ <b>Données extrapolées — {periode_donnees} {annee_donnees}</b><br>
            <span style="font-size:0.9em">
            {methode_extrapol}<br>
            Résultat saisi : <b>{(resultat_saisi_b if est_banque else resultat_saisi):.0f}M FCFA</b>
            → Résultat annuel estimé : <b>{resultat_annuel:.0f}M FCFA</b>
            </span>
            </div>""", unsafe_allow_html=True)

        # Filtres techniques
        st.markdown("#### 📡 Filtres techniques")
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            rc = "#f85149" if filtre_rsi else ("#3fb950" if rsi_survente else "#79c0ff")
            rl = f"🔴 BLOQUÉ (>{RSI_SURACHAT})" if filtre_rsi else (f"🟢 Survente (<{RSI_SURVENTE})" if rsi_survente else "✅ Zone neutre")
            st.markdown(f"""<div class="filter-block">
            <div class="label-small">RSI (14)</div>
            <b style="font-size:1.6em;color:{rc}">{rsi:.0f}</b><br>
            <span style="color:{rc};font-size:0.85em">{rl}</span></div>""", unsafe_allow_html=True)
        with tc2:
            bc = "#f85149" if filtre_bb_sup else ("#3fb950" if prix < bb_inf else "#79c0ff")
            bl = "🔴 BLOQUÉ" if filtre_bb_sup else ("🟢 Sous BB inf" if prix < bb_inf else "✅ Dans les bandes")
            st.markdown(f"""<div class="filter-block">
            <div class="label-small">Bollinger Bands — position</div>
            <b style="color:{bc}">{bb_pct:.0f}% de la bande</b><br>
            <span style="color:#8b949e;font-size:0.82em">{bb_inf:,.0f} | <b style="color:#e6edf3">{prix:,.0f}</b> | {bb_sup:,.0f}</span><br>
            <span style="color:{bc};font-size:0.85em">{bl}</span></div>""", unsafe_allow_html=True)
        with tc3:
            mc = "#3fb950" if prix > ema20 else "#f85149"
            ml = "✅ Prix > EMA20 (haussier)" if prix > ema20 else "⚠️ Prix < EMA20 (baissier)"
            st.markdown(f"""<div class="filter-block">
            <div class="label-small">EMA 20</div>
            <b style="color:{mc}">{ema20:,.0f} FCFA</b><br>
            <span style="color:#8b949e;font-size:0.82em">Écart : {ecart_ma:+.1f}%</span><br>
            <span style="color:{mc};font-size:0.85em">{ml}</span></div>""", unsafe_allow_html=True)

        # Verrou Graham
        st.markdown("#### 🔒 Verrou Graham")
        if survalue:
            st.markdown(f"""<div class="alert-red">
            🔒 Titre surévalué — Prix ({prix:,.0f}) > Valeur intrinsèque ({vi:,.0f} FCFA). Aucun achat.</div>""",
            unsafe_allow_html=True)
        elif sous_marge:
            st.markdown(f"""<div class="alert-yellow">
            ⚠️ Sous VI mais hors marge cible — Prix ({prix:,.0f}) entre VI ({vi:,.0f}) et cible
            ({prix_cible:,.0f} FCFA, marge {MARGE_SECURITE*100:.0f}%). On surveille.</div>""",
            unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="alert-green">
            ✅ Marge validée ({MARGE_SECURITE*100:.0f}%) — Prix ({prix:,.0f}) &lt;
            Cible ({prix_cible:,.0f} FCFA). Upside : <b>{upside:.1f}%</b></div>""",
            unsafe_allow_html=True)

        # Ratios
        st.markdown("#### 📊 Ratios calculés")
        r1, r2, r3, r4, r5 = st.columns(5)
        with r1:
            st.markdown(f"""<div class="ratio-box">
            <div class="label-small">BPA {'(estimé)' if donnees_estimees else ''}</div>
            <b>{bpa:,.1f} FCFA</b></div>
            <div class="ratio-box"><div class="label-small">PER</div><b>{per:.1f}x</b>
            <span class="label-small"> cible: {per_cible:.2f}x</span></div>""",
            unsafe_allow_html=True)
        with r2:
            st.markdown(f"""<div class="ratio-box">
            <div class="label-small">P/B</div><b>{pbr:.2f}x</b></div>
            <div class="ratio-box"><div class="label-small">Dividende</div>
            <b>{div_yield*100:.1f}%</b></div>""", unsafe_allow_html=True)
        with r3:
            if est_banque:
                mn_c = "#3fb950" if marge_nette_b >= BENCH_BANQUE["marge_nette_cible"] else "#d29922"
                st.markdown(f"""<div class="ratio-box">
                <div class="label-small">Marge nette / PNB {'(est.)' if donnees_estimees else ''}</div>
                <b style="color:{mn_c}">{marge_nette_b*100:.1f}%</b>
                <span class="label-small"> cible: {BENCH_BANQUE['marge_nette_cible']*100:.0f}%</span></div>
                <div class="ratio-box">
                <div class="label-small">ROE bancaire {'(est.)' if donnees_estimees else ''}</div>
                <b>{roe:.1f}%</b>
                <span class="label-small"> cible: {BENCH_BANQUE['roe_cible']*100:.0f}%</span></div>""",
                unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="ratio-box">
                <div class="label-small">ROE {'(est.)' if donnees_estimees else ''}</div>
                <b>{roe:.1f}%</b></div>
                <div class="ratio-box">
                <div class="label-small">ROA {'(est.)' if donnees_estimees else ''}</div>
                <b>{roa:.1f}%</b></div>""", unsafe_allow_html=True)
        with r4:
            if est_banque:
                b = BENCH_BANQUE
                cd_c = "#f85149" if credits_depots > b["credits_depots_max"] or credits_depots < b["credits_depots_min"] else ("#d29922" if abs(credits_depots - b["credits_depots_opt"]) > 0.15 else "#3fb950")
                st.markdown(f"""<div class="ratio-box">
                <div class="label-small">Crédits / Dépôts</div>
                <b style="color:{cd_c}">{credits_depots*100:.1f}%</b>
                <span class="label-small"> optimal: 70-90%</span></div>
                <div class="ratio-box"><div class="label-small">Δ BPA</div><b>{croissance_bpa:+.1f}%</b></div>""",
                unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="ratio-box">
                <div class="label-small">Dette/CP</div><b>{dette_cp:.2f}x</b></div>
                <div class="ratio-box"><div class="label-small">Δ BPA</div><b>{croissance_bpa:+.1f}%</b></div>""",
                unsafe_allow_html=True)
        with r5:
            st.markdown(f"""<div class="ratio-box">
            <div class="label-small">Graham Number</div>
            <b>{graham_number:,.0f} FCFA</b></div>
            <div class="ratio-box"><div class="label-small">Valeur intrinsèque</div>
            <b>{vi:,.0f} FCFA</b></div>""", unsafe_allow_html=True)

        # Signal final
        couleur_sig = COULEURS.get(signal, "#8b949e")
        badge_est   = " <span class='badge-estimated'>⚠️ DONNÉES ESTIMÉES</span>" if donnees_estimees else ""
        badge_src2  = " <span class='badge-auto'>✅ Cours AUTO</span>" if "prix" in marche_data else ""
        st.markdown(f"""
        <div class="card" style="border-left:5px solid {couleur_sig};margin-top:16px">
        <div class="label-small">Signal de rotation{badge_est}{badge_src2}</div>
        <div style="font-family:'IBM Plex Mono';font-size:1.5em;color:{couleur_sig};font-weight:700;margin:6px 0">
            {signal}
        </div>
        <div style="color:#8b949e;font-size:0.83em">
            Score: <b style="color:#e6edf3">{score_final:.3f}</b> &nbsp;|&nbsp;
            Value: <b style="color:#e6edf3">{value_score:.3f}</b> &nbsp;|&nbsp;
            Quality: <b style="color:#e6edf3">{quality_score:.3f}</b> &nbsp;|&nbsp;
            Momentum: <b style="color:#e6edf3">{momentum_score:.3f}</b> &nbsp;|&nbsp;
            Upside: <b style="color:#e6edf3">{upside:.1f}%</b>
        </div>
        </div>""", unsafe_allow_html=True)

        # Enregistrement session
        st.session_state.actions.append({
            "Titre":              titre.upper(),
            "Secteur":            secteur,
            "🏦 Bancaire":        "✅" if est_banque else "—",
            "Période":            f"{periode_donnees} {annee_donnees}",
            "Confiance":          confiance,
            "Source marché":      "AUTO" if "prix" in marche_data else "Manuel",
            "Source technique":   "AUTO" if source_tech == "auto" else "Manuel",
            "Prix (FCFA)":        round(prix, 0),
            "BPA":                round(bpa, 1),
            "PER":                round(per, 1),
            "P/B":                round(pbr, 2),
            "ROE (%)":            round(roe, 1),
            "ROA (%)":            round(roa, 1) if roa is not None else "—",
            "D/CP":               round(dette_cp, 2) if dette_cp is not None else "N/A",
            "Marge nette/PNB":    f"{marge_nette_b*100:.1f}%" if est_banque else "—",
            "Crédits/Dépôts":     f"{credits_depots*100:.1f}%" if est_banque else "—",
            "ΔBPA (%)":           round(croissance_bpa, 1),
            "RSI":                round(rsi, 1),
            "BB%":                round(bb_pct, 1),
            "vs EMA20 (%)":       round(ecart_ma, 1),
            "Graham Number":      round(graham_number, 0),
            "Valeur intrinseque": round(vi, 0),
            "Prix cible":         round(prix_cible, 0),
            "Upside (%)":         round(upside, 1),
            "Score Value":        round(value_score, 3),
            "Score Quality":      round(quality_score, 3),
            "Score Momentum":     round(momentum_score, 3),
            "Score Final":        round(score_final, 3),
            "Filtre RSI":         "🔴 Bloqué" if filtre_rsi else "✅ OK",
            "Filtre BB":          "🔴 Bloqué" if filtre_bb_sup else "✅ OK",
            "Graham":             "🔴 Hors marge" if survalue else ("🟡 Sous marge" if sous_marge else "✅ OK"),
            "Signal":             signal,
        })
        st.success(f"✅ **{titre.upper()}** enregistré dans le screener.")


# ==========================================================
# TAB 2 — TABLEAU DE BORD
# ==========================================================
with tab2:
    if not st.session_state.actions:
        st.info("Aucun titre analysé. Commencez par l'onglet **➕ Analyser un titre**.")
    else:
        df = pd.DataFrame(st.session_state.actions)
        df = df.sort_values("Score Final", ascending=False).reset_index(drop=True)

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Titres analysés",   len(df))
        k2.metric("Signaux ACHAT",     len(df[df["Signal"].str.contains("ACHAT", na=False)]))
        k3.metric("Titres bloqués 🔴", len(df[df["Signal"].str.startswith("🔴", na=False)]))
        k4.metric("Données estimées ⚠️", len(df[df["Confiance"] != "Annuelle"]))
        k5.metric("Cours auto ✅",     len(df[df["Source marché"] == "AUTO"]))

        st.markdown("---")
        cols = ["Titre", "Secteur", "🏦 Bancaire", "Source marché", "Source technique", "Période", "Confiance",
                "Prix (FCFA)", "PER", "P/B", "ROE (%)", "ROA (%)", "D/CP",
                "Marge nette/PNB", "Crédits/Dépôts",
                "RSI", "BB%", "vs EMA20 (%)",
                "Valeur intrinseque", "Prix cible", "Upside (%)",
                "Score Final", "Filtre RSI", "Filtre BB", "Graham", "Signal"]

        st.dataframe(
            df[cols].style
                .background_gradient(subset=["Score Final"], cmap="RdYlGn")
                .background_gradient(subset=["Upside (%)"], cmap="RdYlGn")
                .background_gradient(subset=["RSI"], cmap="RdYlGn_r"),
            use_container_width=True, height=420
        )

        st.markdown("---")
        st.subheader("🔄 Signaux de rotation")
        for _, row in df.iterrows():
            signal  = row["Signal"]
            couleur = COULEURS.get(signal, "#8b949e")
            badge_rsi = " <span style='background:#f85149;color:white;padding:1px 6px;border-radius:8px;font-size:0.72em'>RSI</span>" if row["Filtre RSI"] == "🔴 Bloqué" else ""
            badge_bb  = " <span style='background:#f85149;color:white;padding:1px 6px;border-radius:8px;font-size:0.72em'>BB</span>" if row["Filtre BB"] == "🔴 Bloqué" else ""
            badge_g   = " <span style='background:#d29922;color:white;padding:1px 6px;border-radius:8px;font-size:0.72em'>GRAHAM</span>" if row["Graham"] != "✅ OK" else ""
            badge_est = " <span style='background:#1f3a5f;color:#79c0ff;border:1px solid #79c0ff;padding:1px 6px;border-radius:8px;font-size:0.72em'>ESTIMÉ</span>" if row["Confiance"] != "Annuelle" else ""
            badge_auto_m = " <span style='background:#1b2d1b;color:#3fb950;border:1px solid #3fb950;padding:1px 6px;border-radius:8px;font-size:0.72em'>AUTO</span>" if row["Source marché"] == "AUTO" else ""

            st.markdown(f"""
            <div class="card" style="border-left:4px solid {couleur}">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                <div>
                    <span style="font-family:'IBM Plex Mono';font-weight:700;color:#e6edf3;font-size:1.05em">{row['Titre']}</span>
                    {badge_rsi}{badge_bb}{badge_g}{badge_est}{badge_auto_m}
                    <span style="color:#8b949e;font-size:0.82em;margin-left:10px">{row['Secteur']}</span><br>
                    <span style="color:#8b949e;font-size:0.78em">{row['Période']}</span>
                </div>
                <div style="text-align:right">
                    <span style="color:{couleur};font-weight:700;font-size:1.1em">{signal}</span><br>
                    <span style="color:#8b949e;font-size:0.8em">
                        Score: <b style="color:#e6edf3">{row['Score Final']:.3f}</b> &nbsp;|&nbsp;
                        Upside: <b style="color:#e6edf3">{row['Upside (%)']:.1f}%</b> &nbsp;|&nbsp;
                        RSI: <b style="color:#e6edf3">{row['RSI']}</b>
                    </span>
                </div>
            </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Screener BRVM")
        st.download_button("⬇️ Exporter en Excel", output.getvalue(), "Screener_BRVM.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True)


# ==========================================================
# TAB 3 — FONDAMENTAUX SAUVEGARDÉS
# ==========================================================
with tab3:
    st.subheader("💾 Fondamentaux sauvegardés")
    sauv_list = list_tickers_sauvegardes()

    if not sauv_list:
        st.info("Aucun fondamental sauvegardé. Analysez un titre avec l'option 💾 cochée.")
    else:
        st.markdown(f"**{len(sauv_list)} titre(s) en base** — chargés automatiquement à la prochaine analyse.")

        for s in sauv_list:
            fond = load_fondamentaux(s["ticker"])
            if not fond:
                continue
            with st.expander(f"**{s['ticker']}** — {s['secteur']} — màj {s['maj_at']}"):
                cols_f = st.columns(3)
                with cols_f[0]:
                    st.markdown(f"""
                    **Secteur** : {fond.get('secteur','—')}<br>
                    **Période** : {fond.get('periode','—')} {fond.get('annee','')}<br>
                    **Nb actions** : {fond.get('nombre_actions','—')} M<br>
                    **Dividende** : {fond.get('dividende','—')} FCFA/action<br>
                    **BPA préc.** : {fond.get('bpa_prec','—')} FCFA
                    """, unsafe_allow_html=True)
                with cols_f[1]:
                    if fond.get("est_banque"):
                        st.markdown(f"""
                        🏦 **Bancaire**<br>
                        PNB : {fond.get('pnb','—')} M FCFA<br>
                        RN : {fond.get('resultat_b','—')} M FCFA<br>
                        Crédits : {fond.get('encours_credits','—')} M FCFA<br>
                        Dépôts : {fond.get('depots_clientele','—')} M FCFA
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        📋 **Standard**<br>
                        RN : {fond.get('resultat','—')} M FCFA<br>
                        CP : {fond.get('capitaux_propres','—')} M FCFA<br>
                        Actif : {fond.get('total_actif','—')} M FCFA<br>
                        Dettes : {fond.get('dettes_totales','—')} M FCFA
                        """, unsafe_allow_html=True)
                with cols_f[2]:
                    if st.button(f"🗑️ Supprimer {s['ticker']}", key=f"del_{s['ticker']}"):
                        delete_fondamentaux(s["ticker"])
                        st.success(f"✅ {s['ticker']} supprimé.")
                        st.rerun()


# ==========================================================
# TAB 4 — MÉTHODOLOGIE
# ==========================================================
with tab4:
    st.subheader("📖 Méthodologie")
    st.markdown("""
    ### Architecture de données

    ```
    ┌─────────────────────────────────────────────────────────────┐
    │  DONNÉES DE MARCHÉ (automatiques) — Source : richbourse.com │
    │                                                             │
    │  1. Cours actuel + variation %                              │
    │     ← /common/variation/index  (tableau HTML)              │
    │                                                             │
    │  2. Indicateurs techniques déjà calculés                    │
    │     ← /common/prevision-boursiere/synthese/TICKER           │
    │       • RSI 14 (valeur numérique exacte)                    │
    │       • Position BB (au-dessus sup / en-dessous inf / dans) │
    │       • Position EMA20                                      │
    │       • Tendance + indice de confiance                      │
    │                                                             │
    │  3. Valeurs numériques BB sup/inf + var 1s                  │
    │     ← /common/variation/historique/TICKER + calcul Python   │
    │                                                             │
    │  Cache : 10 min (indicateurs) / 30 min (cours) / 1h (hist) │
    └───────────────────────────────┬─────────────────────────────┘
                                    │
    ┌───────────────────────────────▼─────────────────────────────┐
    │  FONDAMENTAUX (persistants) — SQLite local                  │
    │  • Pré-rempli à chaque analyse si ticker déjà connu         │
    │  • Mis à jour après chaque publication de résultats         │
    │  • Export/Import JSON (backup)                              │
    └───────────────────────────────┬─────────────────────────────┘
                                    │
    ┌───────────────────────────────▼─────────────────────────────┐
    │  MOTEUR DE SCORING                                          │
    │  Graham · DCF · PER sectoriel · RSI/BB · Momentum           │
    └─────────────────────────────────────────────────────────────┘
    ```

    ### Pourquoi richbourse.com plutôt que brvm.org ou sikafinance ?

    | Critère | richbourse.com | brvm.org | sikafinance.com |
    |---|---|---|---|
    | HTML statique (scrapable) | ✅ | ⚠️ partiel | ⚠️ partiel |
    | Indicateurs déjà calculés | ✅ RSI/BB/EMA en texte | ❌ | ❌ |
    | Historique structuré | ✅ `/historique/TICKER` | ⚠️ | ✅ download CSV |
    | Utilisé par package R officiel | ✅ | ❌ | ❌ |
    | API officielle | ✅ `/investisseur/api` | ⚠️ FIX protocol | ❌ |

    richbourse.com est la seule source à exposer le RSI, la position des BB et la tendance
    **directement en texte HTML** sur une page dédiée par ticker — pas besoin de recalculer.

    ### Installation des dépendances

    ```bash
    pip install streamlit pandas numpy requests beautifulsoup4 openpyxl lxml
    ```

    ### Persistance SQLite — Streamlit Cloud

    Sur Streamlit Cloud, `fondamentaux_brvm.db` est éphémère (reset au redémarrage).
    Utiliser **⬇️ Exporter JSON** régulièrement et **📥 Importer** après redéploiement.
    Pour une persistance permanente : Supabase (PostgreSQL gratuit) ou Google Sheets API.

    ---
    ### Logique de scoring (inchangée)

    ```
    [FILTRE 1] RSI > seuil surachat      → 🔴 BLOQUÉ
    [FILTRE 2] Prix > BB supérieure      → 🔴 BLOQUÉ
    [FILTRE 3] Prix > Valeur intrinsèque → 🔴 HORS MARGE
    [FILTRE 4] Prix > Prix cible (marge) → 🟡 SURVEILLER
    [SCORE]    Value + Quality + Momentum → Signal final
    ```
    """)

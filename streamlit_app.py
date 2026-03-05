"""
Screener BRVM v6.0
Cours        : richbourse → brvm.org → sikafinance
Indicateurs  : richbourse historique → BB(20,2) + EMA(20) + RSI(14) + var_3m + vol_moy_20j
Stratégie    : Value 25% / Quality 40% / Momentum 35%
               Marge sécurité variable par quality score
               Momentum = accélération BPA + variation 3 mois
               Signal plafonné SURVEILLER si Quality < 0.40
               Liquidité : alerte si volume moyen 20j insuffisant
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import json
import requests
import re as _re
from io import BytesIO, StringIO
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ══════════════════════════════════════════════════════════════════
# CONFIG & STYLES
# ══════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Screener BRVM", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

/* Base */
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #070b0f; color: #dde3ea; }

/* Sidebar */
div[data-testid="stSidebar"] {
    background: #0d1117;
    border-right: 1px solid #1e2633;
}
div[data-testid="stSidebar"] .stSlider > div > div { background: #1e2633; }

/* Titres */
h1, h2, h3, .mono { font-family: 'Space Mono', monospace; }
h1 { font-size: 1.6em !important; letter-spacing: -0.5px; color: #e6edf3; }
h3 { font-size: 1.0em !important; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-top: 1.4em !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: #0d1117; gap: 4px; border-bottom: 1px solid #1e2633; }
.stTabs [data-baseweb="tab"] { background: transparent; border-radius: 6px 6px 0 0; color: #8b949e; font-family: 'Space Mono', monospace; font-size: .82em; padding: 8px 18px; border: none; }
.stTabs [aria-selected="true"] { background: #161b22 !important; color: #e6edf3 !important; border-bottom: 2px solid #238636 !important; }

/* Cards */
.card {
    background: #0d1117;
    border: 1px solid #1e2633;
    border-radius: 12px;
    padding: 18px 22px;
    margin: 10px 0;
}
.card-accent { border-left: 3px solid #238636; }

/* Metric pills */
.pill {
    display: inline-block;
    background: #161b22;
    border: 1px solid #1e2633;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: .75em;
    font-family: 'Space Mono', monospace;
    margin: 2px 3px;
    color: #8b949e;
}
.pill-green  { border-color: #238636; color: #3fb950; background: #0d1f12; }
.pill-red    { border-color: #da3633; color: #f85149; background: #1f0d0d; }
.pill-yellow { border-color: #9e6a03; color: #d29922; background: #1f1a0d; }
.pill-blue   { border-color: #1f6feb; color: #79c0ff; background: #0d1627; }

/* Status bar */
.status-bar {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    background: #0d1117;
    border: 1px solid #1e2633;
    border-radius: 8px;
    padding: 8px 14px;
    margin: 8px 0;
    font-family: 'Space Mono', monospace;
    font-size: .75em;
    color: #8b949e;
}
.status-item { display: flex; align-items: center; gap: 5px; }
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-green  { background: #3fb950; box-shadow: 0 0 5px #3fb950; }
.dot-red    { background: #f85149; }
.dot-yellow { background: #d29922; }

/* Indicator boxes */
.ind-box {
    background: #0d1117;
    border: 1px solid #1e2633;
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
    transition: border-color .2s;
}
.ind-value { font-family: 'Space Mono', monospace; font-size: 1.8em; font-weight: 700; line-height: 1.1; }
.ind-label { font-size: .7em; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.ind-sub   { font-size: .72em; margin-top: 4px; }

/* Alert banners */
.banner {
    border-radius: 8px;
    padding: 10px 16px;
    margin: 6px 0;
    font-size: .88em;
    font-weight: 500;
    border-left: 3px solid;
}
.banner-green  { background: #0d1f12; border-color: #3fb950; color: #7ee787; }
.banner-yellow { background: #1a1400; border-color: #d29922; color: #e3b341; }
.banner-red    { background: #1f0d0d; border-color: #f85149; color: #ffa198; }
.banner-blue   { background: #0d1627; border-color: #79c0ff; color: #a5d6ff; }

/* Signal card */
.signal-card {
    border-radius: 12px;
    padding: 20px 24px;
    margin-top: 16px;
    border: 1px solid #1e2633;
    background: #0d1117;
}
.signal-main { font-family: 'Space Mono', monospace; font-size: 1.8em; font-weight: 700; margin: 8px 0 4px; }
.score-row { font-size: .78em; color: #8b949e; font-family: 'Space Mono', monospace; }

/* Ratio grid */
.ratio-item {
    background: #0d1117;
    border: 1px solid #1e2633;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 4px 0;
}
.ratio-label { font-size: .68em; color: #8b949e; text-transform: uppercase; letter-spacing: .8px; }
.ratio-value { font-family: 'Space Mono', monospace; font-size: 1.1em; font-weight: 700; margin-top: 2px; }
.ratio-sub   { font-size: .7em; color: #8b949e; }

/* Separator */
.sep { border: none; border-top: 1px solid #1e2633; margin: 16px 0; }

/* Buttons */
.stButton > button {
    background: #238636 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Space Mono', monospace !important;
    font-size: .82em !important;
    font-weight: 700 !important;
    padding: 10px 20px !important;
    transition: background .2s !important;
    width: 100%;
}
.stButton > button:hover { background: #2ea043 !important; }

/* Selectbox / inputs */
.stSelectbox > div, .stNumberInput > div { font-family: 'DM Sans', sans-serif; }
.stNumberInput input { font-family: 'Space Mono', monospace !important; }

/* DataFrame */
.stDataFrame { border: 1px solid #1e2633; border-radius: 10px; overflow: hidden; }

/* Expander */
.st-expander { border: 1px solid #1e2633 !important; border-radius: 10px !important; background: #0d1117 !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# RÉFÉRENTIEL BRVM
# ══════════════════════════════════════════════════════════════════
TICKERS_BRVM = {
    "SNTS":  ("SONATEL SENEGAL",                         "Télécommunications"),
    "ORAC":  ("ORANGE COTE D'IVOIRE",                    "Télécommunications"),
    "ONTBF": ("ONATEL BURKINA FASO",                     "Télécommunications"),
    "BOAB":  ("BANK OF AFRICA BENIN",                    "Services Financiers"),
    "BOABF": ("BANK OF AFRICA BURKINA FASO",             "Services Financiers"),
    "BOAC":  ("BANK OF AFRICA COTE D'IVOIRE",            "Services Financiers"),
    "BOAM":  ("BANK OF AFRICA MALI",                     "Services Financiers"),
    "BOAN":  ("BANK OF AFRICA NIGER",                    "Services Financiers"),
    "BOAS":  ("BANK OF AFRICA SENEGAL",                  "Services Financiers"),
    "BICB":  ("BICICI BENIN",                            "Services Financiers"),
    "BICC":  ("BICI COTE D'IVOIRE",                      "Services Financiers"),
    "CBIBF": ("CORIS BANK INTERNATIONAL BURKINA FASO",   "Services Financiers"),
    "ECOC":  ("ECOBANK COTE D'IVOIRE",                   "Services Financiers"),
    "ETIT":  ("ECOBANK TRANSNATIONAL (ETI) TOGO",        "Services Financiers"),
    "NSBC":  ("NSIA BANQUE COTE D'IVOIRE",               "Services Financiers"),
    "ORGT":  ("ORAGROUP TOGO",                           "Services Financiers"),
    "SAFC":  ("ALIOS FINANCE COTE D'IVOIRE",             "Services Financiers"),
    "SGBC":  ("SGB COTE D'IVOIRE",                       "Services Financiers"),
    "SIBC":  ("SOCIETE IVOIRIENNE DE BANQUE",            "Services Financiers"),
    "CIEC":  ("CIE COTE D'IVOIRE",                       "Services Publics"),
    "SDCC":  ("SODE COTE D'IVOIRE",                      "Services Publics"),
    "TTLC":  ("TOTAL ENERGIES COTE D'IVOIRE",            "Énergie"),
    "TTLS":  ("TOTAL ENERGIES SENEGAL",                  "Énergie"),
    "SHEC":  ("VIVO ENERGY COTE D'IVOIRE",               "Énergie"),
    "SMBC":  ("SMB COTE D'IVOIRE",                       "Énergie"),
    "FTSC":  ("FILTISAC COTE D'IVOIRE",                  "Industriels"),
    "CABC":  ("SICABLE COTE D'IVOIRE",                   "Industriels"),
    "STAC":  ("SETAO COTE D'IVOIRE",                     "Industriels"),
    "SDSC":  ("AFRICA GLOBAL LOGISTICS CI",              "Industriels"),
    "SEMC":  ("EVIOSYS PACKAGING SIEM CI",               "Industriels"),
    "SIVC":  ("ERIUM CI",                                "Industriels"),
    "NTLC":  ("NESTLE COTE D'IVOIRE",                    "Consommation de base"),
    "PALC":  ("PALM COTE D'IVOIRE",                      "Consommation de base"),
    "SPHC":  ("SAPH COTE D'IVOIRE",                      "Consommation de base"),
    "SICC":  ("SICOR COTE D'IVOIRE",                     "Consommation de base"),
    "STBC":  ("SITAB COTE D'IVOIRE",                     "Consommation de base"),
    "SOGC":  ("SOGB COTE D'IVOIRE",                      "Consommation de base"),
    "SLBC":  ("SOLIBRA COTE D'IVOIRE",                   "Consommation de base"),
    "SCRC":  ("SUCRIVOIRE COTE D'IVOIRE",                "Consommation de base"),
    "UNLC":  ("UNILEVER COTE D'IVOIRE",                  "Consommation de base"),
    "BNBC":  ("BERNABE COTE D'IVOIRE",                   "Consommation discrétionnaire"),
    "CFAC":  ("CFAO MOTORS COTE D'IVOIRE",               "Consommation discrétionnaire"),
    "LNBB":  ("LOTERIE NATIONALE DU BENIN",              "Consommation discrétionnaire"),
    "NEIC":  ("NEI-CEDA COTE D'IVOIRE",                  "Consommation discrétionnaire"),
    "ABJC":  ("SERVAIR ABIDJAN COTE D'IVOIRE",           "Consommation discrétionnaire"),
    "PRSC":  ("TRACTAFRIC MOTORS COTE D'IVOIRE",         "Consommation discrétionnaire"),
    "UNXC":  ("UNIWAX COTE D'IVOIRE",                    "Consommation discrétionnaire"),
}

SECTEURS = [
    "Télécommunications", "Consommation discrétionnaire",
    "Services Financiers", "Consommation de base",
    "Industriels", "Énergie", "Services Publics",
]
SECTEUR_EMOJI = {
    "Télécommunications": "📡", "Services Financiers": "🏦",
    "Consommation de base": "🛒", "Consommation discrétionnaire": "🛍️",
    "Industriels": "⚙️", "Énergie": "⚡", "Services Publics": "🏛️",
}
PER_SECTORIELS  = {"Télécommunications": 10.11, "Consommation discrétionnaire": 72.48,
                   "Services Financiers": 11.08, "Consommation de base": 14.80,
                   "Industriels": 22.23, "Énergie": 17.63, "Services Publics": 17.65}

# P/Book sectoriel calibré BRVM — seuil d'acceptabilité, pas moyenne de marché
# Banques : faible levier historique BRVM → 1.2x raisonnable
# Télécoms : actifs immatériels dominants → 3.5x acceptable
# Conso discrétionnaire : volatile, PBR élevé souvent injustifié → 2.0x
PBR_SECTORIELS  = {"Télécommunications": 3.50, "Consommation discrétionnaire": 2.00,
                   "Services Financiers": 1.20, "Consommation de base": 2.50,
                   "Industriels": 1.80, "Énergie": 2.00, "Services Publics": 1.50}

TAUX_DCF        = {"Télécommunications": 0.11, "Consommation discrétionnaire": 0.13,
                   "Services Financiers": 0.11, "Consommation de base": 0.12,
                   "Industriels": 0.14, "Énergie": 0.13, "Services Publics": 0.11}
SAISONNALITE_S1 = {"Télécommunications": 0.50, "Consommation discrétionnaire": 0.45,
                   "Services Financiers": 0.48, "Consommation de base": 0.48,
                   "Industriels": 0.45, "Énergie": 0.52, "Services Publics": 0.50}

SIGNAL_COLORS = {
    "🟢 FORT ACHAT": "#3fb950", "🔵 ACHAT": "#79c0ff",
    "🟡 SURVEILLER": "#d29922", "🟠 ALLÉGER": "#ffa657",
    "🔴 SORTIR": "#f85149",     "🔴 BLOQUÉ RSI": "#f85149",
    "🔴 BLOQUÉ BB": "#f85149",  "🔴 SURÉVALUÉ": "#f85149",
    "🟡 HORS MARGE": "#d29922", "🟡 LIQUIDITÉ FAIBLE": "#d29922",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
RICHBOURSE_BASE = "https://www.richbourse.com"

# ══════════════════════════════════════════════════════════════════
# SQLITE — FONDAMENTAUX
# ══════════════════════════════════════════════════════════════════
DB_PATH = "fondamentaux_brvm.db"

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS fondamentaux (
        ticker TEXT PRIMARY KEY, secteur TEXT, periode TEXT, annee TEXT,
        est_banque INTEGER DEFAULT 0, nombre_actions REAL, dividende REAL,
        bpa_prec REAL, bpa_n2 REAL, capitaux_propres REAL, resultat REAL,
        total_actif REAL, dettes_totales REAL, stabilite_bpa TEXT,
        pnb REAL, resultat_b REAL, encours_credits REAL, depots_clientele REAL,
        maj_at TEXT)""")
    # Migration douce : ajouter bpa_n2 si absent (base existante)
    try:
        conn.execute("ALTER TABLE fondamentaux ADD COLUMN bpa_n2 REAL")
        conn.commit()
    except Exception:
        pass
    conn.commit()
    return conn

def save_fond(ticker, data):
    data = {**data, "ticker": ticker.upper(), "maj_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
    with db() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO fondamentaux ({','.join(data)}) VALUES ({','.join(['?']*len(data))})",
            list(data.values()))

def load_fond(ticker):
    try:
        with db() as conn:
            row = conn.execute("SELECT * FROM fondamentaux WHERE ticker=?", (ticker.upper(),)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None

def list_fonds():
    try:
        with db() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT ticker, secteur, maj_at FROM fondamentaux ORDER BY maj_at DESC").fetchall()]
    except Exception:
        return []

def del_fond(ticker):
    with db() as conn:
        conn.execute("DELETE FROM fondamentaux WHERE ticker=?", (ticker.upper(),))

# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════
_NULS = {"", "-", "–", "—", "N/D", "N/A", "nd", "na", "nc", "n/c", "null", "none"}

def to_float(v, default=None):
    s = (str(v).replace(" ", "").replace("\u202f", "").replace("\u2009", "")
         .replace("\xa0", "").replace(",", ".").replace("%", "").strip())
    if s.lower() in _NULS:
        return default
    try:
        return float(s)
    except Exception:
        return default

def _normalize(s):
    import unicodedata as _ud
    s = str(s).strip().lower().replace(" ", "").replace("\xa0", "")
    return "".join(c for c in _ud.normalize("NFD", s) if _ud.category(c) != "Mn")

def _parse_table(html, ticker):
    """BS4 row-scanner → pd.read_html fallback. Retourne (prix, variation)."""
    tk = ticker.upper().strip()
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                if tk not in [c.upper() for c in cells]:
                    continue
                nums   = [to_float(c) for c in cells]
                prices = [v for v in nums if v and v > 50]
                if not prices:
                    continue
                prix = prices[0]
                var  = next((v for v in nums if v is not None and -30 < v < 30 and v != prix), 0.0)
                return prix, var
    try:
        for df in pd.read_html(StringIO(html)):
            df.columns = [_normalize(c) for c in df.columns]
            col_tk = next((c for c in df.columns if any(k in c for k in ["symbol","ticker","code","valeur","titre","sigle"])), None)
            col_px = next((c for c in df.columns if any(k in c for k in ["cours","cotation","close","prix","dernier","actuel"])), None)
            if not col_tk or not col_px:
                continue
            mask = df[col_tk].astype(str).str.upper().str.strip() == tk
            if not mask.any():
                continue
            row = df[mask].iloc[0]
            px  = to_float(row[col_px])
            if px and px > 50:
                col_var = next((c for c in df.columns if any(k in c for k in ["variation","var","change","evol","%"])), None)
                return px, to_float(row[col_var], 0.0) if col_var else 0.0
    except Exception:
        pass
    return None, None

# ══════════════════════════════════════════════════════════════════
# SCRAPING — COURS
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_cours(ticker: str) -> dict:
    """Cascade cours : richbourse → brvm.org → sikafinance"""
    tk = ticker.upper().strip()
    COL_TK = ["symbole","ticker","code","valeur","titre","action"]
    COL_PX = ["cours actuel","actuel","dernier cours","cours","clôture","cloture","close","prix"]
    COL_VR = ["variation","var","évolution","evolution"]

    # ── Richbourse ──────────────────────────────────────────────
    for url in [f"{RICHBOURSE_BASE}/common/variation/index",
                f"{RICHBOURSE_BASE}/common/variation/index/veille/tout"]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if resp.status_code != 200 or len(resp.text) < 500:
                continue
            for df in pd.read_html(StringIO(resp.text)):
                df.columns = [str(c).strip().lower().replace(" ", "").replace("\xa0", "") for c in df.columns]
                col_tk  = next((c for c in df.columns if any(k in c for k in COL_TK)), None)
                col_px  = next((c for c in df.columns if any(k in c for k in COL_PX)), None)
                col_var = next((c for c in df.columns if any(k in c for k in COL_VR)), None)
                if not col_tk:
                    for col in df.columns:
                        if df[col].astype(str).str.upper().str.strip().eq(tk).any():
                            col_tk = col; break
                if not col_tk or not col_px:
                    continue
                mask = df[col_tk].astype(str).str.upper().str.strip() == tk
                sub  = df[mask].dropna(subset=[col_px])
                if sub.empty:
                    continue
                px = to_float(sub[col_px].iloc[0])
                vr = to_float(sub[col_var].iloc[0], 0.0) if col_var else 0.0
                if px and px > 0:
                    return {"prix": px, "variation_pct": vr, "source": "richbourse"}
        except Exception:
            continue

    # ── brvm.org ────────────────────────────────────────────────
    for url in ["https://www.brvm.org/fr/cours-actions/0",
                "https://www.brvm.org/fr/cours-actions/0/symbole/asc/100/1"]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code == 200 and tk in r.text.upper():
                px, var = _parse_table(r.text, tk)
                if px:
                    return {"prix": px, "variation_pct": var or 0.0, "source": "brvm.org"}
        except Exception:
            continue

    # ── Sikafinance ─────────────────────────────────────────────
    for url in ["https://www.sikafinance.com/marches/aaz",
                f"https://www.sikafinance.com/valeur/BRVM/{tk}"]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code == 200 and tk in r.text.upper():
                px, var = _parse_table(r.text, tk)
                if px:
                    return {"prix": px, "variation_pct": var or 0.0, "source": "sikafinance"}
        except Exception:
            continue

    return {}

# ══════════════════════════════════════════════════════════════════
# SCRAPING — HISTORIQUE RICHBOURSE → INDICATEURS TECHNIQUES
# ══════════════════════════════════════════════════════════════════
def _parse_historique_html(html: str) -> pd.DataFrame:
    """
    Parse la table historique richbourse — version défensive avec logs.
    """
    if not HAS_BS4:
        return pd.DataFrame()
    soup  = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        st.warning("⚠️ DEBUG: Aucune balise <table> trouvée dans la réponse richbourse")
        return pd.DataFrame()

    rows = table.find_all("tr")
    if len(rows) < 2:
        return pd.DataFrame()

    header_cells = [th.get_text(strip=True).lower().replace("\xa0","").replace(" ","")
                    for th in rows[0].find_all(["th","td"])]

    # ── LOG DEBUG : afficher les en-têtes détectés ──────────────
    if st.session_state.get("_debug_hist"):
        st.code(f"Headers détectés : {header_cells}", language=None)

    # Détection robuste des colonnes
    idx_close = next(
        (i for i, h in enumerate(header_cells) if "ajust" in h and "cours" in h),
        next((i for i, h in enumerate(header_cells) if "normal" in h and "cours" in h),
        next((i for i, h in enumerate(header_cells) if "cours" in h or "close" in h or "prix" in h), 3))
    )
    idx_vol = next(
        (i for i, h in enumerate(header_cells) if "ajust" in h and "vol" in h),
        next((i for i, h in enumerate(header_cells) if "vol" in h), 4)
    )
    idx_date = next(
        (i for i, h in enumerate(header_cells) if "date" in h or "jour" in h), 0
    )

    data = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) <= max(idx_close, idx_date):
            continue
        date_txt  = cells[idx_date].get_text(strip=True)
        close_txt = cells[idx_close].get_text(strip=True)
        vol_txt   = cells[idx_vol].get_text(strip=True) if len(cells) > idx_vol else "0"
        data.append([date_txt, close_txt, vol_txt])

    if not data:
        if st.session_state.get("_debug_hist"):
            st.warning(f"DEBUG: Table trouvée ({len(rows)} lignes) mais aucune donnée extraite")
        return pd.DataFrame()

    def _clean_num(series):
        return pd.to_numeric(
            series.str.replace(r"[\xa0\s\u202f\u2009]", "", regex=True)
                  .str.replace(",", ".", regex=False),
            errors="coerce")

    df = pd.DataFrame(data, columns=["date", "close", "volume"])
    df["date"]   = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["close"]  = _clean_num(df["close"])
    df["volume"] = _clean_num(df["volume"])

    result = df.dropna(subset=["date", "close"])
    if st.session_state.get("_debug_hist"):
        st.success(f"DEBUG: {len(result)} lignes valides extraites (close max={result['close'].max():.0f})")
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_historique(ticker: str, nb: int = 120) -> pd.DataFrame:
    """
    Récupère l'historique — version robuste avec fallback POST et logs.
    """
    tk   = ticker.upper()
    hdrs = {**HEADERS, "Referer": f"{RICHBOURSE_BASE}/", "Accept": "text/html,application/xhtml+xml"}
    frames = []
    errors = []

    url_base = f"{RICHBOURSE_BASE}/common/variation/historique/{tk}"

    # ── Appel 1 : page par défaut ──────────────────────────────
    try:
        r = requests.get(url_base, headers=hdrs, timeout=20, verify=False)
        if r.status_code == 200 and "<table" in r.text.lower():
            df0 = _parse_historique_html(r.text)
            if not df0.empty:
                frames.append(df0)
        else:
            errors.append(f"Appel 1 : HTTP {r.status_code} / table={'<table' in r.text.lower()}")
    except Exception as e:
        errors.append(f"Appel 1 exception : {e}")

    # ── Appels 2-4 : plages glissantes (GET + POST) ────────────
    from datetime import timedelta
    today = datetime.now()
    ranges = [
        (today - timedelta(days=540), today - timedelta(days=360)),
        (today - timedelta(days=360), today - timedelta(days=180)),
        (today - timedelta(days=180), today),
    ]
    for d_start, d_end in ranges:
        for method in ["GET", "POST"]:
            payload = {
                "action":     tk,
                "periode":    "Journalière",
                "date_debut": d_start.strftime("%d/%m/%Y"),   # format FR alternatif
                "date_fin":   d_end.strftime("%d/%m/%Y"),
            }
            try:
                if method == "GET":
                    # Essai avec format ISO
                    p2 = {k: v for k, v in payload.items()}
                    p2["date_debut"] = d_start.strftime("%Y-%m-%d")
                    p2["date_fin"]   = d_end.strftime("%Y-%m-%d")
                    r = requests.get(url_base, params=p2, headers=hdrs, timeout=20, verify=False)
                else:
                    r = requests.post(url_base, data=payload, headers=hdrs, timeout=20, verify=False)

                if r.status_code == 200 and "<table" in r.text.lower():
                    df_i = _parse_historique_html(r.text)
                    if not df_i.empty:
                        frames.append(df_i)
                        break  # POST inutile si GET a marché
                else:
                    errors.append(f"{method} {d_start.date()}→{d_end.date()}: HTTP {r.status_code}")
            except Exception as e:
                errors.append(f"{method} exception : {e}")
                continue

    # ── Stocker les erreurs en session pour debug ───────────────
    if errors and not frames:
        st.session_state["_hist_errors"] = errors

    if not frames:
        return pd.DataFrame()

    df_all = (pd.concat(frames, ignore_index=True)
                .drop_duplicates(subset=["date"])
                .dropna(subset=["date","close"])
                .sort_values("date")
                .tail(nb)
                .reset_index(drop=True))
    return df_all


def calc_indicateurs(df: pd.DataFrame) -> dict:
    """
    Calcule BB(20,2), EMA(20), RSI(14), var_3m, vol_moy_20j.
    Version avec messages d'erreur explicites.
    """
    if df.empty:
        st.session_state["_indic_error"] = "DataFrame historique vide"
        return {}
    if len(df) < 20:
        st.session_state["_indic_error"] = f"Trop peu de points : {len(df)} (min 20)"
        return {}

    try:
        close = df["close"].astype(float)

        ema20    = close.ewm(span=20, adjust=False).mean().iloc[-1]
        delta    = close.diff()
        gain     = delta.clip(lower=0).rolling(14).mean()
        loss     = (-delta.clip(upper=0)).rolling(14).mean()
        rs       = gain / loss.replace(0, np.nan)
        rsi_val  = (100 - (100 / (1 + rs))).iloc[-1]
        bb_mid   = close.rolling(20).mean().iloc[-1]
        bb_std   = close.rolling(20).std().iloc[-1]
        bb_sup   = bb_mid + 2 * bb_std
        bb_inf   = bb_mid - 2 * bb_std

        nb_pts   = len(close)
        lookback = min(63, nb_pts - 1)
        var_3m   = (close.iloc[-1] / close.iloc[-lookback - 1] - 1) * 100 if lookback > 0 else 0.0

        vol_moy_20j = 0.0
        if "volume" in df.columns:
            vols = pd.to_numeric(df["volume"], errors="coerce").dropna()
            if len(vols) >= 5:
                vol_moy_20j = float(vols.tail(20).mean())

        check = {"rsi": rsi_val, "ema20": ema20, "bb_sup": bb_sup,
                 "bb_inf": bb_inf, "bb_mid": bb_mid, "var_3m": var_3m}
        bad = {k: v for k, v in check.items() if not np.isfinite(v)}
        if bad:
            st.session_state["_indic_error"] = f"Valeurs NaN/inf : {bad}"
            return {}

        return {
            "rsi":         round(float(rsi_val), 1),
            "ema20":       round(float(ema20), 0),
            "bb_sup":      round(float(bb_sup), 0),
            "bb_inf":      round(float(bb_inf), 0),
            "bb_mid":      round(float(bb_mid), 0),
            "var_3m":      round(float(var_3m), 2),
            "vol_moy_20j": round(float(vol_moy_20j), 0),
            "nb_pts":      nb_pts,
        }
    except Exception as e:
        st.session_state["_indic_error"] = f"Exception : {type(e).__name__}: {e}"
        return {}


def get_marche(ticker: str) -> dict:
    """
    Pipeline unifié :
      1. fetch_cours()       → prix + variation
      2. fetch_historique()  → BB(20,2) + EMA(20) + RSI(14) calculés localement
    """
    tk = ticker.upper().strip()
    result = {}
    
    try:
        result.update(fetch_cours(tk))
    except Exception:
        pass
    
    try:
        df_hist = fetch_historique(tk)
        if not df_hist.empty:
            indics = calc_indicateurs(df_hist)
            if indics:  # Seulement si calc_indicateurs a réussi
                result.update(indics)
                result["_source_tech"] = f"richbourse · {indics.get('nb_pts', 0)} pts"
    except Exception:
        pass
    
    return result

# ══════════════════════════════════════════════════════════════════
# CALCULS FONDAMENTAUX
# ══════════════════════════════════════════════════════════════════
def extrapoler(resultat, periode, secteur):
    s = SAISONNALITE_S1.get(secteur, 0.50)
    if "9 mois" in periode:
        return resultat / 3 * 4, "9M × 4/3", "Elevee"
    elif "Semestriel" in periode:
        return resultat / s, f"S1 / {s:.2f}", "Moderee"
    return resultat, "Données annuelles", "Annuelle"

def vi_dcf(bpa, g_bpa, taux):
    """
    DCF sur 5 ans + valeur terminale (Gordon-Shapiro).
    g1 borné à [-10%, +20%] pour éviter les extrapolations extrêmes.
    g2 (croissance perpétuelle) = 3% — cohérent avec croissance UEMOA long terme.
    """
    g1 = min(max(g_bpa / 100, -0.10), 0.20)
    g2, r = 0.03, taux
    flux = sum(bpa * (1 + g1) ** t / (1 + r) ** t for t in range(1, 6))
    vt   = bpa * (1 + g1) ** 5 * (1 + g2) / (r - g2) / (1 + r) ** 5
    return flux + vt


def vi_graham_sectoriel(bpa, val_book, secteur):
    """
    Graham recalibré BRVM : √(PER_sect × PBR_sect × BPA × Book).
    Remplace le 22.5 universel (calibré NYSE années 70) par des
    plafonds sectoriels BRVM. Résultat : garde-fou cohérent avec
    les niveaux de valorisation réels du marché.
    """
    per_s = PER_SECTORIELS.get(secteur, 15.0)
    pbr_s = PBR_SECTORIELS.get(secteur, 1.5)
    return np.sqrt(max(per_s * pbr_s * bpa * val_book, 0)) if bpa > 0 else 0


def calc_vi(bpa, val_book, secteur, g_bpa, taux_actua):
    """
    Valeur intrinsèque recalibrée — 3 méthodes, poids optimisés :

      FV_PER  50% — ancre principale : BPA × PER sectoriel BRVM
                    capture le niveau de valorisation "normal" du secteur
      DCF     35% — ancre fondamentale : flux actualisés sur 5 ans
                    capte la croissance et la qualité du business
      Graham  15% — garde-fou : cohérence PER × P/Book sectoriel
                    évite les valorisations déconnectées du bilan
                    (réduit de 40% → 15% : évite la domination d'une
                     formule calibrée pour le NYSE des années 70)

    Fallback : si Graham = 0 (BPA ≤ 0), VI = FV_PER×60% + DCF×40%.
    """
    fv_per   = bpa * PER_SECTORIELS.get(secteur, 15.0) if bpa > 0 else 0
    fv_dcf   = vi_dcf(bpa, g_bpa, taux_actua) if bpa > 0 else 0
    graham   = vi_graham_sectoriel(bpa, val_book, secteur)

    if graham > 0:
        vi = fv_per * 0.50 + fv_dcf * 0.35 + graham * 0.15
    else:
        vi = fv_per * 0.60 + fv_dcf * 0.40

    return vi, fv_per, fv_dcf, graham

QUALITY_FLOOR = 0.40   # en dessous → signal plafonné à SURVEILLER
VOL_MIN_FCFA  = 1_000_000  # volume moyen minimum en FCFA (valeur × volume)

def marge_variable(q_score: float) -> float:
    """Marge de sécurité dynamique selon la qualité du titre."""
    if q_score >= 0.70:  return 0.10
    if q_score >= 0.50:  return 0.15
    return 0.20

def calc_signal(score, upside, survalu, hors_marge, f_rsi, f_bb, q_score, f_liquidite=False):
    if f_rsi:                              return "🔴 BLOQUÉ RSI"
    if f_bb:                               return "🔴 BLOQUÉ BB"
    if f_liquidite:                        return "🟡 LIQUIDITÉ FAIBLE"
    if survalu:                            return "🔴 SURÉVALUÉ"
    if hors_marge:                         return "🟡 HORS MARGE"
    # Quality floor — même un bon score ne passe pas si la qualité est insuffisante
    if q_score < QUALITY_FLOOR:
        if score >= 0.40 and upside > 5:   return "🟡 SURVEILLER"
        return "🟠 ALLÉGER"
    if score >= 0.65 and upside > 25:      return "🟢 FORT ACHAT"
    if score >= 0.50 and upside > 15:      return "🔵 ACHAT"
    if score >= 0.40 and upside > 5:       return "🟡 SURVEILLER"
    if score < 0.35 or upside < -15:       return "🔴 SORTIR"
    return "🟠 ALLÉGER"

# ══════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════
if "screener" not in st.session_state:
    st.session_state.screener = []

# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ Paramètres")
    mode_simple = st.radio("Mode", ["Simple", "Expert"], horizontal=True) == "Simple"

    if mode_simple:
        # Profil Value-Momentum actif, horizon 1–3 ans
        W_V, W_Q, W_M = 0.25, 0.40, 0.35
    else:
        st.markdown("**Pondérations du score**")
        W_V = st.slider("Value",    0.1, 0.6, 0.25, 0.05)
        W_Q = st.slider("Quality",  0.1, 0.6, 0.40, 0.05)
        W_M = st.slider("Momentum", 0.1, 0.6, 0.35, 0.05)
        T   = W_V + W_Q + W_M; W_V /= T; W_Q /= T; W_M /= T
        st.caption(f"V {W_V:.0%} · Q {W_Q:.0%} · M {W_M:.0%}")

    st.markdown("---")
    st.markdown("**Filtres techniques**")
    RSI_HAUT = st.slider("RSI surachat", 65, 85, 75, 5)
    RSI_BAS  = st.slider("RSI survente", 15, 35, 25, 5)

    st.markdown("**Marge de sécurité**")
    st.markdown("""
    <div style='font-size:.75em;color:#8b949e;background:#0d1117;border:1px solid #1e2633;
                border-radius:6px;padding:8px 10px;font-family:Space Mono,monospace'>
    Dynamique selon Quality :<br>
    Quality ≥ 0.70 → <span style='color:#3fb950'>10%</span><br>
    Quality 0.50–0.70 → <span style='color:#d29922'>15%</span><br>
    Quality &lt; 0.50 → <span style='color:#f85149'>20%</span>
    </div>""", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🗑️ Vider cache cours"):
        fetch_cours.clear()
        fetch_historique.clear()
        st.success("Cache vidé ✅"); st.rerun()
    if st.button("🗑️ Vider le screener"):
        st.session_state.screener = []; st.rerun()

    st.markdown("---")
    st.markdown("**Import / Export**")
    fonds_list = list_fonds()
    if fonds_list:
        if st.button("⬇️ Exporter JSON"):
            with db() as conn:
                rows = [dict(r) for r in conn.execute("SELECT * FROM fondamentaux").fetchall()]
            st.download_button("Télécharger", json.dumps(rows, ensure_ascii=False, indent=2),
                               "fondamentaux_brvm.json", mime="application/json")
    up = st.file_uploader("📥 Importer JSON", type="json")
    if up:
        try:
            rows = json.loads(up.read())
            for row in rows:
                tk_ = row.pop("ticker", None)
                if tk_: save_fond(tk_, row)
            st.success(f"✅ {len(rows)} titres importés"); st.rerun()
        except Exception as e:
            st.error(str(e))

st.markdown("---")
    st.markdown("**🐛 Debug**")
    st.session_state["_debug_hist"] = st.checkbox("Activer logs historique", value=False)
    
    # Afficher les erreurs capturées
    if "_hist_errors" in st.session_state and st.session_state["_hist_errors"]:
        with st.expander("❌ Erreurs fetch historique"):
            for e in st.session_state["_hist_errors"]:
                st.code(e)
    if "_indic_error" in st.session_state and st.session_state["_indic_error"]:
        st.error(f"Calc indicateurs : {st.session_state['_indic_error']}")

# ══════════════════════════════════════════════════════════════════
# EN-TÊTE
# ══════════════════════════════════════════════════════════════════
col_title, col_meta = st.columns([3, 1])
with col_title:
    st.markdown("# ⬡ Screener BRVM")
with col_meta:
    nb_screener = len(st.session_state.screener)
    st.markdown(f"""
    <div style='text-align:right;padding-top:8px'>
        <span class='pill pill-{'green' if nb_screener>0 else 'blue'}'>{nb_screener} titre{'s' if nb_screener>1 else ''} analysé{'s' if nb_screener>1 else ''}</span>
    </div>""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["➕  Analyser", "📊  Dashboard", "💾  Fondamentaux", "📖  Méthode"])

# ══════════════════════════════════════════════════════════════════
# TAB 1 — FORMULAIRE
# ══════════════════════════════════════════════════════════════════
with tab1:

    LABELS  = {tk: f"{tk} — {v[0]}" for tk, v in TICKERS_BRVM.items()}
    choices = ["(Saisie libre)"] + [LABELS[tk] for tk in sorted(TICKERS_BRVM)]

    # ── Sélection ──────────────────────────────────────────────
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        choice = st.selectbox("Ticker BRVM", choices)
        if choice == "(Saisie libre)":
            titre = st.text_input("Ticker", placeholder="ex: SNTS").upper().strip()
        else:
            titre = next(tk for tk, lb in LABELS.items() if lb == choice)
    with c2:
        periode = st.selectbox("Période", ["Annuel complet", "9 mois (T1+T2+T3)", "Semestriel (S1)"])
    with c3:
        annee = st.selectbox("Exercice", ["2025", "2024", "2023"])

    secteur_auto = TICKERS_BRVM.get(titre, (None, None))[1] if titre else None
    nom_auto     = TICKERS_BRVM.get(titre, (None, None))[0] if titre else None
    fond_saved   = load_fond(titre) if titre and len(titre) >= 3 else None

    # ── Chargement marché ──────────────────────────────────────
    mdata = {}
    if titre and len(titre) >= 3:
        with st.spinner(f"Chargement {titre}…"):
            mdata = get_marche(titre)

    # ── Carte ticker ───────────────────────────────────────────
    if titre and len(titre) >= 3:
        em  = SECTEUR_EMOJI.get(secteur_auto or "", "")
        px_ok = "prix" in mdata
        var_v = mdata.get("variation_pct", 0.0)
        var_c = "#3fb950" if var_v >= 0 else "#f85149"
        if px_ok:
            px_str = f"{mdata['prix']:,.0f} FCFA &nbsp; <span style='color:{var_c}'>{'+' if var_v >= 0 else ''}{var_v:.2f}%</span>"
        else:
            px_str = "<span style='color:#d29922'>⚠️ Cours non disponible</span>"

        saved_badge = "<span class='pill pill-blue'>💾 sauvegardé</span>" if fond_saved else ""
        src_badge   = f"<span class='pill'>{mdata.get('source','')}</span>" if px_ok else ""

        st.markdown(f"""
        <div class="card card-accent">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
            <div>
              <span style="font-family:'Space Mono',monospace;font-size:1.4em;font-weight:700;color:#e6edf3">{titre}</span>
              <span style="color:#8b949e;margin-left:10px;font-size:.9em">{nom_auto or ''}</span><br>
              <span class="pill">{em} {secteur_auto or ''}</span> {saved_badge}
            </div>
            <div style="text-align:right">
              <div style="font-family:'Space Mono',monospace;font-size:1.15em">{px_str}</div>
              {src_badge}
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        # ── Barre de statut indicateurs ─────────────────────────
        has_prix = px_ok
        has_rsi  = "rsi"    in mdata and mdata.get("rsi") is not None
        has_bb   = "bb_sup" in mdata and "bb_inf" in mdata and mdata.get("bb_sup") is not None and mdata.get("bb_inf") is not None
        has_ema  = "ema20"  in mdata and mdata.get("ema20") is not None
        nb_pts   = mdata.get("nb_pts", 0) if mdata.get("nb_pts") is not None else 0
        src_tech = mdata.get("_source_tech", "—") if mdata.get("_source_tech") else "—"

        def _dot(ok):
            cls = "dot-green" if ok else "dot-red"
            return f"<span class='dot {cls}'></span>"

        all_ok = has_prix and has_rsi and has_bb and has_ema
        bar_border = "#3fb950" if all_ok else ("#d29922" if has_prix else "#f85149")
        
        # Construire les valeurs de manière sécurisée
        cours_val = f" {int(mdata['prix'])} FCFA" if has_prix else ""
        rsi_val = f" {mdata['rsi']:.0f}" if has_rsi else ""
        bb_val = f" {int(mdata.get('bb_inf',0))} / {int(mdata.get('bb_sup',0))}" if has_bb else ""
        ema_val = f" {int(mdata['ema20'])}" if has_ema else ""

        st.markdown(f"""
        <div class="status-bar" style="border-left:3px solid {bar_border}">
          <div class="status-item">{_dot(has_prix)} Cours{cours_val}</div>
          <div style="color:#1e2633">|</div>
          <div class="status-item">{_dot(has_rsi)} RSI{rsi_val}</div>
          <div style="color:#1e2633">|</div>
          <div class="status-item">{_dot(has_bb)} BB{bb_val}</div>
          <div style="color:#1e2633">|</div>
          <div class="status-item">{_dot(has_ema)} EMA20{ema_val}</div>
          <div style="color:#1e2633">|</div>
          <div class="status-item" style="color:#8b949e">{nb_pts} pts · {src_tech}</div>
        </div>""", unsafe_allow_html=True)

        if not has_prix:
            st.markdown('<div class="banner banner-yellow">⚠️ Cours non chargé automatiquement — saisir manuellement ci-dessous. Vider le cache pour réessayer.</div>', unsafe_allow_html=True)

        if "Annuel" not in periode:
            champ = "Crédits / Dépôts" if secteur_auto == "Services Financiers" else "Capitaux propres, actif, dettes"
            st.markdown(f'<div class="banner banner-blue">📅 Publication intermédiaire — {champ} : référez-vous au bilan {int(annee)-1}. Le résultat sera extrapolé.</div>', unsafe_allow_html=True)

    # ── Secteur ────────────────────────────────────────────────
    idx     = SECTEURS.index(secteur_auto) if secteur_auto in SECTEURS else 0
    secteur = st.selectbox("Secteur", SECTEURS, index=idx,
                           format_func=lambda s: f"{SECTEUR_EMOJI.get(s,'')} {s}")
    est_banque = secteur == "Services Financiers"
    TAUX_ACTUA = TAUX_DCF[secteur]
    if not mode_simple:
        st.caption(f"Taux DCF : {TAUX_ACTUA*100:.0f}%  ·  PER cible sectoriel : {PER_SECTORIELS[secteur]:.2f}×")

    # ── Formulaire ─────────────────────────────────────────────
    def fd(k, d):
        return fond_saved[k] if fond_saved and k in fond_saved and fond_saved[k] is not None else d

    with st.form("saisie"):
        # Prix
        px_def   = float(mdata.get("prix", 1000.0))
        src_lbl  = f"[{mdata['source']}]" if "source" in mdata else "⚠️ saisie manuelle"
        prix = st.number_input(f"💰 Prix actuel FCFA {src_lbl}", min_value=1.0, value=px_def)

        st.markdown('<hr class="sep">', unsafe_allow_html=True)

        # ── Fondamentaux ─────────────────────────────────────────
        if est_banque:
            st.markdown("**📊 Données bancaires**")
            a1, a2 = st.columns(2)
            with a1:
                pnb             = st.number_input("PNB (M FCFA)",            min_value=1.0, value=fd("pnb", 5000.0))
                encours_credits = st.number_input("Encours crédits (M FCFA)", min_value=1.0, value=fd("encours_credits", 30000.0))
            with a2:
                resultat_saisi  = st.number_input("Résultat net (M FCFA)",   value=fd("resultat_b", 800.0))
                depots          = st.number_input("Dépôts clientèle (M FCFA)", min_value=1.0, value=fd("depots_clientele", 40000.0))
            b1, b2, b3 = st.columns(3)
            with b1: nombre_actions   = st.number_input("Actions (millions)", min_value=0.001, value=fd("nombre_actions", 10.0))
            with b2: capitaux_propres = st.number_input("Cap. propres (M FCFA)", min_value=1.0, value=fd("capitaux_propres", 8000.0))
            with b3:
                dividende = st.number_input("Dividende/action (FCFA)", min_value=0.0, value=fd("dividende", 0.0))
                bpa_prec  = st.number_input("BPA an préc. (FCFA)",     value=fd("bpa_prec", 80.0))
            bpa_n2 = st.number_input("BPA N-2 (FCFA) — pour accélération",
                                      value=fd("bpa_n2", 0.0),
                                      help="BPA il y a 2 exercices")
            total_actif = dettes_totales = stabilite_bpa = None
        else:
            st.markdown("**📊 Compte de résultat**")
            a1, a2, a3 = st.columns(3)
            with a1:
                resultat_saisi = st.number_input("Résultat net (M FCFA)", value=fd("resultat", 500.0))
                nombre_actions = st.number_input("Actions (millions)",     min_value=0.001, value=fd("nombre_actions", 10.0))
            with a2:
                dividende = st.number_input("Dividende/action (FCFA)", min_value=0.0, value=fd("dividende", 0.0))
                bpa_prec  = st.number_input("BPA an préc. (FCFA)",     value=fd("bpa_prec", 80.0))
            with a3:
                if mode_simple:
                    stabilite_bpa = "Stable"
                else:
                    stabilite_bpa = st.selectbox("Régularité bénéfices", ["Stable", "Volatil", "Exceptionnel"],
                        index=["Stable", "Volatil", "Exceptionnel"].index(fd("stabilite_bpa", "Stable")))

            st.markdown("**🏦 Bilan**")
            b1, b2, b3 = st.columns(3)
            with b1: capitaux_propres = st.number_input("Cap. propres (M FCFA)", min_value=1.0, value=fd("capitaux_propres", 2000.0))
            with b2: total_actif      = st.number_input("Total actif (M FCFA)",  min_value=1.0, value=fd("total_actif", 5000.0))
            with b3: dettes_totales   = st.number_input("Dettes fin. (M FCFA)",  min_value=0.0, value=fd("dettes_totales", 1000.0))

            st.markdown("**📈 Historique BPA**")
            hp1, hp2, hp3 = st.columns(3)
            with hp1: bpa_n2   = st.number_input("BPA N-2 (FCFA)", value=fd("bpa_n2", 0.0),
                                                  help="BPA il y a 2 exercices — pour calculer l'accélération")
            with hp2: bpa_prec = st.number_input("BPA N-1 (FCFA)", value=fd("bpa_prec", 80.0))
            with hp3: st.markdown("""<div style='background:#0d1117;border:1px solid #1e2633;border-radius:8px;
                                      padding:10px;font-size:.75em;color:#8b949e;margin-top:22px'>
                                      BPA N = calculé<br>automatiquement</div>""", unsafe_allow_html=True)
            pnb = encours_credits = depots = None

        # ── Indicateurs techniques ─────────────────────────────
        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown("**📡 Indicateurs techniques**")

        has_tech = all(k in mdata and mdata.get(k) is not None for k in ["rsi", "bb_sup", "bb_inf", "ema20"])
        if has_tech:
            st.markdown(f"""<div class="banner banner-green">
            ✅ BB(20,2) · EMA(20) · RSI(14) calculés depuis l'historique Richbourse
            &nbsp;—&nbsp; RSI <b>{mdata['rsi']:.0f}</b> · BB [{mdata['bb_inf']:,.0f} / {mdata['bb_sup']:,.0f}] · EMA20 <b>{mdata['ema20']:,.0f}</b>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="banner banner-yellow">⚠️ Historique non disponible — saisir manuellement (TradingView ou richbourse.com)</div>', unsafe_allow_html=True)

        t1, t2, t3 = st.columns(3)
        with t1:
            bb_sup = st.number_input("BB supérieure (20,2)", min_value=1.0, value=float(mdata.get("bb_sup", 1100.0)))
            bb_inf = st.number_input("BB inférieure (20,2)", min_value=1.0, value=float(mdata.get("bb_inf", 900.0)))
        with t2:
            ema20  = st.number_input("EMA 20", min_value=1.0, value=float(mdata.get("ema20", 980.0)))
            var_3m = st.number_input("Variation 3 mois (%)", -50.0, 100.0,
                                     float(mdata.get("var_3m", 0.0)),
                                     help="Momentum 3 mois — signal tendance")
        with t3:
            rsi = st.number_input("RSI (14)", 0.0, 100.0, float(mdata.get("rsi", 50.0)))
            st.markdown(f"""
            <div style='background:#0d1117;border:1px solid #1e2633;border-radius:8px;padding:10px 12px;margin-top:4px;font-size:.76em;font-family:"Space Mono",monospace'>
            <div style='color:#8b949e;margin-bottom:4px'>SEUILS RSI</div>
            <span style='color:#f85149'>▲ Surachat {RSI_HAUT}</span><br>
            <span style='color:#3fb950'>▼ Survente {RSI_BAS}</span>
            </div>""", unsafe_allow_html=True)

        # Liquidité affichée hors form
        vol_20j = mdata.get("vol_moy_20j", 0)
        if vol_20j > 0:
            prix_tmp = float(mdata.get("prix", 1))
            vol_fcfa = vol_20j * prix_tmp
            liq_ok   = vol_fcfa >= VOL_MIN_FCFA
            liq_col  = "#3fb950" if liq_ok else "#d29922"
            liq_lbl  = f"{vol_fcfa/1e6:.1f} M FCFA/j" if vol_fcfa >= 1e6 else f"{vol_fcfa/1e3:.0f} K FCFA/j"
            st.markdown(f"""<div class="banner {'banner-green' if liq_ok else 'banner-yellow'}">
            {'✅' if liq_ok else '⚠️'} <b>Liquidité</b> : {liq_lbl} (vol. moy. 20j)
            {'— Suffisante pour une position standard' if liq_ok else '— Faible : entrée/sortie délicate, position réduite conseillée'}
            </div>""", unsafe_allow_html=True)

        save_cb   = st.checkbox("💾 Sauvegarder fondamentaux", value=True)
        submitted = st.form_submit_button("🔍 Analyser", use_container_width=True)

    # ─────────────────────────────────────────────────────────────
    # CALCULS & AFFICHAGE RÉSULTATS
    # ─────────────────────────────────────────────────────────────
    if submitted and titre:
        # Écraser l'entrée existante si le ticker est déjà dans le screener
        st.session_state.screener = [a for a in st.session_state.screener if a["Titre"] != titre.upper()]

        # Extrapolation
        r_an, meth, conf = extrapoler(resultat_saisi, periode, secteur)
        pnb_ = pnb if est_banque else None

        # ── Ratios de base ──────────────────────────────────────
        bpa       = r_an / nombre_actions
        val_book  = capitaux_propres / nombre_actions
        per       = prix / bpa if bpa > 0 else 99
        pbr       = prix / val_book if val_book > 0 else 99
        dy        = dividende / prix if prix > 0 else 0
        g_bpa     = ((bpa - bpa_prec) / abs(bpa_prec) * 100) if bpa_prec else 0
        roe       = r_an / capitaux_propres * 100

        # ── Accélération BPA (dérivée seconde) ─────────────────
        # g_bpa     = croissance N-1 → N
        # g_bpa_n1  = croissance N-2 → N-1
        # accel_bpa = différence → positif = accélération, négatif = décélération
        if bpa_n2 and bpa_n2 != 0 and bpa_prec:
            g_bpa_n1  = ((bpa_prec - bpa_n2) / abs(bpa_n2) * 100)
            accel_bpa = g_bpa - g_bpa_n1   # en points de %
        else:
            g_bpa_n1  = None
            accel_bpa = 0.0

        # ── Yield on Cost projeté (dividende + croissance estimée) ──
        # On estime la croissance future du dividende = moyenne g_bpa sur 2 ans
        if g_bpa_n1 is not None:
            g_div_est = (g_bpa + g_bpa_n1) / 2 / 100
        else:
            g_div_est = g_bpa / 100
        g_div_est  = min(max(g_div_est, -0.05), 0.15)   # borné entre -5% et +15%
        yoc_2ans   = (dividende * (1 + g_div_est) ** 2) / prix * 100 if prix > 0 else 0

        # ── Valeurs intrinsèques — méthode recalibrée BRVM ─────
        vi, fv_per, fv_dcf, graham = calc_vi(bpa, val_book, secteur, g_bpa, TAUX_ACTUA)

        # ── Scores ──────────────────────────────────────────────
        # Value : PER relatif 45% + P/Book relatif 55%
        # Dividende retiré — stratégie de réévaluation de cours, pas de revenus
        per_cap = min(PER_SECTORIELS[secteur], 25)
        pbr_cib = PBR_SECTORIELS[secteur]
        s_per   = np.clip(per_cap / per, 0, 1) if per > 0 else 0
        s_pbr   = np.clip(pbr_cib / pbr, 0, 1) if pbr > 0 else 0
        v_score = s_per * 0.45 + s_pbr * 0.55

        if est_banque:
            roa = dette_cp = None
            marge_b  = r_an / pnb_ if pnb_ else 0
            cd_ratio = encours_credits / depots if depots else 0
            q_score  = (np.clip(marge_b / 0.20, 0, 1) * 0.45
                      + np.clip(1 - abs(cd_ratio - 0.80) / 0.40, 0, 1) * 0.30
                      + np.clip(roe / 15, 0, 1) * 0.25)
        else:
            roa      = r_an / total_actif * 100
            dette_cp = dettes_totales / capitaux_propres
            marge_b  = cd_ratio = None
            bonus    = {"Stable": 0.20, "Volatil": 0.0, "Exceptionnel": 0.30}.get(stabilite_bpa, 0)
            q_score  = (np.clip(roe / 25, 0, 1) * 0.35
                      + np.clip(roa / 12, 0, 1) * 0.30
                      + np.clip(1 - dette_cp / 3, 0, 1) * 0.25
                      + bonus * 0.10)

        # Momentum : 60% accélération/croissance BPA + 40% variation 3 mois
        # g_bpa capte la croissance fondamentale, accel_bpa booste si accélération
        g_bpa_eff = g_bpa + np.clip(accel_bpa * 0.5, -10, 10)  # accélération amplifie
        m_score   = np.clip(g_bpa_eff / 30, -1, 1) * 0.60 + np.clip(var_3m / 20, -1, 1) * 0.40

        score = W_V * v_score + W_Q * q_score + W_M * m_score

        # ── Marge variable + prix cible ─────────────────────────
        MARGE      = marge_variable(q_score)
        prix_cible = vi * (1 - MARGE)
        upside     = (prix_cible / prix - 1) * 100
        survalu    = prix > vi
        hors_marge = prix > prix_cible and not survalu

        # ── Filtres techniques ──────────────────────────────────
        f_rsi = rsi > RSI_HAUT
        f_bb  = prix > bb_sup
        bb_pct = ((prix - bb_inf) / (bb_sup - bb_inf) * 100) if (bb_sup - bb_inf) > 0 else 50
        ecart_ema = (prix / ema20 - 1) * 100

        # ── Filtre liquidité ────────────────────────────────────
        vol_20j    = mdata.get("vol_moy_20j", 0)
        vol_fcfa   = vol_20j * prix if vol_20j > 0 else 0
        f_liquidite = vol_fcfa > 0 and vol_fcfa < VOL_MIN_FCFA

        sig     = calc_signal(score, upside, survalu, hors_marge, f_rsi, f_bb, q_score, f_liquidite)
        col_sig = SIGNAL_COLORS.get(sig, "#8b949e")

        # ── Sauvegarde ─────────────────────────────────────────
        if save_cb:
            fd_data = {"secteur": secteur, "periode": periode, "annee": annee,
                       "est_banque": 1 if est_banque else 0,
                       "nombre_actions": nombre_actions, "dividende": dividende,
                       "bpa_prec": bpa_prec, "bpa_n2": bpa_n2,
                       "capitaux_propres": capitaux_propres}
            if est_banque:
                fd_data.update({"pnb": pnb_, "resultat_b": resultat_saisi,
                                "encours_credits": encours_credits, "depots_clientele": depots})
            else:
                fd_data.update({"resultat": resultat_saisi, "total_actif": total_actif,
                                "dettes_totales": dettes_totales, "stabilite_bpa": stabilite_bpa})
            save_fond(titre, fd_data)

        # ══════════════════════════════════════════════════════
        # RÉSULTATS
        # ══════════════════════════════════════════════════════
        st.markdown("---")

        # En-tête résultats
        tags = ""
        if conf != "Annuelle":   tags += "<span class='pill pill-yellow'>⚠️ Estimé</span>"
        if "prix" in mdata:      tags += "<span class='pill pill-green'>✅ Cours auto</span>"
        if est_banque:           tags += "<span class='pill pill-blue'>🏦 Bancaire</span>"
        st.markdown(f"<h2 style='font-family:Space Mono,monospace'>{titre.upper()} {tags}</h2>", unsafe_allow_html=True)

        if conf != "Annuelle":
            st.markdown(f'<div class="banner banner-blue">📅 Résultat {periode} → annualisé : <b>{r_an:.0f} M FCFA</b> — méthode : {meth}</div>', unsafe_allow_html=True)

        # ── Section : Indicateurs techniques ─────────────────
        st.markdown("#### 📡 Indicateurs techniques")
        ic1, ic2, ic3 = st.columns(3)

        # RSI
        rsi_color = "#f85149" if f_rsi else ("#3fb950" if rsi < RSI_BAS else "#79c0ff")
        rsi_label = "🔴 Surachat" if f_rsi else ("🟢 Survente" if rsi < RSI_BAS else "✅ Neutre")
        with ic1:
            st.markdown(f"""
            <div class="ind-box" style="border-color:{rsi_color}33">
              <div class="ind-label">RSI · 14</div>
              <div class="ind-value" style="color:{rsi_color}">{rsi:.0f}</div>
              <div class="ind-sub" style="color:{rsi_color}">{rsi_label}</div>
            </div>""", unsafe_allow_html=True)

        # Bollinger
        bb_color = "#f85149" if f_bb else ("#3fb950" if prix < bb_inf else "#79c0ff")
        bb_label = "🔴 Au-dessus" if f_bb else ("🟢 En-dessous" if prix < bb_inf else "✅ Dans la bande")
        with ic2:
            st.markdown(f"""
            <div class="ind-box" style="border-color:{bb_color}33">
              <div class="ind-label">Bollinger · 20, 2</div>
              <div class="ind-value" style="color:{bb_color}">{bb_pct:.0f}<span style="font-size:.5em">%</span></div>
              <div class="ind-sub" style="color:#8b949e">{bb_inf:,.0f} · {prix:,.0f} · {bb_sup:,.0f}</div>
              <div class="ind-sub" style="color:{bb_color}">{bb_label}</div>
            </div>""", unsafe_allow_html=True)

        # EMA20
        ema_color = "#3fb950" if prix > ema20 else "#f85149"
        ema_label = "✅ Haussier" if prix > ema20 else "⚠️ Baissier"
        with ic3:
            st.markdown(f"""
            <div class="ind-box" style="border-color:{ema_color}33">
              <div class="ind-label">EMA · 20</div>
              <div class="ind-value" style="color:{ema_color}">{ema20:,.0f}</div>
              <div class="ind-sub" style="color:#8b949e">Écart <b>{ecart_ema:+.1f}%</b></div>
              <div class="ind-sub" style="color:{ema_color}">{ema_label}</div>
            </div>""", unsafe_allow_html=True)

        # ── Section : Momentum fondamental ───────────────────
        st.markdown("#### 📈 Momentum fondamental")
        mf1, mf2, mf3 = st.columns(3)

        with mf1:
            if g_bpa_n1 is not None:
                accel_col   = "#3fb950" if accel_bpa > 0 else ("#d29922" if accel_bpa > -5 else "#f85149")
                accel_icon  = "↗" if accel_bpa > 0 else ("→" if accel_bpa > -5 else "↘")
                accel_label = "Accélération" if accel_bpa > 0 else ("Stable" if accel_bpa > -5 else "Décélération")
                st.markdown(f"""
                <div class="ind-box" style="border-color:{accel_col}33">
                  <div class="ind-label">Accélération BPA</div>
                  <div class="ind-value" style="color:{accel_col}">{accel_icon} {accel_bpa:+.1f}<span style="font-size:.4em">pp</span></div>
                  <div class="ind-sub" style="color:#8b949e">N-2→N-1 : <b>{g_bpa_n1:+.1f}%</b> · N-1→N : <b>{g_bpa:+.1f}%</b></div>
                  <div class="ind-sub" style="color:{accel_col}">{accel_label}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="ind-box">
                  <div class="ind-label">Accélération BPA</div>
                  <div class="ind-value" style="color:#8b949e">—</div>
                  <div class="ind-sub" style="color:#8b949e">Saisir BPA N-2 pour activer</div>
                </div>""", unsafe_allow_html=True)

        with mf2:
            v3m_col  = "#3fb950" if var_3m > 10 else ("#d29922" if var_3m > -5 else "#f85149")
            v3m_icon = "↗" if var_3m > 10 else ("→" if var_3m > -5 else "↘")
            st.markdown(f"""
            <div class="ind-box" style="border-color:{v3m_col}33">
              <div class="ind-label">Variation 3 mois</div>
              <div class="ind-value" style="color:{v3m_col}">{v3m_icon} {var_3m:+.1f}<span style="font-size:.4em">%</span></div>
              <div class="ind-sub" style="color:#8b949e">Signal de tendance cours</div>
            </div>""", unsafe_allow_html=True)

        with mf3:
            yoc_col = "#3fb950" if yoc_2ans > 5 else ("#d29922" if yoc_2ans > 2 else "#8b949e")
            st.markdown(f"""
            <div class="ind-box" style="border-color:{yoc_col}33">
              <div class="ind-label">Yield on Cost · 2 ans</div>
              <div class="ind-value" style="color:{yoc_col}">{yoc_2ans:.1f}<span style="font-size:.4em">%</span></div>
              <div class="ind-sub" style="color:#8b949e">Div. actuel {dy*100:.1f}% · g div. {g_div_est*100:+.1f}%/an</div>
            </div>""", unsafe_allow_html=True)

        # ── Section : Valorisation ────────────────────────────
        marge_pct = MARGE * 100
        marge_qual = "haute qualité" if MARGE == 0.10 else ("standard" if MARGE == 0.15 else "prudente")
        st.markdown("#### 🔒 Valorisation")
        if f_liquidite:
            st.markdown(f'<div class="banner banner-yellow">⚠️ Liquidité faible ({vol_fcfa/1e3:.0f} K FCFA/j) — signal dégradé automatiquement</div>', unsafe_allow_html=True)
        if q_score < QUALITY_FLOOR:
            st.markdown(f'<div class="banner banner-yellow">⚠️ Quality score {q_score:.2f} &lt; {QUALITY_FLOOR} — signal plafonné à SURVEILLER</div>', unsafe_allow_html=True)
        if survalu:
            st.markdown(f'<div class="banner banner-red">🔒 Surévalué — Prix {prix:,.0f} &gt; VI {vi:,.0f} FCFA</div>', unsafe_allow_html=True)
        elif hors_marge:
            st.markdown(f'<div class="banner banner-yellow">⚠️ Hors marge ({marge_pct:.0f}% · {marge_qual}) — Prix {prix:,.0f} entre VI {vi:,.0f} et cible {prix_cible:,.0f} FCFA</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="banner banner-green">✅ Dans la marge ({marge_pct:.0f}% · {marge_qual}) — Prix {prix:,.0f} &lt; Cible {prix_cible:,.0f} · Potentiel +{upside:.1f}%</div>', unsafe_allow_html=True)

        # ── Section : Ratios ──────────────────────────────────
        st.markdown("#### 📊 Ratios fondamentaux")
        r1, r2, r3, r4, r5 = st.columns(5)

        def ratio_box(label, value, sub=""):
            sub_html = f"<div class='ratio-sub'>{sub}</div>" if sub else ""
            return (f"<div class='ratio-item'>"
                    f"<div class='ratio-label'>{label}</div>"
                    f"<div class='ratio-value'>{value}</div>"
                    f"{sub_html}"
                    f"</div>")

        with r1:
            st.markdown(ratio_box("BPA", f"{bpa:,.1f} F") + ratio_box("PER", f"{per:.1f}×", f"cible {PER_SECTORIELS[secteur]:.1f}×"), unsafe_allow_html=True)
        with r2:
            st.markdown(ratio_box("P/Book", f"{pbr:.2f}×") + ratio_box("Rend. div.", f"{dy*100:.1f}%"), unsafe_allow_html=True)
        with r3:
            if est_banque:
                st.markdown(ratio_box("Marge / PNB", f"{marge_b*100:.1f}%") + ratio_box("Crédits / Dépôts", f"{cd_ratio*100:.1f}%"), unsafe_allow_html=True)
            else:
                st.markdown(ratio_box("ROE", f"{roe:.1f}%") + ratio_box("ROA", f"{roa:.1f}%"), unsafe_allow_html=True)
        with r4:
            st.markdown(ratio_box("N° Graham BRVM", f"{graham:,.0f}", f"PER×PBR sect.") +
                        ratio_box("Δ BPA", f"{g_bpa:+.1f}%"), unsafe_allow_html=True)
        with r5:
            vi_detail = f"PER {fv_per:,.0f}·DCF {fv_dcf:,.0f}·G {graham:,.0f}"
            st.markdown(ratio_box("Val. intrinsèque", f"{vi:,.0f}", vi_detail) +
                        ratio_box("Prix cible", f"{prix_cible:,.0f}", f"marge {MARGE*100:.0f}%"), unsafe_allow_html=True)

        # ── Signal final ──────────────────────────────────────
        score_bar_w = int(score * 100)
        score_clr   = "#3fb950" if score >= 0.60 else ("#d29922" if score >= 0.40 else "#f85149")
        st.markdown(f"""
        <div class="signal-card" style="border-left:4px solid {col_sig}">
          <div style="color:#8b949e;font-size:.72em;font-family:'Space Mono',monospace;text-transform:uppercase;letter-spacing:1px">Signal de rotation</div>
          <div class="signal-main" style="color:{col_sig}">{sig}</div>
          <div class="score-row">
            Score global <b style="color:{score_clr}">{score:.3f}</b> &nbsp;·&nbsp;
            Value <b style="color:#e6edf3">{v_score:.3f}</b> &nbsp;·&nbsp;
            Quality <b style="color:#e6edf3">{q_score:.3f}</b> &nbsp;·&nbsp;
            Momentum <b style="color:#e6edf3">{m_score:.3f}</b> &nbsp;·&nbsp;
            Upside <b style="color:{('#3fb950' if upside > 15 else '#d29922') if upside > 0 else '#f85149'}">{upside:.1f}%</b>
          </div>
          <div style="background:#1e2633;border-radius:4px;height:4px;margin-top:10px;overflow:hidden">
            <div style="background:{score_clr};width:{score_bar_w}%;height:100%;border-radius:4px;transition:width .5s"></div>
          </div>
        </div>""", unsafe_allow_html=True)

        # ── Ajout screener ────────────────────────────────────
        was_update = any(a["Titre"] == titre.upper() for a in st.session_state.screener)
        # (déjà retiré plus haut, on ajoute la nouvelle entrée)
        st.session_state.screener.append({
            "Titre": titre.upper(), "Secteur": secteur,
            "Bancaire": "✅" if est_banque else "—",
            "Période": f"{periode} {annee}", "Confiance": conf,
            "Cours auto": "✅" if "prix" in mdata else "—",
            "Prix": round(prix, 0), "BPA": round(bpa, 1), "PER": round(per, 1),
            "P/B": round(pbr, 2), "ROE%": round(roe, 1),
            "ROA%": round(roa, 1) if roa else "—",
            "D/CP": round(dette_cp, 2) if dette_cp else "—",
            "Marge/PNB": f"{marge_b*100:.1f}%" if est_banque else "—",
            "Crd/Dep": f"{cd_ratio*100:.1f}%" if est_banque else "—",
            "RSI": round(rsi, 1), "BB%": round(bb_pct, 1), "vs EMA%": round(ecart_ema, 1),
            "Var3M%": round(var_3m, 1), "Accel BPA": round(accel_bpa, 1) if g_bpa_n1 is not None else "—",
            "YoC2ans%": round(yoc_2ans, 1),
            "Liquidité": f"{vol_fcfa/1e6:.1f}M" if vol_fcfa >= 1e6 else (f"{vol_fcfa/1e3:.0f}K" if vol_fcfa > 0 else "—"),
            "Marge%": round(MARGE * 100, 0),
            "VI": round(vi, 0), "Cible": round(prix_cible, 0), "Upside%": round(upside, 1),
            "Value": round(v_score, 3), "Quality": round(q_score, 3),
            "Momentum": round(m_score, 3), "Score": round(score, 3), "Signal": sig,
        })
        st.success(f"🔄 {titre.upper()} mis à jour dans le screener." if was_update else f"✅ {titre.upper()} ajouté au screener.")

# ══════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════

# ── Helpers Kanban ────────────────────────────────────────────────
def _signal_bucket(sig):
    """Classe un signal dans l'un des 3 seaux visuels."""
    if "FORT ACHAT" in sig or sig == "🔵 ACHAT":
        return "achat"
    if "SURVEILLER" in sig or "ALLÉGER" in sig or "HORS MARGE" in sig:
        return "surveiller"
    return "eviter"   # SORTIR, BLOQUÉ, SURÉVALUÉ

KANBAN_CFG = {
    "achat":      {"label": "ACHETER",    "icon": "↑", "border": "#3fb950", "bg": "#0a1f0e", "head_bg": "#0d2912", "count_bg": "#1b3d1f"},
    "surveiller": {"label": "SURVEILLER", "icon": "◎", "border": "#d29922", "bg": "#1a1400", "head_bg": "#221b00", "count_bg": "#3d3000"},
    "eviter":     {"label": "ÉVITER",     "icon": "↓", "border": "#f85149", "bg": "#1f0d0d", "head_bg": "#2d1212", "count_bg": "#4d1f1f"},
}

def _kanban_card(row, bucket):
    """Génère le HTML d'une carte Kanban."""
    cfg      = KANBAN_CFG[bucket]
    sig      = row["Signal"]
    sig_col  = SIGNAL_COLORS.get(sig, "#8b949e")
    upside   = row["Upside%"]
    up_col   = "#3fb950" if upside > 15 else ("#d29922" if upside > 0 else "#f85149")
    score    = row["Score"]
    sc_w     = int(min(max(score, 0), 1) * 100)
    sc_col   = "#3fb950" if score >= .60 else ("#d29922" if score >= .40 else "#f85149")
    rsi_col  = "#f85149" if row["RSI"] > RSI_HAUT else ("#3fb950" if row["RSI"] < RSI_BAS else "#8b949e")

    return f"""
    <div style="background:{cfg['bg']};border:1px solid {cfg['border']}22;border-left:3px solid {cfg['border']};
                border-radius:10px;padding:12px 14px;margin-bottom:10px">
      <!-- Ticker + signal -->
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
        <div>
          <span style="font-family:'Space Mono',monospace;font-weight:700;font-size:1.05em;color:#e6edf3">{row['Titre']}</span><br>
          <span style="font-size:.72em;color:#8b949e">{row['Secteur']}</span>
        </div>
        <span style="font-family:'Space Mono',monospace;font-size:.78em;font-weight:700;color:{sig_col};
                     background:{sig_col}18;border:1px solid {sig_col}44;border-radius:20px;
                     padding:2px 10px;white-space:nowrap">{sig}</span>
      </div>
      <!-- Métriques clés -->
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px">
        <div style="background:#0d1117;border-radius:6px;padding:5px 8px;text-align:center">
          <div style="font-size:.62em;color:#8b949e;text-transform:uppercase;letter-spacing:.5px">Prix</div>
          <div style="font-family:'Space Mono',monospace;font-size:.9em;font-weight:700;color:#e6edf3">{row['Prix']:,.0f}</div>
        </div>
        <div style="background:#0d1117;border-radius:6px;padding:5px 8px;text-align:center">
          <div style="font-size:.62em;color:#8b949e;text-transform:uppercase;letter-spacing:.5px">Upside</div>
          <div style="font-family:'Space Mono',monospace;font-size:.9em;font-weight:700;color:{up_col}">{upside:+.1f}%</div>
        </div>
        <div style="background:#0d1117;border-radius:6px;padding:5px 8px;text-align:center">
          <div style="font-size:.62em;color:#8b949e;text-transform:uppercase;letter-spacing:.5px">RSI</div>
          <div style="font-family:'Space Mono',monospace;font-size:.9em;font-weight:700;color:{rsi_col}">{row['RSI']:.0f}</div>
        </div>
      </div>
      <!-- Barre de score -->
      <div style="display:flex;align-items:center;gap:8px">
        <div style="font-size:.65em;color:#8b949e;white-space:nowrap;font-family:'Space Mono',monospace">Score</div>
        <div style="flex:1;background:#1e2633;border-radius:3px;height:4px;overflow:hidden">
          <div style="background:{sc_col};width:{sc_w}%;height:100%;border-radius:3px"></div>
        </div>
        <div style="font-size:.65em;font-family:'Space Mono',monospace;color:{sc_col};white-space:nowrap">{score:.2f}</div>
      </div>
    </div>"""

with tab2:
    if not st.session_state.screener:
        st.markdown("""
        <div class="card" style="text-align:center;padding:40px;color:#8b949e">
            <div style="font-size:2em;margin-bottom:8px">📊</div>
            <div style="font-family:'Space Mono',monospace">Aucun titre analysé</div>
            <div style="font-size:.85em;margin-top:4px">Commencez par l'onglet ➕ Analyser</div>
        </div>""", unsafe_allow_html=True)
    else:
        df = pd.DataFrame(st.session_state.screener).sort_values("Score", ascending=False).reset_index(drop=True)

        # ── KPIs ────────────────────────────────────────────────
        k1, k2, k3, k4 = st.columns(4)
        nb_achat  = len(df[df["Signal"].str.contains("ACHAT", na=False)])
        nb_watch  = len(df[df["Signal"].str.contains("SURVEILLER|ALLÉGER|HORS MARGE", na=False)])
        nb_eviter = len(df[df["Signal"].str.startswith("🔴", na=False)])
        nb_auto   = len(df[df["Cours auto"] == "✅"])

        for col, val, label, color in [
            (k1, len(df),    "TOTAL",      "#8b949e"),
            (k2, nb_achat,   "ACHETER",    "#3fb950"),
            (k3, nb_watch,   "SURVEILLER", "#d29922"),
            (k4, nb_eviter,  "ÉVITER",     "#f85149"),
        ]:
            with col:
                st.markdown(f"""
                <div style="background:#0d1117;border:1px solid {color}44;border-top:3px solid {color};
                            border-radius:10px;padding:14px;text-align:center">
                  <div style="font-size:2em;font-family:'Space Mono',monospace;font-weight:700;color:{color}">{val}</div>
                  <div style="font-size:.7em;color:#8b949e;text-transform:uppercase;letter-spacing:1px;margin-top:2px">{label}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Alerte concentration sectorielle ─────────────────────
        secteur_counts = df.groupby("Secteur").size()
        total_titres   = len(df)
        surpoids = {s: n/total_titres for s, n in secteur_counts.items() if n/total_titres > 0.40}
        if surpoids and total_titres >= 3:
            alertes = " · ".join(f"<b>{s}</b> {p*100:.0f}%" for s, p in surpoids.items())
            st.markdown(f'<div class="banner banner-yellow">⚠️ Concentration sectorielle élevée : {alertes} — diversification recommandée</div>',
                        unsafe_allow_html=True)

        # ── Vue Kanban ───────────────────────────────────────────
        buckets = {"achat": [], "surveiller": [], "eviter": []}
        for _, row in df.iterrows():
            buckets[_signal_bucket(row["Signal"])].append(row)

        col_a, col_s, col_e = st.columns(3)

        for col_widget, bucket_key in [(col_a, "achat"), (col_s, "surveiller"), (col_e, "eviter")]:
            cfg   = KANBAN_CFG[bucket_key]
            items = buckets[bucket_key]
            with col_widget:
                # En-tête colonne
                st.markdown(f"""
                <div style="background:{cfg['head_bg']};border:1px solid {cfg['border']}33;
                            border-radius:10px 10px 0 0;padding:10px 14px;
                            display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
                  <span style="font-family:'Space Mono',monospace;font-weight:700;font-size:.9em;
                               color:{cfg['border']};letter-spacing:1px">{cfg['icon']} {cfg['label']}</span>
                  <span style="background:{cfg['count_bg']};color:{cfg['border']};border-radius:20px;
                               padding:2px 10px;font-family:'Space Mono',monospace;font-size:.8em;font-weight:700">{len(items)}</span>
                </div>""", unsafe_allow_html=True)

                if not items:
                    st.markdown(f"""
                    <div style="background:{cfg['bg']};border:1px solid {cfg['border']}22;border-radius:0 0 10px 10px;
                                padding:24px;text-align:center;color:#8b949e;font-size:.82em">
                        Aucun titre
                    </div>""", unsafe_allow_html=True)
                else:
                    html_cards = "".join(_kanban_card(r, bucket_key) for r in items)
                    st.markdown(f"""
                    <div style="background:{cfg['bg']}88;border:1px solid {cfg['border']}22;
                                border-top:none;border-radius:0 0 10px 10px;padding:10px 8px 4px">
                        {html_cards}
                    </div>""", unsafe_allow_html=True)

        # ── Tableau détaillé ─────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("📋 Tableau détaillé", expanded=False):
            def _cs(v):
                try:
                    v = float(v)
                    if v >= .60: return "background-color:#0d1f12;color:#3fb950"
                    if v >= .45: return "background-color:#1a1400;color:#e3b341"
                    return "background-color:#1f0d0d;color:#f85149"
                except: return ""
            def _cu(v):
                try:
                    v = float(v)
                    if v >= 20: return "background-color:#0d1f12;color:#3fb950"
                    if v >= 5:  return "background-color:#1a1400;color:#e3b341"
                    return "background-color:#1f0d0d;color:#f85149"
                except: return ""

            cols_show = ["Titre", "Secteur", "Prix", "PER", "P/B", "ROE%",
                         "RSI", "BB%", "vs EMA%", "Var3M%", "Accel BPA",
                         "YoC2ans%", "Liquidité", "Marge%",
                         "VI", "Cible", "Upside%", "Quality", "Score", "Signal"]
            st.dataframe(
                df[cols_show].style
                    .applymap(_cs, subset=["Score"])
                    .applymap(_cu, subset=["Upside%"]),
                use_container_width=True, height=420)

        # ── Export ─────────────────────────────────────────────
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="BRVM")
        st.download_button("⬇️ Exporter Excel", buf.getvalue(), "screener_brvm.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)



# ══════════════════════════════════════════════════════════════════
# TAB 3 — FONDAMENTAUX SAUVEGARDÉS
# ══════════════════════════════════════════════════════════════════
with tab3:
    fonds = list_fonds()
    if not fonds:
        st.markdown("""
        <div class="card" style="text-align:center;padding:40px;color:#8b949e">
            <div style="font-size:2em">💾</div>
            <div style="font-family:'Space Mono',monospace;margin-top:6px">Aucun fondamental sauvegardé</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"<span class='pill pill-green'>{len(fonds)} titre(s) en base</span> — pré-remplis automatiquement à la prochaine analyse.", unsafe_allow_html=True)
        st.markdown("")
        for s in fonds:
            f = load_fond(s["ticker"])
            if not f: continue
            with st.expander(f"**{s['ticker']}** — {s['secteur']} — màj {s['maj_at']}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write(f"**Secteur** : {f.get('secteur','—')}")
                    st.write(f"**Période** : {f.get('periode','—')} {f.get('annee','')}")
                    st.write(f"**Actions** : {f.get('nombre_actions','—')} M")
                    st.write(f"**Dividende** : {f.get('dividende','—')} FCFA")
                    st.write(f"**BPA préc.** : {f.get('bpa_prec','—')} FCFA")
                with c2:
                    if f.get("est_banque"):
                        st.write(f"🏦 **PNB** : {f.get('pnb','—')} M")
                        st.write(f"**RN** : {f.get('resultat_b','—')} M")
                        st.write(f"**Crédits** : {f.get('encours_credits','—')} M")
                        st.write(f"**Dépôts** : {f.get('depots_clientele','—')} M")
                    else:
                        st.write(f"**RN** : {f.get('resultat','—')} M")
                        st.write(f"**CP** : {f.get('capitaux_propres','—')} M")
                        st.write(f"**Actif** : {f.get('total_actif','—')} M")
                        st.write(f"**Dettes** : {f.get('dettes_totales','—')} M")
                with c3:
                    if st.button(f"🗑️ Supprimer", key=f"del_{s['ticker']}"):
                        del_fond(s["ticker"]); st.success("Supprimé"); st.rerun()

# ══════════════════════════════════════════════════════════════════
# TAB 4 — MÉTHODE
# ══════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("""
### Architecture fetch v6.0

```
Cours (cascade, 1er succès) :
  1. richbourse.com/common/variation/index
  2. brvm.org/fr/cours-actions/0
  3. sikafinance.com/marches/aaz

Indicateurs techniques (richbourse historique) :
  → BB(20,2) · EMA(20) · RSI(14) · Var 3 mois · Vol. moy. 20j
  Minimum 20 bougies — saisie manuelle si indispo
```

### Valeur intrinsèque recalibrée BRVM

```
VI = FV_PER × 50% + DCF × 35% + Graham_sect × 15%

  FV_PER (50%) : BPA × PER sectoriel BRVM
    Ancre principale — capte le niveau de valorisation
    "normal" du secteur sur ce marché

  DCF (35%) : actualisation flux 5 ans + valeur terminale
    g1 borné [-10%, +20%] · g_perp = 3% (croissance UEMOA)
    Taux d'actualisation sectoriels : 11–14%

  Graham BRVM (15%) : √(PER_sect × PBR_sect × BPA × Book)
    Garde-fou cohérence bilan — calibré avec plafonds
    sectoriels BRVM, remplace le 22.5 universel (NYSE 1970)
    Réduit de 40% → 15% : rôle de vérification, pas d'ancre

  PBR sectoriels BRVM :
    Télécoms 3.5x · Services Financiers 1.2x
    Conso. base 2.5x · Industriels 1.8x
    Énergie 2.0x · Services Publics 1.5x
```

### Score de rotation

```
Score = Value×25% + Quality×40% + Momentum×35%

  Value (25%) : PER relatif (45%) + P/Book relatif (55%)
    Dividende retiré — stratégie réévaluation cours, pas revenus

  Quality (40%) : ROE · ROA · dette/CP · stabilité BPA
    Banques : marge/PNB · crédits/dépôts · ROE

  Momentum (35%) : accélération BPA (60%) + variation 3M (40%)
    Accélération = dérivée seconde du BPA — détecte les titres
    en phase d'expansion avant que le marché ne les price

  Quality floor : signal plafonné à SURVEILLER si Quality < 0.40
  Marge dynamique : 10% (Q≥0.70) · 15% (Q 0.50–0.70) · 20% (<0.50)
  Liquidité : signal dégradé si vol. moy. 20j × prix < 1M FCFA/j
```

### Filtres de blocage (priorité absolue)

```
[1] RSI > seuil surachat   → 🔴 BLOQUÉ RSI
[2] Prix > BB supérieure   → 🔴 BLOQUÉ BB
[3] Liquidité insuffisante → 🟡 LIQUIDITÉ FAIBLE
[4] Prix > VI              → 🔴 SURÉVALUÉ
[5] Prix > Prix cible      → 🟡 HORS MARGE
[6] Quality < 0.40         → plafonnement signal
```

### Installation

```bash
pip install streamlit pandas numpy requests beautifulsoup4 openpyxl lxml
streamlit run screener_brvm_v5.py
```
""")

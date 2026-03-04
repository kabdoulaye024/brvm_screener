"""
Screener BRVM v5.0
Cours      : richbourse → brvm.org → sikafinance
Indicateurs: richbourse historique → calc BB(20,2) + EMA(20) + RSI(14)
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
    "🟡 HORS MARGE": "#d29922",
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
        bpa_prec REAL, capitaux_propres REAL, resultat REAL,
        total_actif REAL, dettes_totales REAL, stabilite_bpa TEXT,
        pnb REAL, resultat_b REAL, encours_credits REAL, depots_clientele REAL,
        maj_at TEXT)""")
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
    Parse la table historique richbourse.
    Colonnes confirmées (2026-03) :
      Date | Variation(%) | Valeur(FCFA) | Cours ajusté | Volume ajusté | Cours normal | Volume normal
    On utilise 'Cours ajusté' (index 3) comme close.
    """
    if not HAS_BS4:
        return pd.DataFrame()
    soup  = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return pd.DataFrame()

    rows = table.find_all("tr")
    if len(rows) < 2:
        return pd.DataFrame()

    # Détecter l'index de la colonne "cours ajusté" depuis le header
    header_cells = [th.get_text(strip=True).lower().replace("\xa0","").replace(" ","")
                    for th in rows[0].find_all(["th","td"])]
    # Priorité : "coursajusté" → "coursnormal" → index 3 (fallback)
    idx_close = next(
        (i for i, h in enumerate(header_cells) if "ajust" in h and "cours" in h),
        next((i for i, h in enumerate(header_cells) if "normal" in h and "cours" in h), 3)
    )

    data = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) <= idx_close:
            continue
        date_txt  = cells[0].get_text(strip=True)
        close_txt = cells[idx_close].get_text(strip=True)
        data.append([date_txt, close_txt])

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data, columns=["date", "close"])
    df["date"]  = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["close"] = pd.to_numeric(
        df["close"].str.replace(r"[\xa0\s,]", "", regex=True)
                   .str.replace(r"\.", "", regex=True)   # séparateur milliers
                   .str.replace(",", ".", regex=False),
        errors="coerce")
    # Si toutes les valeurs sont NaN, les nombres étaient peut-être sans séparateur
    if df["close"].isna().all():
        df["close"] = pd.to_numeric(
            df["close_raw"] if "close_raw" in df else
            pd.Series([c[1] for c in data])
              .str.replace(r"[\xa0\s]", "", regex=True)
              .str.replace(",", ".", regex=False),
            errors="coerce")
    return df.dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_historique(ticker: str, nb: int = 120) -> pd.DataFrame:
    """
    Récupère l'historique journalier depuis richbourse.com.
    La page par défaut ne retourne que ~20 lignes.
    On effectue plusieurs appels avec des plages de dates glissantes
    pour obtenir au moins nb points (minimum 35 pour RSI+BB fiables).
    Retourne un DataFrame [date, close] trié ASC, dédupliqué.
    """
    tk   = ticker.upper()
    hdrs = {**HEADERS, "Referer": f"{RICHBOURSE_BASE}/", "Accept": "text/html,application/xhtml+xml"}
    frames = []

    # ── Appel 1 : page par défaut (dernières séances) ──────────
    url_base = f"{RICHBOURSE_BASE}/common/variation/historique/{tk}"
    try:
        r = requests.get(url_base, headers=hdrs, timeout=20, verify=False)
        if r.status_code == 200:
            df0 = _parse_historique_html(r.text)
            if not df0.empty:
                frames.append(df0)
    except Exception:
        pass

    # ── Appels 2-4 : plages de dates couvrant ~18 mois ─────────
    # Richbourse accepte date_debut / date_fin en GET sur l'URL de base
    from datetime import timedelta
    today = datetime.now()
    ranges = [
        (today - timedelta(days=540), today - timedelta(days=360)),
        (today - timedelta(days=360), today - timedelta(days=180)),
        (today - timedelta(days=180), today),
    ]
    for d_start, d_end in ranges:
        params = {
            "action":     tk,
            "periode":    "Journali\u00e8re",
            "date_debut": d_start.strftime("%Y-%m-%d"),
            "date_fin":   d_end.strftime("%Y-%m-%d"),
        }
        try:
            r = requests.get(url_base, params=params, headers=hdrs, timeout=20, verify=False)
            if r.status_code == 200 and "<table" in r.text.lower():
                df_i = _parse_historique_html(r.text)
                if not df_i.empty:
                    frames.append(df_i)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    # Concat + dédup + tri
    df_all = (pd.concat(frames, ignore_index=True)
                .drop_duplicates(subset=["date"])
                .dropna()
                .sort_values("date")
                .tail(nb)
                .reset_index(drop=True))
    return df_all


def calc_indicateurs(df: pd.DataFrame) -> dict:
    """
    Calcule BB(20,2), EMA(20), RSI(14) depuis l'historique.
    Nécessite au minimum 20 bougies.
    """
    if df.empty or len(df) < 20:
        return {}
    close = df["close"]

    # EMA 20
    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]

    # RSI 14 (méthode Wilder SMA initiale → RMA)
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs       = avg_gain / avg_loss
    rsi_ser  = 100 - (100 / (1 + rs))
    rsi_val  = rsi_ser.iloc[-1]

    # Bollinger Bands (20, 2)
    bb_mid = close.rolling(20).mean().iloc[-1]
    bb_std = close.rolling(20).std().iloc[-1]
    bb_sup = bb_mid + 2 * bb_std
    bb_inf = bb_mid - 2 * bb_std

    # Variation 1 semaine
    var_1s = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0.0

    return {
        "rsi":    round(rsi_val, 1),
        "ema20":  round(ema20, 0),
        "bb_sup": round(bb_sup, 0),
        "bb_inf": round(bb_inf, 0),
        "bb_mid": round(bb_mid, 0),
        "var_1s": round(var_1s, 2),
        "nb_pts": len(close),
    }


def get_marche(ticker: str) -> dict:
    """
    Pipeline unifié :
      1. fetch_cours()       → prix + variation
      2. fetch_historique()  → BB(20,2) + EMA(20) + RSI(14) calculés localement
    """
    tk = ticker.upper().strip()
    result = {}
    result.update(fetch_cours(tk))
    df_hist = fetch_historique(tk)
    if not df_hist.empty:
        indics = calc_indicateurs(df_hist)
        result.update(indics)
        result["_source_tech"] = f"richbourse · {indics.get('nb_pts', 0)} pts"
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
    g1 = min(max(g_bpa / 100, -0.10), 0.20)
    g2, r = 0.03, taux
    flux = sum(bpa * (1 + g1) ** t / (1 + r) ** t for t in range(1, 6))
    vt   = bpa * (1 + g1) ** 5 * (1 + g2) / (r - g2) / (1 + r) ** 5
    return flux + vt

def calc_signal(score, upside, survalu, hors_marge, f_rsi, f_bb):
    if f_rsi:                              return "🔴 BLOQUÉ RSI"
    if f_bb:                               return "🔴 BLOQUÉ BB"
    if survalu:                            return "🔴 SURÉVALUÉ"
    if hors_marge:                         return "🟡 HORS MARGE"
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
        W_V, W_Q, W_M = 0.35, 0.40, 0.25
    else:
        st.markdown("**Pondérations du score**")
        W_V = st.slider("Value",    0.1, 0.6, 0.30, 0.05)
        W_Q = st.slider("Quality",  0.1, 0.6, 0.40, 0.05)
        W_M = st.slider("Momentum", 0.1, 0.6, 0.30, 0.05)
        T   = W_V + W_Q + W_M; W_V /= T; W_Q /= T; W_M /= T

    st.markdown("---")
    st.markdown("**Filtres techniques**")
    RSI_HAUT = st.slider("RSI surachat",   60, 80, 70, 5)
    RSI_BAS  = st.slider("RSI survente",   20, 40, 30, 5)
    MARGE    = st.slider("Marge sécurité (%)", 5, 30, 20, 5) / 100

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
        has_rsi  = "rsi"    in mdata
        has_bb   = "bb_sup" in mdata and "bb_inf" in mdata
        has_ema  = "ema20"  in mdata
        nb_pts   = mdata.get("nb_pts", 0)
        src_tech = mdata.get("_source_tech", "—")

        def _dot(ok):
            cls = "dot-green" if ok else "dot-red"
            return f"<span class='dot {cls}'></span>"

        all_ok = has_prix and has_rsi and has_bb and has_ema
        bar_border = "#3fb950" if all_ok else ("#d29922" if has_prix else "#f85149")

        st.markdown(f"""
        <div class="status-bar" style="border-left:3px solid {bar_border}">
          <div class="status-item">{_dot(has_prix)} Cours{' '+str(int(mdata['prix']))+' FCFA' if has_prix else ''}</div>
          <div style="color:#1e2633">|</div>
          <div class="status-item">{_dot(has_rsi)} RSI{' '+str(mdata['rsi']) if has_rsi else ''}</div>
          <div style="color:#1e2633">|</div>
          <div class="status-item">{_dot(has_bb)} BB &nbsp;{str(int(mdata.get('bb_inf',0)))+' / '+str(int(mdata.get('bb_sup',0))) if has_bb else ''}</div>
          <div style="color:#1e2633">|</div>
          <div class="status-item">{_dot(has_ema)} EMA20 &nbsp;{str(int(mdata['ema20'])) if has_ema else ''}</div>
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
            pnb = encours_credits = depots = None

        # ── Indicateurs techniques ─────────────────────────────
        st.markdown('<hr class="sep">', unsafe_allow_html=True)
        st.markdown("**📡 Indicateurs techniques**")

        has_tech = all(k in mdata for k in ["rsi", "bb_sup", "bb_inf", "ema20"])
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
            ema20  = st.number_input("EMA 20",           min_value=1.0, value=float(mdata.get("ema20", 980.0)))
            var_1s = st.number_input("Variation 1 sem. (%)", -30.0, 30.0, float(mdata.get("var_1s", 0.0)))
        with t3:
            rsi = st.number_input("RSI (14)", 0.0, 100.0, float(mdata.get("rsi", 50.0)))
            st.markdown(f"""
            <div style='background:#0d1117;border:1px solid #1e2633;border-radius:8px;padding:10px 12px;margin-top:4px;font-size:.76em;font-family:"Space Mono",monospace'>
            <div style='color:#8b949e;margin-bottom:4px'>SEUILS RSI</div>
            <span style='color:#f85149'>▲ Surachat {RSI_HAUT}</span><br>
            <span style='color:#3fb950'>▼ Survente {RSI_BAS}</span>
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

        # Ratios
        bpa       = r_an / nombre_actions
        val_book  = capitaux_propres / nombre_actions
        per       = prix / bpa if bpa > 0 else 99
        pbr       = prix / val_book if val_book > 0 else 99
        dy        = dividende / prix if prix > 0 else 0
        g_bpa     = ((bpa - bpa_prec) / abs(bpa_prec) * 100) if bpa_prec else 0
        roe       = r_an / capitaux_propres * 100

        # Valeurs intrinsèques
        graham    = np.sqrt(max(22.5 * bpa * val_book, 0)) if bpa > 0 else 0
        fv_per    = bpa * PER_SECTORIELS[secteur] if bpa > 0 else 0
        fv_dcf    = vi_dcf(bpa, g_bpa, TAUX_ACTUA) if bpa > 0 else 0
        if graham > 0 and fv_dcf > 0:
            vi = graham * 0.40 + fv_per * 0.35 + fv_dcf * 0.25
        elif graham > 0:
            vi = graham * 0.5 + fv_per * 0.5
        else:
            vi = fv_per
        prix_cible = vi * (1 - MARGE)
        upside     = (prix_cible / prix - 1) * 100
        survalu    = prix > vi
        hors_marge = prix > prix_cible and not survalu

        # Scores
        per_cap = min(PER_SECTORIELS[secteur], 25)
        s_per   = np.clip(per_cap / per, 0, 1) if per > 0 else 0
        s_pbr   = np.clip(1.5 / pbr, 0, 1)
        s_dy    = np.clip(dy / 0.08, 0, 1)
        v_score = s_per * 0.40 + s_pbr * 0.35 + s_dy * 0.25

        if est_banque:
            roa = dette_cp = None
            marge_b = r_an / pnb_ if pnb_ else 0
            cd_ratio = encours_credits / depots if depots else 0
            q_score = (np.clip(marge_b / 0.20, 0, 1) * 0.45
                     + np.clip(1 - abs(cd_ratio - 0.80) / 0.40, 0, 1) * 0.30
                     + np.clip(roe / 15, 0, 1) * 0.25)
        else:
            roa = r_an / total_actif * 100
            dette_cp = dettes_totales / capitaux_propres
            marge_b = cd_ratio = None
            bonus = {"Stable": 0.20, "Volatil": 0.0, "Exceptionnel": 0.30}.get(stabilite_bpa, 0)
            q_score = (np.clip(roe / 25, 0, 1) * 0.35
                     + np.clip(roa / 12, 0, 1) * 0.30
                     + np.clip(1 - dette_cp / 3, 0, 1) * 0.25
                     + bonus * 0.10)

        m_score = np.clip(g_bpa / 30, -1, 1) * 0.60 + np.clip(var_1s / 10, -1, 1) * 0.40
        score   = W_V * v_score + W_Q * q_score + W_M * m_score

        f_rsi    = rsi > RSI_HAUT
        f_bb     = prix > bb_sup
        bb_pct   = ((prix - bb_inf) / (bb_sup - bb_inf) * 100) if (bb_sup - bb_inf) > 0 else 50
        ecart_ema = (prix / ema20 - 1) * 100
        sig      = calc_signal(score, upside, survalu, hors_marge, f_rsi, f_bb)
        col_sig  = SIGNAL_COLORS.get(sig, "#8b949e")

        # ── Sauvegarde ─────────────────────────────────────────
        if save_cb:
            fd_data = {"secteur": secteur, "periode": periode, "annee": annee,
                       "est_banque": 1 if est_banque else 0,
                       "nombre_actions": nombre_actions, "dividende": dividende,
                       "bpa_prec": bpa_prec, "capitaux_propres": capitaux_propres}
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

        # ── Section : Verrou Graham ───────────────────────────
        st.markdown("#### 🔒 Valorisation")
        if survalu:
            st.markdown(f'<div class="banner banner-red">🔒 Surévalué — Prix {prix:,.0f} FCFA &gt; Valeur intrinsèque {vi:,.0f} FCFA</div>', unsafe_allow_html=True)
        elif hors_marge:
            st.markdown(f'<div class="banner banner-yellow">⚠️ Hors marge de sécurité — Prix {prix:,.0f} entre VI {vi:,.0f} et cible {prix_cible:,.0f} FCFA</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="banner banner-green">✅ Dans la marge — Prix {prix:,.0f} &lt; Cible {prix_cible:,.0f} FCFA · Potentiel +{upside:.1f}%</div>', unsafe_allow_html=True)

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
            st.markdown(ratio_box("N° Graham", f"{graham:,.0f}") + ratio_box("Δ BPA", f"{g_bpa:+.1f}%"), unsafe_allow_html=True)
        with r5:
            st.markdown(ratio_box("Val. intrinsèque", f"{vi:,.0f}") + ratio_box("Prix cible", f"{prix_cible:,.0f}", f"marge {MARGE*100:.0f}%"), unsafe_allow_html=True)

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
                         "RSI", "BB%", "vs EMA%", "VI", "Cible", "Upside%", "Score", "Signal"]
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
### Architecture fetch v5.0

```
Cours (cascade, 1er succès) :
  1. richbourse.com/common/variation/index   — données J
  2. brvm.org/fr/cours-actions/0             — officiel BRVM
  3. sikafinance.com/marches/aaz             — agrégateur

Indicateurs techniques (richbourse historique) :
  richbourse.com/common/variation/historique/TICKER
  → Parsing HTML table → DataFrame [date, close]
  → BB(20,2)  : mid ± 2σ sur 20 séances
  → EMA(20)   : moyenne exponentielle span=20
  → RSI(14)   : gains/pertes moyens sur 14 séances
  Minimum : 20 bougies — saisie manuelle si indispo
```

### Logique de scoring

```
[FILTRE 1] RSI > seuil      → 🔴 BLOQUÉ RSI
[FILTRE 2] Prix > BB sup    → 🔴 BLOQUÉ BB
[FILTRE 3] Prix > VI        → 🔴 SURÉVALUÉ
[FILTRE 4] Prix > Cible     → 🟡 HORS MARGE

Score = Value×w + Quality×w + Momentum×w
  Value    : PER, P/Book, rendement dividende
  Quality  : ROE, ROA, dette/CP | marge PNB, Crd/Dep (banques)
  Momentum : Δ BPA YoY + variation cours 1 semaine
```

### Valeur intrinsèque (3 méthodes combinées)

```
VI  = Graham(40%) + Fair Value PER(35%) + DCF(25%)
    — Graham   : √(22.5 × BPA × Book Value)
    — PER cible: BPA × PER sectoriel BRVM
    — DCF      : actualisation sur 5 ans + valeur terminale

Prix cible = VI × (1 − marge de sécurité)
```

### Installation

```bash
pip install streamlit pandas numpy requests beautifulsoup4 openpyxl lxml
streamlit run screener_brvm_v5.py
```
""")

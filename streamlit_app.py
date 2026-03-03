"""
Screener BRVM v4.0 — refactorisé
Cours automatiques : brvm.org → sikafinance.com → saisie manuelle
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

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Screener BRVM", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');
html,body,[class*="css"]{ font-family:'IBM Plex Sans',sans-serif; }
h1,h2,h3{ font-family:'IBM Plex Mono',monospace; }
.stApp{ background:#0d1117; color:#e6edf3; }
div[data-testid="stSidebar"]{ background:#161b22; border-right:1px solid #30363d; }
.card{ background:#161b22; border:1px solid #30363d; border-radius:10px; padding:16px 20px; margin:8px 0; }
.tag{ display:inline-block; border-radius:10px; padding:1px 9px; font-size:.72em; font-weight:700; margin-left:5px; vertical-align:middle; }
.tag-blue  { background:#1f3a5f; color:#79c0ff; border:1px solid #79c0ff; }
.tag-green { background:#1b2d1b; color:#3fb950; border:1px solid #3fb950; }
.tag-yellow{ background:#2d2500; color:#d29922; border:1px solid #d29922; }
.tag-red   { background:#2d1b1b; color:#f85149; border:1px solid #f85149; }
.alert-red   { background:#2d1b1b; border:1px solid #f85149; border-radius:8px; padding:13px; margin:6px 0; color:#ffa198; font-weight:600; }
.alert-yellow{ background:#2d2500; border:1px solid #d29922; border-radius:8px; padding:13px; margin:6px 0; color:#e3b341; font-weight:600; }
.alert-green { background:#1b2d1b; border:1px solid #3fb950; border-radius:8px; padding:13px; margin:6px 0; color:#7ee787; font-weight:600; }
.alert-blue  { background:#1a1f2e; border:1px solid #79c0ff; border-radius:8px; padding:12px; margin:6px 0; color:#a5d6ff; }
.box{ background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:10px 14px; margin:4px 0; font-family:'IBM Plex Mono',monospace; font-size:.88em; }
.lbl{ color:#8b949e; font-size:.78em; }
.stButton>button{ background:#238636; color:white; border:none; border-radius:6px; font-family:'IBM Plex Mono',monospace; font-weight:600; width:100%; padding:10px; }
.stButton>button:hover{ background:#2ea043; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# RÉFÉRENTIEL BRVM
# ─────────────────────────────────────────────
TICKERS_BRVM = {
    "SNTS":  ("SONATEL SENEGAL",                        "Télécommunications"),
    "ORAC":  ("ORANGE COTE D'IVOIRE",                   "Télécommunications"),
    "ONTBF": ("ONATEL BURKINA FASO",                    "Télécommunications"),
    "BOAB":  ("BANK OF AFRICA BENIN",                   "Services Financiers"),
    "BOABF": ("BANK OF AFRICA BURKINA FASO",            "Services Financiers"),
    "BOAC":  ("BANK OF AFRICA COTE D'IVOIRE",           "Services Financiers"),
    "BOAM":  ("BANK OF AFRICA MALI",                    "Services Financiers"),
    "BOAN":  ("BANK OF AFRICA NIGER",                   "Services Financiers"),
    "BOAS":  ("BANK OF AFRICA SENEGAL",                 "Services Financiers"),
    "BICB":  ("BICICI BENIN",                           "Services Financiers"),
    "BICC":  ("BICI COTE D'IVOIRE",                     "Services Financiers"),
    "CBIBF": ("CORIS BANK INTERNATIONAL BURKINA FASO",  "Services Financiers"),
    "ECOC":  ("ECOBANK COTE D'IVOIRE",                  "Services Financiers"),
    "ETIT":  ("ECOBANK TRANSNATIONAL (ETI) TOGO",       "Services Financiers"),
    "NSBC":  ("NSIA BANQUE COTE D'IVOIRE",              "Services Financiers"),
    "ORGT":  ("ORAGROUP TOGO",                          "Services Financiers"),
    "SAFC":  ("ALIOS FINANCE COTE D'IVOIRE",            "Services Financiers"),
    "SGBC":  ("SGB COTE D'IVOIRE",                      "Services Financiers"),
    "SIBC":  ("SOCIETE IVOIRIENNE DE BANQUE",           "Services Financiers"),
    "CIEC":  ("CIE COTE D'IVOIRE",                      "Services Publics"),
    "SDCC":  ("SODE COTE D'IVOIRE",                     "Services Publics"),
    "TTLC":  ("TOTAL ENERGIES COTE D'IVOIRE",           "Énergie"),
    "TTLS":  ("TOTAL ENERGIES SENEGAL",                 "Énergie"),
    "SHEC":  ("VIVO ENERGY COTE D'IVOIRE",              "Énergie"),
    "SMBC":  ("SMB COTE D'IVOIRE",                      "Énergie"),
    "FTSC":  ("FILTISAC COTE D'IVOIRE",                 "Industriels"),
    "CABC":  ("SICABLE COTE D'IVOIRE",                  "Industriels"),
    "STAC":  ("SETAO COTE D'IVOIRE",                    "Industriels"),
    "SDSC":  ("AFRICA GLOBAL LOGISTICS CI",             "Industriels"),
    "SEMC":  ("EVIOSYS PACKAGING SIEM CI",              "Industriels"),
    "SIVC":  ("ERIUM CI",                               "Industriels"),
    "NTLC":  ("NESTLE COTE D'IVOIRE",                   "Consommation de base"),
    "PALC":  ("PALM COTE D'IVOIRE",                     "Consommation de base"),
    "SPHC":  ("SAPH COTE D'IVOIRE",                     "Consommation de base"),
    "SICC":  ("SICOR COTE D'IVOIRE",                    "Consommation de base"),
    "STBC":  ("SITAB COTE D'IVOIRE",                    "Consommation de base"),
    "SOGC":  ("SOGB COTE D'IVOIRE",                     "Consommation de base"),
    "SLBC":  ("SOLIBRA COTE D'IVOIRE",                  "Consommation de base"),
    "SCRC":  ("SUCRIVOIRE COTE D'IVOIRE",               "Consommation de base"),
    "UNLC":  ("UNILEVER COTE D'IVOIRE",                 "Consommation de base"),
    "BNBC":  ("BERNABE COTE D'IVOIRE",                  "Consommation discrétionnaire"),
    "CFAC":  ("CFAO MOTORS COTE D'IVOIRE",              "Consommation discrétionnaire"),
    "LNBB":  ("LOTERIE NATIONALE DU BENIN",             "Consommation discrétionnaire"),
    "NEIC":  ("NEI-CEDA COTE D'IVOIRE",                 "Consommation discrétionnaire"),
    "ABJC":  ("SERVAIR ABIDJAN COTE D'IVOIRE",          "Consommation discrétionnaire"),
    "PRSC":  ("TRACTAFRIC MOTORS COTE D'IVOIRE",        "Consommation discrétionnaire"),
    "UNXC":  ("UNIWAX COTE D'IVOIRE",                   "Consommation discrétionnaire"),
}

# ─────────────────────────────────────────────
# RÉFÉRENTIELS SECTORIELS
# ─────────────────────────────────────────────
PER_SECTORIELS = {
    "Télécommunications":         10.11,
    "Consommation discrétionnaire": 72.48,
    "Services Financiers":        11.08,
    "Consommation de base":       14.80,
    "Industriels":                22.23,
    "Énergie":                    17.63,
    "Services Publics":           17.65,
}
TAUX_DCF = {
    "Télécommunications":         0.11,
    "Consommation discrétionnaire": 0.13,
    "Services Financiers":        0.11,
    "Consommation de base":       0.12,
    "Industriels":                0.14,
    "Énergie":                    0.13,
    "Services Publics":           0.11,
}
SAISONNALITE_S1 = {
    "Télécommunications":         0.50,
    "Consommation discrétionnaire": 0.45,
    "Services Financiers":        0.48,
    "Consommation de base":       0.48,
    "Industriels":                0.45,
    "Énergie":                    0.52,
    "Services Publics":           0.50,
}
COULEURS_SIGNAL = {
    "🟢 FORT ACHAT":  "#3fb950",
    "🔵 ACHAT":       "#79c0ff",
    "🟡 SURVEILLER":  "#d29922",
    "🟠 ALLÉGER":     "#ffa657",
    "🔴 SORTIR":      "#f85149",
    "🔴 BLOQUÉ RSI":  "#f85149",
    "🔴 BLOQUÉ BB":   "#f85149",
    "🔴 SURÉVALUÉ":   "#f85149",
    "🟡 HORS MARGE":  "#d29922",
}
SECTEURS = list(PER_SECTORIELS.keys())

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

# ─────────────────────────────────────────────
# SQLITE
# ─────────────────────────────────────────────
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
            list(data.values())
        )

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
            return [dict(r) for r in conn.execute("SELECT ticker,secteur,maj_at FROM fondamentaux ORDER BY maj_at DESC").fetchall()]
    except Exception:
        return []

def del_fond(ticker):
    with db() as conn:
        conn.execute("DELETE FROM fondamentaux WHERE ticker=?", (ticker.upper(),))

# ─────────────────────────────────────────────
# HELPERS NUMÉRIQUES
# ─────────────────────────────────────────────
_NULS = {"", "-", "–", "—", "N/D", "N/A", "nd", "na", "nc", "n/c", "null", "none"}

def to_float(v, default=None):
    s = (str(v)
         .replace(" ","").replace(" ","").replace("\u2009","")
         .replace(" ","").replace(",",".").replace("%","").strip())
    if s.lower() in _NULS:
        return default
    try:
        return float(s)
    except Exception:
        return default

def _normalize(s):
    import unicodedata as _ud
    s = str(s).strip().lower().replace(" ","").replace(" ","")
    return "".join(c for c in _ud.normalize("NFD", s) if _ud.category(c) != "Mn")

# ─────────────────────────────────────────────
# SCRAPING — ARCHITECTURE SIMPLIFIÉE
#
# Stratégie : 2 sources directes, parser unique
#  1. brvm.org  — site officiel, pas de bot-blocker
#  2. sikafinance.com — agrégateur, accès direct
#  Chaque source : GET → BS4 row-scanner → pd.read_html
# ─────────────────────────────────────────────

def _parse_table(html, ticker):
    """
    Cherche le ticker dans les tables HTML.
    Retourne (prix, variation) ou (None, None).
    """
    tk = ticker.upper().strip()

    # ── BS4 row scanner ──────────────────────────────────
    if HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            for tr in rows:
                cells = [c.get_text(strip=True) for c in tr.find_all(["td","th"])]
                if tk not in [c.upper() for c in cells]:
                    continue
                # Le ticker est dans cette ligne — chercher le premier nombre > 50
                nums = [to_float(c) for c in cells]
                prices = [v for v in nums if v and v > 50]
                if not prices:
                    continue
                prix = prices[0]
                # Variation : chercher un float entre -30 et 30 après le prix
                var = 0.0
                for v in nums:
                    if v is not None and -30 < v < 30 and v != prix:
                        var = v
                        break
                return prix, var

    # ── pd.read_html fallback ────────────────────────────
    try:
        tables = pd.read_html(StringIO(html))
    except Exception:
        return None, None

    for df in tables:
        df.columns = [_normalize(c) for c in df.columns]
        # Chercher colonne ticker
        col_tk = next((c for c in df.columns if any(k in c for k in ["symbol","ticker","code","valeur","titre","sigle"])), None)
        col_px = next((c for c in df.columns if any(k in c for k in ["cours","cotation","close","prix","dernier","actuel"])), None)
        if col_tk is None or col_px is None:
            continue
        mask = df[col_tk].astype(str).str.upper().str.strip() == tk
        if not mask.any():
            continue
        row = df[mask].iloc[0]
        px = to_float(row[col_px])
        if px and px > 50:
            col_var = next((c for c in df.columns if any(k in c for k in ["variation","var","change","evol","%"])), None)
            var = to_float(row[col_var], 0.0) if col_var else 0.0
            return px, var

    return None, None


# ─────────────────────────────────────────────
# CONSTANTE BASE URL
RICHBOURSE_BASE = "https://www.richbourse.com"

# ─────────────────────────────────────────────
# SCRAPING — COURS + INDICATEURS TECHNIQUES
# ─────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_cours(ticker: str) -> dict:
    """
    Cascade cours : richbourse → brvm.org → sikafinance
    Colonnes richbourse confirmées (2025-03) : Symbole | Cours actuel | Variation
    """
    tk = ticker.upper().strip()

    COL_TICKER_VARIANTS = ["symbole", "ticker", "code", "valeur", "titre", "action"]
    COL_PRIX_VARIANTS   = ["cours actuel", "actuel", "dernier cours", "cours",
                           "clôture", "cloture", "close", "prix"]
    COL_VAR_VARIANTS    = ["variation", "var", "évolution", "evolution"]

    # ── Source 1 : richbourse ──────────────────────────────────────────────────
    for url in [
        f"{RICHBOURSE_BASE}/common/variation/index",
        f"{RICHBOURSE_BASE}/common/variation/index/veille/tout",
    ]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if resp.status_code != 200 or len(resp.text) < 500:
                continue
            tables = pd.read_html(StringIO(resp.text))
            for df in tables:
                df.columns = [
                    str(c).strip().lower()
                    .replace(" ", "").replace(" ", "")
                    for c in df.columns
                ]
                col_tk  = next((c for c in df.columns if any(k in c for k in COL_TICKER_VARIANTS)), None)
                col_px  = next((c for c in df.columns if any(k in c for k in COL_PRIX_VARIANTS)), None)
                col_var = next((c for c in df.columns if any(k in c for k in COL_VAR_VARIANTS)), None)
                if not col_tk:
                    for col in df.columns:
                        if df[col].astype(str).str.upper().str.strip().eq(tk).any():
                            col_tk = col; break
                if not col_tk or not col_px:
                    continue
                mask   = df[col_tk].astype(str).str.upper().str.strip() == tk
                subset = df[mask].dropna(subset=[col_px])
                if subset.empty:
                    continue
                try:
                    px = to_float(subset[col_px].iloc[0])
                    vr = to_float(subset[col_var].iloc[0], 0.0) if col_var else 0.0
                    if px and px > 0:
                        return {"prix": px, "variation_pct": vr, "source": "richbourse"}
                except Exception:
                    continue
        except Exception:
            continue

    # ── Source 2 : brvm.org ────────────────────────────────────────────────────
    for url in [
        "https://www.brvm.org/fr/cours-actions/0",
        "https://www.brvm.org/fr/cours-actions/0/symbole/asc/100/1",
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200 or tk not in r.text.upper():
                continue
            px, var = _parse_table(r.text, tk)
            if px:
                return {"prix": px, "variation_pct": var or 0.0, "source": "brvm.org"}
        except Exception:
            continue

    # ── Source 3 : sikafinance ─────────────────────────────────────────────────
    for url in [
        "https://www.sikafinance.com/marches/aaz",
        f"https://www.sikafinance.com/valeur/BRVM/{tk}",
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=False)
            if r.status_code != 200 or tk not in r.text.upper():
                continue
            px, var = _parse_table(r.text, tk)
            if px:
                return {"prix": px, "variation_pct": var or 0.0, "source": "sikafinance"}
        except Exception:
            continue

    return {}


@st.cache_data(ttl=600, show_spinner=False)
def fetch_tech_synthese(ticker: str) -> dict:
    """
    richbourse.com/common/prevision-boursiere/synthese/TICKER
    Patterns calés sur le vrai texte richbourse (confirmés).
    """
    if not HAS_BS4:
        return {}
    tk  = ticker.upper().strip()
    url = f"{RICHBOURSE_BASE}/common/prevision-boursiere/synthese/{tk}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code != 200:
            return {}
        soup  = BeautifulSoup(resp.text, "html.parser")
        texte = soup.get_text(" ", strip=True)
        if "rsi" not in texte.lower() and "bollinger" not in texte.lower():
            return {}
        result = {"_source_tech": "richbourse"}
        # RSI — format exact : "RSI 14 jours est de 54,32 %"
        m_rsi = _re.search(r"RSI\s*14\s*jours\s*est\s*de\s*([\d,\.]+)\s*%", texte, _re.IGNORECASE)
        if m_rsi:
            result["rsi"] = float(m_rsi.group(1).replace(",", "."))
        tl = texte.lower()
        # Bollinger — phrases exactes richbourse
        if "au-dessus de la bande supérieure" in tl or "bande supérieure de bollinger" in tl:
            result["bb_position"] = "above_sup"
        elif "en-dessous de la bande inférieure" in tl or "bande inférieure de bollinger" in tl:
            result["bb_position"] = "below_inf"
        else:
            result["bb_position"] = "inside"
        # EMA20 — phrase exacte richbourse
        if "au-dessus de leur moyenne mobile à 20" in tl:
            result["ema20_position"] = "above"
        elif "en-dessous de leur moyenne mobile à 20" in tl:
            result["ema20_position"] = "below"
        else:
            result["ema20_position"] = "unknown"
        # Tendance + confiance
        m_tend = _re.search(r"Tendance\s*[àa]\s*court\s*terme\s*:\s*(\w+)", texte, _re.IGNORECASE)
        m_conf = _re.search(r"indice de confiance de\s*([\d,\.]+)\s*%", texte, _re.IGNORECASE)
        if m_tend: result["tendance"]  = m_tend.group(1).capitalize()
        if m_conf: result["confiance"] = float(m_conf.group(1).replace(",", "."))
        return result
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_historique(ticker: str, nb: int = 120):

    tk = ticker.upper()
    url = f"{RICHBOURSE_BASE}/common/variation/historique/{tk}"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.richbourse.com/",
        "Accept": "text/html,application/xhtml+xml"
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            return pd.DataFrame()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")

        table = soup.find("table")
        if table is None:
            return pd.DataFrame()

        rows = table.find_all("tr")
        data = []

        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) >= 2:
                date = cols[0].get_text(strip=True)
                close = cols[1].get_text(strip=True)
                data.append([date, close])

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=["date", "close"])

        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        df["close"] = (
            df["close"]
            .str.replace("\xa0", "", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace(",", ".", regex=False)
        )

        df["close"] = pd.to_numeric(df["close"], errors="coerce")

        df = df.dropna().sort_values("date")

        return df.tail(nb).reset_index(drop=True)

    except Exception as e:
        st.write("Erreur fetch:", e)
        return pd.DataFrame()


def calc_indicateurs(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 20:
        return {}

    close = df["close"]

    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = rsi.iloc[-1]

    bb_mid = close.rolling(20).mean().iloc[-1]
    bb_std = close.rolling(20).std().iloc[-1]
    bb_sup = bb_mid + 2 * bb_std
    bb_inf = bb_mid - 2 * bb_std

    var_1s = (close.iloc[-1] / close.iloc[-6] - 1) * 100

    return {
        "rsi": round(rsi_val, 1),
        "ema20": round(ema20, 0),
        "bb_sup": round(bb_sup, 0),
        "bb_inf": round(bb_inf, 0),
        "bb_mid": round(bb_mid, 0),
        "var_1s": round(var_1s, 2),
        "nb_pts": len(close),
    }


def get_marche(ticker: str) -> dict:
    """
    Pipeline unifié :
      1. Cours       ← fetch_cours()          richbourse → brvm.org → sikafinance
      2. Tech qual.  ← fetch_tech_synthese()  RSI précis + positions BB/EMA
      3. Tech num.   ← fetch_historique() + calc_indicateurs()
                       BB sup/inf FCFA, EMA20, var_1s, nb_pts
    Priorité RSI : synthèse richbourse > calcul local.
    """
    tk = ticker.upper().strip()
    result = {}
    result.update(fetch_cours(tk))
    result.update(fetch_tech_synthese(tk))
    df_hist = fetch_historique(tk)
    if not df_hist.empty:
        indics = calc_indicateurs(df_hist)
        for k_ind, v_ind in indics.items():
            if k_ind == "rsi" and "rsi" in result:
                continue  # RSI synthèse richbourse a priorité
            result[k_ind] = v_ind
        result["_source_tech"] = "richbourse+historique"
    elif "rsi" in result:
        result["_source_tech"] = "richbourse_only"
    return result

def extrapoler(resultat, periode, secteur):
    s = SAISONNALITE_S1.get(secteur, 0.50)
    if '9 mois' in periode:
        return resultat/3*4, '9M x 4/3', 'Elevee'
    elif 'Semestriel' in periode:
        return resultat/s, f'S1 / {s:.2f}', 'Moderee'
    return resultat, 'Donnees annuelles', 'Annuelle'


def vi_dcf(bpa, g_bpa, taux):
    g1 = min(max(g_bpa/100, -0.10), 0.20)
    g2, r = 0.03, taux
    flux = sum(bpa*(1+g1)**t/(1+r)**t for t in range(1,6))
    vt   = bpa*(1+g1)**5*(1+g2)/(r-g2)/(1+r)**5
    return flux + vt

def signal(score, upside, survalu, hors_marge, f_rsi, f_bb):
    if f_rsi:       return "🔴 BLOQUÉ RSI"
    if f_bb:        return "🔴 BLOQUÉ BB"
    if survalu:     return "🔴 SURÉVALUÉ"
    if hors_marge:  return "🟡 HORS MARGE"
    if score >= 0.65 and upside > 25: return "🟢 FORT ACHAT"
    if score >= 0.50 and upside > 15: return "🔵 ACHAT"
    if score >= 0.40 and upside > 5:  return "🟡 SURVEILLER"
    if score < 0.35 or upside < -15:  return "🔴 SORTIR"
    return "🟠 ALLÉGER"

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "screener" not in st.session_state:
    st.session_state.screener = []

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.markdown("## ⚙️ Paramètres")
mode_simple = st.sidebar.radio("Mode", ["Simple","Expert"]) == "Simple"

if mode_simple:
    W_V, W_Q, W_M = 0.35, 0.40, 0.25
else:
    st.sidebar.markdown("### Pondérations")
    W_V = st.sidebar.slider("Value",    0.1, 0.6, 0.30, 0.05)
    W_Q = st.sidebar.slider("Quality",  0.1, 0.6, 0.40, 0.05)
    W_M = st.sidebar.slider("Momentum", 0.1, 0.6, 0.30, 0.05)
    T = W_V+W_Q+W_M; W_V/=T; W_Q/=T; W_M/=T

st.sidebar.markdown("---")
MARGE = st.sidebar.slider("Marge de sécurité (%)", 5, 30, 20, 5) / 100
RSI_HAUT = st.sidebar.slider("RSI surachat", 60, 80, 70, 5)
RSI_BAS  = st.sidebar.slider("RSI survente", 20, 40, 30, 5)

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Vider cache cours"):
    fetch_cours.clear(); fetch_historique.clear(); fetch_tech_synthese.clear(); fetch_tech_sika.clear()
    st.sidebar.success("Cache vidé ✅"); st.rerun()

if st.sidebar.button("🗑️ Vider le screener"):
    st.session_state.screener = []; st.rerun()

# Export/Import JSON
fonds = list_fonds()
if fonds:
    if st.sidebar.button("⬇️ Exporter fondamentaux JSON"):
        with db() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM fondamentaux").fetchall()]
        st.sidebar.download_button("Télécharger", json.dumps(rows, ensure_ascii=False, indent=2),
                                   "fondamentaux_brvm.json", mime="application/json")
up = st.sidebar.file_uploader("📥 Importer JSON", type="json")
if up:
    try:
        rows = json.loads(up.read())
        for row in rows:
            tk_ = row.pop("ticker", None)
            if tk_: save_fond(tk_, row)
        st.sidebar.success(f"✅ {len(rows)} titres importés"); st.rerun()
    except Exception as e:
        st.sidebar.error(str(e))

# ─────────────────────────────────────────────
# TITRE
# ─────────────────────────────────────────────
st.title("⬡ Screener BRVM v4.0")
st.caption("brvm.org → sikafinance.com · BS4 + pandas · SQLite")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Analyser", "📊 Tableau de bord", "💾 Fondamentaux", "📖 Méthode"])

# ─────────────────────────────────────────────
# TAB 1 — FORMULAIRE
# ─────────────────────────────────────────────
with tab1:
    # ── Sélection ticker ─────────────────────
    LABELS = {tk: f"{tk} — {v[0]}" for tk, v in TICKERS_BRVM.items()}
    choices = ["(Saisie libre)"] + [LABELS[tk] for tk in sorted(TICKERS_BRVM)]

    c1, c2, c3 = st.columns([3,2,1])
    with c1:
        choice = st.selectbox("Ticker BRVM", choices)
        if choice == "(Saisie libre)":
            titre = st.text_input("Ticker", placeholder="ex: SNTS").upper().strip()
        else:
            titre = next(tk for tk,lb in LABELS.items() if lb==choice)
    with c2:
        periode = st.selectbox("Période", ["Annuel complet","9 mois (T1+T2+T3)","Semestriel (S1)"])
    with c3:
        annee = st.selectbox("Exercice", ["2025","2024","2023"])

    # ── Infos ticker ─────────────────────────
    secteur_auto = TICKERS_BRVM.get(titre,(None,None))[1] if titre else None
    nom_auto     = TICKERS_BRVM.get(titre,(None,None))[0] if titre else None
    fond_saved   = load_fond(titre) if titre and len(titre)>=3 else None

    # ── Données marché ────────────────────────
    mdata = {}
    if titre and len(titre) >= 3:
        with st.spinner(f"Chargement cours {titre}…"):
            mdata = get_marche(titre)

    # ── Carte ticker ──────────────────────────
    if titre and len(titre) >= 3:
        px_str = f"{mdata['prix']:,.0f} FCFA  {'+' if mdata.get('variation_pct',0)>=0 else ''}{mdata.get('variation_pct',0):.2f}%  ← {mdata.get('source','')}" if "prix" in mdata else "⚠️ Cours non disponible — saisie manuelle"
        couleur_px = "#3fb950" if "prix" in mdata else "#d29922"
        st.markdown(f"""<div class="card">
        <span style="font-family:'IBM Plex Mono';font-size:1.5em;font-weight:700">{titre}</span>
        {"<span class='lbl'> "+nom_auto+"</span>" if nom_auto else ""}
        {"<span class='tag tag-blue'>"+secteur_auto+"</span>" if secteur_auto else ""}
        {"<span class='tag tag-green'>Fondamentaux sauvegardés</span>" if fond_saved else ""}
        <br><span style="font-family:'IBM Plex Mono';color:{couleur_px};font-size:1.1em">{px_str}</span>
        </div>""", unsafe_allow_html=True)

        if not mdata.get("prix"):
            st.markdown("""<div class="alert-yellow">
            ⚠️ Cours non chargé automatiquement — saisir manuellement ci-dessous.<br>
            <small>Sources tentées : brvm.org, sikafinance.com · Vider le cache si réessai</small>
            </div>""", unsafe_allow_html=True)


        # Bandeau statut données — visible immédiatement, hors form
        _has_cours = 'prix' in mdata
        _has_rsi   = 'rsi' in mdata
        _has_bb    = 'bb_sup' in mdata and 'bb_inf' in mdata
        _has_ema   = 'ema20' in mdata
        _nb_pts    = mdata.get('nb_pts', 0)
        _src_tech  = mdata.get('_source_tech', 'aucune')
        def _ok(b, val=''):
            return f'✅ {val}' if b else '❌'
        _items = [
            f"Cours : {_ok(_has_cours, str(int(mdata['prix']))+' FCFA') if _has_cours else _ok(False)}",
            f"RSI : {_ok(_has_rsi, str(mdata['rsi'])) if _has_rsi else _ok(False)}",
            f"BB : {_ok(_has_bb, str(int(mdata.get('bb_inf',0)))+'/'+str(int(mdata.get('bb_sup',0)))) if _has_bb else _ok(False)}",
            f"EMA20 : {_ok(_has_ema, str(int(mdata['ema20']))) if _has_ema else _ok(False)}",
            f"Hist : {_nb_pts} pts",
            f"Source tech : {_src_tech}",
        ]
        _col = '#3fb950' if (_has_cours and _has_rsi and _has_bb and _has_ema) else ('#d29922' if _has_cours else '#f85149')
        st.markdown(
            f"<div style='background:#0d1117;border:1px solid #30363d;border-left:4px solid {_col};"
            f"border-radius:6px;padding:7px 14px;margin:4px 0 8px 0;font-family:IBM Plex Mono,monospace;"
            f"font-size:0.78em;color:#8b949e'>" + " &nbsp;·&nbsp; ".join(_items) + "</div>",
            unsafe_allow_html=True
        )

    # ── Secteur ──────────────────────────────
    idx = SECTEURS.index(secteur_auto) if secteur_auto in SECTEURS else 0
    secteur = st.selectbox("Secteur", SECTEURS, index=idx)
    est_banque = secteur == "Services Financiers"

    if not mode_simple:
        TAUX_ACTUA = TAUX_DCF[secteur]
        st.caption(f"Taux DCF : {TAUX_ACTUA*100:.0f}% · PER cible : {PER_SECTORIELS[secteur]:.2f}x")
    else:
        TAUX_ACTUA = TAUX_DCF[secteur]

    # ── Alerte période intermédiaire ──────────
    if titre and len(titre)>=3 and "Annuel" not in periode:
        champ_bilan = "Crédits/Dépôts" if est_banque else "Capitaux propres, actif, dettes"
        st.markdown(f"""<div class="alert-blue">
        📅 Publication intermédiaire — {champ_bilan} : référez-vous au bilan {int(annee)-1}.
        Le résultat sera extrapolé automatiquement.
        </div>""", unsafe_allow_html=True)

    # ─────────────────────────────────────────
    # FORMULAIRE
    # ─────────────────────────────────────────
    def fd(k, d):
        return fond_saved[k] if fond_saved and k in fond_saved and fond_saved[k] is not None else d

    with st.form("saisie"):
        # Prix
        px_def   = mdata.get("prix", 1000.0)
        px_label = f"💰 Prix actuel FCFA {'['+mdata['source']+']' if 'source' in mdata else '⚠️ saisie manuelle'}"
        prix = st.number_input(px_label, min_value=1.0, value=float(px_def), key=f"prix_{titre}")

        # ── Fondamentaux ─────────────────────
        if est_banque:
            st.markdown("**📊 Données bancaires**")
            a1, a2 = st.columns(2)
            with a1:
                pnb             = st.number_input("PNB (millions FCFA)", min_value=1.0, value=fd("pnb",5000.0))
                encours_credits = st.number_input("Encours crédits (M FCFA)", min_value=1.0, value=fd("encours_credits",30000.0))
            with a2:
                resultat_saisi  = st.number_input("Résultat net (M FCFA)", value=fd("resultat_b",800.0))
                depots          = st.number_input("Dépôts clientèle (M FCFA)", min_value=1.0, value=fd("depots_clientele",40000.0))
            b1, b2, b3 = st.columns(3)
            with b1: nombre_actions   = st.number_input("Actions (millions)", min_value=0.001, value=fd("nombre_actions",10.0))
            with b2: capitaux_propres = st.number_input("Capitaux propres (M FCFA)", min_value=1.0, value=fd("capitaux_propres",8000.0))
            with b3:
                dividende = st.number_input("Dividende/action (FCFA)", min_value=0.0, value=fd("dividende",0.0))
                bpa_prec  = st.number_input("BPA an préc. (FCFA)", value=fd("bpa_prec",80.0))
            total_actif = dettes_totales = stabilite_bpa = None
        else:
            st.markdown("**📊 Compte de résultat**")
            a1, a2, a3 = st.columns(3)
            with a1:
                resultat_saisi = st.number_input("Résultat net (M FCFA)", value=fd("resultat",500.0))
                nombre_actions = st.number_input("Actions (millions)", min_value=0.001, value=fd("nombre_actions",10.0))
            with a2:
                dividende = st.number_input("Dividende/action (FCFA)", min_value=0.0, value=fd("dividende",0.0))
                bpa_prec  = st.number_input("BPA an préc. (FCFA)", value=fd("bpa_prec",80.0))
            with a3:
                stabilite_bpa = st.selectbox("Régularité bénéfices", ["Stable","Volatil","Exceptionnel"],
                    index=["Stable","Volatil","Exceptionnel"].index(fd("stabilite_bpa","Stable"))) if not mode_simple else "Stable"

            st.markdown("**🏦 Bilan**")
            b1, b2, b3 = st.columns(3)
            with b1: capitaux_propres = st.number_input("Capitaux propres (M FCFA)", min_value=1.0, value=fd("capitaux_propres",2000.0))
            with b2: total_actif      = st.number_input("Total actif (M FCFA)", min_value=1.0, value=fd("total_actif",5000.0))
            with b3: dettes_totales   = st.number_input("Dettes financières (M FCFA)", min_value=0.0, value=fd("dettes_totales",1000.0))
            pnb = encours_credits = depots = None

        # ── Indicateurs techniques ─────────────
        st.markdown("**📡 Indicateurs techniques**")
        has_tech = all(k in mdata for k in ["rsi","bb_sup","bb_inf","ema20"])
        if has_tech:
            st.markdown(f"""<div class="alert-green">✅ Indicateurs calculés depuis historique brvm.org
            — RSI {mdata['rsi']:.0f} · BB [{mdata['bb_inf']:,.0f} / {mdata['bb_sup']:,.0f}] · EMA20 {mdata['ema20']:,.0f}</div>""",
            unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-yellow">⚠️ Historique non disponible — saisir manuellement (TradingView ou richbourse.com)</div>',
            unsafe_allow_html=True)

        t1, t2, t3 = st.columns(3)
        with t1:
            bb_sup = st.number_input("BB supérieure", min_value=1.0, value=float(mdata.get("bb_sup",1100.0)), key=f"ti_bb_sup_{titre}")
            bb_inf = st.number_input("BB inférieure", min_value=1.0, value=float(mdata.get("bb_inf",900.0)), key=f"ti_bb_inf_{titre}")
        with t2:
            ema20  = st.number_input("EMA20", min_value=1.0, value=float(mdata.get("ema20",980.0)), key=f"ti_ema20_{titre}")
            var_1s = st.number_input("Variation 1 semaine (%)", -30.0, 30.0, float(mdata.get("var_1s",0.0)), key=f"ti_var1s_{titre}")
        with t3:
            rsi = st.number_input("RSI (14)", 0.0, 100.0, float(mdata.get("rsi",50.0)), key=f"ti_rsi_{titre}")
            st.markdown(f"<div class='box'><div class='lbl'>Seuils</div>Surachat : <b style='color:#f85149'>{RSI_HAUT}</b> · Survente : <b style='color:#3fb950'>{RSI_BAS}</b></div>",
            unsafe_allow_html=True)

        save_cb = st.checkbox("💾 Sauvegarder fondamentaux", value=True)
        submitted = st.form_submit_button("🔍 Analyser", use_container_width=True)

    # ─────────────────────────────────────────
    # CALCULS & RÉSULTATS
    # ─────────────────────────────────────────
    if submitted and titre:
        if any(a["Titre"] == titre.upper() for a in st.session_state.screener):
            st.error(f"'{titre.upper()}' est déjà dans le screener."); st.stop()

        # Extrapolation
        if est_banque:
            r_an, meth, conf = extrapoler(resultat_saisi, periode, secteur)
            pnb_ = pnb
        else:
            r_an, meth, conf = extrapoler(resultat_saisi, periode, secteur)
            pnb_ = None

        bpa         = r_an / nombre_actions
        val_book    = capitaux_propres / nombre_actions
        per         = prix / bpa if bpa > 0 else 99
        pbr         = prix / val_book if val_book > 0 else 99
        dy          = dividende / prix if prix > 0 else 0
        g_bpa       = ((bpa - bpa_prec) / abs(bpa_prec) * 100) if bpa_prec else 0
        roe         = r_an / capitaux_propres * 100

        # Valeurs intrinsèques
        graham      = np.sqrt(max(22.5 * bpa * val_book, 0)) if bpa > 0 else 0
        fv_per      = bpa * PER_SECTORIELS[secteur] if bpa > 0 else 0
        fv_dcf      = vi_dcf(bpa, g_bpa, TAUX_ACTUA) if bpa > 0 else 0
        vi          = graham*0.40 + fv_per*0.35 + fv_dcf*0.25 if graham > 0 and fv_dcf > 0 else (graham*0.5 + fv_per*0.5 if graham > 0 else fv_per)
        prix_cible  = vi * (1 - MARGE)
        upside      = (prix_cible / prix - 1) * 100
        survalu     = prix > vi
        hors_marge  = prix > prix_cible and not survalu

        # Scores
        per_cap = min(PER_SECTORIELS[secteur], 25)
        s_per   = np.clip(per_cap/per, 0, 1) if per > 0 else 0
        s_pbr   = np.clip(1.5/pbr, 0, 1)
        s_dy    = np.clip(dy/0.08, 0, 1)
        v_score = s_per*0.40 + s_pbr*0.35 + s_dy*0.25

        if est_banque:
            roa = dette_cp = None
            marge_b = r_an/pnb_ if pnb_ else 0
            cd_ratio = encours_credits/depots if depots else 0
            q_score = (np.clip(marge_b/0.20,0,1)*0.45 + np.clip(1-abs(cd_ratio-0.80)/0.40,0,1)*0.30 + np.clip(roe/15,0,1)*0.25)
        else:
            roa = r_an/total_actif*100
            dette_cp = dettes_totales/capitaux_propres
            marge_b = cd_ratio = None
            bonus = {"Stable":0.20,"Volatil":0.0,"Exceptionnel":0.30}.get(stabilite_bpa,0)
            q_score = (np.clip(roe/25,0,1)*0.35 + np.clip(roa/12,0,1)*0.30 + np.clip(1-dette_cp/3,0,1)*0.25 + bonus*0.10)

        m_score = np.clip(g_bpa/30,-1,1)*0.60 + np.clip(var_1s/10,-1,1)*0.40
        score   = W_V*v_score + W_Q*q_score + W_M*m_score

        f_rsi = rsi > RSI_HAUT
        f_bb  = prix > bb_sup
        bb_pct = ((prix - bb_inf)/(bb_sup - bb_inf)*100) if (bb_sup - bb_inf) > 0 else 50
        ecart_ema = (prix/ema20 - 1)*100

        sig = signal(score, upside, survalu, hors_marge, f_rsi, f_bb)
        col_sig = COULEURS_SIGNAL.get(sig, "#8b949e")
        est = conf != "Annuelle"

        # ── Sauvegarde ─────────────────────────
        if save_cb:
            fd_data = {"secteur":secteur,"periode":periode,"annee":annee,
                       "est_banque":1 if est_banque else 0,
                       "nombre_actions":nombre_actions,"dividende":dividende,
                       "bpa_prec":bpa_prec,"capitaux_propres":capitaux_propres}
            if est_banque:
                fd_data.update({"pnb":pnb_,"resultat_b":resultat_saisi,
                                "encours_credits":encours_credits,"depots_clientele":depots})
            else:
                fd_data.update({"resultat":resultat_saisi,"total_actif":total_actif,
                                "dettes_totales":dettes_totales,"stabilite_bpa":stabilite_bpa})
            save_fond(titre, fd_data)

        # ── Affichage ─────────────────────────
        st.markdown("---")
        tags = ""
        if est:          tags += "<span class='tag tag-blue'>⚠️ Estimé</span>"
        if "prix" in mdata: tags += "<span class='tag tag-green'>✅ Cours auto</span>"
        if est_banque:   tags += "<span class='tag tag-blue'>🏦 Bancaire</span>"
        st.markdown(f"### {titre.upper()} {tags}", unsafe_allow_html=True)

        if est:
            st.markdown(f"""<div class="alert-blue">
            Résultat {periode} → annualisé : <b>{r_an:.0f}M FCFA</b> ({meth})
            </div>""", unsafe_allow_html=True)

        # Filtres techniques
        st.markdown("#### 📡 Filtres techniques")
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            rc = "#f85149" if f_rsi else ("#3fb950" if rsi < RSI_BAS else "#79c0ff")
            st.markdown(f"""<div class="box"><div class="lbl">RSI (14)</div>
            <b style="font-size:1.5em;color:{rc}">{rsi:.0f}</b><br>
            <span style="color:{rc};font-size:.85em">{"🔴 Surachat" if f_rsi else ("🟢 Survente" if rsi<RSI_BAS else "✅ Neutre")}</span></div>""",
            unsafe_allow_html=True)
        with tc2:
            bc = "#f85149" if f_bb else ("#3fb950" if prix<bb_inf else "#79c0ff")
            st.markdown(f"""<div class="box"><div class="lbl">Bollinger</div>
            <b style="color:{bc}">{bb_pct:.0f}% bande</b><br>
            <span style="color:#8b949e;font-size:.82em">{bb_inf:,.0f} | {prix:,.0f} | {bb_sup:,.0f}</span><br>
            <span style="color:{bc};font-size:.85em">{"🔴 Surachat" if f_bb else ("🟢 Sous inf" if prix<bb_inf else "✅ OK")}</span></div>""",
            unsafe_allow_html=True)
        with tc3:
            mc = "#3fb950" if prix>ema20 else "#f85149"
            st.markdown(f"""<div class="box"><div class="lbl">EMA20</div>
            <b style="color:{mc}">{ema20:,.0f} FCFA</b><br>
            <span style="color:#8b949e;font-size:.82em">Écart {ecart_ema:+.1f}%</span><br>
            <span style="color:{mc};font-size:.85em">{"✅ Haussier" if prix>ema20 else "⚠️ Baissier"}</span></div>""",
            unsafe_allow_html=True)

        # Graham
        st.markdown("#### 🔒 Verrou Graham")
        if survalu:
            st.markdown(f'<div class="alert-red">🔒 Surévalué — Prix {prix:,.0f} > VI {vi:,.0f} FCFA</div>', unsafe_allow_html=True)
        elif hors_marge:
            st.markdown(f'<div class="alert-yellow">⚠️ Hors marge — Prix {prix:,.0f} entre VI {vi:,.0f} et cible {prix_cible:,.0f}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-green">✅ OK — Prix {prix:,.0f} &lt; Cible {prix_cible:,.0f} · Upside {upside:.1f}%</div>', unsafe_allow_html=True)

        # Ratios
        st.markdown("#### 📊 Ratios")
        cols_r = st.columns(5)
        with cols_r[0]:
            st.markdown(f'<div class="box"><div class="lbl">BPA</div><b>{bpa:,.1f}</b> FCFA</div><div class="box"><div class="lbl">PER</div><b>{per:.1f}x</b> <span class="lbl">({PER_SECTORIELS[secteur]:.1f}x)</span></div>', unsafe_allow_html=True)
        with cols_r[1]:
            st.markdown(f'<div class="box"><div class="lbl">P/Book</div><b>{pbr:.2f}x</b></div><div class="box"><div class="lbl">Rendement</div><b>{dy*100:.1f}%</b></div>', unsafe_allow_html=True)
        with cols_r[2]:
            if est_banque:
                st.markdown(f'<div class="box"><div class="lbl">Marge/PNB</div><b>{marge_b*100:.1f}%</b></div><div class="box"><div class="lbl">Crédits/Dépôts</div><b>{cd_ratio*100:.1f}%</b></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="box"><div class="lbl">ROE</div><b>{roe:.1f}%</b></div><div class="box"><div class="lbl">ROA</div><b>{roa:.1f}%</b></div>', unsafe_allow_html=True)
        with cols_r[3]:
            st.markdown(f'<div class="box"><div class="lbl">Graham N°</div><b>{graham:,.0f}</b></div><div class="box"><div class="lbl">Δ BPA</div><b>{g_bpa:+.1f}%</b></div>', unsafe_allow_html=True)
        with cols_r[4]:
            st.markdown(f'<div class="box"><div class="lbl">Val. intrin.</div><b>{vi:,.0f}</b></div><div class="box"><div class="lbl">Prix cible</div><b>{prix_cible:,.0f}</b></div>', unsafe_allow_html=True)

        # Signal
        st.markdown(f"""<div class="card" style="border-left:5px solid {col_sig};margin-top:16px">
        <div class="lbl">Signal de rotation</div>
        <div style="font-family:'IBM Plex Mono';font-size:1.5em;color:{col_sig};font-weight:700;margin:6px 0">{sig}</div>
        <div class="lbl">Score <b style="color:#e6edf3">{score:.3f}</b> · Value <b style="color:#e6edf3">{v_score:.3f}</b> · Quality <b style="color:#e6edf3">{q_score:.3f}</b> · Momentum <b style="color:#e6edf3">{m_score:.3f}</b> · Upside <b style="color:#e6edf3">{upside:.1f}%</b></div>
        </div>""", unsafe_allow_html=True)

        # Ajouter au screener
        st.session_state.screener.append({
            "Titre": titre.upper(), "Secteur": secteur, "Bancaire": "✅" if est_banque else "—",
            "Période": f"{periode} {annee}", "Confiance": conf,
            "Cours auto": "✅" if "prix" in mdata else "—",
            "Prix": round(prix,0), "BPA": round(bpa,1), "PER": round(per,1),
            "P/B": round(pbr,2), "ROE%": round(roe,1),
            "ROA%": round(roa,1) if roa else "—", "D/CP": round(dette_cp,2) if dette_cp else "—",
            "Marge/PNB": f"{marge_b*100:.1f}%" if est_banque else "—",
            "Crd/Dep": f"{cd_ratio*100:.1f}%" if est_banque else "—",
            "RSI": round(rsi,1), "BB%": round(bb_pct,1), "vs EMA%": round(ecart_ema,1),
            "VI": round(vi,0), "Cible": round(prix_cible,0), "Upside%": round(upside,1),
            "Value": round(v_score,3), "Quality": round(q_score,3), "Momentum": round(m_score,3),
            "Score": round(score,3), "Signal": sig,
        })
        st.success(f"✅ {titre.upper()} enregistré.")


# ─────────────────────────────────────────────
# TAB 2 — TABLEAU DE BORD
# ─────────────────────────────────────────────
with tab2:
    if not st.session_state.screener:
        st.info("Aucun titre analysé. Commencez par l'onglet ➕.")
    else:
        df = pd.DataFrame(st.session_state.screener).sort_values("Score", ascending=False).reset_index(drop=True)

        m1,m2,m3,m4 = st.columns(4)
        m1.metric("Titres", len(df))
        m2.metric("Signaux ACHAT", len(df[df["Signal"].str.contains("ACHAT",na=False)]))
        m3.metric("Bloqués 🔴", len(df[df["Signal"].str.startswith("🔴",na=False)]))
        m4.metric("Cours auto ✅", len(df[df["Cours auto"]=="✅"]))

        def _cs(v):
            try:
                v = float(v)
                if v >= .60: return "background:#1b2d1b;color:#3fb950"
                if v >= .45: return "background:#2d2500;color:#e3b341"
                return "background:#2d1b1b;color:#f85149"
            except: return ""
        def _cu(v):
            try:
                v = float(v)
                if v >= 20: return "background:#1b2d1b;color:#3fb950"
                if v >= 5:  return "background:#2d2500;color:#e3b341"
                return "background:#2d1b1b;color:#f85149"
            except: return ""

        cols_show = ["Titre","Secteur","Cours auto","Prix","PER","P/B","ROE%","RSI","VI","Cible","Upside%","Score","Signal"]
        st.dataframe(df[cols_show].style.applymap(_cs,subset=["Score"]).applymap(_cu,subset=["Upside%"]),
                     use_container_width=True, height=400)

        st.markdown("---")
        for _, row in df.iterrows():
            sig  = row["Signal"]
            col  = COULEURS_SIGNAL.get(sig,"#8b949e")
            st.markdown(f"""<div class="card" style="border-left:4px solid {col}">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
            <div>
                <span style="font-family:'IBM Plex Mono';font-weight:700;font-size:1.05em">{row['Titre']}</span>
                <span class="lbl" style="margin-left:10px">{row['Secteur']}</span>
                <span class="lbl"> · {row['Période']}</span>
            </div>
            <div style="text-align:right">
                <span style="color:{col};font-weight:700;font-size:1.1em">{sig}</span><br>
                <span class="lbl">Score <b style="color:#e6edf3">{row['Score']}</b> · Upside <b style="color:#e6edf3">{row['Upside%']}%</b> · RSI <b style="color:#e6edf3">{row['RSI']}</b></span>
            </div>
            </div></div>""", unsafe_allow_html=True)

        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name="BRVM")
        st.download_button("⬇️ Export Excel", buf.getvalue(), "screener_brvm.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)


# ─────────────────────────────────────────────
# TAB 3 — FONDAMENTAUX SAUVEGARDÉS
# ─────────────────────────────────────────────
with tab3:
    fonds = list_fonds()
    if not fonds:
        st.info("Aucun fondamental sauvegardé.")
    else:
        st.markdown(f"**{len(fonds)} titre(s)** en base — pré-remplis automatiquement à la prochaine analyse.")
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


# ─────────────────────────────────────────────
# TAB 4 — MÉTHODE
# ─────────────────────────────────────────────
with tab4:
    st.markdown("""
### Architecture fetch v4.0

```
Sources (en cascade, stop au premier succès) :
  1. brvm.org/fr/cours-actions/0        — officiel BRVM, pas de bot-blocker
  2. brvm.org/fr/cours-actions/0/…/1    — page 2
  3. sikafinance.com/marches/aaz        — agrégateur
  4. sikafinance.com/valeur/BRVM/TICKER — fiche ticker

Parser unique :
  BS4 row-scanner → pd.read_html fallback
  Heuristique : ticker en colonne → premier float > 50 = prix
```

### Logique de scoring

```
[FILTRE 1] RSI > seuil      → 🔴 BLOQUÉ RSI
[FILTRE 2] Prix > BB sup    → 🔴 BLOQUÉ BB
[FILTRE 3] Prix > VI        → 🔴 SURÉVALUÉ
[FILTRE 4] Prix > Cible     → 🟡 HORS MARGE

Score = Value×w + Quality×w + Momentum×w
  Value    : PER, P/Book, rendement dividende
  Quality  : ROE, ROA, dette/CP (standard) | marge, crédits/dépôts (bancaire)
  Momentum : Δ BPA + variation 1 semaine
```

### Valeur intrinsèque
```
VI = Graham(40%) + Fair Value PER(35%) + DCF(25%)
Prix cible = VI × (1 − marge de sécurité)
```

### Installation
```bash
pip install streamlit pandas numpy requests beautifulsoup4 openpyxl lxml
```
""")

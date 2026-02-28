import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

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
    .card {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 10px; padding: 16px 20px; margin: 8px 0;
    }
    .card-green  { border-left: 4px solid #3fb950; }
    .card-blue   { border-left: 4px solid #79c0ff; }
    .card-yellow { border-left: 4px solid #d29922; }
    .card-red    { border-left: 4px solid #f85149; }
    .alert-red {
        background: #2d1b1b; border: 1px solid #f85149; border-radius: 8px;
        padding: 13px 17px; margin: 8px 0; color: #ffa198; font-weight: 600;
    }
    .alert-yellow {
        background: #2d2500; border: 1px solid #d29922; border-radius: 8px;
        padding: 13px 17px; margin: 8px 0; color: #e3b341; font-weight: 600;
    }
    .alert-green {
        background: #1b2d1b; border: 1px solid #3fb950; border-radius: 8px;
        padding: 13px 17px; margin: 8px 0; color: #7ee787; font-weight: 600;
    }
    .alert-estimated {
        background: #1a1f2e; border: 1px solid #79c0ff; border-radius: 8px;
        padding: 12px 16px; margin: 8px 0; color: #a5d6ff;
    }
    .ratio-box {
        background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
        padding: 10px 14px; margin: 4px 0;
        font-family: 'IBM Plex Mono', monospace; font-size: 0.88em;
    }
    .filter-block {
        background: #0d1117; border: 1px solid #30363d; border-radius: 8px;
        padding: 14px 18px; margin: 6px 0;
    }
    .label-small { color: #8b949e; font-size: 0.78em; }
    .stButton>button {
        background: #238636; color: white; border: none;
        border-radius: 6px; font-family: 'IBM Plex Mono', monospace; font-weight: 600;
        width: 100%; padding: 10px;
    }
    .stButton>button:hover { background: #2ea043; }
    .tooltip-text { color: #8b949e; font-size: 0.77em; font-style: italic; margin: -4px 0 6px 0; }
    .section-header {
        font-family: 'IBM Plex Mono', monospace; font-size: 0.8em;
        color: #8b949e; text-transform: uppercase; letter-spacing: 2px;
        border-bottom: 1px solid #30363d; padding-bottom: 6px; margin: 18px 0 10px 0;
    }
    .badge-estimated {
        display: inline-block; background: #1f3a5f; color: #79c0ff;
        border: 1px solid #79c0ff; border-radius: 10px;
        padding: 1px 8px; font-size: 0.72em; font-weight: 700;
        margin-left: 6px; vertical-align: middle;
    }
    .badge-annuel {
        display: inline-block; background: #1b2d1b; color: #3fb950;
        border: 1px solid #3fb950; border-radius: 10px;
        padding: 1px 8px; font-size: 0.72em; font-weight: 700;
        margin-left: 6px; vertical-align: middle;
    }
    /* Séparateur de section dans le formulaire */
    .form-divider {
        border: none; border-top: 1px solid #30363d; margin: 16px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SESSION STATE
# ==========================================================
if "actions"         not in st.session_state: st.session_state.actions = []
if "secteur_sel"     not in st.session_state: st.session_state.secteur_sel = "Télécommunications"
if "periode_sel"     not in st.session_state: st.session_state.periode_sel = "Annuel complet (2024 ou 2025)"
if "annee_sel"       not in st.session_state: st.session_state.annee_sel   = "2025"

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

# Taux d'actualisation DCF suggérés par secteur
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
    "Services Financiers":                  0.48,  # banques UEMOA légèrement back-loaded (provisions Q4)
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
    "marge_nette_cible":  0.20,  # RN / PNB : banque efficace > 20%
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
if st.sidebar.button("🗑️ Vider le screener"):
    st.session_state.actions = []
    st.rerun()

# ==========================================================
# HELPERS
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
    """DCF 2 phases + Graham Number."""
    g1 = min(max(croissance_bpa / 100, -0.10), 0.20)
    g2, r = 0.03, taux
    flux = sum(bpa * (1 + g1) ** t / (1 + r) ** t for t in range(1, 6))
    vt   = (bpa * (1 + g1) ** 5 * (1 + g2)) / (r - g2) / (1 + r) ** 5
    return flux + vt

# ==========================================================
# EN-TÊTE
# ==========================================================
st.title("⬡ Screener BRVM")
st.caption("Valeur intrinsèque (Graham) • Marge de sécurité • Filtres techniques • Rotation hebdomadaire - ABDOULAYE KONÉ")

tab1, tab2, tab3 = st.tabs(["➕ Analyser un titre", "📊 Tableau de bord", "📖 Méthodologie"])

# ==========================================================
# TAB 1 — FORMULAIRE INTERACTIF
# ==========================================================
with tab1:

    # ── SECTION 1 : Identification — HORS FORM pour réactivité ──
    st.markdown("<div class='section-header'>1 — Identification & Contexte</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        titre = st.text_input("Nom / Ticker", placeholder="ex: SONATEL, SGBCI…", key="titre_input")
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

    # Affichage contextuel réactif — s'actualise immédiatement
    est_banque  = (secteur == SECTEUR_BANCAIRE)
    per_cible   = PER_SECTORIELS[secteur]
    taux_suggere = TAUX_DCF_SECTEUR[secteur]

    info_cols = st.columns(4)
    with info_cols[0]:
        st.markdown(f"""
        <div class="filter-block">
        <div class="label-small">PER cible sectoriel</div>
        <b style="font-family:'IBM Plex Mono';font-size:1.2em">{per_cible:.2f}x</b>
        </div>""", unsafe_allow_html=True)
    with info_cols[1]:
        taux_color = "#79c0ff"
        st.markdown(f"""
        <div class="filter-block">
        <div class="label-small">Taux DCF suggéré</div>
        <b style="font-family:'IBM Plex Mono';font-size:1.2em;color:{taux_color}">{taux_suggere*100:.0f}%</b>
        </div>""", unsafe_allow_html=True)
    with info_cols[2]:
        if periode_donnees == "9 mois (T1+T2+T3)":
            msg, col = "Extrapolation × 4/3 — confiance élevée", "#3fb950"
        elif periode_donnees == "Semestriel (S1 — 6 mois)":
            saison = SAISONNALITE_S1[secteur]
            msg, col = f"Extrapolation ÷ {saison:.2f} — confiance modérée", "#d29922"
        else:
            msg, col = "Données complètes — aucune extrapolation", "#3fb950"
        st.markdown(f"""
        <div class="filter-block">
        <div class="label-small">Méthode données</div>
        <b style="font-size:0.85em;color:{col}">{msg}</b>
        </div>""", unsafe_allow_html=True)
    with info_cols[3]:
        badge_b = "🏦 Formulaire bancaire actif" if est_banque else "📋 Formulaire standard"
        col_b   = "#79c0ff" if est_banque else "#8b949e"
        st.markdown(f"""
        <div class="filter-block">
        <div class="label-small">Mode saisie</div>
        <b style="font-size:0.85em;color:{col_b}">{badge_b}</b>
        </div>""", unsafe_allow_html=True)

    st.markdown("<hr class='form-divider'>", unsafe_allow_html=True)

    # ── Bilan de référence pour données intermédiaires ────────
    if periode_donnees != "Annuel complet (2024 ou 2025)":
        annee_bilan_ref = str(int(annee_donnees) - 1) if annee_donnees != "2024" else "2024"
        if est_banque:
            msg_bilan = f"Crédits et dépôts : référez-vous au bilan {annee_bilan_ref}."
        else:
            msg_bilan = f"Capitaux propres, total actif, dettes : référez-vous au bilan {annee_bilan_ref}."
        st.markdown(f"""
        <div class="alert-estimated">
        📅 <b>Publication intermédiaire détectée</b> — {msg_bilan}
        Le résultat saisi sera extrapolé automatiquement.
        </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════
    # FORMULAIRE DE SAISIE (st.form pour les données chiffrées)
    # ══════════════════════════════════════════════════════════
    with st.form("saisie_titre", clear_on_submit=True):

        prix = st.number_input("💰 Prix actuel de l'action (FCFA)",
                               min_value=1.0, value=1000.0,
                               help="Cours du jour — brvm.org → Cotations")

        # ── SECTION 2 : Données financières ───────────────────
        if est_banque:
            # ─────────────────────────────────────────────────
            # FORMULAIRE BANCAIRE SIMPLIFIÉ
            # Données disponibles en pratique sur BRVM :
            #   Compte de résultat : PNB + Résultat net
            #   Bilan              : Encours crédits + Dépôts
            # ─────────────────────────────────────────────────
            st.markdown("<div class='section-header'>2 — Données bancaires</div>", unsafe_allow_html=True)

            st.markdown("""
            <div class="alert-estimated">
            🏦 <b>Secteur bancaire — saisie simplifiée</b><br>
            <span style="font-size:0.88em">
            Seules les données réellement disponibles dans les publications BRVM sont demandées.
            Le ratio Dette/CP classique est remplacé par des métriques UEMOA adaptées.
            </span>
            </div>""", unsafe_allow_html=True)

            label_rn = {
                "Annuel complet (2024 ou 2025)": "Résultat net annuel (millions FCFA)",
                "9 mois (T1+T2+T3)":            "Résultat net 9 mois (millions FCFA)",
                "Semestriel (S1 — 6 mois)":     "Résultat net S1 (millions FCFA)",
            }[periode_donnees]

            st.markdown("**📊 Compte de résultat**")
            st.markdown(f"<div class='tooltip-text'>📍 Rapport {annee_donnees} — {periode_donnees}</div>",
                        unsafe_allow_html=True)
            bc1, bc2 = st.columns(2)
            with bc1:
                pnb = st.number_input("PNB — Produit Net Bancaire (millions FCFA)",
                                      min_value=1.0, value=5000.0,
                                      help="Marge d'intérêts + commissions nettes. "
                                           "C'est le 'chiffre d'affaires' de la banque.\n"
                                           "Compte de résultat → Produit Net Bancaire.")
                st.markdown("<div class='tooltip-text'>📍 Compte de résultat → Produit Net Bancaire</div>",
                            unsafe_allow_html=True)
            with bc2:
                resultat_saisi_b = st.number_input(label_rn, value=800.0,
                                                   help="Bénéfice net de la période.\n"
                                                        "Compte de résultat → Résultat net.")
                st.markdown("<div class='tooltip-text'>📍 Compte de résultat → Résultat net</div>",
                            unsafe_allow_html=True)

            st.markdown("**🏦 Bilan**")
            if periode_donnees != "Annuel complet (2024 ou 2025)":
                st.markdown(f"<div class='tooltip-text'>📍 Bilan {annee_bilan_ref} (dernière année complète publiée)</div>",
                            unsafe_allow_html=True)
            bc3, bc4 = st.columns(2)
            with bc3:
                encours_credits = st.number_input("Encours crédits à la clientèle (millions FCFA)",
                                                  min_value=1.0, value=30000.0,
                                                  help="Total des crédits accordés aux clients.\n"
                                                       "Bilan → Créances sur la clientèle.")
                st.markdown("<div class='tooltip-text'>📍 Bilan → Créances sur la clientèle</div>",
                            unsafe_allow_html=True)
            with bc4:
                depots_clientele = st.number_input("Dépôts de la clientèle (millions FCFA)",
                                                   min_value=1.0, value=40000.0,
                                                   help="Total des dépôts (vue + terme + épargne).\n"
                                                        "Bilan → Dettes envers la clientèle.")
                st.markdown("<div class='tooltip-text'>📍 Bilan → Dettes envers la clientèle</div>",
                            unsafe_allow_html=True)

            # Données complémentaires communes
            st.markdown("**📌 Données complémentaires**")
            bx1, bx2, bx3 = st.columns(3)
            with bx1:
                nombre_actions_b = st.number_input("Nombre d'actions (millions)",
                                                   min_value=0.001, value=10.0)
            with bx2:
                capitaux_propres_b = st.number_input("Capitaux propres (millions FCFA)",
                                                     min_value=1.0, value=8000.0,
                                                     help="Bilan → Capitaux propres. Nécessaire pour le P/B et le ROE.")
                st.markdown("<div class='tooltip-text'>📍 Bilan → Capitaux propres</div>",
                            unsafe_allow_html=True)
            with bx3:
                dividende_b  = st.number_input("Dividende par action (FCFA)", min_value=0.0, value=0.0)
                bpa_prec_b   = st.number_input("BPA année précédente (FCFA)", value=80.0)

        else:
            # ─────────────────────────────────────────────────
            # FORMULAIRE STANDARD (non-bancaire)
            # ─────────────────────────────────────────────────
            st.markdown("<div class='section-header'>2A — Compte de résultat</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='tooltip-text'>📍 Rapport {annee_donnees} — {periode_donnees}</div>",
                        unsafe_allow_html=True)

            label_rn_std = {
                "Annuel complet (2024 ou 2025)": "Résultat net annuel (millions FCFA)",
                "9 mois (T1+T2+T3)":            "Résultat net 9 mois (millions FCFA)",
                "Semestriel (S1 — 6 mois)":     "Résultat net S1 (millions FCFA)",
            }[periode_donnees]

            s1, s2, s3 = st.columns(3)
            with s1:
                resultat_saisi = st.number_input(label_rn_std, value=500.0,
                                                 help="Compte de résultat → Résultat net.")
                nombre_actions = st.number_input("Nombre d'actions (millions)", min_value=0.001, value=10.0)
            with s2:
                dividende    = st.number_input("Dividende par action (FCFA)", min_value=0.0, value=0.0)
                bpa_prec     = st.number_input("BPA année précédente (FCFA)", value=80.0)
            with s3:
                if not mode_simple:
                    stabilite_bpa = st.selectbox("Régularité bénéfices (3-5 ans)",
                                                 ["Stable", "Volatil", "Exceptionnel"])
                else:
                    stabilite_bpa = "Stable"

            if periode_donnees != "Annuel complet (2024 ou 2025)":
                annee_bilan_ref = str(int(annee_donnees) - 1) if annee_donnees != "2024" else "2024"
                source_bilan = f"Bilan {annee_bilan_ref}"
            else:
                source_bilan = f"Bilan {annee_donnees}"

            st.markdown(f"<div class='section-header'>2B — Bilan ({source_bilan})</div>",
                        unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                capitaux_propres = st.number_input("Capitaux propres (millions FCFA)",
                                                   min_value=1.0, value=2000.0)
            with b2:
                total_actif = st.number_input("Total actif (millions FCFA)",
                                              min_value=1.0, value=5000.0)
            with b3:
                dettes_totales = st.number_input("Dettes financières (millions FCFA)",
                                                 min_value=0.0, value=1000.0,
                                                 help="Emprunts + dettes bancaires. "
                                                      "Vérifiez si un emprunt majeur est intervenu depuis.")

        # ── SECTION 3 : Indicateurs techniques ────────────────
        st.markdown("<div class='section-header'>3 — Indicateurs techniques</div>", unsafe_allow_html=True)
        st.markdown("""<div class='tooltip-text'>
        📍 TradingView → chercher le ticker BRVM → ajouter BB (20,2), EMA (20), RSI (14)
        </div>""", unsafe_allow_html=True)

        t1, t2, t3, t4 = st.columns(4)
        with t1:
            st.markdown("**📈 Bollinger Bands (20,2)**")
            bb_sup = st.number_input("BB supérieure (FCFA)", min_value=1.0, value=1100.0)
            bb_inf = st.number_input("BB inférieure (FCFA)", min_value=1.0, value=900.0)
        with t2:
            st.markdown("**📊 EMA 20**")
            ema20    = st.number_input("EMA20 (FCFA)", min_value=1.0, value=980.0)
            var_1s   = st.number_input("Variation 1 semaine (%)", min_value=-30.0, max_value=30.0, value=0.0)
        with t3:
            st.markdown("**🌡️ RSI (14)**")
            rsi = st.number_input("RSI", min_value=0.0, max_value=100.0, value=50.0)
            st.markdown(f"""
            <div class="filter-block">
            <div class="label-small">Seuils actifs</div>
            Surachat : <b style="color:#f85149">> {RSI_SURACHAT}</b><br>
            Survente  : <b style="color:#3fb950">< {RSI_SURVENTE}</b>
            </div>""", unsafe_allow_html=True)
        with t4:
            st.markdown(f"""
            <div class="filter-block" style="margin-top:28px">
            <div class="label-small">Marge de sécurité</div>
            <b style="font-size:1.3em;font-family:'IBM Plex Mono'">{MARGE_SECURITE*100:.0f}%</b>
            </div>
            <div class="filter-block">
            <div class="label-small">Taux DCF utilisé</div>
            <b style="font-size:1.3em;font-family:'IBM Plex Mono'">{TAUX_ACTUA*100:.0f}%</b>
            </div>""", unsafe_allow_html=True)

        submitted = st.form_submit_button("🔍 Analyser ce titre", use_container_width=True)

    # ==========================================================
    # CALCULS
    # ==========================================================
    if submitted and titre:

        if any(a["Titre"] == titre for a in st.session_state.actions):
            st.error(f"⚠️ '{titre}' est déjà dans le screener.")
            st.stop()

        per_cible_score = PER_CAP_SCORE[secteur]

        # ── Extrapolation & ratios de base ─────────────────────
        if est_banque:
            resultat_annuel, methode_extrapol, confiance = extrapoler_annuel(
                resultat_saisi_b, periode_donnees, secteur)
            nombre_actions = nombre_actions_b
            capitaux_propres = capitaux_propres_b
            dividende        = dividende_b
            bpa_prec         = bpa_prec_b
            stabilite_bpa    = "Stable"
            total_actif      = encours_credits + depots_clientele   # approximation bilan bancaire
        else:
            resultat_annuel, methode_extrapol, confiance = extrapoler_annuel(
                resultat_saisi, periode_donnees, secteur)

        donnees_estimees = confiance != "Annuelle"
        bpa          = resultat_annuel / nombre_actions
        valeur_book  = capitaux_propres / nombre_actions
        per          = prix / bpa if bpa > 0 else 99
        pbr          = prix / valeur_book if valeur_book > 0 else 99
        div_yield    = dividende / prix if prix > 0 else 0
        croissance_bpa = ((bpa - bpa_prec) / abs(bpa_prec) * 100 if bpa_prec != 0 else 0)

        # ── Valeur intrinsèque (Graham — universel) ────────────
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

        # ── Scores ─────────────────────────────────────────────
        score_per = np.clip(per_cible_score / per, 0, 1) if per > 0 else 0
        score_pbr = np.clip(1.5 / pbr, 0, 1)
        score_dy  = np.clip(div_yield / 0.08, 0, 1)
        value_score = score_per * 0.40 + score_pbr * 0.35 + score_dy * 0.25

        if est_banque:
            b = BENCH_BANQUE
            roe = (resultat_annuel / capitaux_propres) * 100

            # Marge nette bancaire = RN / PNB
            marge_nette_b  = resultat_annuel / pnb if pnb > 0 else 0
            score_marge    = np.clip(marge_nette_b / b["marge_nette_cible"], 0, 1)

            # Ratio crédits/dépôts
            credits_depots = encours_credits / depots_clientele if depots_clientele > 0 else 0
            ecart_opt      = abs(credits_depots - b["credits_depots_opt"])
            score_cd       = np.clip(1 - ecart_opt / 0.40, 0, 1)

            # ROE bancaire
            score_roe_b = np.clip(roe / (b["roe_cible"] * 100), 0, 1)

            # Quality score bancaire
            # Marge nette PNB (45%) + Crédits/Dépôts (30%) + ROE (25%)
            quality_score = score_marge * 0.45 + score_cd * 0.30 + score_roe_b * 0.25

            # Pour affichage
            dette_cp      = None
            roa           = None
            coeff_exploit = None
            cout_risque   = None

        else:
            roe       = (resultat_annuel / capitaux_propres) * 100
            roa       = (resultat_annuel / total_actif) * 100
            dette_cp  = dettes_totales / capitaux_propres
            bonus_stab = {"Stable": 0.20, "Volatil": 0.0, "Exceptionnel": 0.30}[stabilite_bpa]
            quality_score = (
                np.clip(roe / 25, 0, 1)      * 0.35 +
                np.clip(roa / 12, 0, 1)      * 0.30 +
                np.clip(1 - dette_cp / 3, 0, 1) * 0.25 +
                bonus_stab                   * 0.10
            )
            marge_nette_b = credits_depots = coeff_exploit = cout_risque = None

        mom_fond  = np.clip(croissance_bpa / 30, -1, 1)
        mom_prix  = np.clip(var_1s / 10, -1, 1)
        momentum_score = mom_fond * 0.60 + mom_prix * 0.40
        score_final = W_VALUE * value_score + W_QUALITY * quality_score + W_MOMENTUM * momentum_score

        # ── Technique ──────────────────────────────────────────
        filtre_rsi    = rsi > RSI_SURACHAT
        filtre_bb_sup = prix > bb_sup
        bb_pct        = ((prix - bb_inf) / (bb_sup - bb_inf) * 100) if (bb_sup - bb_inf) > 0 else 50
        ecart_ma      = (prix / ema20 - 1) * 100
        rsi_survente  = rsi < RSI_SURVENTE

        signal = get_signal(score_final, upside, survalue, sous_marge,
                            filtre_rsi, filtre_bb_sup, var_1s)

        # ══════════════════════════════════════════════════════
        # AFFICHAGE RÉSULTAT
        # ══════════════════════════════════════════════════════
        st.markdown("---")
        badge_b_html = " <span style='background:#1f3a5f;color:#79c0ff;border:1px solid #79c0ff;border-radius:10px;padding:1px 8px;font-size:0.72em;font-weight:700'>🏦 BANCAIRE</span>" if est_banque else ""
        st.markdown(f"### {titre} {badge_donnees(confiance)}{badge_b_html}", unsafe_allow_html=True)

        if donnees_estimees:
            st.markdown(f"""
            <div class="alert-estimated">
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
            🔒 Titre surévalué — Prix ({prix:,.0f}) > Valeur intrinsèque ({vi:,.0f} FCFA).
            Marge de sécurité négative. Aucun achat.</div>""", unsafe_allow_html=True)
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

        # Ratios calculés
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
                <div class="label-small">Marge nette / PNB {'(estimée)' if donnees_estimees else ''}</div>
                <b style="color:{mn_c}">{marge_nette_b*100:.1f}%</b>
                <span class="label-small"> cible: {BENCH_BANQUE['marge_nette_cible']*100:.0f}%</span></div>
                <div class="ratio-box">
                <div class="label-small">ROE bancaire {'(estimé)' if donnees_estimees else ''}</div>
                <b>{roe:.1f}%</b>
                <span class="label-small"> cible: {BENCH_BANQUE['roe_cible']*100:.0f}%</span></div>""",
                unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="ratio-box">
                <div class="label-small">ROE {'(estimé)' if donnees_estimees else ''}</div>
                <b>{roe:.1f}%</b></div>
                <div class="ratio-box">
                <div class="label-small">ROA {'(estimé)' if donnees_estimees else ''}</div>
                <b>{roa:.1f}%</b></div>""", unsafe_allow_html=True)
        with r4:
            if est_banque:
                b = BENCH_BANQUE
                cd_c = "#f85149" if credits_depots > b["credits_depots_max"] or credits_depots < b["credits_depots_min"] else ("#d29922" if abs(credits_depots - b["credits_depots_opt"]) > 0.15 else "#3fb950")
                st.markdown(f"""<div class="ratio-box">
                <div class="label-small">Crédits / Dépôts</div>
                <b style="color:{cd_c}">{credits_depots*100:.1f}%</b>
                <span class="label-small"> optimal: 70-90%</span></div>
                <div class="ratio-box">
                <div class="label-small">Δ BPA</div><b>{croissance_bpa:+.1f}%</b></div>""",
                unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="ratio-box">
                <div class="label-small">Dette/CP</div><b>{dette_cp:.2f}x</b></div>
                <div class="ratio-box">
                <div class="label-small">Δ BPA</div><b>{croissance_bpa:+.1f}%</b></div>""",
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
        st.markdown(f"""
        <div class="card" style="border-left:5px solid {couleur_sig};margin-top:16px">
        <div class="label-small">Signal de rotation — semaine en cours{badge_est}</div>
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

        # Enregistrement
        st.session_state.actions.append({
            "Titre":              titre,
            "Secteur":            secteur,
            "🏦 Bancaire":        "✅" if est_banque else "—",
            "Période":            f"{periode_donnees} {annee_donnees}",
            "Confiance":          confiance,
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
        st.success(f"✅ **{titre}** enregistré.")

# ==========================================================
# TAB 2 — TABLEAU DE BORD
# ==========================================================
with tab2:
    if not st.session_state.actions:
        st.info("Aucun titre analysé. Commencez par l'onglet **➕ Analyser un titre**.")
    else:
        df = pd.DataFrame(st.session_state.actions)
        df = df.sort_values("Score Final", ascending=False).reset_index(drop=True)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Titres analysés",   len(df))
        k2.metric("Signaux ACHAT",     len(df[df["Signal"].str.contains("ACHAT", na=False)]))
        k3.metric("Titres bloqués 🔴", len(df[df["Signal"].str.startswith("🔴", na=False)]))
        k4.metric("Données estimées ⚠️", len(df[df["Confiance"] != "Annuelle"]))

        st.markdown("---")
        cols = ["Titre", "Secteur", "🏦 Bancaire", "Période", "Confiance",
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
            badge_bb  = " <span style='background:#f85149;color:white;padding:1px 6px;border-radius:8px;font-size:0.72em'>BB</span>"  if row["Filtre BB"] == "🔴 Bloqué" else ""
            badge_g   = " <span style='background:#d29922;color:white;padding:1px 6px;border-radius:8px;font-size:0.72em'>GRAHAM</span>" if row["Graham"] != "✅ OK" else ""
            badge_est = " <span style='background:#1f3a5f;color:#79c0ff;border:1px solid #79c0ff;padding:1px 6px;border-radius:8px;font-size:0.72em'>ESTIMÉ</span>" if row["Confiance"] != "Annuelle" else ""
            badge_bq  = " <span style='background:#1f3a5f;color:#79c0ff;border:1px solid #79c0ff;padding:1px 6px;border-radius:8px;font-size:0.72em'>🏦</span>" if row["🏦 Bancaire"] == "✅" else ""

            st.markdown(f"""
            <div class="card" style="border-left:4px solid {couleur}">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                <div>
                    <span style="font-family:'IBM Plex Mono';font-weight:700;color:#e6edf3;font-size:1.05em">{row['Titre']}</span>
                    {badge_rsi}{badge_bb}{badge_g}{badge_est}{badge_bq}
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
# TAB 3 — MÉTHODOLOGIE
# ==========================================================
with tab3:
    st.subheader("📖 Méthodologie")
    st.markdown("""
    ### Logique globale du modèle

    ```
    [FILTRE 1] RSI > seuil surachat     → 🔴 BLOQUÉ
    [FILTRE 2] Prix > BB supérieure     → 🔴 BLOQUÉ
    [FILTRE 3] Prix > Valeur intrinsèque → 🔴 HORS MARGE
    [FILTRE 4] Prix > Prix cible (marge) → 🟡 SURVEILLER
    [SCORE]    Value + Quality + Momentum → Signal final
    ```

    ---
    ### Score Quality — différence bancaire / standard

    | Critère | Standard | Bancaire |
    |---|---|---|
    | Rentabilité | ROE (35%) | ROE (25%) |
    | Efficacité actif | ROA (30%) | Marge nette/PNB (45%) |
    | Levier / Structure | Dette/CP (25%) | Crédits/Dépôts (30%) |
    | Stabilité | Bonus stabilité (10%) | — |

    **Pourquoi la marge nette/PNB plutôt que le coefficient d'exploitation pour les banques BRVM ?**
    Le coefficient d'exploitation (Charges/PNB) nécessite les charges générales qui ne sont pas
    toujours publiées dans les rapports intermédiaires BRVM. La marge nette (RN/PNB) est
    calculable avec uniquement PNB et Résultat net — les deux données systématiquement disponibles.

    ---
    ### Taux DCF par secteur

    | Secteur | Taux suggéré | Justification |
    |---|---|---|
    | Télécommunications | 11% | Flux stables, visibilité élevée |
    | Services Financiers | 11% | Modèle régulé, risque modéré |
    | Services Publics | 11% | Revenus contractuels |
    | Consommation de base | 12% | Demande stable mais marché |
    | Énergie | 13% | Cyclicité des matières premières |
    | Consommation discrétionnaire | 13% | Sensibilité au cycle économique |
    | Industriels | 14% | Cyclicité élevée, carnet de commandes |

    Base : Taux sans risque UEMOA (~5.5%) + prime de risque BRVM (~6-8%)

    ---
    ### Extrapolation des données intermédiaires

    **9 mois :** Résultat annuel = 9M × 4/3 — confiance élevée (75% de l'exercice connu)

    **Semestriel :** Résultat annuel = S1 ÷ facteur saisonnalité sectoriel
    Les banques UEMOA ont un facteur S1 = 0.48 (légèrement back-loaded : les provisions
    de fin d'année sont typiquement plus élevées au S2).
    """)
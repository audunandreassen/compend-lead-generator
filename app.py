import streamlit as st
import streamlit.components.v1 as components
from streamlit_searchbox import st_searchbox
import requests
import pandas as pd
import html
from duckduckgo_search import DDGS
from openai import OpenAI
from io import BytesIO
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone

# Konfigurasjon
brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"
klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
modell_navn = "gpt-4o-mini"

NETTSIDE_KILDE_ETIKETTER = {
    "brreg": "Brreg",
    "fallback": "Automatisk funnet",
    "invalid": "Ugyldig",
    "missing": "Ikke funnet",
    "unknown": "Ukjent",
}

BHT_PLIKTIGE_SN2007_KODER = {
    "02", "03.2", "03.3", "05", "07", "08", "09.9", "10", "11", "12", "13", "14", "15", "16", "17", "18.1", "19", "20", "21", "22", "23", "24", "25", "26.1", "26.2", "26.3", "26.4", "26.51", "26.6", "26.7", "27", "28", "29", "30", "31", "32.3", "32.4", "32.5", "32.990", "33", "35.1", "35.21", "35.22", "35.23", "35.3", "35.4", "36", "37", "38", "39", "41", "42", "43.1", "43.2", "43.3", "43.4", "43.5", "43.9", "46.87", "49", "52.21", "52.22", "52.23", "52.24", "53.1", "53.2", "55.1", "56.11", "56.22", "56.3", "61", "75", "77.1", "80.01", "80.09", "81.2", "84.23", "84.24", "84.25", "85.1", "85.2", "85.3", "85.4", "85.5", "85.69", "86.1", "86.2", "86.91", "86.92", "86.93", "86.94", "86.95", "86.96", "86.99", "87.1", "87.2", "87.3", "87.99", "88", "91.3", "95.23", "95.24", "95.29", "95.31", "95.32", "96.1", "96.21", "96.91",
}

# --- HJELPEFUNKSJONER ---

def normaliser_naeringskode(naeringskode):
    if not naeringskode: return ""
    return "".join(ch for ch in str(naeringskode).strip() if ch.isdigit() or ch == ".")

def er_underlagt_bht(naeringskode):
    kode = normaliser_naeringskode(naeringskode)
    if not kode: return False
    for bht_kode in BHT_PLIKTIGE_SN2007_KODER:
        if kode == bht_kode or kode.startswith(f"{bht_kode}."): return True
    return False

def bht_svar_for_firma(firma):
    kode = (firma or {}).get("naeringskode1", {}).get("kode")
    return "Ja" if er_underlagt_bht(kode) else "Nei"

def begrens_score(verdi, minimum=0, maksimum=100):
    return max(minimum, min(maksimum, int(round(verdi))))

def beregn_alder_aar(stiftelsesdato):
    if not stiftelsesdato: return None
    dato_tekst = str(stiftelsesdato).replace("Z", "+00:00")
    try:
        stiftet = datetime.fromisoformat(dato_tekst)
    except ValueError: return None
    if stiftet.tzinfo is None: stiftet = stiftet.replace(tzinfo=timezone.utc)
    alder = (datetime.now(timezone.utc) - stiftet).days / 365.25
    return max(0.0, alder)

def tell_kontaktpunkter(kontaktinfo, eposter=None):
    eposter = eposter or []
    return min(5, len([ep for ep in eposter if ep]) + (1 if kontaktinfo.get("epost") else 0) + (1 if kontaktinfo.get("telefon") else 0) + (1 if kontaktinfo.get("mobil") else 0))

def hent_datakvalitet_label(score):
    if score >= 75: return {"tekst": "God datakvalitet", "css_klasse": "datakvalitet-label datakvalitet-label--god"}
    if score >= 50: return {"tekst": "OK datakvalitet", "css_klasse": "datakvalitet-label datakvalitet-label--ok"}
    return {"tekst": "Dårlig datakvalitet", "css_klasse": "datakvalitet-label datakvalitet-label--lav"}

# --- SCORE LOGIKK ---

def kalkuler_total_health(passform, intent, kvalitet):
    # Vekting: Passform (40%), Intent (40%), Datakvalitet (20%)
    return begrens_score((passform * 0.4) + (intent * 0.4) + (kvalitet * 0.2))

# --- DESIGN OG STYLING ---
def bruk_stil():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #003642; background-color: #f7f9fb; }
        .stApp { background-color: #f7f9fb; }
        .block-container { padding-top: 2rem; max-width: 960px; }
        .stButton>button { background-color: #368373; color: white; border-radius: 8px; border: none; padding: 10px 24px; transition: all 0.2s ease; font-weight: 500; font-size: 0.9rem; letter-spacing: 0.01em; }
        .stButton>button:hover { background-color: #2a6a5c; color: white; border: none; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(54, 131, 115, 0.3); }
        .stTextInput>div>div>input { background-color: #FFFFFF !important; border-radius: 8px; border: 1.5px solid #d0dde3; padding: 12px 20px; color: #003642; font-size: 0.95rem; }
        .stAlert { background-color: #ffffff !important; border: 1px solid #d0dde3 !important; border-left: 4px solid #368373 !important; color: #003642; border-radius: 8px; padding: 1rem 1.5rem; line-height: 1.6; }
        h1, h2, h3 { color: #003642; font-weight: 700; }
        div[data-testid="stVerticalBlockBorderWrapper"] { background: #ffffff; border-radius: 12px !important; border: 1px solid #e0e7ec !important; box-shadow: 0 1px 3px rgba(0, 54, 66, 0.06); position: relative; }
        
        /* Health Score Badge */
        .health-score-badge { position: absolute; top: 15px; right: 15px; background: #003642; color: #ffffff; padding: 4px 12px; border-radius: 6px; font-weight: 700; font-size: 0.85rem; z-index: 10; }
        
        .firma-badge { display: inline-block; background: #eef6f4; color: #368373; padding: 3px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 500; margin-bottom: 1rem; }
        .firma-detaljer { display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem 2rem; margin-top: 1rem; }
        .firma-detaljer .detalj { font-size: 0.88rem; color: #4a6a72; }
        .firma-detaljer .detalj strong { color: #003642; font-weight: 600; }
        .analyse-kort { background: linear-gradient(135deg, #003642 0%, #0a4f5c 100%); border-radius: 12px; padding: 1.5rem 1.8rem; color: #ffffff; margin: 1rem 0; line-height: 1.7; font-size: 0.92rem; }
        .analyse-kort .analyse-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: rgba(255,255,255,0.6); margin-bottom: 0.5rem; font-weight: 600; }
        .lead-navn { font-weight: 600; color: #003642; font-size: 0.92rem; }
        .lead-ansatte { display: inline-block; background: #eef6f4; color: #368373; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 500; margin-left: 8px; }
        .datakvalitet-label { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; margin-left: 8px; }
        .datakvalitet-label--lav { background: #fdecec; color: #b42318; }
        .datakvalitet-label--ok { background: #fff6e5; color: #b54708; }
        .datakvalitet-label--god { background: #ecfdf3; color: #027a48; }
        .score-kort { margin-top: 0.6rem; border: 1px solid #e0e7ec; border-radius: 8px; padding: 0.6rem 0.75rem; background: #ffffff; min-height: 150px; }
        .score-kort .score-title { font-size: 0.72rem; text-transform: uppercase; color: #6b8a93; font-weight: 600; }
        .score-kort .score-value { font-size: 1.1rem; font-weight: 700; color: #003642; margin-bottom: 0.3rem; }
        .score-kort ul { margin: 0; padding-left: 1.1rem; color: #37535b; font-size: 0.75rem; line-height: 1.4; }
        .app-header { text-align: center; padding: 1rem 0 2rem 0; }
        .seksjon-header { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; color: #6b8a93; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.8rem; }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# --- APP START ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

st.markdown('<div id="compend-top"></div><div class="app-header"><h1>Compend Insights</h1><p>Strategisk leadsgenerator for kurs og kompetanse</p></div>', unsafe_allow_html=True)

# Init session state
for key in ["mine_leads", "hoved_firma", "soke_felt", "forrige_sok", "isbryter", "eposter", "vis_vent_modal", "scroll_topp"]:
    if key not in st.session_state: st.session_state[key] = "" if "felt" in key or "sok" in key else [] if "leads" in key or "eposter" in key else None if "firma" in key or "isbryter" in key else False

# --- UTFYRENDE LOGIKK (BEHOLDES FRA DIN KODE) ---

def utfor_analyse(orgnr):
    hoved = hent_firma_data(orgnr)
    if hoved:
        hoved = berik_firma_med_kontaktinfo(hoved)
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        firmanavn = hoved.get("navn", "Ukjent")
        
        # Nyhetshenting og isbryter
        nyheter = finn_nyheter(firmanavn)
        st.session_state.isbryter = lag_isbryter(firmanavn, nyheter, hoved.get("naeringskode1", {}).get("beskrivelse", "Ukjent"), bht_svar_for_firma(hoved))
        st.session_state.eposter = finn_eposter(hoved.get("hjemmeside"), "brreg")
        
        # Hent leads
        kode = hoved.get("naeringskode1", {}).get("kode")
        if kode:
            res = requests.get(brreg_adresse, params={"naeringskode": kode, "size": 15, "sort": "antallAnsatte,desc"}).json()
            leads = res.get("_embedded", {}).get("enheter", [])
            st.session_state.mine_leads = [berik_firma_med_kontaktinfo(l) for l in leads if l["organisasjonsnummer"] != orgnr]
    else:
        st.error("Ugyldig organisasjonsnummer.")

# --- SØKEFELT ---
col_l, col_m, col_r = st.columns([1, 3, 1])
with col_m:
    valgt = st_searchbox(sok_brreg, placeholder="Søk på navn eller orgnr...", key="brreg_sok")

if valgt and valgt != st.session_state.forrige_sok:
    with st.spinner("Genererer analyse..."):
        utfor_analyse(valgt)
    st.rerun()

# --- VISNING ---
if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    h_score = bygg_hovedscore(f, st.session_state.mine_leads)
    total_health = kalkuler_total_health(h_score['passformscore'], h_score['intentscore'], h_score['datakvalitet'])
    
    with st.container(border=True):
        st.markdown(f'<div class="health-score-badge">Health Score: {total_health}%</div>', unsafe_allow_html=True)
        st.markdown(f'<h3>{f.get("navn")}</h3><span class="firma-badge">{bransje}</span>', unsafe_allow_html=True)
        
        # Detaljer (samme som før)
        st.markdown(f'<div class="firma-detaljer"><div class="detalj"><strong>Org.nr</strong> {f.get("organisasjonsnummer")}</div><div class="detalj"><strong>Ansatte</strong> {f.get("antallAnsatte", "Ukjent")}</div><div class="detalj"><strong>Adresse</strong> {formater_adresse(f)}</div><div class="detalj"><strong>BHT-plikt</strong> {bht_svar_for_firma(f)}</div></div>', unsafe_allow_html=True)

        # AI Analyse
        if st.session_state.isbryter:
            st.markdown(f'<div class="analyse-kort"><div class="analyse-label">Strategisk Rådgivning</div>{st.session_state.isbryter}</div>', unsafe_allow_html=True)

        # Scorecards
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="score-kort"><div class="score-title">Salgsmatch</div><div class="score-value">{h_score["passformscore"]}/100</div><ul><li>{"</li><li>".join(h_score["passform_grunner"][:3])}</li></ul></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="score-kort"><div class="score-title">Temperatur</div><div class="score-value">{h_score["intentscore"]}/100</div><ul><li>{"</li><li>".join(h_score["intent_grunner"][:3])}</li></ul></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="score-kort"><div class="score-title">Datakvalitet</div><div class="score-value">{h_score["datakvalitet"]}/100</div><ul><li>{"</li><li>".join(h_score["datakvalitet_grunner"][:3])}</li></ul></div>', unsafe_allow_html=True)

        if st.button("Send til HubSpot", use_container_width=True):
            st.success("Lead overført!")

    # Lignende aktører
    if st.session_state.mine_leads:
        st.markdown('<div class="seksjon-header">Anbefalte Leads i samme bransje</div>', unsafe_allow_html=True)
        for i, lead in enumerate(st.session_state.mine_leads[:10]):
            l_score = bygg_leadscore(lead, f)
            l_health = kalkuler_total_health(l_score['passformscore'], l_score['intentscore'], l_score['datakvalitet'])
            
            with st.container(border=True):
                st.markdown(f'<div class="health-score-badge">Health: {l_health}%</div>', unsafe_allow_html=True)
                st.markdown(f'<span class="lead-navn">{lead["navn"]}</span><span class="lead-ansatte">{lead.get("antallAnsatte", 0)} ansatte</span>', unsafe_allow_html=True)
                
                lc1, lc2, lc3 = st.columns(3)
                with lc1:
                    st.markdown(f'<div class="score-kort"><div class="score-title">Match</div><div class="score-value">{l_score["passformscore"]}%</div><ul><li>{l_score["passform_grunner"][0]}</li></ul></div>', unsafe_allow_html=True)
                with lc2:
                    st.markdown(f'<div class="score-kort"><div class="score-title">Temperatur</div><div class="score-value">{l_score["intentscore"]}%</div><ul><li>{l_score["intent_grunner"][0]}</li></ul></div>', unsafe_allow_html=True)
                with lc3:
                    if st.button("Analyser", key=f"an_{i}", use_container_width=True):
                        st.session_state.auto_analyse_orgnr = lead["organisasjonsnummer"]
                        st.rerun()

# --- HJELPEFUNKSJONER FOR DATA HENTES FRA DIN KODE ---
# (Her limer du inn de gjenværende datafunksjonene dine som sok_brreg, hent_firma_data, etc.)

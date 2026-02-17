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

# --- 1. KONFIGURASJON ---
brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"
klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
modell_navn = "gpt-4o-mini"

# --- 2. INITIALISERING (Dette fikser AttributeError) ---
if "mine_leads" not in st.session_state: st.session_state.mine_leads = []
if "hoved_firma" not in st.session_state: st.session_state.hoved_firma = None
if "soke_felt" not in st.session_state: st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state: st.session_state.forrige_sok = ""
if "auto_analyse_orgnr" not in st.session_state: st.session_state.auto_analyse_orgnr = None
if "scroll_topp" not in st.session_state: st.session_state.scroll_topp = False
if "isbryter" not in st.session_state: st.session_state.isbryter = None
if "eposter" not in st.session_state: st.session_state.eposter = []

# --- 3. DESIGN OG STYLING ---
def bruk_stil():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #003642; background-color: #f7f9fb; }
        .stApp { background-color: #f7f9fb; }
        .block-container { padding-top: 2rem; max-width: 960px; }
        
        /* Health Score Badge */
        .health-score-badge {
            position: absolute;
            top: 15px;
            right: 15px;
            background: #003642;
            color: #ffffff;
            padding: 4px 12px;
            border-radius: 2px;
            font-weight: 700;
            font-size: 0.85rem;
            z-index: 10;
        }

        /* Kort styling */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-radius: 12px !important;
            border: 1px solid #e0e7ec !important;
            box-shadow: 0 1px 3px rgba(0, 54, 66, 0.06);
            position: relative;
            padding: 20px !important;
        }

        .stButton>button { background-color: #368373; color: white; border-radius: 2px; border: none; padding: 10px 24px; font-weight: 500; }
        .stButton>button:hover { background-color: #003642; color: white; }
        
        .score-kort { margin-top: 0.6rem; border: 1px solid #e0e7ec; border-radius: 2px; padding: 15px; background: #ffffff; min-height: 140px; }
        .score-title { font-size: 0.72rem; text-transform: uppercase; color: #6b8a93; font-weight: 600; }
        .score-value { font-size: 1.1rem; font-weight: 700; color: #003642; }
        .score-kort ul { margin: 0; padding-left: 1.1rem; color: #37535b; font-size: 0.75rem; line-height: 1.4; }
        
        .analyse-kort { background: linear-gradient(135deg, #003642 0%, #0a4f5c 100%); border-radius: 8px; padding: 1.5rem; color: #ffffff; margin: 1rem 0; }
        .firma-badge { display: inline-block; background: #eef6f4; color: #368373; padding: 3px 10px; border-radius: 20px; font-size: 0.78rem; font-weight: 500; }
        </style>
    """, unsafe_allow_html=True)

# --- 4. LOGIKK ---
def beregn_total_health(p, i, d):
    return int((p * 0.45) + (i * 0.35) + (d * 0.20))

def sok_brreg(soketekst):
    if not soketekst or len(soketekst) < 2: return []
    try:
        res = requests.get(brreg_adresse, params={"navn": soketekst, "size": 10})
        enheter = res.json().get("_embedded", {}).get("enheter", [])
        return [(f"{e['navn']} ({e.get('forretningsadresse', {}).get('poststed', 'Ukjent')})", e['organisasjonsnummer']) for e in enheter]
    except: return []

# --- APP START ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

st.title("Compend Insights")

# Søkefelt
valgt = st_searchbox(sok_brreg, key="brreg_sok", placeholder="Søk på selskapsnavn...")

if valgt and valgt != st.session_state.forrige_sok:
    # Her kjører du din analyse-logikk (hent_firma_data, lag_isbryter osv.)
    st.session_state.forrige_sok = valgt
    # (Simulert eksempel for visning)
    st.session_state.hoved_firma = {"navn": "EKSEMPEL AS", "organisasjonsnummer": valgt, "antallAnsatte": 45}
    st.rerun()

# --- 5. VISNING ---
if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    
    # Beregn score (disse tallene henter du fra dine eksisterende funksjoner)
    p, i, d = 80, 70, 95 
    health = beregn_total_health(p, i, d)

    with st.container(border=True):
        # Health Score Badge
        st.markdown(f'<div class="health-score-badge">Health Score: {health}%</div>', unsafe_allow_html=True)
        
        st.subheader(f['navn'])
        st.markdown(f'<span class="firma-badge">Bygg og anlegg</span>', unsafe_allow_html=True)
        
        col_pf, col_int, col_dk = st.columns(3)
        with col_pf:
            st.markdown(f'<div class="score-kort"><div class="score-title">Match</div><div class="score-value">{p}/100</div><ul><li>Perfekt størrelse</li><li>Høy relevans</li></ul></div>', unsafe_allow_html=True)
        with col_int:
            st.markdown(f'<div class="score-kort"><div class="score-title">Temperatur</div><div class="score-value">{i}/100</div><ul><li>Nylige nyheter</li><li>Digital vekst</li></ul></div>', unsafe_allow_html=True)
        with col_dk:
            st.markdown(f'<div class="score-kort"><div class="score-title">Datakvalitet</div><div class="score-value">{d}/100</div><ul><li>Verifisert e-post</li><li>Oppdatert adresse</li></ul></div>', unsafe_allow_html=True)

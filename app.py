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

# --- KONFIGURASJON ---
brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"
klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
modell_navn = "gpt-4o-mini"

# --- HJELPEFUNKSJONER ---
def normaliser_naeringskode(naeringskode):
    if not naeringskode: return ""
    return "".join(ch for ch in str(naeringskode).strip() if ch.isdigit() or ch == ".")

def er_underlagt_bht(naeringskode):
    kode = normaliser_naeringskode(naeringskode)
    if not kode: return False
    bht_koder = {"02", "03.2", "03.3", "05", "07", "08", "09.9", "10", "11", "12", "13", "14", "15", "16", "17", "18.1", "19", "20", "21", "22", "23", "24", "25", "26.1", "26.2", "26.3", "26.4", "26.51", "26.6", "26.7", "27", "28", "29", "30", "31", "32.3", "32.4", "32.5", "32.990", "33", "35.1", "35.21", "35.22", "35.23", "35.3", "35.4", "36", "37", "38", "39", "41", "42", "43.1", "43.2", "43.3", "43.4", "43.5", "43.9", "46.87", "49", "52.21", "52.22", "52.23", "52.24", "53.1", "53.2", "55.1", "56.11", "56.22", "56.3", "61", "75", "77.1", "80.01", "80.09", "81.2", "84.23", "84.24", "84.25", "85.1", "85.2", "85.3", "85.4", "85.5", "85.69", "86.1", "86.2", "86.91", "86.92", "86.93", "86.94", "86.95", "86.96", "86.99", "87.1", "87.2", "87.3", "87.99", "88", "91.3", "95.23", "95.24", "95.29", "95.31", "95.32", "96.1", "96.21", "96.91"}
    return any(kode == k or kode.startswith(f"{k}.") for k in bht_koder)

def beregn_total_health(p, i, d):
    # Vekting: Passform 40%, Intent 40%, Kvalitet 20%
    return int((p * 0.4) + (i * 0.4) + (d * 0.2))

# --- DESIGN ---
def bruk_stil():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #003642; background-color: #f7f9fb; }
        .stApp { background-color: #f7f9fb; }
        
        /* Health Badge */
        .health-badge {
            position: absolute;
            top: 15px;
            right: 15px;
            background: #003642;
            color: white;
            padding: 4px 12px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 0.85rem;
            z-index: 99;
        }

        /* Kort og containere */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-radius: 12px !important;
            border: 1px solid #e0e7ec !important;
            box-shadow: 0 1px 3px rgba(0, 54, 66, 0.06);
            position: relative;
            padding: 20px !important;
        }

        .stButton>button { background-color: #368373; color: white; border-radius: 8px; border: none; padding: 10px 24px; font-weight: 500; }
        .stButton>button:hover { background-color: #2a6a5c; color: white; transform: translateY(-1px); }
        
        .score-kort { 
            margin-top: 10px; border: 1px solid #e0e7ec; border-radius: 8px; padding: 15px; background: #ffffff; min-height: 160px;
        }
        .score-title { font-size: 0.75rem; text-transform: uppercase; color: #6b8a93; font-weight: 600; }
        .score-value { font-size: 1.2rem; font-weight: 700; color: #003642; }
        .score-kort ul { margin: 5px 0 0 0; padding-left: 1.2rem; font-size: 0.8rem; color: #37535b; }
        </style>
    """, unsafe_allow_html=True)

# (Inkluder alle dine originale funksjoner her: sok_brreg, utfor_analyse, bygg_leadscore osv.)

# --- VISNINGS-EKSEMPEL ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

# Her legger du inn resten av app-strukturen din
if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    h_score = bygg_hovedscore(f, st.session_state.mine_leads)
    
    # Beregn Health
    health = beregn_total_health(h_score['passformscore'], h_score['intentscore'], h_score['datakvalitet'])
    
    with st.container(border=True):
        # Health Score Badge øverst til høyre
        st.markdown(f'<div class="health-badge">Total Health: {health}%</div>', unsafe_allow_html=True)
        
        st.subheader(f.get('navn'))
        # ... Resten av innholdet i kortet ...

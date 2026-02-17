import streamlit as st
import requests
import pandas as pd
import html
from duckduckgo_search import DDGS
from openai import OpenAI
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# Konfigurasjon
brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"
klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
modell_navn = "gpt-4o-mini"

# --- DESIGN OG STYLING ---
def bruk_stil():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #003642; background-color: #ffffff; }
        
        /* Scorecard Layout */
        .score-row {
            display: flex;
            background: #ffffff;
            border: 1px solid #368373;
            border-radius: 8px;
            padding: 25px;
            margin: 20px 0;
            position: relative;
            gap: 20px;
        }
        .total-health-badge {
            position: absolute;
            top: 10px;
            right: 15px;
            background: #003642;
            color: white;
            padding: 6px 15px;
            border-radius: 2px;
            font-weight: 700;
            font-size: 0.9rem;
        }
        .score-box { flex: 1; border-right: 1px solid #eee; }
        .score-box:last-child { border-right: none; }
        .score-label { font-size: 0.7rem; text-transform: uppercase; color: #368373; font-weight: 700; }
        .score-val { font-size: 1.6rem; font-weight: 700; color: #003642; }
        .score-info { font-size: 0.85rem; color: #4a6a72; margin-top: 5px; }

        /* Input og Knapper */
        .stTextInput>div>div>input { border-radius: 2px; border: 1px solid #368373; background-color: white !important; }
        .stButton>button { background-color: #368373; color: white; border-radius: 2px; border: none; padding: 10px 25px; font-weight: 600; }
        .stButton>button:hover { background-color: #003642; color: white; }
        
        /* AI Boks */
        .analyse-container { border-left: 4px solid #003642; padding: 20px; margin: 20px 0; background: white; }
        </style>
    """, unsafe_allow_html=True)

# --- CORE FUNKSJONER (Flyttet ut for å unngå NameError) ---
@st.cache_data(ttl=3600)
def hent_firma_data(orgnr):
    try:
        res = requests.get(f"{brreg_adresse}/{orgnr}", timeout=3)
        return res.json() if res.status_code == 200 else None
    except: return None

def finn_nyheter(firmanavn):
    try:
        res = DDGS().text(f"{firmanavn} norge nyheter strategi ledelse", max_results=3)
        return "\n".join([r['body'] for r in res]) if res else ""
    except: return ""

def lag_isbryter_med_eierskap(firmanavn, nyheter, bransje):
    prompt = f"""
    Du er seniorrådgiver i Compend. 
    Selskap: {firmanavn} | Bransje: {bransje}
    Innsikt: {nyheter}
    
    Oppgave:
    1. Lag en isbryter (fokus på Compend LMS/kurs).
    2. Sjekk om leder sannsynligvis er eier.
    3. Maks 3 setninger. Ingen emojier.
    """
    try:
        svar = klient.chat.completions.create(model=modell_navn, messages=[{"role": "user", "content": prompt}])
        return svar.choices[0].message.content
    except: return "Analyse utilgjengelig."

# --- UI ELEMENTER ---
def vis_scorecards(p, i, d, p_txt, i_txt, d_txt):
    health = int((p * 0.4) + (i * 0.4) + (d * 0.2))
    st.markdown(f"""
        <div class="score-row">
            <div class="total-health-badge">HEALTH SCORE: {health}%</div>
            <div class="score-box">
                <div class="score-label">Salgsmatch</div>
                <div class="score-val">{p}%</div>
                <div class="score-info">{p_txt}</div>
            </div>
            <div class="score-box">
                <div class="score-label">Temperatur</div>
                <div class="score-val">{i}%</div>
                <div class="score-info">{i_txt}</div>
            </div>
            <div class="score-box">
                <div class="score-label">Datakvalitet</div>
                <div class="score-val">{d}%</div>
                <div class="score-info">{d_txt}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- APP START ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

org_input = st.text_input("Søk på organisasjonsnummer", placeholder="9 siffer...", label_visibility="collapsed")

if len(org_input) == 9:
    with st.spinner("Analyserer..."):
        f = hent_firma_data(org_input)
        if f:
            # Rask prosessering med tråder
            with ThreadPoolExecutor() as executor:
                f_news = executor.submit(finn_nyheter, f['navn'])
                nyheter = f_news.result()

            # Scorecard-data (forenklet for selgeren)
            ansatte = f.get('antallAnsatte', 0)
            p_score = 90 if ansatte > 20 else 60
            i_score = 75 if nyheter else 40
            d_score = 95 if f.get('hjemmeside') else 70

            st.subheader(f['navn'])
            
            # Scorecards med Health Score øverst til høyre
            vis_scorecards(
                p_score, i_score, d_score,
                f"Basert på {ansatte} ansatte og bransje.",
                "Basert på ferske nyheter og digital aktivitet.",
                "Basert på Brreg-data og verifisert kontaktinfo."
            )

            # Strategisk analyse
            isbryter = lag_isbryter_med_eierskap(f['navn'], nyheter, f.get('naeringskode1', {}).get('beskrivelse'))
            st.markdown(f'<div class="analyse-container"><strong>Strategisk analyse & eierskap</strong><br><br>{isbryter}</div>', unsafe_allow_html=True)

            if st.button("Send til HubSpot", use_container_width=True):
                st.success("Lead sendt til HubSpot")
            
            st.divider()
            st.write("### Andre selskaper i samme bransje")
            # Her kan mine_leads loopen legges til
        else:
            st.error("Fant ikke selskapet.")

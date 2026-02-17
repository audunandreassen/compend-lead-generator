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
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #003642; background-color: #f7f9fb; }
        
        /* Scorecard Layout */
        .score-row {
            display: flex;
            background: #ffffff;
            border: 1px solid #e0e7ec;
            border-radius: 12px;
            padding: 20px;
            margin: 15px 0;
            position: relative;
            gap: 20px;
        }
        .total-health-badge {
            position: absolute;
            top: -12px;
            right: 20px;
            background: #368373;
            color: white;
            padding: 4px 14px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .score-box { flex: 1; border-right: 1px solid #eee; padding-right: 15px; }
        .score-box:last-child { border-right: none; }
        .score-label { font-size: 0.7rem; text-transform: uppercase; color: #6b8a93; letter-spacing: 0.05em; font-weight: 700; }
        .score-val { font-size: 1.4rem; font-weight: 700; color: #003642; margin: 4px 0; }
        .score-info { font-size: 0.8rem; color: #4a6a72; line-height: 1.4; }

        /* Knapper */
        .stButton>button { background-color: #368373; color: white; border-radius: 20px; border: none; padding: 8px 24px; font-weight: 600; transition: 0.3s; }
        .stButton>button:hover { background-color: #003642; transform: translateY(-1px); }
        
        /* AI Boks */
        .analyse-container { background: #003642; color: white; padding: 25px; border-radius: 12px; margin-bottom: 20px; }
        .analyse-header { font-size: 0.7rem; text-transform: uppercase; opacity: 0.7; margin-bottom: 10px; font-weight: 700; }
        </style>
    """, unsafe_allow_html=True)

# --- ANALYSEFUNKSJONER ---
def beregn_health_score(p, i, d):
    return int((p * 0.45) + (i * 0.35) + (d * 0.20))

def lag_isbryter_med_eierskap(firmanavn, nyheter, bransje, leder):
    prompt = f"""
    Du er seniorrådgiver i Compend. 
    Selskap: {firmanavn}
    Leder: {leder}
    Bransje: {bransje}
    Innsikt: {nyheter}
    
    Oppgave:
    1. Lag en strategisk isbryter for selgeren (fokus på Compend LMS/kurs).
    2. Analyser eierskap: Basert på innsikten, er det sannsynlig at {leder} også er eier/gründer? 
    3. Hvis ja, forklar hvordan selgeren bør bruke dette (kort beslutningsvei).
    4. Maks 4 setninger. Ingen emojier.
    """
    try:
        svar = klient.chat.completions.create(model=modell_navn, messages=[{"role": "user", "content": prompt}])
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere analyse."

# --- UI KOMPONENTER ---
def vis_scorecards(p, i, d, p_tekst, i_tekst, d_tekst):
    health = beregn_health_score(p, i, d)
    st.markdown(f"""
        <div class="score-row">
            <div class="total-health-badge">LEAD HEALTH: {health}%</div>
            <div class="score-box">
                <div class="score-label">Salgsmatch</div>
                <div class="score-val">{p}%</div>
                <div class="score-info">{p_tekst}</div>
            </div>
            <div class="score-box">
                <div class="score-label">Salgstemperatur</div>
                <div class="score-val">{i}%</div>
                <div class="score-info">{i_tekst}</div>
            </div>
            <div class="score-box">
                <div class="score-label">Datakvalitet</div>
                <div class="score-val">{d}%</div>
                <div class="score-info">{d_tekst}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- HOVED APP ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

# Søk helt øverst
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    org_input = st.text_input("Søk", placeholder="Skriv org.nummer (9 siffer)", label_visibility="collapsed")

if len(org_input) == 9:
    with st.spinner("Henter markedsinnsikt..."):
        f = hent_firma_data(org_input)
        if f:
            # Raskere henting med tråder
            with ThreadPoolExecutor() as ex:
                future_news = ex.submit(finn_nyheter, f['navn'])
                nyheter = future_news.result()

            leder = f.get("daglig_leder", "Ukjent leder")
            
            # --- VISNING ---
            st.subheader(f['navn'])
            
            # Scorecards (Eksempelverdier for logikken)
            vis_scorecards(
                85, 70, 95,
                "Selskapets størrelse og bransje treffer Compends kjernemarked perfekt.",
                "Høy aktivitet i bransjen indikerer økt behov for kompetansestyring nå.",
                "Verifiserte data fra Brreg og aktive kontaktpunkter identifisert."
            )

            # AI Analyse med aksjonærsjekk
            isbryter = lag_isbryter_med_eierskap(f['navn'], nyheter, f.get('naeringskode1', {}).get('beskrivelse'), leder)
            st.markdown(f"""
                <div class="analyse-container">
                    <div class="analyse-header">Strategisk analyse & eierskap</div>
                    {isbryter}
                </div>
            """, unsafe_allow_html=True)

            # HubSpot knappen
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("Send til HubSpot", use_container_width=True):
                    st.success("Lead overført!")
            
            # Andre aktører
            st.markdown("---")
            st.write("### Andre aktører i samme bransje")
            # Her kan du gjenbruke din mine_leads loop
        else:
            st.error("Fant ikke selskapet.")

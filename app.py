import streamlit as st
import requests
import pandas as pd
import html
from duckduckgo_search import DDGS
from openai import OpenAI
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# --- KONFIGURASJON ---
BRREG_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
ZAPIER_WEBHOOK = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

# --- DESIGN & CSS ---
def bruk_stil():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
            color: #003642;
            background-color: #FFFFFF;
        }}

        /* Scorecards med Health Badge */
        .score-row {{
            display: flex;
            background: #FFFFFF;
            border: 1px solid #368373;
            border-radius: 8px;
            padding: 25px;
            margin: 20px 0;
            position: relative;
            gap: 20px;
        }}
        .total-health-badge {{
            position: absolute;
            top: 10px;
            right: 15px;
            background: #003642;
            color: white;
            padding: 6px 15px;
            border-radius: 2px;
            font-weight: 700;
            font-size: 0.9rem;
        }}
        .score-box {{ flex: 1; border-right: 1px solid #E0E7EC; padding-right: 15px; }}
        .score-box:last-child {{ border-right: none; }}
        .score-label {{ font-size: 0.7rem; text-transform: uppercase; color: #368373; font-weight: 700; letter-spacing: 0.05em; }}
        .score-val {{ font-size: 1.6rem; font-weight: 700; color: #003642; margin: 5px 0; }}
        .score-info {{ font-size: 0.85rem; color: #4A6A72; line-height: 1.4; }}

        /* UI Elementer */
        .stButton>button {{
            background-color: #368373; color: white; border-radius: 2px; border: none; 
            padding: 10px 25px; font-weight: 600; transition: 0.2s;
        }}
        .stButton>button:hover {{ background-color: #003642; color: white; }}
        .stTextInput>div>div>input {{
            background-color: #FFFFFF !important; border-radius: 2px; border: 1px solid #368373; color: #003642;
        }}
        .analyse-container {{
            border-left: 4px solid #003642; padding: 20px; margin: 20px 0; background: #F8FAFC;
        }}
        
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        </style>
    """, unsafe_allow_html=True)

# --- DATAFUNKSJONER ---
@st.cache_data(ttl=3600)
def sok_brreg(query):
    if query.isdigit() and len(query) == 9:
        res = requests.get(f"{BRREG_URL}/{query}")
        return [res.json()] if res.status_code == 200 else []
    res = requests.get(BRREG_URL, params={"navn": query, "size": 10})
    return res.json().get("_embedded", {}).get("enheter", []) if res.status_code == 200 else []

def hent_nyheter(navn):
    try:
        with DDGS() as ddgs:
            res = list(ddgs.text(f"{navn} norge strategi HMS ledelse", max_results=3))
            return "\n".join([r['body'] for r in res])
    except: return ""

def lag_isbryter(f_navn, nyheter, bransje):
    prompt = f"Du er salgsstrateg for Compend. Selskap: {f_navn}. Bransje: {bransje}. Innsikt: {nyheter}. Lag en analyse på 3 setninger om hvorfor de trenger Compend LMS og kurs, spesielt med tanke på HMS/BHT. Sjekk om daglig leder virker å være eier. Ingen emojier."
    try:
        svar = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}])
        return svar.choices[0].message.content
    except: return "Analysen kunne ikke genereres."

# --- UI LOGIKK ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

# Søkefelt øverst
st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    sok_tekst = st.text_input("Søk", placeholder="Selskapsnavn eller org.nummer...", label_visibility="collapsed")

if len(sok_tekst) > 2:
    treff = sok_brreg(sok_tekst)
    if not treff:
        st.error("Ingen selskaper funnet.")
    else:
        # Hvis flere treff, vis en enkel liste, ellers analyser direkte
        f = treff[0]
        if len(treff) > 1 and not sok_tekst.isdigit():
            valg = st.selectbox("Velg riktig selskap", options=treff, format_func=lambda x: f"{x['navn']} ({x.get('forretningsadresse', {}).get('poststed', 'Ukjent')})")
            f = valg

        # Start prosessering
        with st.spinner("Beriker data og beregner Health Score..."):
            with ThreadPoolExecutor() as ex:
                future_news = ex.submit(hent_nyheter, f['navn'])
                nyheter = future_news.result()
            
            # Beregn score (forenklet logikk for hastighet)
            ansatte = f.get('antallAnsatte', 0)
            p_score = min(100, 40 + (ansatte * 0.5)) if ansatte > 0 else 30
            i_score = 80 if nyheter else 40
            d_score = 95 if f.get('hjemmeside') else 60
            health = int((p_score * 0.45) + (i_score * 0.35) + (d_score * 0.20))

            # --- VISNING ---
            st.markdown("---")
            st.subheader(f['navn'])
            
            # Scorecard Rad
            st.markdown(f"""
                <div class="score-row">
                    <div class="total-health-badge">HEALTH SCORE: {health}%</div>
                    <div class="score-box">
                        <div class="score-label">Salgsmatch</div>
                        <div class="score-val">{int(p_score)}%</div>
                        <div class="score-info">Basert på {ansatte} ansatte og bransjesegment.</div>
                    </div>
                    <div class="score-box">
                        <div class="score-label">Salgstemperatur</div>
                        <div class="score-val">{int(i_score)}%</div>
                        <div class="score-info">Digital tilstedeværelse og nyhetsverdi.</div>
                    </div>
                    <div class="score-box">
                        <div class="score-label">Datakvalitet</div>
                        <div class="score-val">{int(d_score)}%</div>
                        <div class="score-info">Verifisert kontaktinformasjon fra Brreg.</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # Informasjonskolonner
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Org.nr:** {f['organisasjonsnummer']}")
                st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse', 'Ukjent')}")
            with c2:
                st.write(f"**Adresse:** {f.get('forretningsadresse', {}).get('adresse', [''])[0]}, {f.get('forretningsadresse', {}).get('poststed', '')}")
                st.write(f"**Nettside:** {f.get('hjemmeside', 'Ikke oppgitt')}")

            # AI Analyse
            isbryter = lag_isbryter(f['navn'], nyheter, f.get('naeringskode1', {}).get('beskrivelse'))
            st.markdown(f"""
                <div class="analyse-container">
                    <div style="font-size: 0.7rem; text-transform: uppercase; font-weight: 700; margin-bottom: 10px;">Compend Strategisk Analyse</div>
                    {isbryter}
                </div>
            """, unsafe_allow_html=True)

            # HubSpot
            if st.button("Overfør lead til HubSpot", use_container_width=True):
                requests.post(ZAPIER_WEBHOOK, json={"firma": f['navn'], "isbryter": isbryter, "health": health})
                st.success("Lead sendt til CRM!")

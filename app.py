import streamlit as st
import requests
import pandas as pd
from duckduckgo_search import DDGS
from openai import OpenAI
from io import BytesIO

# Konfigurasjon
brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"
klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
modell_navn = "gpt-4o-mini"

# --- DESIGN OG STYLING ---
def bruk_stil():
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
        
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
            color: #003642;
            background-color: #FFFFFF;
        }}

        .stApp {{
            background-color: #FFFFFF;
        }}
        
        /* Knapper - Farge 368373 med 20px avrunding */
        .stButton>button {{
            background-color: #368373;
            color: white;
            border-radius: 20px;
            border: none;
            padding: 10px 24px;
            transition: 0.2s;
            font-weight: 400;
        }}
        
        .stButton>button:hover {{
            background-color: #003642;
            color: white;
            border: none;
        }}

        /* Inndatafelt med 20px avrunding */
        .stTextInput>div>div>input {{
            border-radius: 20px;
            border: 1px solid #368373;
            padding: 10px 20px;
        }}

        /* Strategisk boks - Rent design uten bakgrunn */
        .stAlert {{
            background-color: transparent;
            border: none;
            border-left: 4px solid #003642;
            color: #003642;
            border-radius: 0px;
            padding-left: 1.5rem;
        }}

        /* Overskrifter */
        h1, h2, h3 {{
            color: #003642;
            font-weight: 600;
        }}
        
        hr {{
            border: 0;
            border-top: 1px solid #368373;
            opacity: 0.1;
        }}

        /* Avstand fra toppen til innholdet */
        .block-container {{
            padding-top: 5rem;
        }}

        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        </style>
    """, unsafe_allow_html=True)

# Hjelpefunksjoner
def hent_firma_data(orgnr):
    try:
        svar = requests.get(f"{brreg_adresse}/{{orgnr}}", timeout=5)
        return svar.json() if svar.status_code == 200 else None
    except:
        return None

def finn_nyheter(firmanavn):
    try:
        resultater = DDGS().text(f"{{firmanavn}} norge nyheter strategi ledelse", max_results=5)
        return "\n".join([r['body'] for r in resultater]) if resultater else ""
    except:
        return ""

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    prompt = f"""
    Du er en salgsstrateg for Compend (www.compend.no). 
    Compend leverer plattformer for kurs, opplæring og kompetanseutvikling (LMS).
    Selskap: {{firmanavn}}
    Bransje: {{bransje}}
    Innsikt: {{nyhetstekst}}
    OPPGAVE:
    Skriv en analyse på maks 3 korte setninger som selgeren kan bruke. 
    1. Ingen hilsener eller emojier. 
    2. KNYTT innsikten direkte til Compends løsninger.
    3. Foreslå en konkret tittel å kontakte.
    """
    try:
        svar = klient.chat.completions.create(
            model=modell_navn, 
            messages=[{{"role": "system", "content": "Du er en profesjonell salgsrådgiver for Compend. Du bruker aldri emojier."}}, {{"role": "user", "content": prompt}}]
        )
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere analyse."

def finn_eposter(domene):
    if not domene: return []
    rent_domene = domene.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    try:
        res = requests.get("https://api.hunter.io/v2/domain-search", params={{"domain": rent_domene, "api_key": st.secrets["HUNTER_API_KEY"], "limit": 5}})
        return [e["value"] for e in res.json().get("data", {{}}).get("emails", [])] if res.status_code == 200 else []
    except: return []

def formater_adresse(f):
    adr = f.get("forretningsadresse", {{}})
    if not adr: return "Ingen adresse registrert"
    gate = adr.get("adresse", [""])[0]
    post = f"{{adr.get('postnummer', '')}} {{adr.get('poststed', '')}}"
    return f"{{gate}}, {{post}}".strip(", ")

# --- APP START ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

if "mine_leads" not in st.session_state: st.session_state.mine_leads = []
if "hoved_firma" not in st.session_state: st.session_state.hoved_firma = None
if "soke_felt" not in st.session_state: st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state: st.session_state.forrige_sok = ""

# Søkefelt med avstand fra toppen
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    org_input = st.text_input("Søk på organisasjonsnummer", value=st.session_state.soke_felt, label_visibility="collapsed", placeholder="Tast inn organisasjonsnummer (9 siffer)")
    start_knapp = st.button("Analyser selskap", use_container_width=True)

def utfor_analyse(orgnr):
    hoved = hent_firma_data(orgnr)
    if hoved:
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        nyheter = finn_nyheter(hoved['navn'])
        st.session_state.isbryter = lag_isbryter(hoved['navn'], nyheter, hoved.get('naeringskode1', {{}}).get('beskrivelse', 'Ukjent'))
        st.session_state.eposter = finn_eposter(hoved.get('hjemmeside'))
        
        kode = hoved.get("naeringskode1", {{}}).get("kode")
        if kode:
            res = requests.get(brreg_adresse, params={{"naeringskode": kode, "size": 100}}).json()
            alle = res.get("_embedded", {{}}).get("enheter", [])
            st.session_state.mine_leads = [e for e in alle if e['organisasjonsnummer'] != orgnr]
    else:
        st.error("Ugyldig organisasjonsnummer.")

if (org_input != st.session_state.forrige_sok and len(org_input) == 9):
    utfor_analyse(org_input)
    st.rerun()

if start_knapp:
    utfor_analyse(org_input)
    st.rerun()

# --- VISNING ---
if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    st.markdown("<hr>", unsafe_allow_html=True)
    
    st.subheader(f.get('navn'))
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.write(f"**Organisasjonsnummer:** {{f['organisasjonsnummer']}}")
        st.write(f"**Ansatte:** {{f.get('antallAntatte', 'Ukjent')}}")
        st.write(f"**Bransje:** {{f.get('naeringskode1', {{}}).get('beskrivelse', 'Ukjent')}}")
    with c2:
        st.write(f"**Nettside:** {{f.get('hjemmeside', 'Ikke oppgitt')}}")
        st.write(f"**Adresse:** {{formater_adresse(f)}}")
        if st.session_state.get('eposter'):
            st.write(f"**E-postadresser:** {{', '.join(st.session_state.eposter)}}")
    with c3:
        if st.button("Overfør til HubSpot", use_container_width=True):
            data_pakke = {{
                "firma": f['navn'],
                "orgnr": f['organisasjonsnummer'],
                "isbryter": st.session_state.get('isbryter'),
                "bransje": f.get('naeringskode1', {{}}).get('beskrivelse'),
                "ansatte": f.get('antallAntatte'),
                "adresse": formater_adresse(f),
                "nettside": f.get('hjemmeside'),
                "eposter": ", ".join(st.session_state.get('eposter', []))
            }}
            requests.post(zapier_mottaker, json=data_pakke)
            st.success("Data overført")

    st.info(st.session_state.get('isbryter'))
    
    if st.session_state.mine_leads:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Andre aktører i bransjen")
        
        for i, lead in enumerate(st.session_state.mine_leads):
            with st.container():
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.write(f"**{{lead['navn']}}** | {{lead.get('antallAntatte', 0)}} ansatte")
                    st.write(f"{{lead.get('forretningsadresse', {{}}).get('poststed', 'Ukjent')}} | {{lead.get('hjemmeside', 'Ingen nettside')}}")
                with col_b:
                    if st.button("Analyser", key=f"an_{{lead['organisasjonsnummer']}}_{{i}}"):
                        st.session_state.soke_felt = lead['organisasjonsnummer']
                        st.rerun()
                st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

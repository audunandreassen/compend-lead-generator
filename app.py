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
        
        .stButton>button {{
            background-color: #368373;
            color: white;
            border-radius: 2px;
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

        .stTextInput>div>div>input {{
            background-color: #FFFFFF !important;
            border-radius: 2px;
            border: 1px solid #368373;
            padding: 10px 20px;
            color: #003642;
        }}

        .stAlert {{
            background-color: transparent !important;
            border: none !important;
            border-left: 4px solid #003642 !important;
            color: #003642;
            border-radius: 0px;
            padding-left: 1.5rem;
        }}

        h1, h2, h3 {{
            color: #003642;
            font-weight: 600;
        }}
        
        hr {{
            border: 0;
            border-top: 1px solid #368373;
            opacity: 0.1;
        }}

        .block-container {{
            padding-top: 5rem;
        }}

        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        </style>
    """, unsafe_allow_html=True)

# --- APP START ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

# Anker på toppen
st.markdown('<a id="top"></a>', unsafe_allow_html=True)

if "mine_leads" not in st.session_state:
    st.session_state.mine_leads = []
if "hoved_firma" not in st.session_state:
    st.session_state.hoved_firma = None
if "soke_felt" not in st.session_state:
    st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state:
    st.session_state.forrige_sok = ""

# Hjelpefunksjoner
def hent_firma_data(orgnr):
    try:
        svar = requests.get(f"{brreg_adresse}/{orgnr}", timeout=5)
        return svar.json() if svar.status_code == 200 else None
    except:
        return None

def finn_nyheter(firmanavn):
    try:
        resultater = DDGS().text(f"{firmanavn} norge nyheter strategi ledelse", max_results=5)
        return "\n".join([r['body'] for r in resultater]) if resultater else ""
    except:
        return ""

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    prompt = f"""
    Du er en salgsstrateg for Compend (www.compend.no). 
    Compend leverer plattformer for kurs, opplæring og kompetanseutvikling (LMS).
    Selskap: {firmanavn}
    Bransje: {bransje}
    Innsikt: {nyhetstekst}
    OPPGAVE:
    Skriv en analyse på maks 3 korte setninger som selgeren kan bruke. 
    1. Ingen hilsener eller emojier. 
    2. KNYTT innsikten direkte til Compends løsninger.
    3. Foreslå en konkret tittel å kontakte.
    """
    try:
        svar = klient.chat.completions.create(
            model=modell_navn, 
            messages=[
                {
                    "role": "system",
                    "content": "Du er en profesjonell salgsrådgiver for Compend. Du bruker aldri emojier."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere analyse."

def finn_eposter(domene):
    if not domene:
        return []
    rent_domene = (
        domene.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
    )
    try:
        res = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain": rent_domene,
                "api_key": st.secrets["HUNTER_API_KEY"],
                "limit": 5,
            },
        )
        return [
            e["value"] for e in res.json().get("data", {}).get("emails", [])
        ] if res.status_code == 200 else []
    except:
        return []

def formater_adresse(f):
    adr = f.get("forretningsadresse", {})
    if not adr:
        return "Ingen adresse registrert"
    gate = adr.get("adresse", [""])[0]
    post = f"{adr.get('postnummer', '')} {adr.get('poststed', '')}"
    return f"{gate}, {post}".strip(", ")

def utfor_analyse(orgnr):
    hoved = hent_firma_data(orgnr)
    if hoved:
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        firmanavn = hoved.get("navn", "Ukjent")
        nyheter = finn_nyheter(firmanavn)
        st.session_state.isbryter = lag_isbryter(
            firmanavn,
            nyheter,
            hoved.get("naeringskode1", {}).get("beskrivelse", "Ukjent"),
        )
        st.session_state.eposter = finn_eposter(hoved.get("hjemmeside"))
        
        kode = hoved.get("naeringskode1", {}).get("kode")
        if kode:
            antall = hoved.get("antallAnsatte") or 0
            params = {
                "naeringskode": kode,
                "sort": "antallAnsatte,desc",
                "fraAntallAnsatte": 5,
                "size": 50,
            }
            # Filtrer på kommune hvis tilgjengelig
            kommune = hoved.get("forretningsadresse", {}).get("kommunenummer")
            if kommune:
                params["kommunenummer"] = kommune

            res = requests.get(brreg_adresse, params=params).json()
            alle = res.get("_embedded", {}).get("enheter", [])
            leads = [e for e in alle if e["organisasjonsnummer"] != orgnr]

            # Hvis kommune-søk ga for få resultater, utvid til hele landet
            if len(leads) < 10 and kommune:
                del params["kommunenummer"]
                res2 = requests.get(brreg_adresse, params=params).json()
                alle2 = res2.get("_embedded", {}).get("enheter", [])
                eksisterende = {e["organisasjonsnummer"] for e in leads}
                for e in alle2:
                    if e["organisasjonsnummer"] != orgnr and e["organisasjonsnummer"] not in eksisterende:
                        leads.append(e)

            st.session_state.mine_leads = leads
    else:
        st.error("Ugyldig organisasjonsnummer.")

# Søkefelt
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    org_input = st.text_input(
        "Søk på organisasjonsnummer",
        value=st.session_state.soke_felt,
        label_visibility="collapsed",
        placeholder="Tast inn organisasjonsnummer (9 siffer)",
    )
    start_knapp = st.button("Analyser selskap", use_container_width=True)

# Automatisk analyse ved direkte orgnr-innskriving
if (org_input != st.session_state.forrige_sok and len(org_input) == 9):
    utfor_analyse(org_input)
    st.rerun()

# Manuell analyse-knapp
if start_knapp:
    utfor_analyse(org_input)
    st.rerun()

# --- VISNING ---
if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    st.markdown("<hr>", unsafe_allow_html=True)
    
    st.subheader(f.get("navn"))
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.write(f"**Organisasjonsnummer:** {f['organisasjonsnummer']}")
        st.write(f"**Ansatte:** {f.get('antallAnsatte', 'Ukjent')}")
        st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse', 'Ukjent')}")
    with c2:
        st.write(f"**Nettside:** {f.get('hjemmeside', 'Ikke oppgitt')}")
        st.write(f"**Adresse:** {formater_adresse(f)}")
        if st.session_state.get("eposter"):
            st.write(f"**E-postadresser:** {', '.join(st.session_state.eposter)}")
    with c3:
        if st.button("Overfør til HubSpot", use_container_width=True):
            data_pakke = {
                "firma": f.get("navn", "Ukjent"),
                "orgnr": f["organisasjonsnummer"],
                "isbryter": st.session_state.get("isbryter"),
                "bransje": f.get("naeringskode1", {}).get("beskrivelse"),
                "ansatte": f.get("antallAnsatte"),
                "adresse": formater_adresse(f),
                "nettside": f.get("hjemmeside"),
                "eposter": ", ".join(st.session_state.get("eposter", [])),
            }
            requests.post(zapier_mottaker, json=data_pakke)
            st.success("Data overført")

    st.info(st.session_state.get("isbryter"))
    
    if st.session_state.mine_leads:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("Andre aktører i bransjen")
        
        for i, lead in enumerate(st.session_state.mine_leads):
            with st.container():
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.write(f"**{lead['navn']}** | {lead.get('antallAnsatte', 0)} ansatte")
                    st.write(
                        f"{lead.get('forretningsadresse', {}).get('poststed', 'Ukjent')} | "
                        f"{lead.get('hjemmeside', 'Ingen nettside')}"
                    )
                with col_b:
                    if st.button("Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}"):
                        st.session_state.soke_felt = lead["organisasjonsnummer"]
                        utfor_analyse(lead["organisasjonsnummer"])
                        st.rerun()
                st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)


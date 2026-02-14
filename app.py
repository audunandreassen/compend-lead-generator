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
    Skriv en isbryter på maks 3 korte setninger. 
    1. Gå rett på sak, ingen hilsener. 
    2. KNYTT innsikten direkte til hvordan Compends løsninger kan hjelpe (f.eks. sikre etterlevelse, raskere onboarding eller sentralisert kursstyring).
    3. Foreslå en konkret tittel å kontakte.
    """
    try:
        svar = klient.chat.completions.create(
            model=modell_navn, 
            messages=[{"role": "system", "content": "Du er en profesjonell salgsrådgiver for Compend."}, {"role": "user", "content": prompt}]
        )
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere analyse."

def finn_eposter(domene):
    if not domene: return []
    rent_domene = domene.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    try:
        res = requests.get("https://api.hunter.io/v2/domain-search", params={"domain": rent_domene, "api_key": st.secrets["HUNTER_API_KEY"], "limit": 5})
        return [e["value"] for e in res.json().get("data", {}).get("emails", [])] if res.status_code == 200 else []
    except: return []

def formater_adresse(f):
    adr = f.get("forretningsadresse", {})
    if not adr: return "Ingen adresse registrert"
    gate = adr.get("adresse", [""])[0]
    post = f"{adr.get('postnummer', '')} {adr.get('poststed', '')}"
    return f"{gate}, {post}".strip(", ")

# --- STREAMLIT UI ---
st.set_page_config(page_title="Compend Lead-Maskin", layout="wide")
st.title("📊 Compend AI: Markedsanalyse & Prospektering")

if "hoved_firma" not in st.session_state: st.session_state.hoved_firma = None
if "soke_felt" not in st.session_state: st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state: st.session_state.forrige_sok = ""

# Søkefelt
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    org_input = st.text_input("Skriv inn organisasjonsnummer for dyp analyse:", value=st.session_state.soke_felt)
    start_knapp = st.button("Start Markedsanalyse", use_container_width=True)

def utfor_analyse(orgnr):
    hoved = hent_firma_data(orgnr)
    if hoved:
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        nyheter = finn_nyheter(hoved['navn'])
        st.session_state.isbryter = lag_isbryter(hoved['navn'], nyheter, hoved.get('naeringskode1', {}).get('beskrivelse', 'Ukjent'))
        st.session_state.eposter = finn_eposter(hoved.get('hjemmeside'))
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
    st.divider()
    
    st.subheader(f"🎯 Fokusbedrift: {f['navn']}")
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.write(f"**Org.nr:** {f['organisasjonsnummer']}")
        st.write(f"**Ansatte:** {f.get('antallAntatte', 'Ukjent')}")
        st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse', 'Ukjent')}")
    with c2:
        st.write(f"**Nettside:** {f.get('hjemmeside', 'Ikke oppgitt')}")
        st.write(f"**Adresse:** {formater_adresse(f)}")
        if st.session_state.get('eposter'):
            st.write(f"**E-poster:** {', '.join(st.session_state.eposter)}")
    with c3:
        if st.button("🚀 Send til HubSpot", type="primary", use_container_width=True):
            data_pakke = {
                "firma": f['navn'],
                "orgnr": f['organisasjonsnummer'],
                "isbryter": st.session_state.get('isbryter'),
                "bransje": f.get('naeringskode1', {}).get('beskrivelse'),
                "ansatte": f.get('antallAntatte'),
                "adresse": formater_adresse(f),
                "nettside": f.get('hjemmeside'),
                "eposter": ", ".join(st.session_state.get('eposter', []))
            }
            requests.post(zapier_mottaker, json=data_pakke)
            st.success("Lead sendt!")

    st.warning(f"**Compend Strategi:** {st.session_state.get('isbryter')}")

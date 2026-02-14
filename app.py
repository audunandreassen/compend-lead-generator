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
    # Instruks spisset mot Compends leveranse (LMS, kurs, kompetanse)
    prompt = f"""
    Du er en salgsstrateg for Compend (www.compend.no). 
    Compend leverer plattformer for kurs, opplæring og kompetanseutvikling.
    
    Selskap: {firmanavn}
    Bransje: {bransje}
    Innsikt: {nyhetstekst}
    
    OPPGAVE:
    Skriv en isbryter på maks 3 korte setninger. 
    1. Gå rett på sak, ingen hilsener. 
    2. KNYTT innsikten direkte til hvordan Compend kan hjelpe (f.eks. ved vekst trengs rask onboarding, ved sikkerhetskrav trengs kontroll på sertifisering).
    3. Foreslå en konkret tittel å kontakte (f.eks. HR-ansvarlig eller Operasjonell leder).
    """
    try:
        svar = klient.chat.completions.create(
            model=modell_navn, 
            messages=[{"role": "system", "content": "Du er en profesjonell salgsrådgiver for Compend."}, {"role": "user", "content": prompt}]
        )
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere analyse."

# --- STREAMLIT UI ---
st.set_page_config(page_title="Compend Lead-Maskin", layout="wide")
st.title("📊 Compend AI: Markedsanalyse")

# Session State
if "mine_leads" not in st.session_state: st.session_state.mine_leads = []
if "hoved_firma" not in st.session_state: st.session_state.hoved_firma = None
if "soke_felt" not in st.session_state: st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state: st.session_state.forrige_sok = ""

def utfor_analyse(orgnr):
    hoved = hent_firma_data(orgnr)
    if hoved:
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        nyheter = finn_nyheter(hoved['navn'])
        st.session_state.isbryter = lag_isbryter(hoved['navn'], nyheter, hoved.get('naeringskode1', {}).get('beskrivelse', 'Ukjent'))
        
        kode = hoved.get("naeringskode1", {}).get("kode")
        if kode:
            # Henter 100 selskaper i én operasjon for maksimal oversikt
            res = requests.get(brreg_adresse, params={"naeringskode": kode, "size": 100}).json()
            alle = res.get("_embedded", {}).get("enheter", [])
            # Filtrerer bort seg selv, men beholder alle 100 treff fra Brreg
            st.session_state.mine_leads = [e for e in alle if e['organisasjonsnummer'] != orgnr]
    else:
        st.error("Ugyldig organisasjonsnummer.")

# Inndatafelt
org_input = st.text_input("Skriv inn organisasjonsnummer for dyp analyse:", value=st.session_state.soke_felt)

# Trigger analyse ved nytt nummer eller knapp
if (org_input != st.session_state.forrige_sok and len(org_input) == 9):
    utfor_analyse(org_input)
    st.rerun()

if st.button("Start Markedsanalyse", use_container_width=True):
    utfor_analyse(org_input)
    st.rerun()

# --- VISNING ---
if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    st.divider()
    st.subheader(f"🎯 Fokusbedrift: {f['navn']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Org.nr:** {f['organisasjonsnummer']}")
        st.write(f"**Ansatte:** {f.get('antallAnsatte', 'Ukjent')}")
    with col2:
        st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse', 'Ukjent')}")
        if st.button("🚀 Send hovedfokus til HubSpot", type="primary", use_container_width=True):
            data_pakke = {
                "firma": f['navn'],
                "isbryter": st.session_state.get('isbryter'),
                "bransje": f.get('naeringskode1', {}).get('beskrivelse'),
                "ansatte": f.get('antallAnsatte'),
                "kilde": "Compend Lead Generator"
            }
            requests.post(zapier_mottaker, json=data_pakke)
            st.success("Sendt til HubSpot!")

    st.warning(f"**Compend Salgsstrategi:**\n{st.session_state.get('isbryter')}")
    
    if st.session_state.mine_leads:
        st.markdown("---")
        st.subheader(f"📈 Relevante selskaper i samme bransje ({len(st.session_state.mine_leads)} funnet)")
        
        for i, lead in enumerate(st.session_state.mine_leads):
            with st.container():
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{lead['navn']}** | {lead.get('antallAnsatte', 0)} ansatte | {lead.get('forretningsadresse', {}).get('poststed', 'Ukjent sted')}")
                if c2.button("Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}"):
                    st.session_state.soke_felt = lead['organisasjonsnummer']
                    st.rerun()
                st.divider()

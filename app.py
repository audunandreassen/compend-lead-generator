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
        resultater = DDGS().text(f"{firmanavn} norge nyheter", max_results=3)
        return "\n".join([r['body'] for r in resultater]) if resultater else ""
    except:
        return ""

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    prompt = f"Lag en profesjonell isbryter på 2 setninger for {firmanavn} i bransjen {bransje} basert på: {nyhetstekst}. Foreslå kontaktperson uten å gjette navn."
    try:
        svar = klient.chat.completions.create(model=modell_navn, messages=[{"role": "user", "content": prompt}])
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere analyse."

def finn_eposter(domene):
    if not domene: return []
    rent_domene = domene.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    try:
        res = requests.get("https://api.hunter.io/v2/domain-search", params={"domain": rent_domene, "api_key": st.secrets["HUNTER_API_KEY"], "limit": 3})
        return [e["value"] for e in res.json().get("data", {}).get("emails", [])] if res.status_code == 200 else []
    except: return []

# --- STREAMLIT UI ---
st.set_page_config(page_title="Compend Lead-Maskin", layout="wide")
st.title("📊 Compend AI: Markedsanalyse")

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
        st.session_state.eposter = finn_eposter(hoved.get('hjemmeside'))
        
        kode = hoved.get("naeringskode1", {}).get("kode")
        if kode:
            res = requests.get(brreg_adresse, params={"naeringskode": kode, "size": 50}).json()
            alle = res.get("_embedded", {}).get("enheter", [])
            st.session_state.mine_leads = [e for e in alle if e.get('antallAnsatte', 0) >= 10 and e['organisasjonsnummer'] != orgnr][:10]
    else:
        st.error("Ugyldig organisasjonsnummer.")

# Inndatafelt
org_input = st.text_input("Organisasjonsnummer:", value=st.session_state.soke_felt)

# Vaktpost: Hvis feltet endrer seg (f.eks. via Analyser-knapp), kjør analyse automatisk
if org_input != st.session_state.forrige_sok and len(org_input) == 9:
    utfor_analyse(org_input)
    st.rerun()

if st.button("Start Analyse", use_container_width=True):
    utfor_analyse(org_input)
    st.rerun()

if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    st.divider()
    st.subheader(f"🎯 {f['navn']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse')}")
        st.write(f"**Ansatte:** {f.get('antallAnsatte')}")
    with col2:
        if st.button("🚀 Send til HubSpot", type="primary"):
            full_adresse = f"{f.get('forretningsadresse', {}).get('adresse', [''])[0]}, {f.get('forretningsadresse', {}).get('postnummer', '')} {f.get('forretningsadresse', {}).get('poststed', '')}"
            data_pakke = {
                "firma": f['navn'],
                "organisasjonsnummer": f['organisasjonsnummer'],
                "isbryter": st.session_state.get('isbryter'),
                "eposter": ", ".join(st.session_state.get('eposter', [])),
                "bransje": f.get('naeringskode1', {}).get('beskrivelse'),
                "ansatte": f.get('antallAnsatte'),
                "adresse": full_adresse,
                "nettside": f.get('hjemmeside')
            }
            requests.post(zapier_mottaker, json=data_pakke)
            st.success("Sendt!")

    st.info(st.session_state.get('isbryter'))
    
    if st.session_state.mine_leads:
        st.markdown("---")
        st.write("### Lignende selskaper")
        for i, lead in enumerate(st.session_state.mine_leads):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{lead['navn']}** ({lead.get('antallAnsatte')} ansatte)")
            # Denne knappen endrer soke_felt, som fanges opp av vaktposten øverst
            if c2.button("Analyser", key=f"an_{lead['organisasjonsnummer']}"):
                st.session_state.soke_felt = lead['organisasjonsnummer']
                st.rerun()

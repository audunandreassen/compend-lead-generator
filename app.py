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
        # Søker bredere for å finne faktiske problemer eller mål
        resultater = DDGS().text(f"{firmanavn} norge strategi utfordringer regnskap", max_results=5)
        return "\n".join([r['body'] for r in resultater]) if resultater else ""
    except:
        return ""

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    prompt = f"""
    Du er en sylskarp salgsstrateg for Compend. 
    Selskap: {firmanavn}
    Bransje: {bransje}
    Innsikt: {nyhetstekst}
    
    OPPGAVE:
    Skriv en isbryter til selgeren vår. 
    1. ALDRI start med "Velkommen til" eller "Hei". 
    2. Ikke snakk som en reklamebrosjyre. 
    3. Finn en konkret vinkel: Hvis nyhetene nevner vekst, snakk om behovet for rask opplæring. Hvis bransjen er kompleks, snakk om sertifisering og kontroll.
    4. Foreslå en tittel på hvem man skal be om å få snakke med (f.eks. Operasjonell leder eller HR).
    5. Maks 3 korte setninger.
    """
    try:
        svar = klient.chat.completions.create(
            model=modell_navn, 
            messages=[{"role": "system", "content": "Du hater floskler og elsker konkret salgsstrategi."}, {"role": "user", "content": prompt}]
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
if "side_nummer" not in st.session_state: st.session_state.side_nummer = 0

def utfor_analyse(orgnr):
    st.session_state.side_nummer = 0
    hoved = hent_firma_data(orgnr)
    if hoved:
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        nyheter = finn_nyheter(hoved['navn'])
        st.session_state.isbryter = lag_isbryter(hoved['navn'], nyheter, hoved.get('naeringskode1', {}).get('beskrivelse', 'Ukjent'))
        
        kode = hoved.get("naeringskode1", {}).get("kode")
        if kode:
            res = requests.get(brreg_adresse, params={"naeringskode": kode, "size": 100}).json()
            alle = res.get("_embedded", {}).get("enheter", [])
            st.session_state.mine_leads = [e for e in alle if e.get('antallAnsatte', 0) >= 10 and e['organisasjonsnummer'] != orgnr][:15]
    else:
        st.error("Ugyldig organisasjonsnummer.")

# Inndata og automatisk scroll-trigger via rerun
org_input = st.text_input("Organisasjonsnummer:", value=st.session_state.soke_felt)

if (org_input != st.session_state.forrige_sok and len(org_input) == 9):
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
            data_pakke = {
                "firma": f['navn'],
                "isbryter": st.session_state.get('isbryter'),
                "bransje": f.get('naeringskode1', {}).get('beskrivelse'),
                "ansatte": f.get('antallAnsatte')
            }
            requests.post(zapier_mottaker, json=data_pakke)
            st.success("Sendt!")

    st.warning(f"**Strategisk tips:**\n{st.session_state.get('isbryter')}")
    
    if st.session_state.mine_leads:
        st.markdown("---")
        st.write("### Lignende selskaper")
        for i, lead in enumerate(st.session_state.mine_leads):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{lead['navn']}** ({lead.get('antallAnsatte')} ansatte)")
            if c2.button("Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}"):
                st.session_state.soke_felt = lead['organisasjonsnummer']
                st.rerun()

        if st.button("Last inn flere..."):
            st.session_state.side_nummer += 1
            kode = f.get("naeringskode1", {}).get("kode")
            res = requests.get(brreg_adresse, params={"naeringskode": kode, "size": 100, "page": st.session_state.side_nummer}).json()
            nye = [e for e in res.get("_embedded", {}).get("enheter", []) if e.get('antallAnsatte', 0) >= 10]
            st.session_state.mine_leads.extend(nye[:15])
            st.rerun()

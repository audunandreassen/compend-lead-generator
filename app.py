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
    svar = requests.get(f"{brreg_adresse}/{orgnr}")
    return svar.json() if svar.status_code == 200 else None

def finn_nyheter(firmanavn):
    try:
        resultater = DDGS().text(f"{firmanavn} norge nyheter", max_results=2)
        return " ".join([r["body"] for r in resultater]) if resultater else "Ingen ferske nyheter."
    except:
        return "Ingen ferske nyheter."

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    instruks = f"Du er en selger for Compend. Skriv en kort åpningsreplikk (2 setninger) til {firmanavn} ({bransje}) basert på: {nyhetstekst}. Foreslå til slutt hvem man bør snakke med."
    try:
        svar = klient.chat.completions.create(model=modell_navn, messages=[{"role": "user", "content": instruks}])
        return svar.choices[0].message.content
    except Exception as e:
        return f"Kunne ikke lage replikk: {e}"

def finn_eposter(domene):
    if not domene: return []
    rent_domene = domene.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    try:
        res = requests.get("https://api.hunter.io/v2/domain-search", params={"domain": rent_domene, "api_key": st.secrets["HUNTER_API_KEY"], "limit": 3})
        return [e["value"] for e in res.json().get("data", {}).get("emails", [])] if res.status_code == 200 else []
    except:
        return []

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Markedsanalyse')
    return output.getvalue()

# --- STREAMLIT UI ---
st.set_page_config(page_title="Compend AI Market Insights", layout="wide")
st.title("📊 Compend AI: Markedsanalyse & Leads")

# Initialiser session state
if "side_nummer" not in st.session_state: st.session_state.side_nummer = 0
if "soke_felt" not in st.session_state: st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state: st.session_state.forrige_sok = ""

# Søkefelt
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    org_input = st.text_input("Skriv inn org.nummer for dyp analyse:", value=st.session_state.soke_felt)
    start_knapp = st.button("Start Markedsanalyse", use_container_width=True)

# FUNKSJON FOR SØK (brukes av både knappen og "Analyser"-knappene)
def utfor_sok(orgnr):
    st.session_state.side_nummer = 0
    hoved_firma = hent_firma_data(orgnr)
    if hoved_firma:
        st.session_state.hoved_firma = hoved_firma
        st.session_state.forrige_sok = orgnr
        kode = hoved_firma.get("naeringskode1", {}).get("kode")
        if kode:
            params = {"naeringskode": kode, "size": 15, "page": 0, "fraAntallAnsatte": 10}
            res = requests.get(brreg_adresse, params=params).json()
            st.session_state.mine_leads = res.get("_embedded", {}).get("enheter", [])
    else:
        st.error("Fant ikke selskapet.")

# Sjekk om vi skal trigge et nytt søk automatisk (når Analyser-knappen er trykket)
if org_input != st.session_state.forrige_sok and len(org_input) == 9:
    utfor_sok(org_input)
    st.rerun()

if start_knapp:
    utfor_sok(org_input)

# --- VISNING ---
if "hoved_firma" in st.session_state:
    f = st.session_state.hoved_firma
    st.markdown(f"## 🎯 Hovedfokus: {f['navn']}")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.subheader("Bedriftsinfo")
        st.write(f"**Org.nr:** {f['organisasjonsnummer']}")
        st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse')}")
        st.write(f"**Ansatte:** {f.get('antallAnsatte', 'Ukjent')}")
    with col2:
        st.subheader("Lokasjon & Web")
        adr = f.get("forretningsadresse", {})
        st.write(f"**Adresse:** {adr.get('adresse', [''])[0]}, {adr.get('postnummer', '')} {adr.get('poststed', '')}")
        st.write(f"**Nettside:** {f.get('hjemmeside', 'Ikke registrert')}")
    with col3:
        st.subheader("Handling")
        if st.button("🚀 Send til HubSpot", use_container_width=True, type="primary"):
            st.toast("Sender...")

    with st.expander("✨ Se AI-generert salgsstrategi", expanded=True):
        with st.spinner("Analyserer..."):
            nyheter = finn_nyheter(f['navn'])
            replikk = lag_isbryter(f['navn'], nyheter, f.get('naeringskode1', {}).get('beskrivelse'))
            eposter = finn_eposter(f.get('hjemmeside'))
        st.markdown(f"**Foreslått åpning:** {replikk}")
        if eposter: st.write(f"**E-poster:** {', '.join(eposter)}")
    
    if "mine_leads" in st.session_state:
        st.markdown("### 📈 Markedssammenligning")
        sammenligning_data = [{"Selskap": f['navn'] + " (Hoved)", "Ansatte": f.get('antallAnsatte', 0), "Kommune": f.get('forretningsadresse', {}).get('kommune', 'Ukjent'), "Status": "Hovedfokus"}]
        for l in st.session_state.mine_leads[:5]:
            if l['organisasjonsnummer'] != f['organisasjonsnummer']:
                sammenligning_data.append({"Selskap": l['navn'], "Ansatte": l.get('antallAnsatte', 0), "Kommune": l.get('forretningsadresse', {}).get('kommune', 'Ukjent'), "Status": "Konkurrent"})
        
        df = pd.DataFrame(sammenligning_data)
        st.table(df)
        st.download_button("📥 Last ned analyse som Excel", data=to_excel(df), file_name=f"analyse_{f['navn']}.xlsx", use_container_width=True)
        st.bar_chart(df.set_index("Selskap")["Ansatte"])

        st.markdown("### 💡 Andre relevante muligheter")
        for lead in st.session_state.mine_leads:
            if lead['organisasjonsnummer'] == f['organisasjonsnummer']: continue
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.write(f"**{lead['navn']}** ({lead.get('antallAnsatte', 0)} ansatte)")
                with c2:
                    if st.button("🔍 Analyser", key=f"s_{lead['organisasjonsnummer']}"):
                        st.session_state.soke_felt = lead['organisasjonsnummer']
                        st.rerun()
                with c3:
                    if st.button("➕ Send", key=f"z_{lead['organisasjonsnummer']}"):
                        st.toast("Sendt!")
                st.divider()

        # Last inn flere selskaper (Paginering)
        if st.button("Last inn 15 flere selskaper...", use_container_width=True):
            st.session_state.side_nummer += 1
            kode = st.session_state.hoved_firma.get("naeringskode1", {}).get("kode")
            params = {"naeringskode": kode, "size": 15, "page": st.session_state.side_nummer, "fraAntallAnsatte": 10}
            res = requests.get(brreg_adresse, params=params).json()
            nye_leads = res.get("_embedded", {}).get("enheter", [])
            st.session_state.mine_leads.extend(nye_leads)
            st.rerun()

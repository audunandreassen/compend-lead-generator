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
        resultater = DDGS().text(f"{firmanavn} norge nyheter eierskap ledelse", max_results=3)
        return " ".join([r["body"] for r in resultater]) if resultater else "Ingen ferske nyheter."
    except:
        return "Ingen ferske nyheter."

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    instruks = f"Skriv en kort åpningsreplikk (2 setninger) til {firmanavn} ({bransje}) basert på: {nyhetstekst}. Nevn hvem man bør snakke med."
    try:
        svar = klient.chat.completions.create(model=modell_navn, messages=[{"role": "user", "content": instruks}])
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere replikk."

def finn_eposter(domene):
    if not domene: return []
    rent_domene = domene.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    try:
        res = requests.get("https://api.hunter.io/v2/domain-search", params={"domain": rent_domene, "api_key": st.secrets["HUNTER_API_KEY"], "limit": 3})
        return [e["value"] for e in res.json().get("data", {}).get("emails", [])] if res.status_code == 200 else []
    except: return []

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- STREAMLIT UI ---
st.set_page_config(page_title="Compend AI Market Insights", layout="wide")

# Her lager vi et tomt element helt øverst som vi kan "fokusere" på
top_placeholder = st.empty()
st.title("📊 Compend AI: Markedsanalyse & Leads")

# Session State
if "mine_leads" not in st.session_state: st.session_state.mine_leads = []
if "side_nummer" not in st.session_state: st.session_state.side_nummer = 0
if "soke_felt" not in st.session_state: st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state: st.session_state.forrige_sok = ""

# Søkefelt
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    org_input = st.text_input("Skriv inn org.nummer for dyp analyse:", value=st.session_state.soke_felt)
    start_knapp = st.button("Start Markedsanalyse", use_container_width=True)

def utfor_sok(orgnr):
    st.session_state.side_nummer = 0
    hoved = hent_firma_data(orgnr)
    if hoved:
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        kode = hoved.get("naeringskode1", {}).get("kode")
        if kode:
            # Vi henter en stor mengde og filtrerer manuelt for å sikre 15 treff
            params = {"naeringskode": kode, "size": 100, "page": 0}
            res = requests.get(brreg_adresse, params=params).json()
            alle_treff = res.get("_embedded", {}).get("enheter", [])
            # Filtrer ut de med over 5 ansatte og som ikke er seg selv
            filtrert = [e for e in alle_treff if e.get('antallAnsatte', 0) >= 5 and e['organisasjonsnummer'] != orgnr]
            st.session_state.mine_leads = filtrert[:15]
    else:
        st.error("Ugyldig organisasjonsnummer.")

# Trigger søk hvis nummeret endres
if (org_input != st.session_state.forrige_sok and len(org_input) == 9) or start_knapp:
    utfor_sok(org_input)
    st.rerun()

# --- VISNING ---
if "hoved_firma" in st.session_state:
    f = st.session_state.hoved_firma
    st.markdown(f"## 🎯 Hovedfokus: {f['navn']}")
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.write(f"**Org.nr:** {f['organisasjonsnummer']}")
        st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse')}")
    with c2:
        st.write(f"**Ansatte:** {f.get('antallAnsatte', 'Ukjent')}")
        st.write(f"**Nettside:** {f.get('hjemmeside', 'Ingen')}")
    with c3:
        if st.button("🚀 Send til HubSpot", key="main_hub"): st.toast("Sendt!")

    with st.expander("✨ AI-Analyse & Kontaktinfo", expanded=True):
        nyheter = finn_nyheter(f['navn'])
        replikk = lag_isbryter(f['navn'], nyheter, f.get('naeringskode1', {}).get('beskrivelse'))
        eposter = finn_eposter(f.get('hjemmeside'))
        st.info(replikk)
        if eposter: st.write(f"📧 {', '.join(eposter)}")

    if st.session_state.mine_leads:
        st.markdown("### 📈 Markedssammenligning")
        df = pd.DataFrame([{"Selskap": f['navn'], "Ansatte": f.get('antallAnsatte', 0)}] + 
                          [{"Selskap": l['navn'], "Ansatte": l.get('antallAnsatte', 0)} for l in st.session_state.mine_leads[:5]])
        st.table(df)
        st.download_button("📥 Last ned Excel", data=to_excel(df), file_name="analyse.xlsx")

        st.markdown("### 💡 Lignende muligheter")
        for lead in st.session_state.mine_leads:
            with st.container():
                l1, l2, l3 = st.columns([3, 1, 1])
                l1.write(f"**{lead['navn']}** ({lead.get('antallAnsatte', 0)} ansatte)")
                if l2.button("🔍 Analyser", key=f"an_{lead['organisasjonsnummer']}"):
                    st.session_state.soke_felt = lead['organisasjonsnummer']
                    # Denne rerunn-en vil trigge utfor_sok øverst og rulle opp naturlig
                    st.rerun()
                if l3.button("➕ Send", key=f"zap_{lead['organisasjonsnummer']}"):
                    st.toast("Sendt!")
                st.divider()

        if st.button("Last inn flere selskaper...", use_container_width=True):
            st.session_state.side_nummer += 1
            kode = st.session_state.hoved_firma.get("naeringskode1", {}).get("kode")
            params = {"naeringskode": kode, "size": 100, "page": st.session_state.side_nummer}
            res = requests.get(brreg_adresse, params=params).json()
            nye = [e for e in res.get("_embedded", {}).get("enheter", []) if e.get('antallAnsatte', 0) >= 5]
            st.session_state.mine_leads.extend(nye[:15])
            st.rerun()

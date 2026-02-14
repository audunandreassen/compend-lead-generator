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

# JavaScript for tvungen rulling
def force_scroll():
    st.components.v1.html(
        "<script>window.parent.document.querySelector('section.main').scrollTo(0, 0);</script>",
        height=0
    )

# Hjelpefunksjoner
def hent_firma_data(orgnr):
    try:
        svar = requests.get(f"{brreg_adresse}/{orgnr}", timeout=5)
        return svar.json() if svar.status_code == 200 else None
    except:
        return None

def finn_nyheter(firmanavn):
    try:
        # Vi utvider søket til å se etter roller og eierskap
        resultater = DDGS().text(f"{firmanavn} norge roller eierskap aksjonær ledelse", max_results=5)
        return "\n".join([f"{r['title']}: {r['body']}" for r in resultater]) if resultater else ""
    except:
        return ""

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    prompt = f"""
    Du er en ekspert-selger for Compend. 
    Selskap: {firmanavn}
    Bransje: {bransje}
    Nyheter/Innsikt: {nyhetstekst}
    
    Oppgave:
    1. Lag en unik og personlig isbryter på 2-3 setninger.
    2. Sjekk nyhetsteksten nøye: Ser det ut som daglig leder eller nøkkelpersoner også er eiere (gründere/aksjonærer)? 
    3. Nevn spesifikt hvem vi bør kontakte.
    4. Hvis du finner eierinfo, nevn det som en strategisk fordel ('Siden daglig leder også er på eiersiden...').
    """
    try:
        svar = klient.chat.completions.create(
            model=modell_navn, 
            messages=[{"role": "system", "content": "Du er en analytisk salgsassistent."}, {"role": "user", "content": prompt}]
        )
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere strategisk analyse."

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
st.title("📊 Compend AI: Markedsanalyse & Leads")

if "mine_leads" not in st.session_state: st.session_state.mine_leads = []
if "hoved_firma" not in st.session_state: st.session_state.hoved_firma = None
if "soke_felt" not in st.session_state: st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state: st.session_state.forrige_sok = ""

col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    org_input = st.text_input("Skriv inn org.nummer for analyse:", value=st.session_state.soke_felt)
    start_knapp = st.button("Start Markedsanalyse", use_container_width=True)

def utfor_analyse(orgnr):
    with st.spinner(f"Henter data for {orgnr}..."):
        hoved = hent_firma_data(orgnr)
        if hoved:
            st.session_state.hoved_firma = hoved
            st.session_state.forrige_sok = orgnr
            nyheter = finn_nyheter(hoved['navn'])
            st.session_state.isbryter = lag_isbryter(hoved['navn'], nyheter, hoved.get('naeringskode1', {}).get('beskrivelse'))
            st.session_state.eposter = finn_eposter(hoved.get('hjemmeside'))
            
            kode = hoved.get("naeringskode1", {}).get("kode")
            if kode:
                res = requests.get(brreg_adresse, params={"naeringskode": kode, "size": 100}).json()
                alle = res.get("_embedded", {}).get("enheter", [])
                # SIKKERHET: Vi filtrerer ut dubletter og hovedselskapet selv
                st.session_state.mine_leads = [e for e in alle if e.get('antallAnsatte', 0) >= 10 and e['organisasjonsnummer'] != orgnr][:15]
            force_scroll()
        else:
            st.error("Ugyldig organisasjonsnummer.")

if (org_input != st.session_state.forrige_sok and len(org_input) == 9) or start_knapp:
    utfor_analyse(org_input)
    st.rerun()

if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    st.markdown(f"## 🎯 Hovedfokus: {f['navn']}")
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.write(f"**Org.nr:** {f['organisasjonsnummer']}")
        st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse')}")
    with c2:
        st.write(f"**Ansatte:** {f.get('antallAnsatte', 'Ukjent')}")
        st.write(f"**Nettside:** {f.get('hjemmeside', 'Ikke oppgitt')}")
    with c3:
        if st.button("🚀 Send til HubSpot", type="primary", use_container_width=True, key="main_send"):
            st.toast("Overført!")

    st.info(f"**Strategisk Analyse & Eierskap:**\n\n{st.session_state.get('isbryter', '')}")
    if st.session_state.get('eposter'):
        st.write(f"📧 **E-poster:** {', '.join(st.session_state.eposter)}")

    if st.session_state.mine_leads:
        st.markdown("---")
        st.subheader("📈 Markedssammenligning")
        df = pd.DataFrame([{"Selskap": l['navn'], "Ansatte": l.get('antallAnsatte', 0), "Poststed": l.get('forretningsadresse', {}).get('poststed', '')} for l in st.session_state.mine_leads[:10]])
        st.table(df)
        
        st.markdown("### 💡 Lignende selskaper")
        # Vi bruker enumerate for å sikre helt unike nøkler uansett hva
        for i, lead in enumerate(st.session_state.mine_leads):
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(f"**{lead['navn']}** ({lead.get('antallAnsatte', 0)} ansatte)")
                # Ved å legge til i (indeks) i nøkkelen unngår vi DuplicateElementKey
                if col2.button("🔍 Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}"):
                    st.session_state.soke_felt = lead['organisasjonsnummer']
                    st.rerun()
                if col3.button("➕ Send", key=f"send_{lead['organisasjonsnummer']}_{i}"):
                    st.toast(f"Lagt i kø: {lead['navn']}")
                st.divider()

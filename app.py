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
        return "\n".join([f"{r['title']}: {r['body']}" for r in resultater]) if resultater else ""
    except:
        return ""

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    # Her ber vi om en mye mer nøkternt og profesjonelt svar
    prompt = f"""
    Du er en salgsstrateg for Compend. 
    Selskap: {firmanavn}
    Bransje: {bransje}
    Nyhetsinnsikt: {nyhetstekst}
    
    Oppgave:
    1. Lag en konkret isbryter på 2 setninger. Unngå "Hei [Navn]". Gå rett på sak.
    2. Hvis nyhetene nevner spesifikke utfordringer eller prosjekter, nevn disse.
    3. Gi et råd om hvem man bør kontakte. Hvis du ikke har et navn, foreslå en tittel (f.eks. Daglig leder).
    4. ALDRI gjett på navn eller bruk klammer som [Navn]. Hvis informasjonen mangler, snakk generelt om rollen.
    """
    try:
        svar = klient.chat.completions.create(
            model=modell_navn, 
            messages=[{"role": "system", "content": "Du er en profesjonell rådgiver som aldri gjetter på data du ikke har."}, {"role": "user", "content": prompt}]
        )
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

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- STREAMLIT UI ---
st.set_page_config(page_title="Compend Lead-Maskin", layout="wide")

# JavaScript for tvungen rulling som kjøres HVER gang siden tegnes
st.components.v1.html(
    "<script>window.parent.document.querySelector('section.main').scrollTo(0, 0);</script>",
    height=0
)

st.title("📊 Compend AI: Markedsanalyse")

if "mine_leads" not in st.session_state: st.session_state.mine_leads = []
if "hoved_firma" not in st.session_state: st.session_state.hoved_firma = None
if "soke_felt" not in st.session_state: st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state: st.session_state.forrige_sok = ""

# Søkefelt
col_l, col_m, col_r = st.columns([1, 2, 1])
with col_m:
    org_input = st.text_input("Skriv inn org.nummer for analyse:", value=st.session_state.soke_felt)
    start_knapp = st.button("Start Markedsanalyse", use_container_width=True)

def utfor_analyse(orgnr):
    with st.spinner(f"Henter fakta om {orgnr}..."):
        hoved = hent_firma_data(orgnr)
        if hoved:
            st.session_state.hoved_firma = hoved
            st.session_state.forrige_sok = orgnr
            # Hent innsikt
            nyheter = finn_nyheter(hoved['navn'])
            st.session_state.isbryter = lag_isbryter(hoved['navn'], nyheter, hoved.get('naeringskode1', {}).get('beskrivelse', 'Ukjent bransje'))
            st.session_state.eposter = finn_eposter(hoved.get('hjemmeside'))
            
            # Hent lignende selskaper
            kode = hoved.get("naeringskode1", {}).get("kode")
            if kode:
                res = requests.get(brreg_adresse, params={"naeringskode": kode, "size": 100}).json()
                alle = res.get("_embedded", {}).get("enheter", [])
                st.session_state.mine_leads = [e for e in alle if e.get('antallAnsatte', 0) >= 10 and e['organisasjonsnummer'] != orgnr][:15]
        else:
            st.error("Ugyldig organisasjonsnummer.")

if (org_input != st.session_state.forrige_sok and len(org_input) == 9) or start_knapp:
    utfor_analyse(org_input)
    st.rerun()

# --- VISNING ---
if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    st.markdown(f"## 🎯 {f['navn']}")
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        st.write(f"**Org.nr:** {f['organisasjonsnummer']}")
        st.write(f"**Form:** {f.get('organisasjonsform', {}).get('beskrivelse', 'AS')}")
    with c2:
        st.write(f"**Ansatte:** {f.get('antallAnsatte', 'Ukjent')}")
        st.write(f"**Bransje:** {f.get('naeringskode1', {}).get('beskrivelse', 'Ukjent')}")
    with c3:
        if st.button("🚀 Send til CRM", type="primary", use_container_width=True, key="main_hub"):
            st.toast("Lead sendt!")

    st.info(st.session_state.get('isbryter', 'Ingen analyse tilgjengelig.'))
    
    if st.session_state.get('eposter'):
        st.write(f"📧 **Kontaktadresser funnet:** {', '.join(st.session_state.eposter)}")

    if st.session_state.mine_leads:
        st.markdown("---")
        st.subheader("📈 Markedssammenligning")
        df = pd.DataFrame([{"Selskap": l['navn'], "Ansatte": l.get('antallAnsatte', 0), "Sted": l.get('forretningsadresse', {}).get('poststed', '')} for l in st.session_state.mine_leads[:5]])
        st.table(df)
        
        st.markdown("### 💡 Andre selskaper i samme bransje")
        for i, lead in enumerate(st.session_state.mine_leads):
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                col1.write(f"**{lead['navn']}** ({lead.get('antallAnsatte', 0)} ansatte)")
                if col2.button("🔍 Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}"):
                    st.session_state.soke_felt = lead['organisasjonsnummer']
                    st.rerun()
                if col3.button("➕ Send", key=f"zap_{lead['organisasjonsnummer']}_{i}"):
                    st.toast(f"Lagt i kø: {lead['navn']}")
                st.divider()

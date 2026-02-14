import streamlit as st
import requests
from duckduckgo_search import DDGS
import openai

brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"

# Her henter vi nøkkelen trygt fra Streamlit sin bankboks!
openai.api_key = st.secrets["OPENAI_API_KEY"]

def finn_nyheter(firmanavn):
    try:
        resultater = DDGS().text(f"{firmanavn} norge nyheter", max_results=2)
        if resultater:
            innhold = resultater[0]["body"]
            if len(resultater) > 1:
                innhold += " " + resultater[1]["body"]
            return innhold
        else:
            return "Fant ingen store nyheter om selskapet nylig."
    except Exception:
        return "Klarte ikke å søke etter nyheter."

def lag_ekte_isbryter(firmanavn, nyhetstekst):
    if "Fant ingen store nyheter" in nyhetstekst or "Klarte ikke" in nyhetstekst:
        return f"Hei! Vi ser at det er god aktivitet hos {firmanavn} om dagen. Hvordan rigger dere bedriften for å sikre at de ansatte har oppdatert kompetanse?"
    
    instruks = f"Du er en dyktig og hyggelig selger for Compend. Compend selger en plattform for kurs og opplæring. Her er litt fersk informasjon om bedriften {firmanavn}: {nyhetstekst} Din oppgave: Skriv en kort åpningsreplikk på maksimalt to setninger som bruker denne informasjonen for å starte en salgssamtale."
    
    try:
        svar = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": instruks}]
        )
        return svar.choices[0].message.content
    except Exception:
        return f"Hei! Hvordan jobber dere i {firmanavn} med systematisk opplæring i dag?"

st.title("Compend Lead Generator")

if "mine_leads" not in st.session_state:
    st.session_state.mine_leads = []

orgnummer = st.text_input("Organisasjonsnummer (9 siffer):")

if st.button("Finn leads til Compend"):
    svar = requests.get(f"{brreg_adresse}/{orgnummer}")
    
    if svar.status_code == 200:
        firma = svar.json()
        
        if "naeringskode1" in firma:
            kode = firma["naeringskode1"]["kode"]
            parameter = {"naeringskode": kode, "size": 10}
            lignende_svar = requests.get(brreg_adresse, params=parameter)
            lignende_data = lignende_svar.json()
            
            if "_embedded" in lignende_data:
                st.session_state.mine_leads = lignende_data["_embedded"]["enheter"]
        else:
            st.warning("Fant ingen bransjekode.")
    else:
        st.error("Ugyldig organisasjonsnummer.")

if len(st.session_state.mine_leads) > 0:
    st.write("Her er ti potensielle kunder i samme bransje:")
    
    for treff in st.session_state.mine_leads:
        nytt_firma = treff["navn"]
        nytt_orgnr = treff["organisasjonsnummer"]
        
        with st.container():
            st.subheader(nytt_firma)
            st.write(f"Organisasjonsnummer: {nytt_orgnr}")
            
            with st.spinner("Leter etter nyheter og skriver replikk..."):
                nyheter = finn_nyheter(nytt_firma)
                replikk = lag_ekte_isbryter(nytt_firma, nyheter)
            
            st.info(f"Forslag til selger: {replikk}")
            
            if st.button(f"Send {nytt_firma} til HubSpot", key=nytt_orgnr):
                lead_pakke = {
                    "firma": nytt_firma,
                    "organisasjonsnummer": nytt_orgnr,
                    "isbryter": replikk
                }
                requests.post(zapier_mottaker, json=lead_pakke)
                st.success(f"Suksess! {nytt_firma} ble sendt til HubSpot via Zapier.")
            
            st.divider()

import streamlit as st
import requests
from duckduckgo_search import DDGS
from openai import OpenAI

brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"

# Vi oppdaterer oppkoblingen til nyeste metode
klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Vi bygger modellnavnet slik for å unngå spesialtegn i koden
modell_navn = "gpt" + chr(45) + "4o" + chr(45) + "mini"

def finn_nyheter(firmanavn):
    try:
        resultater = DDGS().text(f"{firmanavn} norge nyheter", max_results=2)
        if resultater:
            innhold = resultater[0]["body"]
            if len(resultater) > 1:
                innhold += " " + resultater[1]["body"]
            return innhold
        else:
            return "Ingen ferske nyheter."
    except Exception:
        return "Ingen ferske nyheter."

def lag_ekte_isbryter(firmanavn, nyhetstekst, bransje):
    instruks = f"Du er en dyktig og hyggelig selger for Compend. Compend selger en plattform for kurs og opplæring. Selskapet {firmanavn} opererer i denne bransjen: '{bransje}'. Nyheter om selskapet: '{nyhetstekst}'. Din oppgave: Skriv en kort åpningsreplikk på maksimalt to setninger for en telefonsamtale. Finn en naturlig vinkel for å selge inn et læringssystem. Hvis nyhetene er tomme, lag replikken utelukkende basert på opplæringsbehov, sertifiseringer eller utfordringer som er helt typiske for bransjen '{bransje}'."
    
    try:
        svar = klient.chat.completions.create(
            model=modell_navn,
            messages=[{"role": "user", "content": instruks}]
        )
        return svar.choices[0].message.content
    except Exception as feilmelding:
        # Her fanger vi den faktiske feilen og viser den til deg!
        return f"Systemfeil fra maskinen: {feilmelding}"

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
        
        bransje_navn = treff.get("naeringskode1", {}).get("beskrivelse", "Ukjent bransje")
        
        with st.container():
            st.subheader(nytt_firma)
            st.write(f"Organisasjonsnummer: {nytt_orgnr}")
            st.write(f"Bransje: {bransje_navn}")
            
            with st.spinner("Leter etter nyheter og skriver replikk..."):
                nyheter = finn_nyheter(nytt_firma)
                replikk = lag_ekte_isbryter(nytt_firma, nyheter, bransje_navn)
            
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

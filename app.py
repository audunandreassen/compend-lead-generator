import streamlit as st
import requests
from duckduckgo_search import DDGS
from openai import OpenAI

brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"

klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
modell_navn = "gpt" + chr(45) + "4o" + chr(45) + "mini"

def finn_eposter(domene):
    if not domene:
        return []
        
    rent_domene = domene.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    hunter_url = "https://api.hunter.io/v2/domain" + chr(45) + "search"
    
    if "HUNTER_API_KEY" in st.secrets:
        hunter_nokkel = st.secrets["HUNTER_API_KEY"]
        parametere = {"domain": rent_domene, "api_key": hunter_nokkel, "limit": 3}
        
        try:
            hunter_svar = requests.get(hunter_url, params=parametere)
            if hunter_svar.status_code == 200:
                data = hunter_svar.json()
                eposter = [epost["value"] for epost in data.get("data", {}).get("emails", [])]
                return eposter
            else:
                return [f"Feilkode fra Hunter: {hunter_svar.status_code}"]
        except Exception as feilmelding:
            return [f"Klarte ikke koble til: {feilmelding}"]
            
    return ["Mangler Hunter passord i bankboksen."]

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
    instruks = f"Du er en dyktig og hyggelig selger for Compend. Compend selger en plattform for kurs og opplæring. Selskapet {firmanavn} opererer i denne bransjen: '{bransje}'. Nyheter om selskapet: '{nyhetstekst}'. Din oppgave: Skriv en kort åpningsreplikk på maksimalt to setninger for en telefonsamtale. Finn en naturlig vinkel for å selge inn et læringssystem. Legg deretter til en tredje og siste setning der du foreslår nøyaktig hvilken rolle selgeren bør be om å få snakke med hos kunden."
    
    try:
        svar = klient.chat.completions.create(
            model=modell_navn,
            messages=[{"role": "user", "content": instruks}]
        )
        return svar.choices[0].message.content
    except Exception as feilmelding:
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
        nettside = treff.get("hjemmeside", "")
        antall_ansatte = treff.get("antallAnsatte", 0)
        
        adresse_data = treff.get("forretningsadresse", {})
        gateadresse = ", ".join(adresse_data.get("adresse", ["Ukjent"]))
        postnummer = adresse_data.get("postnummer", "")
        poststed = adresse_data.get("poststed", "")
        full_adresse = f"{gateadresse}, {postnummer} {poststed}"
        
        with st.container():
            st.subheader(nytt_firma)
            st.write(f"Organisasjonsnummer: {nytt_orgnr}")
            st.write(f"Bransje: {bransje_navn}")
            st.write(f"Ansatte: {antall_ansatte}")
            
            if nettside:
                if not nettside.startswith("http"):
                    nettside_visning = "https://" + nettside
                else:
                    nettside_visning = nettside
                st.markdown(f"[Besøk nettsiden til {nytt_firma}]({nettside_visning})")
            
            with st.spinner("Leter etter nyheter, kontaktinfo og skriver replikk..."):
                nyheter = finn_nyheter(nytt_firma)
                replikk = lag_ekte_isbryter(nytt_firma, nyheter, bransje_navn)
                funnede_eposter = finn_eposter(nettside)
            
            if funnede_eposter:
                st.write("Resultat fra Hunter:")
                for epost in funnede_eposter:
                    st.write(f"* {epost}")
            else:
                st.write("Hunter fant ingen eposter automatisk.")
            
            st.info(f"Forslag til selger: {replikk}")
            
            if st.button(f"Send {nytt_firma} til HubSpot", key=nytt_orgnr):
                epost_tekst = ", ".join(funnede_eposter)
                lead_pakke = {
                    "firma": nytt_firma,
                    "organisasjonsnummer": nytt_orgnr,
                    "isbryter": replikk,
                    "eposter": epost_tekst,
                    "bransje": bransje_navn,
                    "ansatte": antall_ansatte,
                    "adresse": full_adresse,
                    "nettside": nettside
                }
                requests.post(zapier_mottaker, json=lead_pakke)
                st.success(f"Suksess! {nytt_firma} ble sendt til HubSpot via Zapier.")
            
            st.divider()

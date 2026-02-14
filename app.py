import streamlit as st
import requests

# Nettadressene vi trenger
brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "DIN_ZAPIER_ADRESSE_HER"

# En liten hjelpemotor som later som den er kunstig intelligens for prototypen
def lag_isbryter(firmanavn):
    return f"Hei! Vi ser at det er god aktivitet hos {firmanavn} om dagen. Hvordan rigger dere bedriften for å sikre at de ansatte har oppdatert kompetanse?"

st.title("Compend Lead Generator")
st.write("Skriv inn et organisasjonsnummer for å finne tilsvarende selskaper med ferdige salgsreplikker.")

orgnummer = st.text_input("Organisasjonsnummer (9 siffer):")

if st.button("Finn leads til Compend"):
    svar = requests.get(f"{brreg_adresse}/{orgnummer}")
    
    if svar.status_code == 200:
        firma = svar.json()
        
        if "naeringskode1" in firma:
            kode = firma["naeringskode1"]["kode"]
            beskrivelse = firma["naeringskode1"]["beskrivelse"]
            
            st.success(f"Fant bransjen: {beskrivelse}")
            st.write("Her er ti potensielle kunder i samme bransje:")
            
            # Vi ber om ti selskaper fra samme bransje
            parameter = {"naeringskode": kode, "size": 10}
            lignende_svar = requests.get(brreg_adresse, params=parameter)
            lignende_data = lignende_svar.json()
            
            if "_embedded" in lignende_data:
                treff_liste = lignende_data["_embedded"]["enheter"]
                
                # Nå går vi gjennom alle de ti selskapene ett for ett
                for treff in treff_liste:
                    nytt_firma = treff["navn"]
                    nytt_orgnr = treff["organisasjonsnummer"]
                    
                    # 1. Her skaper vi åpningsreplikken for dette spesifikke selskapet
                    replikk = lag_isbryter(nytt_firma)
                    
                    # 2. Vi tegner en pen, innpakket boks for hvert selskap på nettsiden
                    with st.container():
                        st.subheader(nytt_firma)
                        st.write(f"Organisasjonsnummer: {nytt_orgnr}")
                        st.info(f"Forslag til selger: {replikk}")
                        
                        # 3. Vi lager eksportknappen
                        # Vi må gi knappen en unik nøkkel (orgnummer) slik at systemet vet hvilken som trykkes
                        if st.button(f"Send {nytt_firma} til HubSpot", key=nytt_orgnr):
                            
                            # Pakker dataene og sender dem avgårde
                            lead_pakke = {
                                "firma": nytt_firma,
                                "organisasjonsnummer": nytt_orgnr,
                                "isbryter": replikk
                            }
                            requests.post(zapier_mottaker, json=lead_pakke)
                            
                            st.success("Lead sendt til HubSpot via Zapier!")
                            
                        # Vi legger inn en skillelinje for å gjøre listen pen og ryddig
                        st.divider()

        else:
            st.warning("Fant ingen bransjekode.")
    else:
        st.error("Ugyldig organisasjonsnummer.")

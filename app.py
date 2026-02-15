import streamlit as st
import streamlit.components.v1 as components
from streamlit_searchbox import st_searchbox
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

# --- DESIGN OG STYLING ---
def bruk_stil():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #003642;
            background-color: #f7f9fb;
        }

        .stApp {
            background-color: #f7f9fb;
        }

        .block-container {
            padding-top: 2rem;
            max-width: 960px;
        }

        /* --- Knapper --- */
        .stButton>button {
            background-color: #368373;
            color: white;
            border-radius: 8px;
            border: none;
            padding: 10px 24px;
            transition: all 0.2s ease;
            font-weight: 500;
            font-size: 0.9rem;
            letter-spacing: 0.01em;
        }

        .stButton>button:hover {
            background-color: #2a6a5c;
            color: white;
            border: none;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(54, 131, 115, 0.3);
        }

        .stButton>button:active {
            transform: translateY(0);
        }


        /* --- Input-felt --- */
        .stTextInput>div>div>input {
            background-color: #FFFFFF !important;
            border-radius: 8px;
            border: 1.5px solid #d0dde3;
            padding: 12px 20px;
            color: #003642;
            font-size: 0.95rem;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .stTextInput>div>div>input:focus {
            border-color: #368373 !important;
            box-shadow: 0 0 0 3px rgba(54, 131, 115, 0.12) !important;
        }

        /* --- Alerts / Info-bokser --- */
        .stAlert {
            background-color: #ffffff !important;
            border: 1px solid #d0dde3 !important;
            border-left: 4px solid #368373 !important;
            color: #003642;
            border-radius: 8px;
            padding: 1rem 1.5rem;
            line-height: 1.6;
        }

        /* --- Overskrifter --- */
        h1, h2, h3 {
            color: #003642;
            font-weight: 700;
        }

        h1 {
            font-size: 1.6rem !important;
        }

        h2 {
            font-size: 1.2rem !important;
            font-weight: 600;
        }

        hr {
            border: 0;
            border-top: 1px solid #e0e7ec;
            margin: 1.5rem 0;
        }

        /* --- Kort-styling (st.container med border) --- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-radius: 12px !important;
            border: 1px solid #e0e7ec !important;
            box-shadow: 0 1px 3px rgba(0, 54, 66, 0.06), 0 1px 2px rgba(0, 54, 66, 0.04);
        }

        .firma-badge {
            display: inline-block;
            background: #eef6f4;
            color: #368373;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 500;
            margin-bottom: 1rem;
        }

        .firma-detaljer {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.6rem 2rem;
            margin-top: 1rem;
        }

        .firma-detaljer .detalj {
            font-size: 0.88rem;
            color: #4a6a72;
        }

        .firma-detaljer .detalj strong {
            color: #003642;
            font-weight: 600;
        }

        /* --- Analyse-kort --- */
        .analyse-kort {
            background: linear-gradient(135deg, #003642 0%, #0a4f5c 100%);
            border-radius: 12px;
            padding: 1.5rem 1.8rem;
            color: #ffffff;
            margin: 1rem 0;
            line-height: 1.7;
            font-size: 0.92rem;
        }

        .analyse-kort .analyse-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: rgba(255,255,255,0.6);
            margin-bottom: 0.5rem;
            font-weight: 600;
        }

        /* --- Lead-kort (st.container med border) --- */

        .lead-navn {
            font-weight: 600;
            color: #003642;
            font-size: 0.92rem;
        }

        .lead-info {
            color: #6b8a93;
            font-size: 0.82rem;
            margin-top: 2px;
        }

        .lead-ansatte {
            display: inline-block;
            background: #eef6f4;
            color: #368373;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-left: 8px;
        }

        .lead-why-now {
            margin-top: 0.7rem;
            font-size: 0.82rem;
            color: #23444d;
            line-height: 1.55;
            background: #f7fbfa;
            border: 1px solid #e0ece8;
            border-radius: 8px;
            padding: 0.7rem 0.8rem;
        }

        .score-kort {
            margin-top: 0.6rem;
            border: 1px solid #e0e7ec;
            border-radius: 8px;
            padding: 0.6rem 0.75rem;
            background: #ffffff;
        }

        .score-kort .score-title {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #6b8a93;
            font-weight: 600;
        }

        .score-kort .score-value {
            font-size: 1rem;
            font-weight: 700;
            color: #003642;
            margin: 0.1rem 0 0.35rem 0;
        }

        .score-kort ul {
            margin: 0;
            padding-left: 1rem;
            color: #37535b;
            font-size: 0.8rem;
            line-height: 1.45;
        }

        /* --- Header --- */
        .app-header {
            text-align: center;
            padding: 1rem 0 2rem 0;
        }

        .app-header h1 {
            font-size: 1.8rem !important;
            font-weight: 700;
            color: #003642;
            margin-bottom: 0.3rem;
        }

        .app-header p {
            color: #6b8a93;
            font-size: 0.95rem;
            margin: 0;
        }

        /* --- Seksjon-headers --- */
        .seksjon-header {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #6b8a93;
            font-weight: 600;
            margin-bottom: 0.8rem;
            margin-top: 1.5rem;
        }

        /* --- HubSpot-knapp spesialstyling --- */
        .hubspot-btn button {
            background-color: #003642 !important;
            border-radius: 8px !important;
        }

        .hubspot-btn button:hover {
            background-color: #00252e !important;
            box-shadow: 0 4px 12px rgba(0, 54, 66, 0.3) !important;
        }

        /* --- Success-melding --- */
        .stSuccess {
            background-color: #eef6f4 !important;
            border: 1px solid #368373 !important;
            color: #003642 !important;
            border-radius: 8px;
        }

        /* --- Spinner / loading --- */
        .stSpinner > div {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.8rem;
        }

        .stSpinner > div > div {
            border-top-color: #368373 !important;
        }

        .stSpinner > div > span {
            color: #003642 !important;
            font-size: 0.9rem;
            font-weight: 500;
        }

        /* --- Skjul Streamlit-elementer --- */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# --- APP START ---
st.set_page_config(page_title="Compend Insights", layout="wide")
bruk_stil()

# Header
st.markdown("""
    <div class="app-header">
        <h1>Compend Insights</h1>
        <p>Finn, analyser og kvalifiser nye leads</p>
    </div>
""", unsafe_allow_html=True)

if "mine_leads" not in st.session_state:
    st.session_state.mine_leads = []
if "hoved_firma" not in st.session_state:
    st.session_state.hoved_firma = None
if "soke_felt" not in st.session_state:
    st.session_state.soke_felt = ""
if "forrige_sok" not in st.session_state:
    st.session_state.forrige_sok = ""
if "auto_analyse_orgnr" not in st.session_state:
    st.session_state.auto_analyse_orgnr = None
if "scroll_topp" not in st.session_state:
    st.session_state.scroll_topp = False

# Hjelpefunksjoner
def hent_firma_data(orgnr):
    try:
        svar = requests.get(f"{brreg_adresse}/{orgnr}", timeout=5)
        return svar.json() if svar.status_code == 200 else None
    except:
        return None

def sok_firma_navn(navn):
    try:
        svar = requests.get(brreg_adresse, params={"navn": navn, "size": 8}, timeout=5)
        if svar.status_code == 200:
            return svar.json().get("_embedded", {}).get("enheter", [])
    except:
        pass
    return []

def finn_nyheter(firmanavn):
    try:
        resultater = DDGS().text(f"{firmanavn} norge nyheter strategi ledelse", max_results=5)
        return "\n".join([r['body'] for r in resultater]) if resultater else ""
    except:
        return ""

def lag_isbryter(firmanavn, nyhetstekst, bransje):
    prompt = f"""
    Du er en salgsstrateg for Compend (www.compend.no). 
    Compend leverer plattformer for kurs, opplæring og kompetanseutvikling (LMS).
    Selskap: {firmanavn}
    Bransje: {bransje}
    Innsikt: {nyhetstekst}
    OPPGAVE:
    Skriv en analyse på maks 3 korte setninger som selgeren kan bruke. 
    1. Ingen hilsener eller emojier. 
    2. KNYTT innsikten direkte til Compends løsninger.
    3. Foreslå en konkret tittel å kontakte.
    """
    try:
        svar = klient.chat.completions.create(
            model=modell_navn, 
            messages=[
                {
                    "role": "system",
                    "content": "Du er en profesjonell salgsrådgiver for Compend. Du bruker aldri emojier."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return svar.choices[0].message.content
    except:
        return "Kunne ikke generere analyse."

def finn_eposter(domene):
    if not domene:
        return []
    rent_domene = (
        domene.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
    )
    try:
        res = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain": rent_domene,
                "api_key": st.secrets["HUNTER_API_KEY"],
                "limit": 5,
            },
        )
        return [
            e["value"] for e in res.json().get("data", {}).get("emails", [])
        ] if res.status_code == 200 else []
    except:
        return []

def formater_adresse(f):
    adr = f.get("forretningsadresse", {})
    if not adr:
        return "Ingen adresse registrert"
    gate = adr.get("adresse", [""])[0]
    post = f"{adr.get('postnummer', '')} {adr.get('poststed', '')}"
    return f"{gate}, {post}".strip(", ")

def bygg_leadscore(lead, hoved_firma):
    lead_ansatte = lead.get("antallAnsatte") or 0
    hoved_ansatte = hoved_firma.get("antallAnsatte") or 0

    lead_bransjekode = lead.get("naeringskode1", {}).get("kode")
    hoved_bransjekode = hoved_firma.get("naeringskode1", {}).get("kode")
    samme_bransje = bool(lead_bransjekode and lead_bransjekode == hoved_bransjekode)

    lead_kommune = lead.get("forretningsadresse", {}).get("kommunenummer")
    hoved_kommune = hoved_firma.get("forretningsadresse", {}).get("kommunenummer")
    samme_kommune = bool(lead_kommune and lead_kommune == hoved_kommune)

    nettside = lead.get("hjemmeside") or ""

    # Passformscore: hvor godt leadet matcher hovedselskapet i størrelse og segment
    passformscore = 35
    if samme_bransje:
        passformscore += 35
    if lead_ansatte >= 20:
        passformscore += 15
    if abs(lead_ansatte - hoved_ansatte) <= 50:
        passformscore += 10
    if nettside:
        passformscore += 5
    passformscore = max(0, min(100, passformscore))

    # Intentscore: sannsynlighet for at timing er riktig
    intentscore = 30
    if lead_ansatte >= 50:
        intentscore += 20
    elif lead_ansatte >= 20:
        intentscore += 10
    if samme_kommune:
        intentscore += 15
    if nettside:
        intentscore += 10
    if lead_ansatte > hoved_ansatte:
        intentscore += 10
    intentscore = max(0, min(100, intentscore))

    bransjetekst = "Samme bransjekode som valgt selskap" if samme_bransje else "Nærliggende bransje med lignende opplæringsbehov"
    geotekst = "Lokalt selskap i samme kommune" if samme_kommune else "Kan prioriteres nasjonalt ved kapasitetsbehov"

    hvorfor_na = (
        f"{lead.get('navn', 'Selskapet')} har {lead_ansatte} ansatte"
        " og kan ha behov for strukturert onboarding og kompetanseheving. "
        f"{geotekst}."
    )

    return {
        "passformscore": passformscore,
        "intentscore": intentscore,
        "passform_grunner": [
            bransjetekst,
            f"Størrelse: {lead_ansatte} ansatte",
            "Egen nettside gjør aktivering enklere" if nettside else "Manglende nettside trekker litt ned",
        ],
        "intent_grunner": [
            "Vekstindikator: over 50 ansatte" if lead_ansatte >= 50 else "Modent nok selskap for strukturert læring",
            geotekst,
            "Har digital tilstedeværelse" if nettside else "Begrenset digital tilstedeværelse",
        ],
        "hvorfor_na": hvorfor_na,
    }

def scroll_til_toppen():
    components.html(
        """
        <script>
            window.parent.scrollTo({ top: 0, behavior: "smooth" });
        </script>
        """,
        height=0,
    )

def utfor_analyse(orgnr):
    hoved = hent_firma_data(orgnr)
    if hoved:
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        firmanavn = hoved.get("navn", "Ukjent")
        nyheter = finn_nyheter(firmanavn)
        st.session_state.isbryter = lag_isbryter(
            firmanavn,
            nyheter,
            hoved.get("naeringskode1", {}).get("beskrivelse", "Ukjent"),
        )
        st.session_state.eposter = finn_eposter(hoved.get("hjemmeside"))
        
        kode = hoved.get("naeringskode1", {}).get("kode")
        if kode:
            antall = hoved.get("antallAnsatte") or 0
            params = {
                "naeringskode": kode,
                "sort": "antallAnsatte,desc",
                "fraAntallAnsatte": 5,
                "size": 50,
            }
            # Filtrer på kommune hvis tilgjengelig
            kommune = hoved.get("forretningsadresse", {}).get("kommunenummer")
            if kommune:
                params["kommunenummer"] = kommune

            res = requests.get(brreg_adresse, params=params).json()
            alle = res.get("_embedded", {}).get("enheter", [])
            leads = [e for e in alle if e["organisasjonsnummer"] != orgnr]

            # Hvis kommune-søk ga for få resultater, utvid til hele landet
            if len(leads) < 10 and kommune:
                del params["kommunenummer"]
                res2 = requests.get(brreg_adresse, params=params).json()
                alle2 = res2.get("_embedded", {}).get("enheter", [])
                eksisterende = {e["organisasjonsnummer"] for e in leads}
                for e in alle2:
                    if e["organisasjonsnummer"] != orgnr and e["organisasjonsnummer"] not in eksisterende:
                        leads.append(e)

            st.session_state.mine_leads = leads
    else:
        st.error("Ugyldig organisasjonsnummer.")

def sok_brreg(soketekst):
    if not soketekst or len(soketekst) < 2:
        return []
    tekst = soketekst.strip()
    # Orgnr-søk
    if tekst.isdigit() and len(tekst) == 9:
        firma = hent_firma_data(tekst)
        if firma:
            return [(firma.get("navn", "Ukjent") + "  ·  " + tekst, tekst)]
        return []
    # Navnesøk
    treff = sok_firma_navn(tekst)
    resultater = []
    for t in treff:
        poststed = t.get("forretningsadresse", {}).get("poststed", "")
        ansatte = t.get("antallAnsatte", 0)
        orgnr = t.get("organisasjonsnummer", "")
        label = f"{t['navn']}  ·  {poststed}  ·  {ansatte} ansatte  ·  {orgnr}"
        resultater.append((label, orgnr))
    return resultater

# Søkefelt
col_l, col_m, col_r = st.columns([1, 3, 1])
with col_m:
    valgt = st_searchbox(
        sok_brreg,
        placeholder="Selskapsnavn eller organisasjonsnummer",
        default_searchterm=st.session_state.soke_felt,
        clear_on_submit=True,
        key="brreg_sok",
    )

if st.session_state.auto_analyse_orgnr:
    orgnr = st.session_state.auto_analyse_orgnr
    st.session_state.auto_analyse_orgnr = None
    with st.spinner("Analyserer selskap..."):
        utfor_analyse(orgnr)
    st.session_state.scroll_topp = True
    st.rerun()

if valgt and valgt != st.session_state.forrige_sok:
    with st.spinner("Analyserer selskap..."):
        utfor_analyse(valgt)
    st.session_state.scroll_topp = True
    st.rerun()

if st.session_state.scroll_topp:
    scroll_til_toppen()
    st.session_state.scroll_topp = False

# --- VISNING ---
if st.session_state.hoved_firma:
    f = st.session_state.hoved_firma
    bransje = f.get('naeringskode1', {}).get('beskrivelse', 'Ukjent')
    eposter = st.session_state.get("eposter", [])
    epost_html = f'<div class="detalj"><strong>E-post</strong> {", ".join(eposter)}</div>' if eposter else ""

    with st.container(border=True):
        st.markdown(f"""<h2 style="margin-top:0; margin-bottom:0.3rem; font-size:1.3rem;">{f.get("navn", "Ukjent")}</h2>
<span class="firma-badge">{bransje}</span>
<div class="firma-detaljer">
    <div class="detalj"><strong>Org.nr.</strong> {f.get('organisasjonsnummer', 'Ukjent')}</div>
    <div class="detalj"><strong>Ansatte</strong> {f.get('antallAnsatte', 'Ukjent')}</div>
    <div class="detalj"><strong>Nettside</strong> {f.get('hjemmeside', 'Ikke oppgitt')}</div>
    <div class="detalj"><strong>Adresse</strong> {formater_adresse(f)}</div>
    {epost_html}
</div>""", unsafe_allow_html=True)

        st.markdown('<div style="margin-top: 0.8rem;"></div>', unsafe_allow_html=True)
        col_hub, col_space = st.columns([1, 2])
        with col_hub:
            if st.button("Overfør til HubSpot", use_container_width=True):
                data_pakke = {
                    "firma": f.get("navn", "Ukjent"),
                    "organisasjonsnummer": f.get("organisasjonsnummer", ""),
                    "isbryter": st.session_state.get("isbryter"),
                    "bransje": bransje,
                    "ansatte": f.get("antallAnsatte"),
                    "adresse": formater_adresse(f),
                    "nettside": f.get("hjemmeside"),
                    "eposter": ", ".join(eposter),
                }
                requests.post(zapier_mottaker, json=data_pakke)
                st.success("Overfort til HubSpot")

    # Analyse-kort
    isbryter = st.session_state.get("isbryter")
    if isbryter:
        st.markdown(f"""
            <div class="analyse-kort">
                <div class="analyse-label">AI-analyse</div>
                {isbryter}
            </div>
        """, unsafe_allow_html=True)
    
    if st.session_state.mine_leads:
        st.markdown('<div class="seksjon-header">Andre aktorer i bransjen</div>', unsafe_allow_html=True)

        for i, lead in enumerate(st.session_state.mine_leads):
            poststed = lead.get('forretningsadresse', {}).get('poststed', 'Ukjent')
            nettside = lead.get('hjemmeside', '')
            ansatte = lead.get('antallAnsatte', 0)
            nettside_tekst = f" &middot; {nettside}" if nettside else ""

            with st.container(border=True):
                st.markdown(f"""<span class="lead-navn">{lead['navn']}</span>
<span class="lead-ansatte">{ansatte} ansatte</span>
<div class="lead-info">{poststed}{nettside_tekst}</div>""", unsafe_allow_html=True)

                scoredata = bygg_leadscore(lead, st.session_state.hoved_firma)
                hvorfor_na_html = scoredata["hvorfor_na"].replace("\n", "<br>")
                st.markdown(f"""<div class="lead-why-now">{hvorfor_na_html}</div>""", unsafe_allow_html=True)

                col_pf, col_int = st.columns(2)
                with col_pf:
                    st.markdown(f"""
                    <div class="score-kort">
                        <div class="score-title">Passformscore</div>
                        <div class="score-value">{scoredata['passformscore']}/100</div>
                        <ul>
                            <li>{scoredata['passform_grunner'][0]}</li>
                            <li>{scoredata['passform_grunner'][1]}</li>
                            <li>{scoredata['passform_grunner'][2]}</li>
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
                with col_int:
                    st.markdown(f"""
                    <div class="score-kort">
                        <div class="score-title">Intentscore</div>
                        <div class="score-value">{scoredata['intentscore']}/100</div>
                        <ul>
                            <li>{scoredata['intent_grunner'][0]}</li>
                            <li>{scoredata['intent_grunner'][1]}</li>
                            <li>{scoredata['intent_grunner'][2]}</li>
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)

                col_a, col_b = st.columns([3, 1])
                with col_b:
                    if st.button("Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}", use_container_width=True):
                        st.session_state.soke_felt = lead["organisasjonsnummer"]
                        st.session_state.auto_analyse_orgnr = lead["organisasjonsnummer"]
                        if "brreg_sok" in st.session_state:
                            del st.session_state["brreg_sok"]
                        st.rerun()

import streamlit as st
import streamlit.components.v1 as components
from streamlit_searchbox import st_searchbox
import requests
import pandas as pd
import html
from duckduckgo_search import DDGS
from openai import OpenAI
from io import BytesIO
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone

# Konfigurasjon
brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"
klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
modell_navn = "gpt-4o-mini"

NETTSIDE_KILDE_ETIKETTER = {
    "brreg": "Brreg",
    "fallback": "Automatisk funnet",
    "invalid": "Ugyldig",
    "missing": "Ikke funnet",
    "unknown": "Ukjent",
}

BHT_PLIKTIGE_SN2007_KODER = {
    "02", "03.2", "03.3", "05", "07", "08", "09.9", "10", "11", "12", "13", "14", "15", "16", "17", "18.1", "19", "20", "21", "22", "23", "24", "25", "26.1", "26.2", "26.3", "26.4", "26.51", "26.6", "26.7", "27", "28", "29", "30", "31", "32.3", "32.4", "32.5", "32.990", "33", "35.1", "35.21", "35.22", "35.23", "35.3", "35.4", "36", "37", "38", "39", "41", "42", "43.1", "43.2", "43.3", "43.4", "43.5", "43.9", "46.87", "49", "52.21", "52.22", "52.23", "52.24", "53.1", "53.2", "55.1", "56.11", "56.22", "56.3", "61", "75", "77.1", "80.01", "80.09", "81.2", "84.23", "84.24", "84.25", "85.1", "85.2", "85.3", "85.4", "85.5", "85.69", "86.1", "86.2", "86.91", "86.92", "86.93", "86.94", "86.95", "86.96", "86.99", "87.1", "87.2", "87.3", "87.99", "88", "91.3", "95.23", "95.24", "95.29", "95.31", "95.32", "96.1", "96.21", "96.91",
}


def normaliser_naeringskode(naeringskode):
    if not naeringskode:
        return ""
    return "".join(ch for ch in str(naeringskode).strip() if ch.isdigit() or ch == ".")


def er_underlagt_bht(naeringskode):
    kode = normaliser_naeringskode(naeringskode)
    if not kode:
        return False

    for bht_kode in BHT_PLIKTIGE_SN2007_KODER:
        if kode == bht_kode or kode.startswith(f"{bht_kode}."):
            return True
    return False


def bht_svar_for_firma(firma):
    kode = (firma or {}).get("naeringskode1", {}).get("kode")
    return "Ja" if er_underlagt_bht(kode) else "Nei"


def hent_datakvalitet_label(score):
    if score >= 75:
        return {
            "tekst": "god datakvalitet",
            "css_klasse": "datakvalitet-label datakvalitet-label--god",
        }
    if score >= 50:
        return {
            "tekst": "ok datakvalitet",
            "css_klasse": "datakvalitet-label datakvalitet-label--ok",
        }
    return {
        "tekst": "lav datakvalitet",
        "css_klasse": "datakvalitet-label datakvalitet-label--lav",
    }

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

        .datakvalitet-label {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-left: 8px;
        }

        .datakvalitet-label--lav {
            background: #fdecec;
            color: #b42318;
        }

        .datakvalitet-label--ok {
            background: #fff6e5;
            color: #b54708;
        }

        .datakvalitet-label--god {
            background: #ecfdf3;
            color: #027a48;
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
if "nettside_kilde" not in st.session_state:
    st.session_state.nettside_kilde = ""
if "nettside_validering_cache" not in st.session_state:
    st.session_state.nettside_validering_cache = {}
if "hoved_nettside_validering" not in st.session_state:
    st.session_state.hoved_nettside_validering = None
if "brreg_detaljer_cache" not in st.session_state:
    st.session_state.brreg_detaljer_cache = {}
if "brreg_roller_cache" not in st.session_state:
    st.session_state.brreg_roller_cache = {}

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

def hent_brreg_detaljer(orgnr):
    cache = st.session_state.setdefault("brreg_detaljer_cache", {})
    if not orgnr:
        return None
    if orgnr not in cache:
        cache[orgnr] = hent_firma_data(orgnr)
    return cache.get(orgnr)

def hent_brreg_roller(orgnr):
    cache = st.session_state.setdefault("brreg_roller_cache", {})
    if not orgnr:
        return {}
    if orgnr in cache:
        return cache[orgnr]

    try:
        svar = requests.get(f"{brreg_adresse}/{orgnr}/roller", timeout=5)
        cache[orgnr] = svar.json() if svar.status_code == 200 else {}
    except:
        cache[orgnr] = {}
    return cache[orgnr]

def finn_daglig_leder(orgnr):
    roller_data = hent_brreg_roller(orgnr)
    rollegrupper = (
        roller_data.get("rollegrupper")
        or roller_data.get("organisasjonsroller")
        or roller_data.get("roller")
        or roller_data.get("_embedded", {}).get("rollegrupper")
        or []
    )

    def normaliser_navnverdi(verdi):
        if isinstance(verdi, dict):
            fulltnavn = verdi.get("fulltNavn") or verdi.get("fulltnavn") or verdi.get("navn")
            if fulltnavn:
                return str(fulltnavn).strip()

            navnedeler = [
                verdi.get("fornavn"),
                verdi.get("mellomnavn"),
                verdi.get("etternavn"),
            ]
            sammensatt = " ".join(str(delnavn).strip() for delnavn in navnedeler if delnavn)
            return sammensatt.strip()

        if isinstance(verdi, (list, tuple, set)):
            sammensatt = " ".join(normaliser_navnverdi(delverdi) for delverdi in verdi)
            return sammensatt.strip()

        if verdi is None:
            return ""

        return str(verdi).strip()

    def hent_personnavn(rolle):
        if not isinstance(rolle, dict):
            return ""

        person = rolle.get("person") or rolle.get("rolleinnehaver") or {}
        if isinstance(person, dict):
            navn = (
                person.get("navn")
                or person.get("fulltNavn")
                or person.get("fulltnavn")
                or person
            )
            return normaliser_navnverdi(navn)

        if isinstance(person, str):
            return person.strip()
        return ""

    def rolle_er_daglig_leder(element):
        if not isinstance(element, dict):
            return False

        tekstfelter = [
            element.get("type"),
            element.get("beskrivelse"),
            element.get("rolle"),
            element.get("rollekode"),
            element.get("rolletype"),
            element.get("kode"),
            (element.get("rolle") or {}).get("beskrivelse") if isinstance(element.get("rolle"), dict) else None,
            (element.get("rolle") or {}).get("kode") if isinstance(element.get("rolle"), dict) else None,
        ]
        samlet = " ".join(str(t) for t in tekstfelter if t).lower()
        return "daglig" in samlet or "dl" == samlet.strip()

    for gruppe in rollegrupper:
        if isinstance(gruppe, dict) and rolle_er_daglig_leder(gruppe):
            navn = hent_personnavn(gruppe)
            if navn:
                return navn

        roller = gruppe.get("roller", []) if isinstance(gruppe, dict) else []
        for rolle in roller:
            if rolle_er_daglig_leder(rolle) or (isinstance(gruppe, dict) and rolle_er_daglig_leder(gruppe)):
                navn = hent_personnavn(rolle)
                if navn:
                    return navn

    for rolle in roller_data.get("_embedded", {}).get("roller", []):
        if rolle_er_daglig_leder(rolle):
            navn = hent_personnavn(rolle)
            if navn:
                return navn

    return "Ikke oppgitt"

def hent_kontaktinfo_fra_firma(firma):
    if not firma:
        return {}

    kontakt = firma.get("kontaktinformasjon", {})
    epost = (
        kontakt.get("epostadresse")
        or kontakt.get("epost")
        or kontakt.get("email")
        or firma.get("epostadresse")
        or firma.get("epost")
        or firma.get("email")
        or ""
    )
    telefon = (
        kontakt.get("telefon")
        or kontakt.get("telefonnummer")
        or kontakt.get("mobiltelefonnummer")
        or firma.get("telefon")
        or firma.get("telefonnummer")
        or firma.get("mobiltelefonnummer")
        or ""
    )
    mobil = (
        kontakt.get("mobil")
        or kontakt.get("mobilnummer")
        or kontakt.get("mobiltelefonnummer")
        or firma.get("mobil")
        or firma.get("mobilnummer")
        or firma.get("mobiltelefonnummer")
        or ""
    )
    return {
        "epost": str(epost).strip(),
        "telefon": str(telefon).strip(),
        "mobil": str(mobil).strip(),
    }

def berik_firma_med_kontaktinfo(firma):
    if not firma:
        return firma

    orgnr = firma.get("organisasjonsnummer")
    detaljer = hent_brreg_detaljer(orgnr) or {}
    kontakt = hent_kontaktinfo_fra_firma({**firma, **detaljer})
    for felt in ("epostadresse", "epost", "telefon", "telefonnummer", "mobil", "mobilnummer", "mobiltelefonnummer"):
        verdi = detaljer.get(felt)
        if verdi and not firma.get(felt):
            firma[felt] = verdi

    firma["daglig_leder"] = finn_daglig_leder(orgnr)
    firma["kontaktinfo"] = kontakt
    return firma

def bygg_kontaktinfo_html(firma):
    kontakt = firma.get("kontaktinfo") or hent_kontaktinfo_fra_firma(firma)
    deler = []
    if kontakt.get("telefon"):
        deler.append(f"Telefon: {html.escape(kontakt['telefon'])}")
    if kontakt.get("mobil"):
        deler.append(f"Mobil: {html.escape(kontakt['mobil'])}")
    if kontakt.get("epost"):
        deler.append(f"E-post: {html.escape(kontakt['epost'])}")
    return " &middot; ".join(deler) if deler else "Ikke oppgitt"

def finn_nyheter(firmanavn):
    try:
        resultater = DDGS().text(f"{firmanavn} norge nyheter strategi ledelse", max_results=5)
        return "\n".join([r['body'] for r in resultater]) if resultater else ""
    except:
        return ""

def normaliser_nettside_url(url):
    if not url:
        return ""
    kandidat = url.strip()
    if not kandidat:
        return ""
    if not kandidat.startswith(("http://", "https://")):
        kandidat = f"https://{kandidat}"
    parsed = urlparse(kandidat)
    host = parsed.netloc.lower().replace("www.", "")
    if not host or "." not in host:
        return ""
    return host

def normaliser_url_for_validering(url):
    if not url:
        return ""

    kandidat = url.strip()
    if not kandidat:
        return ""

    if not kandidat.startswith(("http://", "https://")):
        kandidat = f"https://{kandidat}"

    parsed = urlparse(kandidat)
    if not parsed.netloc or "." not in parsed.netloc:
        return ""

    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower()
    path = parsed.path if parsed.path else ""
    return urlunparse((scheme, netloc, path, "", "", ""))

def valider_nettside(url):
    normalisert_url = normaliser_url_for_validering(url)
    if not normalisert_url:
        return {
            "input_url": url,
            "normalized_url": "",
            "final_url": "",
            "http_status": None,
            "status": "inactive",
            "error": "Ugyldig eller manglende URL",
        }

    def klassifiser_svar(svar):
        slutt_url = getattr(svar, "url", normalisert_url)
        redirectet = bool(getattr(svar, "history", []))
        if 200 <= svar.status_code < 400:
            status = "redirected" if redirectet else "active"
        else:
            status = "inactive"
        return {
            "input_url": url,
            "normalized_url": normalisert_url,
            "final_url": slutt_url,
            "http_status": svar.status_code,
            "status": status,
            "error": "",
        }

    try:
        head_svar = requests.head(normalisert_url, timeout=3, allow_redirects=True)
        if head_svar.status_code not in (405, 501):
            return klassifiser_svar(head_svar)
    except requests.RequestException:
        pass

    try:
        get_svar = requests.get(normalisert_url, timeout=3, allow_redirects=True)
        return klassifiser_svar(get_svar)
    except requests.RequestException as e:
        return {
            "input_url": url,
            "normalized_url": normalisert_url,
            "final_url": "",
            "http_status": None,
            "status": "error",
            "error": str(e),
        }

def hent_validering_fra_cache(url):
    cache = st.session_state.setdefault("nettside_validering_cache", {})
    nokkel = (url or "").strip()
    if nokkel not in cache:
        cache[nokkel] = valider_nettside(nokkel)
    return cache[nokkel]

def valideringsstatus_tekst(status):
    visning = {
        "active": "Aktiv",
        "redirected": "Videresendt",
        "inactive": "Inaktiv",
        "error": "Feil",
    }
    return visning.get(status, "Ukjent")

def verifiser_nettside(url):
    normalisert = normaliser_url_for_validering(url)
    if not normalisert:
        return ""

    validering = valider_nettside(normalisert)
    if validering["status"] in ("active", "redirected"):
        return validering["final_url"] or validering["normalized_url"]
    return ""

def finn_nettside_for_firma(firmanavn):
    if not firmanavn:
        return ""

    blokkerte_domener = {
        "facebook.com", "instagram.com", "linkedin.com", "proff.no", "purehelp.no",
        "wikipedia.org", "gulesider.no", "1881.no", "brreg.no", "enhetsregisteret.no",
    }

    try:
        resultater = DDGS().text(f"{firmanavn} offisiell nettside", max_results=8)
    except:
        return ""

    for resultat in resultater or []:
        href = resultat.get("href", "")
        domene = normaliser_nettside_url(href)
        if not domene:
            continue
        if any(domene == blokkert or domene.endswith(f".{blokkert}") for blokkert in blokkerte_domener):
            continue

        verifisert = verifiser_nettside(domene)
        if verifisert:
            return verifisert
    return ""

def finn_nettside_fallback(firma, orgnr, poststed):
    if not firma:
        return ""

    blokkerte_domener = {
        "facebook.com", "instagram.com", "linkedin.com", "proff.no", "purehelp.no",
        "wikipedia.org", "gulesider.no", "1881.no", "brreg.no", "enhetsregisteret.no",
    }

    stopord = {"as", "asa", "da", "ans", "entreprenør", "entreprenor", "holding", "group", "norge"}
    firmanavn_ord = [
        ord for ord in firma.lower().replace("-", " ").split()
        if len(ord) > 2 and ord not in stopord
    ]
    poststed_lav = (poststed or "").lower()
    orgnr_tekst = str(orgnr or "")

    try:
        resultater = DDGS().text(f"{firma} orgnr {orgnr} offisiell nettside", max_results=12)
    except:
        return ""

    kandidater = []
    for resultat in resultater or []:
        href = resultat.get("href", "")
        domene = normaliser_nettside_url(href)
        if not domene:
            continue
        if any(domene == blokkert or domene.endswith(f".{blokkert}") for blokkert in blokkerte_domener):
            continue

        snippet = f"{resultat.get('title', '')} {resultat.get('body', '')}".lower()
        score = 0

        # Heuristikk: firmanavn i domene
        if any(ord in domene for ord in firmanavn_ord):
            score += 3

        # Heuristikk: norsk TLD
        if domene.endswith(".no"):
            score += 2

        # Heuristikk: samsvar i snippets
        if orgnr_tekst and orgnr_tekst in snippet:
            score += 3
        if poststed_lav and poststed_lav in snippet:
            score += 1
        if any(ord in snippet for ord in firmanavn_ord):
            score += 1

        # Krev minimum relevans slik at tilfeldige, men aktive domener filtreres bort.
        har_domene_treff = any(ord in domene for ord in firmanavn_ord)
        har_snippet_treff = any(ord in snippet for ord in firmanavn_ord)
        if not har_domene_treff and not (har_snippet_treff and orgnr_tekst and orgnr_tekst in snippet):
            continue

        kandidater.append((score, domene))

    for score, domene in sorted(kandidater, key=lambda x: x[0], reverse=True):
        if score < 2:
            continue
        verifisert = verifiser_nettside(domene)
        if verifisert:
            return verifisert
    return ""

def normaliser_nettside_kilde(kilde):
    verdi = (kilde or "").strip().lower()
    mapping = {
        "brreg": "brreg",
        "fallback": "fallback",
        "automatisk funnet": "fallback",
        "invalid": "invalid",
        "ugyldig": "invalid",
        "missing": "missing",
        "ikke funnet": "missing",
    }
    return mapping.get(verdi, "unknown")

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

def finn_eposter(domene=None, nettside_kilde=None):
    domene = domene if domene is not None else st.session_state.get("nettside_url", "")
    nettside_kilde = nettside_kilde if nettside_kilde is not None else st.session_state.get("nettside_kilde", "")
    nettside_kilde = normaliser_nettside_kilde(nettside_kilde)
    if not domene:
        return []

    # Utnytt kun kilder vi eksplisitt stoler på.
    if nettside_kilde not in {"brreg", "fallback"}:
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

def lag_url_lenke(url, etikett=None):
    if not url:
        return ""

    url_tekst = url.strip()
    if not url_tekst:
        return ""

    href = url_tekst if url_tekst.startswith(("http://", "https://")) else f"https://{url_tekst}"
    visning = etikett or url_tekst
    return f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(visning)}</a>'

def bygg_datakvalitet(firma, eposter=None, enrichment_age_timer=None):
    eposter = eposter or []
    adresse = firma.get("forretningsadresse", {})
    nettside = firma.get("hjemmeside") or ""
    nettside_status = bool(verifiser_nettside(nettside) or normaliser_nettside_url(nettside))

    adresse_felt = {
        "adresse": bool(adresse.get("adresse")),
        "postnummer": bool(adresse.get("postnummer")),
        "poststed": bool(adresse.get("poststed")),
        "kommunenummer": bool(adresse.get("kommunenummer")),
    }
    adresse_dekning = sum(adresse_felt.values())

    score = 0
    score += 30 if nettside_status else 0

    if adresse_dekning == 4:
        score += 30
    elif adresse_dekning == 3:
        score += 22
    elif adresse_dekning == 2:
        score += 15
    elif adresse_dekning == 1:
        score += 8

    if len(eposter) >= 2:
        score += 25
    elif len(eposter) == 1:
        score += 15

    if enrichment_age_timer is None:
        score += 8
    elif enrichment_age_timer <= 24:
        score += 15
    elif enrichment_age_timer <= 72:
        score += 12
    elif enrichment_age_timer <= 168:
        score += 8
    else:
        score += 4

    score = max(0, min(100, score))
    er_lav = score < 50

    if enrichment_age_timer is None:
        ferskhet_tekst = "Ferskhet ikke målt – estimat basert på nåværende datagrunnlag."
    elif enrichment_age_timer <= 24:
        ferskhet_tekst = "Enrichment-data er oppdatert siste 24 timer."
    elif enrichment_age_timer <= 168:
        ferskhet_tekst = "Enrichment-data er oppdatert siste uke."
    else:
        ferskhet_tekst = "Enrichment-data er eldre enn én uke."

    return {
        "datakvalitet": score,
        "datakvalitet_grunner": [
            "Nettside-status verifisert." if nettside_status else "Nettside mangler eller er ikke verifisert.",
            f"Adressefelt med verdi: {adresse_dekning}/4.",
            f"E-postdekning: {len(eposter)} registrerte adresser.",
            ferskhet_tekst,
        ],
        "hoy_usikkerhet": er_lav,
    }

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
    nettside_validering = hent_validering_fra_cache(nettside)
    nettside_status = nettside_validering.get("status")
    nettside_ok = nettside_status in ("active", "redirected")

    # Passformscore: hvor godt leadet matcher hovedselskapet i størrelse og segment
    passformscore = 35
    if samme_bransje:
        passformscore += 35
    if lead_ansatte >= 20:
        passformscore += 15
    if abs(lead_ansatte - hoved_ansatte) <= 50:
        passformscore += 10
    if nettside_ok:
        passformscore += 5
    elif nettside_status in ("inactive", "error"):
        passformscore -= 3
    passformscore = max(0, min(100, passformscore))

    # Intentscore: sannsynlighet for at timing er riktig
    intentscore = 30
    if lead_ansatte >= 50:
        intentscore += 20
    elif lead_ansatte >= 20:
        intentscore += 10
    if samme_kommune:
        intentscore += 15
    if nettside_ok:
        intentscore += 10
    elif nettside_status in ("inactive", "error"):
        intentscore -= 5
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

    datakvalitet = bygg_datakvalitet(lead, eposter=[], enrichment_age_timer=0)

    return {
        "passformscore": passformscore,
        "intentscore": intentscore,
        "datakvalitet": datakvalitet["datakvalitet"],
        "passform_grunner": [
            bransjetekst,
            f"Størrelse: {lead_ansatte} ansatte",
            f"Nettsidevalidering: {valideringsstatus_tekst(nettside_status)}",
        ],
        "intent_grunner": [
            "Vekstindikator: over 50 ansatte" if lead_ansatte >= 50 else "Modent nok selskap for strukturert læring",
            geotekst,
            "Digital tilstedeværelse er verifisert" if nettside_ok else "Digital tilstedeværelse er usikker",
        ],
        "datakvalitet_grunner": datakvalitet["datakvalitet_grunner"],
        "hoy_usikkerhet": datakvalitet["hoy_usikkerhet"],
        "hvorfor_na": hvorfor_na,
        "nettside_validering": nettside_validering,
    }

def bygg_hovedscore(hoved_firma, leads):
    ansatte = hoved_firma.get("antallAnsatte") or 0
    epostdekning = len(st.session_state.get("eposter", []))
    adresse = hoved_firma.get("forretningsadresse", {})
    har_full_adresse = bool(adresse.get("adresse") and adresse.get("postnummer") and adresse.get("poststed"))
    bransjekode = hoved_firma.get("naeringskode1", {}).get("kode")
    nettside_validering = st.session_state.get("hoved_nettside_validering") or hent_validering_fra_cache(hoved_firma.get("hjemmeside", ""))
    nettside_status = nettside_validering.get("status")
    nettside_ok = nettside_status in ("active", "redirected")

    sammenlignbare = 0
    storre_enn_hoved = 0
    lokal_klynge = 0
    kommune = hoved_firma.get("forretningsadresse", {}).get("kommunenummer")
    for lead in leads:
        if lead.get("naeringskode1", {}).get("kode") == bransjekode:
            sammenlignbare += 1
        if (lead.get("antallAnsatte") or 0) >= ansatte:
            storre_enn_hoved += 1
        if kommune and lead.get("forretningsadresse", {}).get("kommunenummer") == kommune:
            lokal_klynge += 1

    passformscore = 50
    if ansatte >= 20:
        passformscore += 15
    if ansatte >= 50:
        passformscore += 10
    if nettside_ok:
        passformscore += 10
    elif nettside_status in ("inactive", "error"):
        passformscore -= 5
    if har_full_adresse:
        passformscore += 5
    if epostdekning >= 2:
        passformscore += 10
    passformscore = max(0, min(100, passformscore))

    intentscore = 45
    if storre_enn_hoved >= 5:
        intentscore += 15
    elif storre_enn_hoved >= 2:
        intentscore += 8
    if lokal_klynge >= 5:
        intentscore += 10
    if sammenlignbare >= 10:
        intentscore += 10
    if nettside_ok and epostdekning > 0:
        intentscore += 10
    elif nettside_status in ("inactive", "error"):
        intentscore -= 5
    intentscore = max(0, min(100, intentscore))

    enrichment_tidspunkt = st.session_state.get("enrichment_tidspunkt")
    enrichment_age_timer = None
    if enrichment_tidspunkt:
        enrichment_age_timer = max(
            0,
            (datetime.now(timezone.utc) - enrichment_tidspunkt).total_seconds() / 3600,
        )

    datakvalitet = bygg_datakvalitet(hoved_firma, eposter=st.session_state.get("eposter", []), enrichment_age_timer=enrichment_age_timer)

    return {
        "passformscore": passformscore,
        "intentscore": intentscore,
        "datakvalitet": datakvalitet["datakvalitet"],
        "passform_grunner": [
            f"Størrelse i kjernesegment: {ansatte} ansatte.",
            f"Nettsidevalidering: {valideringsstatus_tekst(nettside_status)}.",
            f"Kontaktbarhet: {epostdekning} identifiserte e-postadresser.",
            "Tydelig registrert forretningsadresse gir høy datakvalitet." if har_full_adresse else "Ufullstendig adresseinformasjon svekker datakvalitet.",
            f"{sammenlignbare} sammenlignbare selskaper i samme bransjekode gir god benchmark.",
        ],
        "intent_grunner": [
            f"{storre_enn_hoved} lignende selskaper er like store eller større – indikerer moden markedsdynamikk.",
            f"{lokal_klynge} relevante aktører i samme kommune øker sannsynlighet for lokal konkurranse om kompetanse.",
            "Nettside med god validering + e-postfunn tyder på at selskapet er mottakelig for digital dialog og oppfølging." if nettside_ok else "Nettsidestatus svekker sannsynlighet for rask digital dialog.",
            "Bransjebredden i lead-settet gir signal om vedvarende opplæringsbehov i segmentet.",
            "Samlet vurdering: timing er gunstig for proaktiv kompetansedialog med beslutningstagere.",
        ],
        "datakvalitet_grunner": datakvalitet["datakvalitet_grunner"],
        "hoy_usikkerhet": datakvalitet["hoy_usikkerhet"],
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
        hoved = berik_firma_med_kontaktinfo(hoved)
        st.session_state.hoved_firma = hoved
        st.session_state.forrige_sok = orgnr
        firmanavn = hoved.get("navn", "Ukjent")

        registrert_hjemmeside = hoved.get("hjemmeside", "")
        registrert_nettside = verifiser_nettside(registrert_hjemmeside)
        if registrert_nettside:
            hoved["hjemmeside"] = registrert_nettside
            hoved["nettside_status"] = "confirmed"
            st.session_state.nettside_kilde = "brreg"
        else:
            funnet_nettside = finn_nettside_fallback(
                firmanavn,
                orgnr,
                hoved.get("forretningsadresse", {}).get("poststed", ""),
            )
            hoved["hjemmeside"] = funnet_nettside
            if funnet_nettside:
                hoved["nettside_status"] = "inferred"
                st.session_state.nettside_kilde = "fallback"
            elif registrert_hjemmeside:
                hoved["nettside_status"] = "invalid"
                st.session_state.nettside_kilde = "invalid"
            else:
                hoved["nettside_status"] = "missing"
                st.session_state.nettside_kilde = "missing"

        st.session_state.hoved_nettside_validering = hent_validering_fra_cache(hoved.get("hjemmeside", ""))

        nyheter = finn_nyheter(firmanavn)
        st.session_state.isbryter = lag_isbryter(
            firmanavn,
            nyheter,
            hoved.get("naeringskode1", {}).get("beskrivelse", "Ukjent"),
        )
        st.session_state.eposter = finn_eposter(hoved.get("hjemmeside"))
        st.session_state.enrichment_tidspunkt = datetime.now(timezone.utc)
        
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

            berikede_leads = []
            for lead in leads:
                berikede_leads.append(berik_firma_med_kontaktinfo(lead))

            st.session_state.mine_leads = berikede_leads
            for lead in st.session_state.mine_leads:
                nettside = lead.get("hjemmeside") or ""
                if not nettside:
                    lead["nettside_status"] = "missing"
                elif normaliser_nettside_url(nettside):
                    lead["nettside_status"] = "inferred"
                else:
                    lead["nettside_status"] = "invalid"
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
    daglig_leder = f.get("daglig_leder") or "Ikke oppgitt"
    hoved_bht_svar = bht_svar_for_firma(f)
    kontaktinfo_html = bygg_kontaktinfo_html(f)
    nettside_kilde = st.session_state.get("nettside_kilde", "")
    nettside_kilde_normalisert = normaliser_nettside_kilde(nettside_kilde)
    nettside_kilde_etikett = NETTSIDE_KILDE_ETIKETTER.get(
        nettside_kilde_normalisert,
        NETTSIDE_KILDE_ETIKETTER["unknown"],
    )
    nettside = st.session_state.get("nettside_url") or f.get("hjemmeside", "")
    nettside_visning = lag_url_lenke(nettside) if nettside else "Ikke oppgitt"
    if nettside and nettside_kilde_normalisert == "fallback":
        nettside_visning = f"{lag_url_lenke(nettside)} ({nettside_kilde_etikett})"

    hoved_validering = st.session_state.get("hoved_nettside_validering") or hent_validering_fra_cache(nettside)
    valideringsstatus = valideringsstatus_tekst(hoved_validering.get("status"))

    with st.container(border=True):
        hovedscore = bygg_hovedscore(f, st.session_state.get("mine_leads", []))
        hoved_dk_label = hent_datakvalitet_label(hovedscore["datakvalitet"])
        st.markdown(f"""<h2 style="margin-top:0; margin-bottom:0.3rem; font-size:1.3rem;">{f.get("navn", "Ukjent")}</h2>
<span class="firma-badge">{bransje}</span>
<div class="firma-detaljer">
    <div class="detalj"><strong>Org.nr.</strong> {f.get('organisasjonsnummer', 'Ukjent')}</div>
    <div class="detalj"><strong>Ansatte</strong> {f.get('antallAnsatte', 'Ukjent')} <span class="{hoved_dk_label['css_klasse']}">{hoved_dk_label['tekst']}</span></div>
    <div class="detalj"><strong>Nettside</strong> {nettside_visning}</div>
    <div class="detalj"><strong>Nettsidevalidering</strong> {valideringsstatus}</div>
    <div class="detalj"><strong>Adresse</strong> {formater_adresse(f)}</div>
    <div class="detalj"><strong>Daglig leder</strong> {html.escape(daglig_leder)}</div>
    <div class="detalj"><strong>Kontaktinfo</strong> {kontaktinfo_html}</div>
    <div class="detalj"><strong>BHT-plikt (SN2007)</strong> {hoved_bht_svar}</div>
    {epost_html}
</div>""", unsafe_allow_html=True)

        isbryter = st.session_state.get("isbryter")
        if isbryter:
            st.markdown(f"""
                <div class="analyse-kort">
                    <div class="analyse-label">AI-analyse</div>
                    {isbryter}
                </div>
            """, unsafe_allow_html=True)

        st.markdown('<div style="margin-top: 0.8rem;"></div>', unsafe_allow_html=True)
        col_h_pf, col_h_int, col_h_dk = st.columns(3)
        with col_h_pf:
            st.markdown(f"""
            <div class="score-kort">
                <div class="score-title">Passformscore (hovedselskap)</div>
                <div class="score-value">{hovedscore['passformscore']}/100</div>
                <ul>
                    <li>{hovedscore['passform_grunner'][0]}</li>
                    <li>{hovedscore['passform_grunner'][1]}</li>
                    <li>{hovedscore['passform_grunner'][2]}</li>
                    <li>{hovedscore['passform_grunner'][3]}</li>
                    <li>{hovedscore['passform_grunner'][4]}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        with col_h_int:
            st.markdown(f"""
            <div class="score-kort">
                <div class="score-title">Intentscore (hovedselskap)</div>
                <div class="score-value">{hovedscore['intentscore']}/100</div>
                <ul>
                    <li>{hovedscore['intent_grunner'][0]}</li>
                    <li>{hovedscore['intent_grunner'][1]}</li>
                    <li>{hovedscore['intent_grunner'][2]}</li>
                    <li>{hovedscore['intent_grunner'][3]}</li>
                    <li>{hovedscore['intent_grunner'][4]}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        with col_h_dk:
            st.markdown(f"""
            <div class="score-kort">
                <div class="score-title">Datakvalitet (hovedselskap)</div>
                <div class="score-value">{hovedscore['datakvalitet']}/100</div>
                <ul>
                    <li>{hovedscore['datakvalitet_grunner'][0]}</li>
                    <li>{hovedscore['datakvalitet_grunner'][1]}</li>
                    <li>{hovedscore['datakvalitet_grunner'][2]}</li>
                    <li>{hovedscore['datakvalitet_grunner'][3]}</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

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
    
    if st.session_state.mine_leads:
        st.markdown('<div class="seksjon-header">Andre aktorer i bransjen</div>', unsafe_allow_html=True)

        for i, lead in enumerate(st.session_state.mine_leads):
            poststed = lead.get('forretningsadresse', {}).get('poststed', 'Ukjent')
            nettside = lead.get('hjemmeside', '')
            ansatte = lead.get('antallAnsatte', 0)
            nettside_tekst = f" &middot; {lag_url_lenke(nettside)}" if nettside else ""
            daglig_leder = lead.get("daglig_leder") or "Ikke oppgitt"
            kontaktinfo = bygg_kontaktinfo_html(lead)
            lead_bht_svar = bht_svar_for_firma(lead)

            with st.container(border=True):
                scoredata = bygg_leadscore(lead, st.session_state.hoved_firma)
                datakvalitet_label = hent_datakvalitet_label(scoredata["datakvalitet"])
                hvorfor_na_html = scoredata["hvorfor_na"].replace("\n", "<br>")
                st.markdown(f"""<span class="lead-navn">{lead['navn']}</span>
<span class="lead-ansatte">{ansatte} ansatte</span>
<span class="{datakvalitet_label['css_klasse']}">{datakvalitet_label['tekst']}</span>
<div class="lead-info">{poststed}{nettside_tekst}</div>
<div class="lead-info"><strong>Daglig leder:</strong> {html.escape(daglig_leder)}</div>
<div class="lead-info"><strong>Kontaktinfo:</strong> {kontaktinfo}</div>
<div class="lead-info"><strong>BHT-plikt (SN2007):</strong> {lead_bht_svar}</div>""", unsafe_allow_html=True)

                st.markdown(f"""<div class="lead-why-now">{hvorfor_na_html}</div>""", unsafe_allow_html=True)

                col_pf, col_int, col_dk = st.columns(3)
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
                with col_dk:
                    st.markdown(f"""
                    <div class="score-kort">
                        <div class="score-title">Datakvalitet</div>
                        <div class="score-value">{scoredata['datakvalitet']}/100</div>
                        <ul>
                            <li>{scoredata['datakvalitet_grunner'][0]}</li>
                            <li>{scoredata['datakvalitet_grunner'][1]}</li>
                            <li>{scoredata['datakvalitet_grunner'][2]}</li>
                            <li>{scoredata['datakvalitet_grunner'][3]}</li>
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown('<div style="margin-top: 0.9rem;"></div>', unsafe_allow_html=True)
                col_a, col_b = st.columns([3, 1])
                with col_b:
                    if st.button("Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}", use_container_width=True):
                        st.session_state.soke_felt = lead["organisasjonsnummer"]
                        st.session_state.auto_analyse_orgnr = lead["organisasjonsnummer"]
                        if "brreg_sok" in st.session_state:
                            del st.session_state["brreg_sok"]
                        st.rerun()

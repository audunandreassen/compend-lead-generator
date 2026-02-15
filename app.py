 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index ce8f5f4eef1284481284ef28e08de6289bfbeeda..639d76fe8cd7ccf213385ea5e9fe92ebf00c4765 100644
--- a/app.py
+++ b/app.py
@@ -1,37 +1,49 @@
 import streamlit as st
+import streamlit.components.v1 as components
 from streamlit_searchbox import st_searchbox
 import requests
 import pandas as pd
 from duckduckgo_search import DDGS
 from openai import OpenAI
 from io import BytesIO
 
 # Konfigurasjon
 brreg_adresse = "https://data.brreg.no/enhetsregisteret/api/enheter"
 zapier_mottaker = "https://hooks.zapier.com/hooks/catch/20188911/uejstea/"
-klient = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
+
+
+def hent_secret(nokkel):
+    try:
+        return st.secrets[nokkel]
+    except Exception:
+        return None
+
+
+openai_api_key = hent_secret("OPENAI_API_KEY")
+hunter_api_key = hent_secret("HUNTER_API_KEY")
+klient = OpenAI(api_key=openai_api_key) if openai_api_key else None
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
@@ -256,161 +268,167 @@ def bruk_stil():
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
-if "soke_felt" not in st.session_state:
-    st.session_state.soke_felt = ""
 if "forrige_sok" not in st.session_state:
     st.session_state.forrige_sok = ""
 if "siste_sok_valg" not in st.session_state:
     st.session_state.siste_sok_valg = None
+if "pending_scroll_orgnr" not in st.session_state:
+    st.session_state.pending_scroll_orgnr = None
+if "scroll_then_analyze" not in st.session_state:
+    st.session_state.scroll_then_analyze = False
+if "skip_searchbox_once" not in st.session_state:
+    st.session_state.skip_searchbox_once = False
 
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
+    if not klient:
+        return "Legg inn OPENAI_API_KEY i secrets for AI-analyse."
+
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
-    if not domene:
+    if not domene or not hunter_api_key:
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
-                "api_key": st.secrets["HUNTER_API_KEY"],
+                "api_key": hunter_api_key,
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
-            antall = hoved.get("antallAnsatte") or 0
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
 
@@ -427,51 +445,87 @@ def sok_brreg(soketekst):
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
         clear_on_submit=True,
         key="brreg_sok",
     )
 
-if valgt and valgt != st.session_state.siste_sok_valg:
+run_analysis_param = st.query_params.get("run_analysis") == "1"
+query_orgnr = st.query_params.get("orgnr")
+
+if st.session_state.scroll_then_analyze and st.session_state.pending_scroll_orgnr and not run_analysis_param:
+    pending_orgnr = st.session_state.pending_scroll_orgnr
+    components.html(
+        f"""
+        <script>
+            window.parent?.scrollTo({{ top: 0, behavior: 'smooth' }});
+            window.scrollTo({{ top: 0, behavior: 'smooth' }});
+            setTimeout(() => {{
+                const url = new URL(window.location.href);
+                url.searchParams.set('run_analysis', '1');
+                url.searchParams.set('orgnr', '{pending_orgnr}');
+                window.location.href = url.toString();
+            }}, 350);
+        </script>
+        """,
+        height=0,
+    )
+    st.stop()
+
+if run_analysis_param:
+    orgnr = query_orgnr or st.session_state.pending_scroll_orgnr
+    st.query_params.clear()
+    st.session_state.pending_scroll_orgnr = None
+    st.session_state.scroll_then_analyze = False
+    if orgnr:
+        with st.spinner("Analyserer..."):
+            utfor_analyse(orgnr)
+        st.session_state.siste_sok_valg = orgnr
+        st.session_state.skip_searchbox_once = True
+    st.rerun()
+
+if st.session_state.skip_searchbox_once:
+    st.session_state.skip_searchbox_once = False
+elif valgt and valgt != st.session_state.siste_sok_valg and not run_analysis_param:
     with st.spinner("Analyserer selskap..."):
         utfor_analyse(valgt)
     st.session_state.siste_sok_valg = valgt
     st.rerun()
 
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
@@ -494,29 +548,28 @@ if st.session_state.hoved_firma:
     isbryter = st.session_state.get("isbryter")
     if isbryter:
         st.markdown(f"""
             <div class="analyse-kort">
                 <div class="analyse-label">AI-analyse</div>
                 {isbryter}
             </div>
         """, unsafe_allow_html=True)
     
     if st.session_state.mine_leads:
         st.markdown('<div class="seksjon-header">Andre lignende aktører</div>', unsafe_allow_html=True)
 
         for i, lead in enumerate(st.session_state.mine_leads):
             poststed = lead.get('forretningsadresse', {}).get('poststed', 'Ukjent')
             nettside = lead.get('hjemmeside', '')
             ansatte = lead.get('antallAnsatte', 0)
             nettside_tekst = f" &middot; {nettside}" if nettside else ""
 
             with st.container(border=True):
                 st.markdown(f"""<span class="lead-navn">{lead['navn']}</span>
 <span class="lead-ansatte">{ansatte} ansatte</span>
 <div class="lead-info">{poststed}{nettside_tekst}</div>""", unsafe_allow_html=True)
                 col_a, col_b = st.columns([3, 1])
                 with col_b:
                     if st.button("Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}", use_container_width=True):
-                        st.session_state.soke_felt = lead["organisasjonsnummer"]
-                        with st.spinner("Analyserer..."):
-                            utfor_analyse(lead["organisasjonsnummer"])
+                        st.session_state.pending_scroll_orgnr = lead["organisasjonsnummer"]
+                        st.session_state.scroll_then_analyze = True
                         st.rerun()
 
EOF
)

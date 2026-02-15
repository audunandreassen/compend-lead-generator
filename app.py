diff --git a/app.py b/app.py
index b168832c0f22afa01ac6b7996025e1a3f5cf84e8..765cbf13f91670bf76d667e6b05edf5aaa6a2b25 100644
--- a/app.py
+++ b/app.py
@@ -1209,51 +1209,115 @@ def bygg_hovedscore(hoved_firma, leads):
 
 def oppdater_scorecards_med_ny_data():
     hoved_firma = st.session_state.get("hoved_firma")
     if not hoved_firma:
         return
 
     oppdatert_hoved = berik_firma_med_kontaktinfo(hoved_firma)
     st.session_state.hoved_firma = oppdatert_hoved
     st.session_state.hoved_nettside_validering = hent_validering_fra_cache(oppdatert_hoved.get("hjemmeside", ""))
     st.session_state.eposter = finn_eposter(oppdatert_hoved.get("hjemmeside"), st.session_state.get("nettside_kilde", ""))
 
     oppdaterte_leads = []
     for lead in st.session_state.get("mine_leads", []):
         oppdatert_lead = berik_firma_med_kontaktinfo(lead)
         oppdatert_lead["_nettside_validering"] = hent_validering_fra_cache(oppdatert_lead.get("hjemmeside", ""))
         oppdatert_lead["_eposter"] = finn_eposter(oppdatert_lead.get("hjemmeside"), oppdatert_lead.get("nettside_kilde", st.session_state.get("nettside_kilde", "")))
         oppdaterte_leads.append(oppdatert_lead)
     st.session_state.mine_leads = oppdaterte_leads
 
     st.session_state.enrichment_tidspunkt = datetime.now(timezone.utc)
 
 def scroll_til_toppen():
     components.html(
         """
         <script>
-            window.parent.scrollTo({ top: 0, behavior: "smooth" });
+            const hentDokument = (ctx) => {
+                try {
+                    return ctx && ctx.document ? ctx.document : null;
+                } catch (_) {
+                    return null;
+                }
+            };
+
+            const scrollContainersToTop = (ctx) => {
+                if (!ctx) return;
+
+                try {
+                    ctx.scrollTo(0, 0);
+                } catch (_) {}
+
+                const d = hentDokument(ctx);
+                if (!d) return;
+
+                const targets = [
+                    d.documentElement,
+                    d.body,
+                    d.querySelector('section.main'),
+                    d.querySelector('[data-testid="stAppViewContainer"]'),
+                    d.querySelector('.stAppViewContainer'),
+                    d.querySelector('main'),
+                ].filter(Boolean);
+
+                targets.forEach((el) => {
+                    try {
+                        el.scrollTop = 0;
+                    } catch (_) {}
+                    try {
+                        el.scrollTo({ top: 0, left: 0, behavior: 'auto' });
+                    } catch (_) {}
+                });
+            };
+
+            const contexts = [window];
+            try {
+                if (window.parent && window.parent !== window) {
+                    contexts.push(window.parent);
+                }
+            } catch (_) {}
+            try {
+                if (window.top && !contexts.includes(window.top)) {
+                    contexts.push(window.top);
+                }
+            } catch (_) {}
+
+            const run = () => {
+                contexts.forEach((ctx) => scrollContainersToTop(ctx));
+            };
+
+            run();
+            requestAnimationFrame(run);
+            setTimeout(run, 60);
+
+            let attempts = 0;
+            const intervalId = setInterval(() => {
+                run();
+                attempts += 1;
+                if (attempts >= 20) {
+                    clearInterval(intervalId);
+                }
+            }, 60);
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
@@ -1337,50 +1401,51 @@ def sok_brreg(soketekst):
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
+    scroll_til_toppen()
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
@@ -1537,29 +1602,30 @@ if st.session_state.hoved_firma:
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
                             <li>{scoredata['datakvalitet_grunner'][4]}</li>
                         </ul>
                     </div>
                     """, unsafe_allow_html=True)
 
                 st.markdown('<div style="margin-top: 0.9rem;"></div>', unsafe_allow_html=True)
                 col_a, col_b = st.columns([3, 1])
                 with col_b:
                     if st.button("Analyser", key=f"an_{lead['organisasjonsnummer']}_{i}", use_container_width=True):
                         st.session_state.soke_felt = lead["organisasjonsnummer"]
+                        st.session_state.scroll_topp = True
                         st.session_state.auto_analyse_orgnr = lead["organisasjonsnummer"]
                         if "brreg_sok" in st.session_state:
                             del st.session_state["brreg_sok"]
                         st.rerun()

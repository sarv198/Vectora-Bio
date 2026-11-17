# Manual tests

Hands-on checks that each major feature produces its intended output on the JUMP pilot data (CPJUMP1, U2OS). Expected values below were measured on the current build of the data. Small differences after a rebuild are fine; large ones are worth investigating.

## Before you start

1. Start Docker Desktop, then the database: `docker compose up -d db` (from `vectora-bio/`).
2. Start the API: `cd backend` then `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`.
3. Start the web app: `cd frontend` then `npm run dev`, and open http://localhost:3000.
4. The sidebar footer should read `Connected · 817 profiles` next to a green dot.

Cell images are fetched from the public Cell Painting Gallery the first time a well is viewed (about 2 to 3 MB per channel, a few seconds), then cached in `data/raw/images/`. You need an internet connection for wells you have not viewed before.

---

## 0. Plates, images and theme

| Step | Expected |
| --- | --- |
| Open **Plates** in the sidebar. | The plate menu lists 10 plates, grouped as 4 CRISPR guide (144 h), 4 compound (48 h) and 2 ORF (48 h) plates. |
| Click plate `BR00117010`. | A 16 x 24 plate map: blue compound wells, gray DMSO control wells, with counts in the legend. Hovering a well names it. |
| Click any blue well. | The well's image appears beside a DMSO control from the same plate. Both have a `100 µm` scale bar. |
| Toggle channels (DNA, ER, RNA, AGP, Mito, BF), change the field (1 to 9), switch the display to **Channels**. | Each change redraws the images. Channels mode shows one grayscale image per selected stain. |
| Hover an image and click the expand icon in its top-right corner. | A full-resolution 1080 px PNG opens in a new tab. |
| Use the sun / moon / monitor switch at the bottom of the sidebar. | The whole app switches between light, dark and system themes, and the choice survives a reload. Image viewers stay black in both themes. |

---

## 1. Compound similarity

**Test 1a: a mechanism with a clear signature.** Query `geldanamycin` (HSP90 inhibitor).

| Check | Expected |
| --- | --- |
| Top hits | The table lists the top 5 by default (raise **Results to show** in Parameters for more). #1 ganetespib (cosine about 0.97) and #2 NVP-HSP990 (about 0.96). Both are HSP inhibitors, so their mechanism is shown in teal with a check mark. |
| Key findings | "Nearest: ganetespib, cosine 0.97 (top 0.1% of compound pairs)" and "2 of 5 share the query's mechanism (HSP inhibitor)". |
| Visual comparison | A large **Cosine similarity 0.97** readout on a -1 to 1 scale sits above the images. Query and hit #1 are shown side by side with the same channels and field. Each phenotype map has its **Largest changes vs. control** list underneath, and the agreement map is mostly teal (same direction). |
| Select hit #4 (azeliragon, an unrelated MoA) by clicking its row. | The comparison panel switches to azeliragon, with a lower overall cosine (about 0.87). Similar-looking cells do not always mean the same mechanism. |

**Test 1b: filters.** Open **Parameters**, tick **Only compounds with a known MoA** and set **Min. replicate agreement** to `0.5`. Rerun. Every hit now has a MoA label and a replicate value of 0.5 or more.

**Test 1c: microtubule drugs.** Query `epothilone-b` with **Results to show** set to 10. Expected: 3 of the top 10 share a tubulin-related MoA.

---

## 2. Drug-to-gene matching and target prioritization

**Test 2a: a kinase inhibitor whose target was knocked out.** Query `AMG900` (Aurora kinase inhibitor, annotated AURKA, AURKB and AURKC).

| Check | Expected |
| --- | --- |
| Key findings | "Annotated target AURKB ranks #1 of 160 genes". The annotated targets are listed above the findings (hover the (i) next to the label: never used in scoring). |
| Candidate genes table | Top 5 genes by default. Row #1 is AURKB, labelled "Annotated target of query", priority about 0.49. |
| Comparison below the table | AMG900 wells beside the AURKB CRISPR knockout. Tick **Show same-plate controls** to add each one's negative control. AMG900 cells typically look much larger, with enlarged and irregular nuclei: Aurora B inhibition blocks cell division. Under each phenotype map, **Largest changes vs. control** lists that perturbation's top five features: for AMG900, nuclear DNA features with very large z-scores. |
| Click the bordered arrow button at the end of the AURKB row (anywhere close to it works) | It lists the genetic reagents with cosine and percentile, and the compounds annotated to AURKB with their cosine to the query. |
| **Reagent matches** tab | The raw reagent ranking by cosine. Selecting a row updates the comparison panel to that reagent. |

**Test 2b: phenotype-only ranking.** Open **Parameters**, set **Weight of similar compounds** to `0` and rerun AMG900. AURKB should still be #1, now from the phenotype match alone. This is the setting to use for novel chemistry (see the evaluation results).

**Test 2c: more cases that should rank their target #1.** `ceritinib` (ALK), `GSK1070916` (AURKB), `RGB-286638` (CDK9), `PP-2` (LCK).

---

## 3. Mechanism of action

**Test 3a.** Query `geldanamycin`.

| Check | Expected |
| --- | --- |
| Top mechanism | `HSP inhibitor`, labelled "Matches the hidden annotation". The query's own label is hidden from inference and shown only for comparison (see the (i) next to "Annotated mechanism"). |
| Key findings | "Most likely: HSP inhibitor, confidence 15% (22% of the vote, 2 of 10 annotated neighbours)" and "Top calls are right for 6% of 291 annotated compounds: treat them as leads." |
| Confidence | About 15%. Low confidence is expected and honest: it is the measured hit rate of calls with this vote share when known compounds were hidden, and many labels in this dataset belong to a single compound. |
| Click the mechanism row or its arrow button | It lists the supporting compounds (ganetespib, NVP-HSP990) with their cosines. |
| Nearest compounds table | Selecting a neighbour shows query and neighbour images and maps side by side, so you can see the evidence behind the vote. |

**Test 3b: other correct calls.** `danusertib` (Aurora kinase inhibitor), `PP-1` and `WH-4-023` (SRC inhibitor), `RGB-286638` (CDK inhibitor).

**Test 3c: an unannotated compound.** Choose one from **Or an unannotated compound**. The query summary says "None: this is a true prediction", and the findings make no claim about matching an annotation.

---

## 4. Phenotypic rescue

**Test 4a: a CDK2 knockout.** On **Genes**, open `CDK2` and choose the CRISPR guide `BRDN0001147786`. Its images should show far fewer, larger, spread-out cells than the same-plate control. Click **Find rescue compounds**.

| Check | Expected |
| --- | --- |
| Perturbation summary | Largest changes include `Cell intensity: IntegratedIntensity [ER]` and `[RNA]`, about 4.7 MAD. |
| Compounds ranked | "202 (104 weak excluded)", out of 306 compounds. |
| Top candidates | #1 CC-401 with a reversal score of about 0.44, #2 GSK2110183 about 0.42, #3 dexamethasone about 0.35. |
| Flags | `desonide` (#4) carries a **Cell loss** flag. Hover it for the explanation. |
| Comparison below the table | A large **Reversal score 0.44** readout (matching the table) sits on a scale from -1 Mimics to 1 Reverses, above the images. CDK2 knockout and its control on the left, CC-401 and its DMSO control on the right. The agreement map is mostly terracotta: those cells are where the compound moves features opposite to the knockout. |
| Click the arrow button at the end of row #1 | It shows the features driving the reversal and those working against it, plus bars by measurement and by stain. The note says the contributions sum to the score. |

**Test 4b: filters.** Open **Parameters** and untick **Exclude weak responses** and rerun. Now all 306 compounds are ranked, and weak compounds can enter the top 10 (e.g. TUG-891 at about 0.37). Then tick **Exclude cell-loss and stress-like compounds**: flagged compounds disappear, and the findings state how many were excluded.

The disclaimer that rescue candidates must be confirmed experimentally is under **How it works**.

---

## 5. Evaluation and interpretability

**Test 5a: run the benchmarks.** Open **Evaluation**, keep the defaults (5 folds, both split strategies) and click **Run benchmarks**. It takes about 15 seconds. Expected on the random split, with the unseen-target split in brackets:

| Metric | Method | Baseline |
| --- | --- | --- |
| Similarity recall@10 | about 19% (14%) | about 4% |
| MoA top-1, recoverable | about 9% (6.5%) | about 0.5% |
| Targets hit@10, phenotype + similar compounds | about 21% (15%) | about 9% |
| Targets hit@10, phenotype only | about 18% (18%) | about 9% |

Every method bar should sit clearly above its gray baseline bar.

**Test 5b: leakage audit.** The leakage audit at the bottom marks each check as Passed: reference and test compounds never overlap, every compound is tested exactly once, and test annotations are hidden from predictions. On **Unseen targets** a fourth check appears: no designed target on both sides of a split.

**Test 5c: the key finding.** On **Unseen targets**, "phenotype only" should beat "phenotype + similar compounds" for targets. This is why test 2b recommends neighbour weight 0 for new chemistry.

**Test 5d: interpretability.** Explanations live next to each prediction:

- Targets: expand a gene row to see the reagent and compound evidence and the priority formula.
- MoA: expand a mechanism to see the supporting compounds.
- Rescue: expand a candidate to see per-feature contributions that sum to the score.
- Every comparison panel shows *where* two profiles agree or oppose, by compartment and stain, next to the cell images.

**Test 5e: history.** Reload the page. The run you just made appears under previous runs and can be reopened.

---

## 6. Work is kept while you move around

| Step | Expected |
| --- | --- |
| Run a similarity search, select row #4, then open **Genes** and come back to **Compound similarity** from the sidebar. | The query box, parameters, results and the selected row are all as you left them. |
| Do the same on Drug-to-gene matching (switch to the **Reagent matches** tab first), Mechanism of action and Phenotypic rescue. | Each page keeps its own query, results, selected row and tab. |
| Start a rescue search and switch pages before it finishes, then come back. | The page shows it is still running, then the results appear. |
| Reload the browser tab. | Everything is still there. Closing the tab clears it. |
| On **Plates**, pick a plate and well, leave, and come back from the sidebar. | The same plate and well are shown. |

---

## Error states (no fabricated results)

| Action | Expected |
| --- | --- |
| Stop the database (`docker compose stop db`), then reload the Overview. | The sidebar footer shows the database as unavailable and database-backed pages such as Compounds show a "Database unavailable" notice instead of empty or invented data. Restart it with `docker compose up -d db`. |
| Disconnect from the internet and open a well you have never viewed. | The image area shows "Could not reach the Cell Painting Gallery" instead of a picture. Wells viewed before still load from the cache. |
| Stop the API. | Pages show "Cannot reach the API at http://localhost:8000". |

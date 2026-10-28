# How to verify every output

Every output has a manual check and an automated one (`python -m pytest tests`; `python -m isoleret.reproduce` rebuilds and compares
everything).

## Three levels
1. **The file:** `MANIFEST.json` (app: `data/manifest.json`) lists each delivered file with SHA-256, producer, inputs (model, fire knowledge
   base, code) and the tests that cover it. Drag a file onto **Verificér**; it is hashed in the browser and never uploaded.
2. **The number:** every run has **Vis beregning**, with each step in numbers: layer diameters, mean temperature, λ, R per layer, surface
   temperature, h_cv, h_r, R_se, q, support allowance, U, class limit, annual loss. Each step ends on the audit's own value (✓). The PDF has
   the same steps in its appendix, so they can be redone by hand or in a spreadsheet.
3. **The method:** two published tables are reproduced cell by cell (CSV downloads on Verificér), and `reproduce` re-runs validation and
   audit from the source IFC.

## Output by output

| Output | Check it yourself | Automated check |
|---|---|---|
| DS 452 class per run | Look up the run's system, part, operation and ambient band in table 6.4 (shown on Metode) | Answer key 25/25 (`test_i5_answer_key`), class cases (`test_i2_table_6_4_and_limits`) |
| Heat loss, U, status | "Vis beregning" or the PDF appendix; redo q = Δθ/(ΣR + R_se) | Browser trace = audit for every run (`test_i11`), physics properties (`test_i1`), parity to 1e-9 (`test_i9`) |
| The physics itself | Compare with DS 452 Annex A and Energihåndbogen (CSV, Metode) | 72 + 96 cells within stated tolerances (`test_i3`, `test_i4`); the 50 % finding is asserted |
| Required thickness and proposal | Beregner: move the slider; the curve crosses the class line at the required thickness | Every proposal meets its class (`test_i6_audit_consistency`) |
| Condensation | Dew point (Magnus) vs surface temperature, both shown | `test_i1b`; KONDENS runs get a proposal above the dew point (`test_i6`) |
| Savings, cost, payback | Per-run kWh = (q_now − q_new)·length·hours; prices are labelled examples | Summary = sum of runs (`test_i6`), `reproduce` |
| Fire cross-check | The cited ETA section and page per penetration | Riser and plant-room cases asserted (`test_i7_fire_crosscheck`); same engine as Gennemført (parity-tested there) |
| Survey CSV | Open in Excel | Round trip CSV → audit = IFC → audit (`test_i8`) |
| PDF / XLSX | Open; row counts | `test_i10_deliverables`, manifest hash (`test_i12_reproduce`) |

## Limits
λ curves are typical class values; prices and CO₂ factors are examples; the Annex A design λ is fitted (stated). The building is fictitious.

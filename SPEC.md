# Isoleret: spec

**One line:** audit the technical insulation of a building against DS 452, with EN ISO 12241 physics, economics and a fire
cross-check at every penetration, from an IFC model or a survey.

## Buyer and setting
A wholesaler/advisory that sells both passive fire protection and technical insulation. Its customers are installers, insulation
contractors, consultants and building owners. Typical questions: *which pipes don't meet DS 452, how thick should they be, what does it
save, and what do we order?* and, on renovations, *can we add insulation without breaking the fire seals?* Today the answers come from
DS 452 tables, a manufacturer's single-pipe calculator, a site walk and experience, one pipe at a time.

## Gap → improvement → proving test
| Gap | Improvement | Proving test |
|---|---|---|
| Class per pipe looked up by hand in table 6.4 | Rule table: system × part × operation × ambient band → class (+ condensation note) | I2 class cases; answer key 25/25 |
| Annex A tables only cover 60 °C/20 °C, Ø18-60 | EN ISO 12241 with λ(θm), h_cv + h_r, support allowance; any temperature, diameter, material, cladding | I3: Annex A reproduced (72 cells, RMS 0.76 mm) |
| Savings estimates from generic tables | Savings per run from the physics, components included (valve = 0.2 m, pump = 1 m) | I4: Energihåndbogen reproduced (96 cells); the 50 % basement rule found to be absent from the numbers |
| Condensation on cold pipes found on site | Dew point vs surface temperature; condensation-free thickness | I1b |
| Energy upgrades and fire seals handled by different people | Every fire-rated crossing checked with the Gennemført engine today and after the proposal; table 6.2 rule applied | I7 |
| No BIM in most existing buildings | Survey CSV with the same fields; identical audit | I8 round trip |
| Calculator only in the office | Browser engine identical to Python; MCP for assistants | I9 parity (1e-9), MCP test |
| Report and order list assembled by hand | PDF report, XLSX, material list with jackets for components | I10 |

## Limits
λ curves are typical class values (replace with the product's declared values). Prices and CO₂ factors are examples. The Annex A design λ is
fitted because the standard does not state it. Fire conclusions are limited to the two ETAs in the knowledge base; deviations need a
brandteknisk vurdering by a person. The demonstration building is fictitious.

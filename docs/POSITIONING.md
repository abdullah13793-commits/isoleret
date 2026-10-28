# Positioning: Isoleret next to existing tools

**Short version:** single-pipe insulation calculators are good and free. Isoleret is not another calculator. It audits a whole building
against DS 452, prices the upgrade, and is, as far as we know, the only tool that checks the upgrade against the fire seals the pipes pass
through.

## What incumbents do well
| Tool type | Strong at |
|---|---|
| Manufacturer calculators (e.g. ROCKWOOL ROCKTEC, Armacell's and Kaimann's calculation tools, Paroc's) | EN ISO 12241 calculations for one pipe or surface with the manufacturer's own λ data; condensation thickness; economic thickness |
| DS 452 itself (Annex A tables) and Energistyrelsen's Energihåndbogen | Quick reference thicknesses and savings for standard cases |
| Energy-consultant spreadsheets | Building-level savings estimates |
| Fire-protection selectors and Gennemført | Tested penetration seals |

Isoleret does not claim better physics than the manufacturers' tools. It uses the same standard and is validated against the published
tables.

## Where Isoleret differs
1. **Whole building, not one pipe.** It takes runs from IFC (pipes, coverings, components, spaces) or a survey CSV, assigns the class from
   table 6.4 automatically, and checks every run, valve and pump.
2. **Brand-neutral.** Material classes with replaceable λ curves, so a wholesaler can show any brand it carries.
3. **Energy meets fire.** It checks every fire-rated crossing against the tested ETA configurations before and after the proposal, and
   resolves conflicts with DS 452 table 6.2. No incumbent tool we know of does this.
4. **Evidence.** It reproduces DS 452 Annex A and Energihåndbogen's tables, states the fitted parameters, and surfaced an inconsistency
   in the published savings tables (the 50 % rule).
5. **From audit to order.** Report, workbook, material list with jackets, and an MCP server.

## Honest gaps
| Gap | Plan |
|---|---|
| λ curves are class-typical | Load declared curves for the products carried |
| Ducts and tanks (plane surfaces) not yet audited at building level | The physics (`flat`) is in place; add DS 452 plane limits to the audit |
| Prices are examples | Connect the customer's price list |
| Demo building is fictitious | Pilot on a real survey (CSV) or MEP model |

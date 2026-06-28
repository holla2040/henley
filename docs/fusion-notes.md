# Fusion Electronics — introspection notes (hendrix)

Recorded from a **live** Autodesk Fusion session via the Fusion MCP server,
reached from WSL2 Claude Code over a Windows port-forward (see the README
"Fusion MCP from WSL" section). Active design at capture: **`comet`**
(schematic-only — no board yet).

## How the design is read

The Fusion MCP exposes one read tool for Electronics:

- `fusion_mcp_electronics_read(entity_type, object?)`
  - `entity_type`: one of `electronics.<Class>` (e.g. `electronics.Part`,
    `electronics.Attribute`, `electronics.Device`, `electronics.Schematic`).
  - `object`: optional `{ fields[], filters[{property,op,value}], pagination{limit,offset} }`.
  - Per-class field/filter schema lives at
    `resource://mcp.electronics_schema_<snake_class>` (e.g.
    `..._schema_part`, `..._schema_attribute`). `tools/list` advertises
    `fusion_mcp_electronics_read`, `fusion_mcp_execute`, `fusion_mcp_read`,
    `fusion_mcp_update`.

Requires an active Electronics document. Read returns rows as a JSON string in
`result.content[0].text` → `{ "items": [...], "pagination": {...} }`.

## Object model (what we walk)

- `electronics.Part` = a placed component **instance** on the schematic.
  Columns: `object_id`, `name` (designator, e.g. `U1`/`R1`), `value`
  (e.g. `22k`, or a supply-net name like `GND` for power symbols),
  `module_object_id`, `deviceset_object_id`, `device_object_id`,
  `package3d_object_id`. **No part-number columns inline** — those are
  attributes (below). `comet` has 50 Part rows, many of which are GND/supply
  pseudo-parts (`value` = `GND`, `package3d_object_id` = 0).
- `electronics.Attribute` = name/value metadata attached to a part. Filter by
  **`part_object_id`** (`{property:"part_object_id", op:"eq", value:<Part.object_id>}`)
  to get a part's metadata, including library-defined defaults. Columns:
  `name`, `value`, `part_object_id`, `element_object_id`, `instance_object_id`,
  `constant`, `default_value`, `display`.

## ⭐ Where the JLCPCB code lives (the open question — RESOLVED)

The JLCPCB / LCSC `Cxxxx` code is a **part attribute named `LCSC`**.
The manufacturer part number is the **`MPN`** attribute. Observed on `comet`:

| Designator | `LCSC` (→ jlcCode) | `MPN` (→ manufacturerPart) | `MANUFACTURER` |
|-----------|--------------------|----------------------------|----------------|
| U1 | `C52717` | `STM8S003F3P6TR` | STMicroelectronics |
| U2 | `C84817` | `MT3608` | XI'AN Aerosemi Tech |
| R1 | `C2907015` | `FRC0603F2202TS` | FOJAN |

So **parts carry the real `Cxxxx` LCSC code directly** — Henley's
code-based enrichment (`getComponentDetailByCode`) works with no MPN→code
mapping step. (If a part ever lacks `LCSC` but has `MPN`, that part would need
an MPN search path, which is not yet wrapped — see `docs/api-reference.md`.)

### Attribute-name mapping to the Henley contract

| Fusion attribute | Henley `DesignPart` field |
|------------------|---------------------------|
| `LCSC`           | `jlc_code` (`jlcCode`)    |
| `MPN` (or `MP`)  | `manufacturer_part` (`manufacturerPart`) |
| `MANUFACTURER` (or `MF`) | kept in `attributes`  |
| `PACKAGE`        | `package`                 |
| Part `value`     | `value`                   |
| Part `name`      | `designator`              |

Caveats seen in real data:
- Attribute names are **not fully standardized** across library parts. U2
  (MT3608) uses `MP`/`MF` **in addition to** `MPN`/`MANUFACTURER`, plus extra
  SnapEDA/DigiKey fields (`CHECK_PRICES`, `SNAPEDA_LINK`, `DIGIKEY_PART_NUMBER`,
  `PRICE`, `AVAILABILITY`, `DESCRIPTION`). The extractor reads `LCSC` for the
  code and falls back `MPN`→`MP` for the MPN.
- `PACKAGE` is sometimes a placeholder (`"Package "`); treat as best-effort.
- GND / supply symbols and the title-block/logo part (`U$1`, value `v1.0`)
  have no `LCSC`/`MPN` and are excluded from the BOM extraction.

## Design name

`electronics.Schematic` row `name` is a temp path ending in `comet sch.sch`;
the design/document name is taken as **`comet`**.

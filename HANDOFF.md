# HANDOFF — Fusion-side work order + verified-facts log

This file is **not** a build directive for the CLI — that work (`henley
alternates`, `scr`, `stock`, and the discover→verify→trade-off workflow) is done
and documented in `CLAUDE.md` (architecture + the agentic workflow) and
`README.md` (usage). What remains here is two things the next agent still needs:

1. **The open Fusion-side work order** — `extract_components()` running *inside*
   Fusion 360 is still a stub (§1).
2. **A verified-facts / decisions log** — hard-won facts and reference data that
   don't live in `CLAUDE.md`/`docs/api-reference.md` (§2–§4).

Do not re-derive the verified facts below; do not web-search the JLC **API/docs**
questions (the docs are local — see §2). For the alternate-finding conversation,
the playbook and the jlcsearch matching rules are in `CLAUDE.md` ("Finding
alternates in a conversation").

---

## 1. OPEN WORK ORDER — Fusion-side `extract_components()` (still a stub)

The goal that is **not yet built**: enumerate the components in the active Fusion
Electronics design *from inside Fusion* and emit the parts-export JSON that
`henley fusion` / `henley stock` consume (the contract is in `fusion.py`).

- `src/henley/fusion.py::extract_components()` raises `NotImplementedError` — it
  must run inside Fusion 360's embedded Python (`adsk.fusion`), i.e. as a Fusion
  add-in / script, not in this package's interpreter.
- Today the live read is done **interactively over the HTTP bridge** (§3), not by
  packaged code. Wrapping that read into a committed Fusion add-in (or a
  bridge-driven extractor) that produces the parts-export JSON is the remaining
  integration work. Runs on the `hendrix` Windows box (localhost to Fusion, can
  use the Fusion API MCP server).
- Known blocker for a pure-bridge extractor: the bridge's `electronics.Attribute`
  reader does **not** surface the JLC attributes (`LCSC`/`MPN`/…) — see §3. So a
  bridge-only path needs another way to read those, or the add-in approach.

---

## 2. JLC API — verified facts NOT already in CLAUDE.md / api-reference.md

The authoritative docs are **local**: `docs/api-reference.md` (committed,
verified against the PDFs), the original JLCPCB API **PDFs** in `sdk/docs/*.pdf`,
and the SDK jars in `sdk/`. Note: `sdk/` (jars **and** `sdk/docs/`) is
**git-ignored** — local reference only, not in a fresh clone.

- **No server-side search** (confirmed three ways): SDK request VOs carry only
  `lastKey`/`pageSize`/`currentPage`; `api-reference.md` bodies are
  pagination-only; live calls agree. The official API's only discovery role is to
  **verify** codes (jlcsearch is the discovery surface — see CLAUDE.md).
- **Catalog-stream throughput (measured)** — relevant only if an exhaustive local
  cache is ever built: `getComponentInfos` returns **1000 rows/request**, ~0.9
  req/s sequential → a full catalog (~400–600k parts) is **~400–600 requests,
  ~7–11 min**. A one-time cache is fine (~500 requests total); per-search full
  scans are not. `429` ("too many requests") is the only documented rate-limit
  signal (no numeric limit published) — if caching, be sequential, backoff,
  resumable. Searches against a local cache cost **zero** API calls.
- **In-API discovery fallback** (for exhaustive completeness only, not routine
  "find an alternate"): iterate `getComponentInfos` + filter client-side, then
  verify. `JLCClient.iter_component_infos()` is wrapped. This means caching the
  whole catalog — the user **rejected** doing this "for one part"; jlcsearch
  makes it unnecessary.
- `getComponentInfos` row shape (the catalog stream, distinct from
  `getComponentDetailByCode`): `lcscPart`, `firstCategory`/`secondCategory`,
  `mfrPart`, `manufacturer`, `libraryType` (`base`/`expand`), `description`
  (specs as text), `price` (encoded `qtyRange:unitPrice,...`), `stock`, `package`.

---

## 3. Fusion Electronics bridge — VERIFIED FACTS

- **Bridge transport:** plain HTTP JSON-RPC at `http://<host>:27182/mcp`. From
  WSL2 reach it at the **WSL gateway IP** (e.g. `172.17.64.1`, from
  `ip route | grep default`), NOT `127.0.0.1`, and the Windows portproxy must bind
  the gateway IP, **never `0.0.0.0`** (0.0.0.0 hijacks loopback and breaks Fusion's
  server + Claude Desktop). Handshake: `initialize` → (capture `Mcp-Session-Id`
  header) → `notifications/initialized` → `tools/call`. Tools:
  `fusion_mcp_electronics_read`, `fusion_mcp_execute` (runs Python), `fusion_mcp_read`,
  `fusion_mcp_update` (undo/redo). MCP tool schemas are available via ToolSearch
  (`mcp__fusion__*`).
- **A modal dialog open in Fusion silently blocks the bridge** — every call
  returns an empty HTTP body. If reads come back empty, ask the user to close any
  open Fusion dialog. (Distinct from a clean `{"items":[]}`, which means "query ran,
  no rows".)
- **The Electronics API is READ-ONLY.** Verified at the API surface: `adsk.electron`
  `Part` exposes only `_get_deviceset` (no setter — can't change a footprint); no
  attribute setter exists; `Schematic` mutators are limited to `deleteEntities` +
  display props + `beginDesignChange/endDesignChange`. `app.executeTextCommand`
  reaches Fusion's **core** command window, NOT the EAGLE electronics command line
  (`GRID`/`UPDATE` → "no command").
- **`neu_dev.run_text_command("SCRIPT path.scr")`** IS the Python→electronics
  command bridge, BUT it lives only in the **Electronics text-command Python
  sandbox** (the "Py" radio in File > View > Show Text Commands), a different
  interpreter from `fusion_mcp_execute`. Verified: `import neu_dev` in the bridge →
  `ModuleNotFoundError`; not a file anywhere in ~30k dirs of the Fusion install.
  **So the bridge can READ the design but cannot WRITE it.** The user applies a
  generated `.scr` themselves: *File > Execute Script*, or the neu_dev line in Py
  mode. (`henley scr` generates that script.)
- **`electronics.Attribute` reader limitation:** the bridge does NOT surface part
  JLC attributes (`LCSC`/`MPN`/`MANUFACTURER`/`DESC`) via any filter — it returns
  `{items:[]}`. Those are visible in Fusion's "Attributes of Rn" dialog but not via
  the reader. `Part`/`Instance`/`Device`/`Package` reads DO work (`Element` is empty
  when only the schematic, not the board, is open). **This blocks a pure-bridge
  `extract_components()`** (§1).
- **Package variant names carry a LEADING HYPHEN.** The comet resistor deviceset's
  0402 variant is literally `-0402`, not `0402`. `CHANGE PACKAGE '0402' Rn` errors;
  `CHANGE PACKAGE '-0402' Rn;` works. Always read the real variant names off the
  device rather than guessing.

---

## 4. Reference data captured (decisions log)

- `C315567` = **AON7544**, N-channel MOSFET, **DFN-8(3×3)**, 30 V / 30 A /
  5 mΩ@10 V, Vgs(th) 2.2 V, **Extended** (`expand`), ~$0.117/ea@1, live stock
  ~252k. The live "find an alternate" target used to validate `henley alternates`.
- `C2907015` = 22 kΩ 0603 ±1% Extended (FRC0603F2202TS); migrated to
  `C25768` = 22 kΩ 0402 ±1% **Basic** (0402WGF2202TCE, stock ~610k). The comet
  22k resistors (R1,R2,R4,R5,R7,R9) were all migrated 0603→0402.
- Worked substitution example: `C114683` 220 Ω 0603 ±5% Extended → `C25091`
  (0402WGF2200TCE, Basic, ±1%) — cheaper, far more stock, tighter tolerance, **but**
  0603→0402 drops power 100 mW → 62.5 mW (75 V → 50 V); 220 Ω across 5 V is
  ~114 mW, which **exceeds** the 0402 rating. That electrical caveat is exactly the
  Claude-in-the-loop judgment step — surface it before recommending.
- Observation: JLC's **Basic library is almost all passives** — a ~170k-part scan
  found only two Basic N-channel MOSFETs (2N7002, AO3400A), both small SOT-23; a
  *Basic* 30 A power MOSFET very likely does not exist. (Reminder: Basic/Extended
  is a fee attribute, **not** a selection criterion — do NOT filter on it.)
- `docs/comet-0402-migration.md` is a migration-decision worksheet (designators,
  qty, value, old/new code, MPN/mfr, caveats) — a good template for substitution
  output.

---

## 5. Standing rules (also in CLAUDE.md)

- Never `git add -A` / `git add .` — stage files individually by path.
- Never commit or push unless the user explicitly asks (each git op is separate).
- Never hardcode or commit secrets; `.keys` stays git-ignored.
- Keep dependencies minimal (core install is `requests` only).
- Update `docs/api-reference.md` alongside any new **JLC endpoint** wrapper.

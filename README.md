# Henley

<img src="image/henley.png" alt="Henley — James Garner as Hendley, 'the Scrounger', in The Great Escape" width="160" align="right">

A small Python tool for querying the **JLCPCB** parts inventory (LCSC / JLC
components) and — going forward — for consolidating part information pulled
directly from **Autodesk Fusion Electronics**, so you can validate part
availability and speed up JLCPCB **PCB Assembly (PCBA)** order submissions.

> Named after James Garner's character Hendley, "the Scrounger", in the film
> *The Great Escape*.

Henley is a Python reimplementation of JLCPCB's official Java OpenAPI SDK. The
reverse-engineered API contract is documented in
[`docs/api-reference.md`](docs/api-reference.md).

> **Note:** the reference JLCPCB Java SDK jars are **not** distributed with this
> repo. You don't need them to run Henley — they were only used to reverse-
> engineer the contract. If you want to cross-check against them, download the
> Core + Business SDK jars from JLCPCB yourself and drop them in a local `sdk/`
> directory (git-ignored).

## Why Henley

In *The Great Escape*, Hendley is **"the Scrounger"** — the guy who quietly goes
out and comes back with whatever the team needs. That's the job here: Henley
scrounges JLCPCB so you don't have to sit on the JLC parts site hand-searching
for components, stock, and equivalents.

A concrete example. Say your schematic is full of **0603** resistors, each
already tagged with a JLC/LCSC part number, and you decide to move the whole
board to **0402** to save space. Now you need, for *every* resistor, the
equivalent **0402** part that:

- matches the electrical spec (resistance, tolerance, power rating, …),
- is actually **in stock** at JLCPCB, and
- ideally is a Basic/preferred assembly part to keep PCBA cost down.

Doing that by hand — one web search per part — is exactly the tedium Henley is
meant to remove. That is what `henley alternates` does **today**: give it a part
and a constraint ("same package", "at least 40 A") and it discovers candidate
replacements, verifies each one's **live** JLC stock / price / specs, and lays
out the trade-off so you can pick. See
[Finding a replacement part](#finding-a-replacement-part).

**Where this is heading.** Henley reads the design and looks up each part, you
pick the replacements, and it generates a Fusion `.scr` script that applies the
package + part-number changes ([The `.scr` file format](#the-scr-file-format)).
The Fusion Electronics *object* API is read-only — **but the EAGLE command line
is reachable from Python/MCP** via
`executeTextCommand('Electron.run "script C:\\path\\changes.scr"')`, so Henley can
fire the `.scr` straight into the running schematic over the bridge (no manual
*Execute Script* step). That closes the loop: writing the new JLC part number
back into the schematic at the new package size, turning a whole-board package
migration from a day of manual searching into a single query. The point of all
this: validate
availability and source equivalents automatically, so JLCPCB **PCBA** orders go
out faster and with fewer surprises.

## What it does today

Read-only component (parts inventory) endpoints, signed with JLCPCB's `JOP`
authentication scheme, exposed through a `henley` CLI and a small Python API:

- **Find an alternate part** (`henley alternates`) — discover candidate
  replacements from a parametric index and verify each one **live** against JLC
  for stock, price, and specs, then weigh the trade-off and choose. See
  [Finding a replacement part](#finding-a-replacement-part).
- **Inventory check** a BOM (`henley stock`) — flag out-of-stock / problem parts
  before a board submission.
- Generate Fusion Electronics migration scripts (`.scr`) to batch part package
  and attribute changes — see
  [The `.scr` file format](#the-scr-file-format).
- Look up full component detail (price tiers, stock, parameters, datasheet).
- Browse the assembly component library.
- List your private / consigned JLC inventory.
- Verify that your credentials and request signing are working.

## Install

Requires **Python >= 3.10**. The core install depends only on `requests`.

```bash
git clone git@github.com:holla2040/henley.git
cd henley
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional extras:

```bash
pip install -e ".[dev]"       # pytest, ruff
```

> **If `henley` isn't found after install** — usually the virtualenv isn't
> activated, or `pip install -e .` put the script somewhere off your `PATH`. You
> don't need the installed command: run it as a module from the repo root, which
> only needs `requests`:
>
> ```bash
> PYTHONPATH=src python -m henley.cli ping     # or: python -m henley ping
> ```
>
> Every `henley <cmd>` example in this README works the same way via that form.

### Set your JLC API keys (required)

Henley authenticates every request with JLCPCB OpenAPI credentials. Without them
the CLI cannot reach the API. The credentials are **not** committed — they are
read at runtime from a **`.keys` file you create at the project root** (the
repo's `.gitignore` already excludes `.keys`, `*.pem`, and `*.key` so they can
never be committed).

1. Get your credentials from the JLCPCB developer console (`api.jlcpcb.com`):
   **AppID**, **Accesskey**, and **SecretKey**.
2. Create **`.keys`** in the repo root (same folder as `pyproject.toml`) with
   this exact layout (placeholders shown — substitute your own values):

   ```
   JLCAPI:
       AppID:     <your-app-id>
       Accesskey: <your-access-key>
       SecretKey: <your-secret-key>
   ```

   These three fields are all Henley uses. The JLCPCB `.keys` file may also
   contain an RSA "Tokenization Key" block — Henley **ignores it** (it would
   only matter for order placement, which is not implemented), so you can leave
   it in or strip it out.
3. Alternatively, point `HENLEY_KEYS` at a `.keys` file elsewhere
   (see [Environment variables](#environment-variables)).

See [Configuration](#configuration) for full details on the file format and
discovery order.

## Quickstart

1. Install and set your `.keys` file as above.
2. Verify credentials and signing:

```bash
henley ping
```

`ping` distinguishes the two states you might hit:

- **Signing OK, permission missing** — the request authenticated correctly but
  your app lacks the component API permission. Enable it for your app in the
  JLC developer console, then retry.
- **Signature rejected** — check the `AppID` / `Accesskey` / `SecretKey` in
  `.keys`.

3. **Find an alternate for a part.** Pick the category (`--list-categories`) and
   the constraint, then let Henley discover + verify candidates:

```bash
henley alternates --list-categories                  # the category slugs (offline)
henley detail C315567                                 # get the part's exact package string
henley alternates C315567 --category mosfets --package "DFN-8(3x3)" --top 10
```

   Henley prints the target, then candidates with their **live** stock, price,
   and specs — it does not pick for you. Pass `--json` to get the full data (e.g.
   to hand to Claude for the trade-off). Full details, including the fuzzy
   `search` path, are in [Finding a replacement part](#finding-a-replacement-part).

## CLI command reference

```
henley [--keys PATH] <command> [options]
```

| Command | Description |
|---------|-------------|
| `henley ping` | Verify credentials + signing; reports whether signing works and whether the component API permission is enabled. |
| `henley detail C2040 [C... ...]` | Full component detail for one or more JLC component codes (price tiers, stock, parameters, datasheet). |
| `henley private [--page N] [--limit N]` | Your private / consigned JLC inventory. |
| `henley library [--limit N]` | Browse the assembly component library. |
| `henley fusion PARTS.json [--no-enrich]` | Ingest a Fusion parts-export JSON and enrich each part against JLC (stock, price tiers, basic/extended). `--no-enrich` validates the file offline without calling the API. |
| `henley stock PARTS.json [--min-stock N] [--json]` | **Inventory check** — look up live stock for every part in a BOM and flag any that are out of stock, not found, or below `--min-stock`. Exits nonzero if any part is out-of-stock or not found, so it can gate a submission (`henley stock bom.json && submit`). |
| `henley scr SWAPS.json [SWAPS2.json ...] [-o FILE.scr] [--design NAME]` | Generate a Fusion `.scr` migration script from one or more swap files (merged into one combo script). Emits the `CHANGE PACKAGE` + `ATTRIBUTE` commands you run in Fusion. Runs offline — no credentials needed. See [The `.scr` file format](#the-scr-file-format). |
| `henley alternates CODE --category SLUG [--package PKG] [-p KEY=VALUE ...] [--top N] [--json]` | **Find an alternate** for a part: DISCOVER candidates from the third-party parametric index `jlcsearch.tscircuit.com`, then VERIFY *every* hit against the live JLC API (stock, price, parameters) and print a trade-off table. It does **not** rank or pick — you (or Claude) weigh stock / price / spec margin / package. `--list-categories` lists the slugs (offline). See [Finding a replacement part](#finding-a-replacement-part). |

`--keys PATH` overrides credential discovery for any command.

**Output format.** `detail`, `private`, `library`, and `fusion` print **JSON** to
stdout by default — they have **no `--json` flag** (passing one is an error); pipe
them to `jq`/`python3` to parse. Only **`stock`** and **`alternates`** accept
`--json`; without it they print a human-readable report. `ping` prints a status
line; `scr` prints (or writes with `-o`) the `.scr` script. A command's flags are
exactly what `henley <cmd> --help` lists — don't assume a flag exists because
another command has it.

## Python usage

```python
from henley import JLCClient

client = JLCClient()

# Full detail by component code
detail = client.get_component_detail_by_code(["C2040"])

# One page of the assembly component library
page = client.get_component_library_list(page_size=30)

# Iterate the entire library (follows the lastKey cursor)
for row in client.iter_component_library():
    print(row["componentCode"], row["componentModel"])

# Your private / consigned inventory
private = client.get_private_component_library(current_page=1, page_size=30)
```

## Configuration

### `.keys` file

Credentials are loaded at runtime from a **git-ignored** `.keys` file at the
project root (it is parsed by `src/henley/config.py`). They are never hardcoded
and never committed. The file is the one issued by JLCPCB and uses this format
(placeholders shown — substitute your own values):

```
JLCAPI:
    AppID:     <your-app-id>
    Accesskey: <your-access-key>
    SecretKey: <your-secret-key>
```

Henley reads only the `AppID`, `Accesskey`, and `SecretKey` fields. The JLCPCB
`.keys` file as issued also includes an RSA "Tokenization Key" block (for
encrypting order-placement fields such as shipping addresses); Henley does not
implement order placement and **ignores that block entirely**, so it is optional
and may be omitted.

### Environment variables

| Variable | Effect |
|----------|--------|
| `HENLEY_KEYS` | Path to the `.keys` file (overrides discovery). |
| `HENLEY_ENDPOINT` | Override the API host. |

Path resolution order for credentials: the `--keys` / explicit argument, then
`HENLEY_KEYS`, then a `.keys` file discovered by walking up from the current
working directory.

## Endpoint and permissions

- **API host:** `https://open.jlcpcb.com` (the default).
  Note: `api.jlcpcb.com` is the developer **portal / console**, not the API
  host.
- **Auth scheme `JOP`:** every request carries
  `Authorization: JOP appid="..",accesskey="..",timestamp="..",nonce="..",signature=".."`,
  where `signature = Base64(HMAC_SHA256(secretKey, stringToSign))` and
  `stringToSign = METHOD\nCANONICAL_URI\nTIMESTAMP\nNONCE\nPAYLOAD\n`.

Signing has been verified empirically against the live API:

- A **valid** signature returns `HTTP 403 {"code":403,"message":"API
  insufficient permissions, access denied"}` for this account.
- A **wrong** signature returns `HTTP 401 {"code":401,"message":"The request
  signature verify failed"}`.

So signing is proven correct — the account just needs the component API
permission enabled in the JLC console.

## Reading from Fusion Electronics (no MCP client required)

Henley reads a live Autodesk Fusion design over **plain HTTP** — it issues
JSON-RPC `POST`s directly to the local endpoint Fusion exposes at
`http://127.0.0.1:27182/mcp`. **You do not need any MCP client or middleware**
to use it: no Claude Desktop "Autodesk Fusion" extension, no MCP connector, and
no `claude mcp add` registration. The endpoint speaks the MCP wire protocol, but
from Henley's side it is just an HTTP API you `POST` to with `curl` / `requests`
(`initialize` → `tools/call` with `fusion_mcp_electronics_read`). See
[`docs/fusion-notes.md`](docs/fusion-notes.md) for the request shapes and where
each part's JLC `Cxxxx` code lives (the part's `LCSC` attribute).

The only requirement on the **Windows / Fusion side** is that Fusion is running
with its built-in server enabled — **Preferences > General > API > Fusion MCP
Server** — and an Electronics document open. That is what publishes the HTTP
endpoint; nothing else needs to be installed.

### Reaching it from WSL2 (networking note)

If you run Henley on the same Windows machine as Fusion, `http://127.0.0.1:27182`
just works. If you run it under **WSL2**, Windows loopback isn't reachable across
the NAT boundary, so forward the port on the **Windows** side (elevated
PowerShell).

> ⚠️ **Use the WSL gateway IP as `listenaddress`, NOT `0.0.0.0`.** A `0.0.0.0`
> listener on `27182` sits in front of the *same* loopback port Fusion's server
> and the Claude Desktop "Autodesk Fusion" connector use, and hijacks their
> `127.0.0.1:27182` traffic — Fusion appears to "connect then close
> unexpectedly" and **Claude Desktop stops connecting**. Bind the WSL-facing
> gateway address specifically so loopback is never intercepted.

First get the WSL→Windows gateway IP **from inside WSL** (it is also the address
WSL uses to reach Windows):

```bash
ip route | grep default | awk '{print $3}'   # e.g. 172.17.64.1
```

Then, on Windows (elevated), forward that address only — substitute your gateway
IP for `172.17.64.1`:

```powershell
netsh interface portproxy add v4tov4 listenaddress=172.17.64.1 listenport=27182 connectaddress=127.0.0.1 connectport=27182
```

From WSL, reach Fusion at `http://172.17.64.1:27182/mcp`. The gateway IP can
change across WSL restarts — re-check it with the `ip route` line above and
re-add the rule if Fusion becomes unreachable.

**Health check / troubleshooting.** On Windows, `curl http://127.0.0.1:27182/mcp`
should return `{"error": "Not Found"}` instantly when Fusion's server is healthy.
If it (or Claude Desktop) "closes the connection unexpectedly," a bad `0.0.0.0`
forward is almost certainly hijacking loopback — delete it and the symptom
clears:

```powershell
netsh interface portproxy show all     # look for a 0.0.0.0 ... 27182 entry
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=27182
```

Remove the (correct) gateway forward when you're done with:

```powershell
netsh interface portproxy delete v4tov4 listenaddress=172.17.64.1 listenport=27182
```

## The workflow

There is **one** workflow. A part needs to change — it's **out of stock**, you
want a **different package**, or a **different value** — and the path is the same
each time; only the trigger differs. It runs as an interactive
[Claude Code](https://claude.com/claude-code) session in this repo: Claude reads
the live design and does the JLC lookups, **you** make the design decision, and
**Fusion** is where the change is written (the Electronics *object* API is
read-only, but the `.scr` can be applied either manually or fired over the bridge
with `Electron.run` — see step 5). `comet` below is just an example design.

**Before you start**

1. Fusion is running with an **Electronics document open** and the **MCP Server
   enabled** (see [Reading from Fusion Electronics](#reading-from-fusion-electronics-no-mcp-client-required)).
2. Under WSL2, the port forward is up (same section,
   [networking note](#reaching-it-from-wsl2-networking-note)).
3. Your `.keys` file is in place (or use the `PYTHONPATH=src` fallback above).
4. **No modal dialog is open in Fusion** — an open dialog (e.g. *Attributes of
   Rn*) silently blocks the bridge, so every read comes back empty.

**The loop**

1. **Read the live design.** Ask Claude — e.g. *"read the comet design and list
   the resistors with their values and package variants."* Claude reports
   designators, values, and the **exact package variant names** on each deviceset
   (literal library names, often with a leading hyphen — `-0402`, not `0402`).
2. **Find a replacement** for the part that needs changing — Claude discovers
   candidates and verifies them live (`henley alternates`, with `henley detail` to
   anchor on the original). See [Finding a replacement part](#finding-a-replacement-part).
3. **Decide the swap** with Claude — weigh inventory / price / spec margin /
   package; Claude surfaces electrical caveats (e.g. a 0603→0402 shrink lowers the
   power rating). The decision is yours.
4. **Generate the `.scr`.** Claude writes a `swaps.json` and runs
   `henley scr swaps.json -o changes.scr`. The script carries the **package
   variant and the attributes** (`LCSC`/`MPN`/`MANUFACTURER`/…). See
   [The `.scr` file format](#the-scr-file-format).
5. **Apply it in Fusion.** Two ways:
   - **Manual** — *File > Execute Script* (or the
     `neu_dev.run_text_command("SCRIPT …")` line in the text-command Py mode), then
     set anything the script doesn't carry — **notably a changed schematic value**
     (e.g. 220 Ω → 330 Ω) — in Fusion as well.
   - **Over the bridge** — have Claude fire it with
     `executeTextCommand('Electron.run "script C:\\tmp\\changes.scr"')` via the MCP
     `fusion_mcp_execute` tool. The same channel sets the value
     (`Electron.run "VALUE R6 330"`), so the whole change is one scripted stream.
     `Electron.run` returns nothing, so Claude verifies by re-reading; changes are
     **unsaved** until you save in Fusion. (Details:
     [Reading from Fusion Electronics](#reading-from-fusion-electronics-no-mcp-client-required)
     and `docs/fusion-notes.md` → "The WRITE path".)
6. **Verify** — ask Claude to re-read the design and confirm each part landed on
   the new package, attributes, and value.
7. **Reconcile** — update your BOM record (the parts JSON) so it points at the new
   code; a later `henley stock` then reflects reality. Save in Fusion.

**Gotchas**

- Close any modal dialog in Fusion before a read — an open dialog returns empty.
- The Fusion Electronics **object** API is read-only, but the EAGLE command line
  is reachable via `Electron.run` (step 5) — so Claude *can* apply the `.scr` over
  the bridge, or you run it manually. A **bare** `executeTextCommand("script …")`
  does **not** work (hits Fusion's core channel); it must be wrapped in
  `Electron.run "…"`.
- A `.scr` **stops at the first failing command**, which can leave a partial
  change — sanity-check variant names before a big batch, and keep the run undoable.

`docs/comet-0402-migration.md` is one worked example of this workflow (a batch of
resistors moved 0603 → 0402) — a useful template for the decision worksheet.

### Finding a replacement part

The official JLCPCB API **cannot search** — it only verifies codes you already
hold (`getComponentDetailByCode`). So `henley alternates` finds replacements in
two steps:

1. **Discover** candidate codes from `jlcsearch.tscircuit.com`, a third-party
   parametric index of the whole JLC catalog (one HTTP query, no catalog download).
2. **Verify** *every* returned code against the live JLC API in one batched call,
   for authoritative stock / price / parameters. jlcsearch's stock is a **stale
   cached snapshot** (seen off by 30–600× in both directions), so the table is
   built on the live numbers, not jlcsearch's.

It deliberately **does not rank or pick** — it gathers and verifies; you (or
Claude) weigh inventory vs. price vs. spec margin vs. package.

```bash
henley alternates --list-categories                 # the jlcsearch category slugs
# same-package alternates for a 30 A DFN-8 MOSFET:
henley alternates C315567 --category mosfets --package "DFN-8(3x3)" --top 10
henley alternates C315567 --category mosfets --package "DFN-8(3x3)" --json   # full data
```

**The spoken filter becomes flags.** "Same package, at least 40 A" → Claude picks
the category and translates the constraint into `--package` / `-p key=value` query
params. A value/numeric hard filter (e.g. "330 Ω") is best applied by reading the
**verified `parameters[]`** in the `--json`, not via jlcsearch query params — see
the matching notes below.

**How jlcsearch matches (verified against its source):**

- `package` (and the other per-category string filters) match by **exact,
  case-sensitive equality — no wildcards**. `DFN-8` ≠ `DFN-8(3x3)`; `%`, `*`, and
  substrings all return nothing. Use the target's exact `componentSpecification`
  (from `henley detail`) as `--package`.
- Numeric `_min` / `_max` params (e.g. `continuous_drain_current_min`) are
  **unreliable** — jlcsearch's structured numeric columns are sparsely populated
  (a `_min` filter silently drops every row whose value is null). Passive value
  fields (`resistance`, `capacitance`) are dense and safe.
- The **fuzzy / cross-package escape hatch** is the generic `components` category
  with a full-text `search`: `henley alternates C315567 --category components -p
  search="AON75"` (token + prefix matching; surfaces the same MPN across package
  spellings; in-stock parts only).

### The `.scr` file format

`henley scr` turns a table of swaps into the `.scr` you run in Fusion (loop step
5) — the write channel for package and attribute changes, ideal for batch edits
(migrating dozens of resistors to a new package, repointing parts to new JLC
codes) without clicking each part by hand.

Describe the changes in a swap JSON file (object with a `swaps` list, or a bare
list). Only `designator` is required per swap:

```json
{
  "design": "comet",
  "swaps": [
    {
      "designator": "R1",
      "package": "-0402",
      "lcsc": "C25768",
      "manufacturer": "UNI-ROYAL",
      "mpn": "0402WGF2202TCE",
      "attributes": { "DESC": "1%" }
    }
  ]
}
```

- `package` is the library **variant name** — note it is the exact name from the
  device, often with a leading hyphen (e.g. `-0402`, not `0402`). Omit it to
  change attributes only.
- `lcsc` / `manufacturer` / `mpn` are conveniences that map to the `LCSC` /
  `MANUFACTURER` / `MPN` attributes; `attributes` carries any other attribute
  (e.g. `DESC`) and overrides the conveniences.

Generate the script (offline — no credentials needed). Multiple swap files merge
into one combo script you execute once:

```bash
henley scr swaps.json -o changes.scr
henley scr 22k.json 10k.json 220r.json -o changes.scr   # combo
```

Each swap renders as `CHANGE PACKAGE` **before** the `ATTRIBUTE` lines (switching
the variant can reset variant-default attributes, so the values are written
afterward):

```
CHANGE PACKAGE '-0402' R1;
ATTRIBUTE R1 LCSC 'C25768';
ATTRIBUTE R1 MANUFACTURER 'UNI-ROYAL';
ATTRIBUTE R1 MPN '0402WGF2202TCE';
ATTRIBUTE R1 DESC '1%';
```

The script covers **package and attributes**. A changed **schematic value** (e.g.
220 Ω → 330 Ω) is not part of the `.scr` — it's set in Fusion when you apply the
change (loop step 5). You run the generated script in Fusion as described in the
loop.

## Security

- `.keys` holds your AppID, access key, and secret key. It is listed in
  `.gitignore` and must **never** be committed.
- Credentials are loaded only at runtime; nothing is hardcoded in the source.
- `*.pem` and `*.key` files are also git-ignored.

## Project history — how this was built

Henley exists because JLCPCB ships an official **Java** OpenAPI SDK but no Python
one. Rather than wrap the Java SDK, the contract was **reverse-engineered from
the JLCPCB Java SDK jars** (the Core SDK + Business SDK) and reimplemented as a
small, dependency-light Python package.

1. **Recover the contract from the jars.** The decompiled Java SDK was read to
   recover: the component (parts inventory) endpoints and their request/response
   value objects; the response envelope (`{ code, message, data }`); and the
   serialization rules (fields emitted as **camelCase**, null fields **omitted**)
   that the wire format depends on. The result is captured as the source of
   truth in [`docs/api-reference.md`](docs/api-reference.md).
2. **Pin the auth scheme.** JLCPCB's `JOP` authentication
   (`Authorization: JOP appid=..,accesskey=..,timestamp=..,nonce=..,signature=..`)
   was reproduced exactly from the SDK's signer: `signature =
   Base64(HMAC_SHA256(secretKey, METHOD\nURI\nTIMESTAMP\nNONCE\nPAYLOAD\n))`.
   `tests/test_auth.py` pins the Python implementation to the Java algorithm so
   it can't drift.
3. **Reimplement in pure Python.** `auth.py` (signing), `client.py` (signed
   `POST` plumbing + the read-only component endpoints + envelope unwrap),
   `config.py` (runtime `.keys` loading), and a `henley` CLI — core install
   depends only on `requests`.
4. **Verify against the live API.** Signing was confirmed empirically: a *valid*
   signature returns `HTTP 403` (insufficient permissions) while a *wrong*
   signature returns `HTTP 401` (signature verify failed) — proving the signing
   is correct and that the remaining gate is account-side permission, not code.
   It also confirmed the real API host is `https://open.jlcpcb.com`
   (`api.jlcpcb.com` is the developer portal).

That JLC reverse-engineering and Python reimplementation was done in Claude Code
on **horton** (the Linux dev box), session
`fd5ea0ac-6e74-4f38-8b3e-8435fc6f1512`.

5. **Add the Fusion Electronics bridge.** On **hendrix** (the Windows box
   running Autodesk Fusion), Henley was extended to read a live electronics
   design over plain HTTP (see
   [Reading from Fusion Electronics](#reading-from-fusion-electronics-no-mcp-client-required)).
   Introspecting a real design answered the key open question — the JLCPCB
   `Cxxxx` code is stored as each part's **`LCSC`** attribute — which lets the
   extractor produce `henley_parts.json` and feed those codes straight into the
   JLC query layer for stock/price enrichment. Details in
   [`docs/fusion-notes.md`](docs/fusion-notes.md).

## Roadmap

1. **Fusion Electronics integration.** Henley will read designs **directly**
   via the Autodesk Fusion API (currently read-only for electronics) — *not* by
   exporting a BOM. A Fusion add-in / script will enumerate the electronic
   design's components and their MPN / LCSC part attributes, then feed those
   part numbers into Henley's JLC query layer to report availability, stock,
   price tiers, and basic/extended (assembly) status — so you know what is
   available before submitting a PCBA order. A stub module is planned at
   `src/henley/fusion.py`.

2. **PCBA order automation.** The JLC SDK also exposes PCB order endpoints
   (`uploadGerber`, calculate price, create order), where address and other
   sensitive fields must be RSA-tokenized with the `.keys` RSA key. These
   endpoints are mapped in [`docs/api-reference.md`](docs/api-reference.md) but
   not yet wrapped — when they are, this is where the RSA tokenization key (and
   a `cryptography` dependency) would come back in.

## Future enhancement: streamlining JLCPCB board submission

> **Earmarked, not yet scoped.** This is a known pain point we intend to address
> later; nothing here is implemented. Captured so we don't lose the problem.

Submitting a PCBA order through the JLCPCB **website** is one of the slowest,
most tedious parts of the whole workflow. The order form validates your uploads
*after* you submit them, so it becomes a back-and-forth loop:

- **BOM errors.** If the Bill of Materials has a problem — an out-of-stock part,
  an unrecognized or mismatched component, a column the parser doesn't like — you
  have to fix the BOM and **re-upload it**. In practice this happens *repeatedly*:
  one fix surfaces the next issue, and each round is a full upload-and-revalidate
  cycle.
- **CPL / placement errors.** Likewise, if the Component Placement List (CPL,
  the pick-and-place file) has a problem — a missing or off placement, a rotation
  or origin mismatch — you have to correct it and **upload a new CPL file**, then
  wait for revalidation again.

This upload → validate → fix → re-upload churn, alternating between BOM and CPL,
eats a lot of time and is the main bottleneck in getting an order placed.

**What to investigate.** Whether the JLCPCB **API** (the order/PCBA endpoints
already documented in [`docs/api-reference.md`](docs/api-reference.md) but not yet
wrapped — gerber/BOM/CPL upload, price calculation, order creation) lets us move
this validation *off* the website and *into* Henley, so problems are caught and
fixed **before** the tedious manual round-trips. The two highest-value targets
are exactly the two error classes above:

- **Inventory / BOM pre-validation** — check every part's stock and
  Basic/Extended status against the JLC API up front (building on Henley's
  existing component lookups and the part-substitution work) so out-of-stock or
  problem parts are resolved *before* submission, not discovered mid-upload.
- **Placement / CPL pre-validation** — sanity-check the CPL against the design
  (designators, rotations, coordinates) before it ever reaches the website.

Goal: turn order submission from a slow, error-prone website loop into a
prepared, pre-validated package — ideally driven (or submitted) through the API.

## License

Proprietary.

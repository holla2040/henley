# HANDOFF — Fusion Electronics integration (for Claude on `hendrix`)

You are Claude Code running on **hendrix** (Windows, `192.168.0.7`), the machine
where **Autodesk Fusion is running**. This document hands off the Fusion side of
the **Henley** project. The JLC (JLCPCB) side is already built and verified on a
Linux box; you can't reach Fusion from there, but you can — Fusion's API is
local to you.

## Why this split

- The **Fusion API MCP server is localhost-only** — it can only drive a Fusion
  instance on the same machine. So **only you (on hendrix) can extract data from
  the running electronics design.** The Linux box has no Fusion and no access.
- Conversely, the JLC client, signing, CLI, and the parts data-contract are
  done. Your job is the missing piece: **get the design's parts out of Fusion in
  the agreed JSON shape**, then let Henley enrich them against JLC.

## Mission

From the **active Fusion electronics design**, produce a `henley_parts.json`
that matches Henley's parts-export contract, then verify it flows through
`henley fusion`. Bonus: implement `extract_components()` in
`src/henley/fusion.py` if the API is reachable from Henley's own Python on
hendrix.

## Getting the project (already done — sshfs mount)

This project directory is **sshfs-mounted on hendrix**, so you already see the
live tree at your local mount path (NOT `/home/holla/...` — use wherever it's
mounted on this Windows box). No clone, push, or copy is needed, and **`.keys`
is present through the mount**, so enrichment can run right here on hendrix.

Two mount caveats:
- The checked-in **`.venv/` is Linux binaries** and will not run on Windows.
  Create a *separate* Windows venv **outside the mount** (e.g.
  `C:\venvs\henley`) so you don't clobber the Linux one on the shared tree.
- Writes you make land on the Linux box too (it's the same files). That's the
  intended data path: write `henley_parts.json` here and it's instantly visible
  on both machines.

Git remote is set (`origin = git@github.com:holla2040/henley.git`) but the repo
is **not committed/pushed** — irrelevant given the mount; don't push without the
user's explicit go-ahead.

## The data contract (what you must produce)

Authoritative definition + loader: `src/henley/fusion.py` (`DesignPart`,
`load_parts_json`). Shape:

```json
{
  "source": "fusion-electronics",
  "schemaVersion": 1,
  "design": "<active document name>",
  "generatedAt": "<ISO-8601, optional>",
  "parts": [
    {
      "designator": "R1",                       // REQUIRED
      "manufacturerPart": "RC0402FR-0710KL",    // optional (MPN); alias: "mpn"
      "jlcCode": "C25744",                       // optional JLC/LCSC code; alias: "lcsc"
      "value": "10k",                            // optional
      "package": "0402",                         // optional
      "quantity": 4,                             // optional, default 1
      "attributes": { }                          // optional raw Fusion attrs
    }
  ]
}
```

- Only `designator` is strictly required per part.
- **`jlcCode` is what JLC enrichment keys on.** Parts without it pass through as
  `found: false`. Capturing the JLC `Cxxxx` code is the highest-value goal.

## Step-by-step

1. **Confirm the Fusion API MCP server is connected** to your Claude Code
   session (check available MCP tools). Confirm Fusion is open with the target
   electronics design active.

2. **Discover the object model (introspection first — don't guess).** The
   Electronics Python API is version-dependent and still maturing, so first
   enumerate what's actually exposed in *this* Fusion:
   - active `Application` → active `Document` / `Product`; is there an
     electronics/ECAD design object? schematic? board?
   - the list of components / devices / parts, and **for one component, dump all
     its attributes/properties** so we can SEE where the JLC `Cxxxx` code and the
     MPN are stored (a named attribute? the device name? a supplier/part field?).
   - Write findings to `docs/fusion-notes.md` so the contract mapping is recorded.

3. **Resolve the open question: where is the JLC code?** (see below). Map the
   real Fusion field → `jlcCode` / `manufacturerPart` in the contract.

4. **Extract → write `henley_parts.json`** matching the contract above.

5. **Validate offline (no credentials needed):**
   ```
   henley fusion henley_parts.json --no-enrich
   ```
   This parses and reports how many parts carry a JLC code. Fix mapping until
   every populated component shows up correctly.

6. **Enrich against JLC** (needs the JLC permission enabled — see Blocker, and
   `.keys` present on whichever box runs it):
   ```
   henley fusion henley_parts.json
   ```
   Emits per-part stock / price tiers / library type (basic vs extended).

7. **(Optional) Implement `extract_components()`** in `src/henley/fusion.py` so
   Henley can pull from Fusion directly on hendrix (replace the
   `NotImplementedError`). Keep the same `DesignPart` output. Then a single
   `henley` command can extract+enrich end to end on hendrix.

## OPEN QUESTION you must resolve with the user / via introspection

Where is the JLCPCB/LCSC `Cxxxx` code stored on each component?
- a **named attribute** (e.g. `LCSC`, `JLCPCB Part #`) — best case,
- only the **MPN** — then we need MPN→JLC mapping. ⚠️ The currently-wrapped JLC
  endpoints look up **by JLC code only** (`getComponentDetailByCode`); there is
  no MPN search wrapped yet. If parts only have MPNs, flag it — we may need to
  add/scrape a search path. See `docs/api-reference.md`.
- encoded in the **device/library name**.

## Blocker (JLC side, account toggle — not code)

JLC enrichment currently returns `403 "API insufficient permissions"`. Signing
is **proven correct** (valid sig → 403 perms; wrong sig → 401). The user must
enable the **component API permission** for their OpenAPI app in the JLC console
(`api.jlcpcb.com`). Until then, `--no-enrich` still fully validates extraction.

## Verified facts (don't re-derive)

- JLC API host: **`https://open.jlcpcb.com`** (`api.jlcpcb.com` is the portal).
- Auth `JOP`: `Authorization: JOP appid="..",accesskey="..",timestamp="..",nonce="..",signature=".."`,
  `signature = Base64(HMAC_SHA256(secretKey, "METHOD\nURI\nTS\nNONCE\nPAYLOAD\n"))`.
- Full API contract: `docs/api-reference.md`. Reference Java SDK jars: `sdk/`.

## Credentials

`.keys` (JLC AppID/Accesskey/SecretKey + RSA tokenization keypair) is **visible
on hendrix through the sshfs mount**, so you can run the full extract→enrich flow
locally. It stays git-ignored — never commit it.
- `config.py` resolves keys via `HENLEY_KEYS` env or a `.keys` discovered by
  walking up from the cwd (the mounted root has it); endpoint via
  `HENLEY_ENDPOINT`.
- Offline `henley fusion … --no-enrich` needs no credentials at all.

## Environment / setup on hendrix

Use a Windows venv **outside the sshfs mount** (the in-tree `.venv/` is Linux):

```
python -m venv C:\venvs\henley
C:\venvs\henley\Scripts\activate
pip install -e ".[dev]"     # run from the mounted project dir; requests + pytest + ruff
pytest                       # 7 tests should pass (signing + ingest contract)
```

## Data path between machines

The sshfs mount **is** the shared path — files you write on hendrix appear on the
Linux box and vice-versa. Just write `henley_parts.json` into the project dir; no
sockets, git transfer, or copying needed. (FYI: hendrix is `192.168.0.7`; the
Linux box is Tailscale-only, but you don't need direct networking given the mount.)

## Standing rules (inherited)

- Never `git add -A` / `git add .` — stage files individually by path.
- Never commit or push unless the user explicitly asks.
- Never hardcode or commit secrets; keep `.keys` out of git.

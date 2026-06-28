# JLCPCB OpenAPI — Reference (reverse-engineered from the official Java SDK)

This document captures the JLCPCB OpenAPI contract as extracted from the
official Java SDK (Core SDK + Business SDK jars under `sdk/`). It is the source
of truth for the Python reimplementation in `src/henley/`.

- **Endpoint (overseas/global):** `https://api.jlcpcb.com` (from `notes`).
  The Java SDK's baked-in default is `https://openapi.jlc.com` (China).
- **All component routes are `POST`** with a JSON body, even ones whose names
  read like getters.

## Authentication — the `JOP` scheme

Each request carries an `Authorization` header built as follows
(`com.jlc.openapi.core.client.auth.authorization.SignAuthorization`):

```
string_to_sign = METHOD + "\n"
               + CANONICAL_URI + "\n"        # raw path, plus "?"+rawQuery if present
               + TIMESTAMP + "\n"            # str(int(epoch_seconds))
               + NONCE + "\n"                # 32-char random token
               + PAYLOAD + "\n"              # exact request body; "" for GET

signature = Base64( HMAC_SHA256(secret_key, string_to_sign) )

Authorization: JOP appid="<AppID>",accesskey="<Accesskey>",
               timestamp="<ts>",nonce="<nonce>",signature="<signature>"
```

Defaults from the SDK (`AuthProfile.Builder`): authenticator `JOP`
(scheme is literally `JOP`, no algorithm suffix), sign algorithm `HMAC_SHA256`.
The `secret_key` is the `.keys` `SecretKey`; `accesskey` is the `.keys`
`Accesskey`.

Other algorithms exist but are not the default: `HmacSHA1`, `SHA256withRSA`
(`RSA_SHA256`, signs with the RSA private key), `HMAC-SM3`.

Standard headers added by the SDK on every JSON call: `Authorization`,
`Content-Type: application/json`, `Accept: application/json`, `Accept-Language`,
`User-Agent`.

### Field tokenization (privacy) — orders only

For order placement the SDK can RSA-encrypt sensitive fields (e.g. shipping
address) with the public key in `.keys` ("Tokenization Key RSA"). Algorithm is
RSA (PKCS#1 v1.5) or SM2. **Not needed for read-only parts queries.**

## Serialization

`toJSON()` serializes Java fields by their **camelCase names** (a `@NameInMap`
annotation can override, but the component VOs don't use it). **Null fields are
omitted.** Nested objects/lists are serialized recursively.

## Response envelope

Responses wrap payloads as `{ code, message, data }` (success code `200`).
`data` is the per-endpoint structure below.

---

## Component (parts inventory) endpoints

### `POST /overseas/openapi/component/getComponentLibraryList`
Browse the assembly (SMT) component library, cursor-paginated.

Request: `{ "pageSize": int = 30, "lastKey": string|null }`
(`ComponentListRequest` uses `currentPage`/`pageSize`; `GetComponentLibraryRequest`
uses `pageSize`/`lastKey` — same URI, cursor form preferred.)

Response `data` (`ComponentLibraryResponseVO`):
- `componentLibraryInfoVOS`: list of
  - `componentCode`: string  (JLC code, e.g. `C2040`)
  - `componentModel`: string  (manufacturer part / model)
  - `componentSpecification`: string
- `lastKey`: string  (cursor for the next page)

### `POST /overseas/openapi/component/getComponentDetailByCode`
Full detail for specific component codes.

Request: `{ "componentCodes": [string, ...] }`

Response `data`: list of `ComponentDetailResponseVO`:
- `componentCode`: string
- `componentModel`: string
- `componentSpecification`: string
- `firstTypeName`: string  (top-level category)
- `secondTypeName`: string  (sub-category)
- `libraryType`: string  (e.g. base/extended)
- `description`: string
- `datasheetUrl`: string
- `solderJointCount`: int
- `priceRanges`: list of `{ startQuantity: long, endQuantity: long, unitPrice: decimal }`
- `stockCount`: int
- `parameters`: list of `{ parameterName: string, parameterValue: string }`
- `assemblyComponentFlag`: bool
- `eccnCode`: string
- `rohsFlag`: bool
- `lcscComponentId`: int

### `POST /overseas/openapi/component/getComponentInfos`
Bulk component info stream (cursor via `lastKey`).

Request: `{ "lastKey": string|null }`

Response `data` (`GetComponentInfoData`):
- `componentInfos`: list of `ComponentInfoVO`:
  - `lcscPart`: string
  - `firstCategory`, `secondCategory`: string
  - `mfrPart`: string
  - `packageInfo`: string
  - `solderJoint`: string
  - `manufacturer`: string
  - `libraryType`: string
  - `description`: string
  - `datasheet`: string
  - `price`: string
  - `stock`: int
- `lastKey`: string

### `POST /overseas/openapi/component/getPrivateComponentLibrary`
Your private/consigned inventory held at JLCPCB.

Request: `{ "currentPage": int = 1, "pageSize": int = 30 }`

Response `data`: list of `ComponentPrivateStockVO`:
- `componentModel`, `componentSpecification`, `componentCode`: string
- `jlcpcbParts`: int
- `globalSourcingParts`: int
- `consignedParts`: int
- `idleStock`: int

---

## PCB order endpoints (future — for automated PCBA submission)

Implemented in the SDK, not yet wrapped in Henley. Summary only:

- `POST /overseas/openapi/pcb/uploadGerber` (multipart) → file key
- `POST /overseas/openapi/pcb/calculate` → price quote (`GetOnlineCalculatePriceRequest`)
- `POST /overseas/openapi/pcb/create` → place order (`PcbCreateOrderRequest`; address
  fields are RSA-tokenized)
- `POST /overseas/openapi/pcb/order/detail`, `/audit/get`, `/wip/get` → status
- `POST /overseas/openapi/pcb/getImpedanceTemplateSettingList`,
  `GET /overseas/openapi/pcb/getSteelPriceConfig`

A parallel `tdp` package covers 3D-printing orders (`/overseas/openapi/tdp/api/*`).

See the decompiled source under the scratch directory for exact field lists of
the PCB/TDP request bodies.

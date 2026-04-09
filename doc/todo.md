# TODO

## Features

### High Priority

- [x] **Home / search page** `GET /`
  Landing page with two input fields — one for IP, one for AS number.
  Template: `html/index.html`

- [x] **My IP** `GET /myip`
  Detect caller's IP from `X-Forwarded-For`, fallback to `request.client.host`.
  Redirects to `/ip/{ip}`.

### Medium Priority

- [x] **Country prefix list** `GET /country/{iso}`
  Serves all IP ranges for a country from `Countries/{ISO}.txt`.
  Template: `html/country.html`

- [x] **Org / ASN search** `GET /search?q=...`
  Searches ASN organization names. Results link to `/asn/{asn}`.
  Template: `html/search.html`

- [x] **ASN scan cache**
  ASN DB iterated once at startup into `ASN_CACHE` dict.
  Country names also cached in `COUNTRY_NAMES` at startup.

### Low Priority

- [x] **CIDR calculator** `GET /cidr/{prefix}`
  Network address, broadcast, host range, host count, masks.
  Supports both IPv4 and IPv6. Template: `html/cidr.html`

- [x] **Bulk IP lookup** `POST /bulk`
  JSON array of up to 100 IPs → array of geo results. Always JSON.

- [x] **Health endpoint** `GET /health`
  Returns uptime, DB file sizes, cache entry counts.

## Possible future additions

- [x] **Subnet divider as standalone page** `GET /subnet`
  Interactive — split any subnet into two equal halves, join siblings back.
  Pure client-side JS, no page reload. IPv4 and IPv6. Template: `html/subnet.html`
  Linked from home page and accessible via `/subnet?q=10.0.0.0/8`.

- [x] **`.gitignore`**
  Excludes `.mmdb` files, `Countries/`, `venv/`, `__pycache__/`, `.idea/`, OS junk.

- [ ] **Reverse DNS integration** — show PTR records alongside IP info.

- [ ] **Rate limiting / auth** — for public-facing deployments.

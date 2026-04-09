# MaxMind GeoIP Lookup — Project Overview

A local GeoIP lookup service built on top of MaxMind's GeoLite2 offline databases.
It exposes both a human-readable web UI and a JSON API, and ships a set of CLI
utility scripts for offline database work.

---

## Directory Layout

```
maxmind/
├── server.py                # Main web server (Starlette/ASGI)
├── cli.py                   # CLI tool — single IP lookup → JSON
├── countries.py             # Utility: extract ISO codes → country_list.txt
├── extract.py               # Utility: dump per-country network ranges
│
├── GeoLite2-ASN.mmdb        # MaxMind ASN database (~11.7 MB)
├── GeoLite2-City.mmdb       # MaxMind City database (~64.8 MB)
├── GeoLite2-Country.mmdb    # MaxMind Country database (~9.5 MB)
├── mmdb_urls                # Download URLs for the .mmdb files
│
├── html/                    # HTML templates (Python string.Template)
│   ├── ip.html              # IP lookup result page
│   └── asn.html             # ASN → prefix list page
│
├── doc/                     # This documentation
│
├── Countries/               # Per-country network files (ISO_CODE.txt)
│   ├── IL.txt
│   ├── US.txt
│   └── ...
│
├── country_list.txt         # Generated: ISO_CODE,Country Name (one per line)
├── requirements.txt         # Python dependencies (see setup)
└── venv/                    # Python virtual environment
```

---

## Components

| Component | Purpose |
|---|---|
| `server.py` | HTTP server — IP and ASN lookups |
| `cli.py` | CLI one-shot IP lookup |
| `countries.py` | Generates `country_list.txt` from Country DB |
| `extract.py` | Exports per-country IP prefixes to `Countries/` |
| `html/ip.html` | Template: IP result UI |
| `html/asn.html` | Template: ASN prefix list UI |

---

## Data Sources

All geolocation data comes from MaxMind's **GeoLite2** free-tier databases.
These are binary `.mmdb` files queried with the `maxminddb` Python library.

| Database | What it provides |
|---|---|
| `GeoLite2-ASN.mmdb` | Maps IP prefixes → AS Number + Organization |
| `GeoLite2-City.mmdb` | Maps IPs → city, subdivision, country, coordinates, timezone |
| `GeoLite2-Country.mmdb` | Maps IPs → country and registered country |

Download URLs are stored in `mmdb_urls`. Databases should be refreshed
periodically (MaxMind updates them weekly).

---

## See Also

- [api.md](api.md) — All HTTP endpoints, request/response details
- [templates.md](templates.md) — How HTML templates work and the variables they use
- [scripts.md](scripts.md) — CLI utilities: usage and internals
- [setup.md](setup.md) — Installation and running the server

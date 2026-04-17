# netscope

A self-hosted GeoIP lookup service for offline IP geolocation and network intelligence. Provides a web interface and REST API backed by MaxMind GeoLite2 databases.

## Features

- **IP lookup** — country, city, coordinates, timezone, and ASN for any IPv4/IPv6 address
- **ASN lookup** — all network prefixes and countries for an Autonomous System
- **Country lookup** — all AS networks registered in a given country
- **Organization search** — find ASNs by company name
- **Multi-country search** — find ASes spanning multiple specified countries
- **CIDR calculator** — subnet details and divider tool
- **Bulk lookup** — up to 100 IPs per request
- **Content negotiation** — returns HTML for browsers, JSON for API clients

## Requirements

- Python 3.x
- MaxMind GeoLite2 databases (free account required at maxmind.com):
  - `GeoLite2-ASN.mmdb`
  - `GeoLite2-City.mmdb`
  - `GeoLite2-Country.mmdb`

## Setup

**Local:**

```bash
pip install -r requirements.txt
# Place the three GeoLite2-*.mmdb files in the project root
python server.py
```

**Docker Compose:**

```bash
# Place the three GeoLite2-*.mmdb files in the project root
docker-compose up -d
```

The server starts on port `8000`. Database loading and cache building takes a few seconds on first start.

## API

All endpoints accept both HTML (`text/html`) and JSON (`application/json`) via the `Accept` header.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/ip/{ip}` | IP lookup (supports CIDR: `/ip/1.1.1.0/24`) |
| `GET` | `/myip` | Redirect to caller's own IP lookup |
| `GET` | `/asn/{asn}` | ASN lookup (e.g. `/asn/15169` or `/asn/AS15169`) |
| `GET` | `/country/{iso}` | All networks in a country (e.g. `/country/US`) |
| `GET` | `/country-search?q=` | Search countries by ISO code or name |
| `GET` | `/search?q=` | Search organizations by name |
| `GET` | `/multi-country?q=` | ASes spanning multiple countries (comma-separated ISOs) |
| `GET` | `/asn/{asn}/country/{iso}` | Networks for an ASN filtered by country |
| `GET` | `/cidr/{prefix}` | CIDR subnet details |
| `GET` | `/subnet?q=` | Interactive subnet divider |
| `POST` | `/bulk` | Bulk IP lookup (JSON array, max 100) |
| `GET` | `/health` | Health check with database stats |

**Examples:**

```bash
curl http://localhost:8000/ip/8.8.8.8
curl http://localhost:8000/asn/15169
curl http://localhost:8000/search?q=Cloudflare
curl -X POST http://localhost:8000/bulk \
  -H "Content-Type: application/json" \
  -d '["1.1.1.1", "8.8.8.8", "9.9.9.9"]'
```

## CLI

A command-line lookup tool is included:

```bash
python cli.py 8.8.8.8
```

## License

Uses MaxMind GeoLite2 data — see [MaxMind's license](https://www.maxmind.com/en/geolite2/eula) for terms.

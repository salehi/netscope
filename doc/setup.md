# Setup & Running

## Requirements

- Python 3.10+
- MaxMind GeoLite2 `.mmdb` database files (see below)

## Install Dependencies

```bash
cd /path/to/maxmind
python -m venv venv
source venv/bin/activate
pip install maxminddb starlette uvicorn
```

## Obtaining the Databases

Download URLs are stored in `mmdb_urls`. You need a free MaxMind account to
download GeoLite2 databases.

Place the following files in the project root:

```
GeoLite2-ASN.mmdb
GeoLite2-City.mmdb
GeoLite2-Country.mmdb
```

MaxMind updates these databases weekly. Re-download and replace the files to
keep data current.

## Running the Server

```bash
source venv/bin/activate
python server.py
```

The server listens on `0.0.0.0:8000`.

Alternatively, run with uvicorn directly:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Verifying It Works

```bash
# JSON response
curl http://localhost:8000/ip/8.8.8.8

# HTML response (open in browser, or with curl)
curl -H "Accept: text/html" http://localhost:8000/ip/8.8.8.8

# ASN reverse lookup — JSON
curl http://localhost:8000/api/asn-networks/15169

# ASN reverse lookup — HTML
curl -H "Accept: text/html" http://localhost:8000/asn/15169
```

## Architecture Notes

- All three `.mmdb` databases are opened **once at startup** and kept open
  for the lifetime of the process. This avoids repeated file-open overhead
  and is safe because MaxMind databases are read-only.
- HTML templates (`html/*.html`) are also loaded once at startup into
  `string.Template` objects. No disk I/O happens per request for rendering.
- The server has no authentication, rate limiting, or caching. It is
  intended for local / trusted-network use.
- The ASN reverse lookup (`/asn/{asn}`) performs a full database scan on
  every request. Keep this in mind for high-traffic environments.

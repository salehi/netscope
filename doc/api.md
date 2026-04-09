# API Reference

The server runs on `http://0.0.0.0:8000` by default.

All error responses are JSON:
```json
{"error": "description of the problem"}
```

---

## IP Lookup

### `GET /ip/{ip}`

Full geolocation lookup for an IP address.

**Response format** is determined by the `Accept` header:
- `Accept: text/html` → renders `html/ip.html` in the browser
- Anything else → JSON

**JSON response structure:**
```json
{
  "asn": {
    "autonomous_system_number": 15169,
    "autonomous_system_organization": "GOOGLE"
  },
  "city": {
    "city": {"names": {"en": "Mountain View"}},
    "continent": {"names": {"en": "North America"}},
    "country": {
      "iso_code": "US",
      "names": {"en": "United States"},
      "is_in_european_union": false
    },
    "registered_country": {"iso_code": "US", "names": {"en": "United States"}},
    "subdivisions": [{"iso_code": "CA", "names": {"en": "California"}}],
    "postal": {"code": "94035"},
    "location": {
      "latitude": 37.386,
      "longitude": -122.0838,
      "accuracy_radius": 1000,
      "time_zone": "America/Los_Angeles"
    }
  },
  "country": {
    "country": {"iso_code": "US", "names": {"en": "United States"}},
    "registered_country": {"iso_code": "US", "names": {"en": "United States"}}
  }
}
```

**Errors:**
| Status | Cause |
|---|---|
| 400 | IP address is malformed or unresolvable in the DB |

---

## ASN Reverse Lookup

### `GET /asn/{asn}`

Finds all network prefixes belonging to an Autonomous System number.

**Accepted formats:** `15169` or `AS15169` (the `AS` prefix is stripped automatically).

**Response format** determined by `Accept` header:
- `Accept: text/html` → renders `html/asn.html`
- Anything else → JSON

**JSON response:**
```json
{
  "asn": 15169,
  "organization": "GOOGLE",
  "network_count": 123,
  "networks": [
    "8.8.4.0/24",
    "8.8.8.0/24",
    "2001:4860::/32",
    "..."
  ]
}
```

Networks are sorted lexicographically. IPv4 and IPv6 prefixes are mixed.

**Performance note:** This endpoint iterates the entire ASN database on every
request (~hundreds of thousands of records). Suitable for occasional use; not
intended for high-frequency automated calls.

**Errors:**
| Status | Cause |
|---|---|
| 400 | `asn` parameter cannot be parsed as an integer |
| 404 | No networks found for that AS number |

---

## JSON-only API Endpoints

These always return JSON regardless of the `Accept` header.

### `GET /api/asn/{ip}`

Returns only the ASN segment for the given IP.

```json
{
  "autonomous_system_number": 15169,
  "autonomous_system_organization": "GOOGLE"
}
```

---

### `GET /api/city/{ip}`

Returns only the city segment for the given IP (full MaxMind city record).

---

### `GET /api/country/{ip}`

Returns only the country segment for the given IP.

---

### `GET /api/asn-networks/{asn}`

Same as `GET /asn/{asn}` but always returns JSON. Accepts `15169` or `AS15169`.

```json
{
  "asn": 15169,
  "organization": "GOOGLE",
  "network_count": 123,
  "networks": ["8.8.4.0/24", "..."]
}
```

---

## Route Summary

| Method | Path | HTML | Description |
|---|---|---|---|
| GET | `/ip/{ip}` | yes | Full IP geolocation |
| GET | `/asn/{asn}` | yes | All prefixes for an ASN |
| GET | `/api/asn/{ip}` | no | ASN data for an IP |
| GET | `/api/city/{ip}` | no | City data for an IP |
| GET | `/api/country/{ip}` | no | Country data for an IP |
| GET | `/api/asn-networks/{asn}` | no | Prefix list for an ASN (JSON only) |

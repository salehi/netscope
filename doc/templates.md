# HTML Templates

Templates live in `html/` and use Python's `string.Template` substitution
(`$variable` syntax). They are loaded once at server startup and kept in
memory — no disk reads per request.

---

## html/ip.html — IP Lookup Page

Rendered by `GET /ip/{ip}` when the browser sends `Accept: text/html`.

### Template Variables

| Variable | Source | Description |
|---|---|---|
| `$ip` | URL path | The queried IP address |
| `$asn_number` | GeoLite2-ASN | Autonomous System number (integer) |
| `$asn_org` | GeoLite2-ASN | AS organization name |
| `$continent` | GeoLite2-City | Continent English name |
| `$country_name` | City → Country fallback | Country English name |
| `$country_iso` | City → Country fallback | ISO 3166-1 alpha-2 code (e.g. `US`) |
| `$registered_country` | City → Country fallback | Registered country English name |
| `$registered_country_iso` | City → Country fallback | Registered country ISO code |
| `$subdivision` | GeoLite2-City | First subdivision (state/province) name |
| `$subdivision_iso` | GeoLite2-City | Subdivision ISO code |
| `$city_name` | GeoLite2-City | City English name |
| `$postal` | GeoLite2-City | Postal / ZIP code |
| `$latitude` | GeoLite2-City | Latitude (decimal degrees) |
| `$longitude` | GeoLite2-City | Longitude (decimal degrees) |
| `$accuracy_radius` | GeoLite2-City | Accuracy radius in km |
| `$timezone` | GeoLite2-City | IANA timezone string (e.g. `America/Los_Angeles`) |
| `$is_eu` | City → Country fallback | `"true"` or `"false"` — whether the country is in the EU |

### Sections

- **Network card** — AS number (links to `/asn/$asn_number`) and organization
- **Location card** — Continent, country with ISO tag, city
- **Coordinates & Time card** — Lat/lon with accuracy radius, timezone
- **API footer** — Quick links to all JSON endpoints for the same IP

### Flattening Logic (`flatten_for_html`)

The server merges data from all three databases into a flat dict of strings
before substitution. Key rules:

- All values are cast to `str`; missing keys produce `""` (never `None`).
- `_en(obj, *keys)` traverses a nested dict and returns the `"en"` name.
- `_val(obj, *keys)` traverses and returns the raw scalar value.
- Country fields prefer the City DB record; the Country DB is the fallback.

---

## html/asn.html — ASN Prefix List Page

Rendered by `GET /asn/{asn}` when the browser sends `Accept: text/html`.

### Template Variables

| Variable | Type | Description |
|---|---|---|
| `$asn_number` | int | The AS number |
| `$asn_org` | str | Organization name from the first matching record |
| `$network_count` | int | Total number of prefixes found |
| `$networks_html` | str (pre-rendered HTML) | `<li>` elements, one per prefix |

### Network list rendering

The server builds `$networks_html` server-side before substitution:

```python
networks_html = "\n".join(
    f'<li class="{"v6" if ":" in n else ""}">{n}</li>'
    for n in networks   # already sorted
)
```

IPv6 prefixes (containing `:`) get the CSS class `v6`, which renders them
in a muted color to visually separate them from IPv4 prefixes.

### Sections

- **Header** — `AS{number}` in accent blue, organization name below
- **ASN Info card** — AS number, organization, total prefix count
- **Network Prefixes card** — scrollable list, count badge in the header
- **API footer** — links to the HTML and JSON endpoints for this ASN

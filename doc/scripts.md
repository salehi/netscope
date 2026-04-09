# Utility Scripts

Three standalone scripts complement the web server. They all open `.mmdb`
files directly from the current working directory, so run them from the
project root.

---

## cli.py — CLI IP Lookup

A minimal command-line tool that queries all three databases for a single IP
and prints the combined result as JSON.

### Usage

```bash
python cli.py -ip <IP_ADDRESS>
```

### Example

```bash
$ python cli.py -ip 8.8.8.8
{
  "ASN": {"autonomous_system_number": 15169, "autonomous_system_organization": "GOOGLE"},
  "City": { ... },
  "Country": { ... }
}
```

### Notes

- Opens and closes all three databases on every invocation (no persistent
  handles). Fine for one-off queries; not designed for batch use.
- Output keys are capitalized (`ASN`, `City`, `Country`) — different from
  the web server which uses lowercase (`asn`, `city`, `country`).
- Raw MaxMind records are printed as-is with no flattening or English-name
  extraction; locale-specific name dicts will appear in full.

---

## countries.py — Extract Country List

Iterates the Country database and writes a sorted list of unique ISO codes
and English country names to `country_list.txt`.

### Usage

```bash
python countries.py
# writes: country_list.txt
```

### Output format

```
AD,Andorra
AE,United Arab Emirates
AF,Afghanistan
...
```

One country per line, `ISO_CODE,English name`, sorted by ISO code.

### Logic

For each network record in `GeoLite2-Country.mmdb`:
1. Tries `registered_country.iso_code` first.
2. Falls back to `country.iso_code` if registered country is absent.
3. Skips records where neither field is a string.

Duplicates are de-duplicated via a Python `set` before writing.

---

## extract.py — Per-Country Network Export

Iterates the Country database and exports every IP network prefix into a
separate file per country under the `Countries/` directory.

### Usage

```bash
mkdir -p Countries
python extract.py
# writes: Countries/US.txt, Countries/IL.txt, ...
```

### Output format

Each file is named `Countries/{ISO_CODE}.txt`. Each line:

```
192.0.2.0/24	US
2001:db8::/32	US
```

Tab-separated: `NETWORK_PREFIX<TAB>ISO_CODE`.

### Logic

1. **Pass 1** — Collects all unique ISO codes from the database (same
   `registered_country` → `country` fallback as `countries.py`).
   Opens one output file per ISO code, stored in `CC_FILE` dict.
2. **Pass 2** — Iterates the database again. For each record, resolves the
   ISO code (registered_country → country) and writes the network line to
   the corresponding open file handle.
3. All file handles are flushed after each write and closed at the end.

### Notes

- The database is iterated **twice** (once per pass).
- Raises an exception if a network record has no ISO code at all — this
  should not happen with a valid MaxMind database.
- The `Countries/` directory must exist before running the script.
- Resulting files represent the full routing table for each country as
  known to MaxMind, useful for firewall rules, blocklists, or analytics.

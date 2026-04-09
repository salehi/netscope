# Memory Usage

## Observed at Startup

From `ps aux` immediately after startup (single worker):

```
VSZ:  246,732 KB  ≈  241 MB   virtual address space
RSS:  173,708 KB  ≈  170 MB   physical RAM actually resident
```

RSS is the number that matters. VSZ is inflated by memory-mapped files that
the OS may never fully load into physical RAM.

---

## Breakdown

| Component | ~Size | Notes |
|---|---|---|
| Python interpreter + stdlib | 25 MB | Baseline for any Python process |
| `GeoLite2-ASN.mmdb` | 12 MB | Memory-mapped by `maxminddb` |
| `GeoLite2-City.mmdb` | 65 MB | Memory-mapped by `maxminddb` |
| `GeoLite2-Country.mmdb` | 10 MB | Memory-mapped by `maxminddb` |
| `ASN_CACHE` dict | 50–60 MB | Dominant cost — see below |
| `COUNTRY_NAMES` dict | < 1 MB | ~250 ISO → name entries |
| Starlette + uvicorn + templates | 5 MB | Framework and HTML in memory |

**Total: ~170 MB RSS**

### Why ASN_CACHE is expensive

At startup, `server.py` iterates the entire ASN database and materializes every
network prefix as a Python string, grouped by AS number into a dict of lists:

```python
ASN_CACHE = {
    15169: {"org": "GOOGLE", "networks": ["8.8.4.0/24", "8.8.8.0/24", ...]},
    ...
}
```

The ASN database contains hundreds of thousands of network records. Python's
object overhead per string (≈ 50 bytes header + content) and per dict entry
makes this significantly larger in RAM than the raw MMDB file would suggest.
The trade-off is that every `/asn/{asn}` and `/api/asn-networks/{asn}` request
is served instantly from memory with no DB scan.

### MMDB files are memory-mapped

The `maxminddb` library opens databases with `mmap`, so the OS controls what
is physically resident. Pages are loaded on first access and evicted under memory
pressure. This means:

- On first request after startup, the City DB (~65 MB) may cause a burst of
  page faults as the OS loads the relevant pages.
- On a warm server with normal traffic patterns, only the frequently accessed
  pages stay resident — the actual RSS contribution from MMDB files is often
  lower than the file sizes suggest.

---

## Multi-Worker Deployments

Each uvicorn/gunicorn worker is a separate OS process. CPython does not share
heap memory between workers, so every worker gets its own copy of `ASN_CACHE`
and the memory-mapped DB handles.

| Workers | Estimated RSS |
|---|---|
| 1 | ~170 MB |
| 2 | ~320 MB |
| 4 | ~620 MB |
| 8 | ~1.2 GB |

These are estimates. The MMDB mmap pages may be shared at the OS level
(same physical pages, multiple virtual mappings) if the files are opened
read-only before forking — but Python dict heap data is never shared.

---

## Production Recommendations

| Deployment | Minimum RAM | Comfortable RAM |
|---|---|---|
| Single worker, internal tool | 256 MB | 384 MB |
| 2 workers | 512 MB | 768 MB |
| 4 workers | 1 GB | 1.5 GB |

Add OS overhead (~100–200 MB for kernel, system services) on top of the
figures above when sizing a dedicated VM or container.

### If memory is constrained

**Option 1 — Reduce workers.**
The `/ip/` lookup is a fast point query; one or two workers handle most
workloads. The expensive `/asn/` and `/search/` endpoints benefit from the
cache but are typically low-traffic.

**Option 2 — Remove `ASN_CACHE`, revert to on-demand scan.**
Replace the cache with a per-request full DB iteration. `/asn/{asn}` becomes
slower (tens to hundreds of milliseconds per scan) but saves 50–60 MB per
worker. Acceptable if the ASN endpoint is rarely called.

**Option 3 — Use a container memory limit as a hard cap.**
Set a container limit (e.g. `--memory=512m`) with at least one worker.
The mmap pages will be evicted by the OS when pressure increases, so the
server degrades gracefully rather than OOM-crashing — as long as the Python
heap (ASN_CACHE + interpreter) fits within the limit.

---

## Process Priority Note

The process was observed running with state `S<` — sleeping at
**elevated priority** (negative nice value). This is unusual for a user
process and was not set by `server.py` itself. Check whether the process
supervisor or launch script is setting a priority, as elevated scheduling
priority has no benefit for an I/O-bound server and may affect other processes
on the same host.

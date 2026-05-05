import asyncio
import ipaddress
import logging
import time
from pathlib import Path
from urllib.parse import quote_plus
import maxminddb

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route, Mount
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

HTML_DIR  = Path(__file__).parent / "html"
templates = Jinja2Templates(directory=str(HTML_DIR))


# --- DB handles & caches ---

DB_ASN     = None
DB_CITY    = None
DB_COUNTRY = None
ASN_CACHE:        dict[int, dict] = {}   # {asn: {"org": str, "networks": [str]}}
COUNTRY_NAMES:    dict[str, str]  = {}   # {iso: country_name}
COUNTRY_ASN_MAP:  dict[str, list] = {}   # {iso: [(cidr, asn_int, org), ...]}
COUNTRY_NAME_TO_ISO: dict[str, str] = {} # {lowercase_name: iso}
START_TIME: float = 0.0
CACHE_READY: bool = False


log = logging.getLogger(__name__)


def _build_caches():
    # Opens its own DB handles so the background thread doesn't share
    # file state with the global handles used by request handlers.
    global ASN_CACHE, COUNTRY_NAMES, COUNTRY_ASN_MAP, COUNTRY_NAME_TO_ISO, CACHE_READY
    log.info("Cache warmup started")
    t0 = time.monotonic()
    db_asn     = maxminddb.open_database("./GeoLite2-ASN.mmdb")
    db_country = maxminddb.open_database("./GeoLite2-Country.mmdb")
    try:
        cache:    dict[int, dict] = {}
        ctry_map: dict[str, list] = {}
        for network, data in db_asn:
            if not data:
                continue
            asn_int = data.get("autonomous_system_number")
            org     = data.get("autonomous_system_organization", "")
            if asn_int is None:
                continue
            cidr = str(network)
            if asn_int not in cache:
                cache[asn_int] = {"org": org, "networks": [], "countries": set()}
            cache[asn_int]["networks"].append(cidr)

            try:
                ctry_data = db_country.get(str(network.network_address))
            except Exception:
                ctry_data = None
            if ctry_data:
                iso = (ctry_data.get("registered_country") or ctry_data.get("country") or {}).get("iso_code")
                if not iso:
                    iso = (ctry_data.get("country") or {}).get("iso_code")
                if iso:
                    ctry_map.setdefault(iso, []).append((cidr, asn_int, org))
                    cache[asn_int]["countries"].add(iso)

        for entry in cache.values():
            entry["networks"].sort()
            entry["countries"] = sorted(entry["countries"])
        for entries in ctry_map.values():
            entries.sort(key=lambda t: t[0])
        ASN_CACHE       = cache
        COUNTRY_ASN_MAP = ctry_map

        names: dict[str, str] = {}
        for _, data in db_country:
            if not data:
                continue
            for field in ("registered_country", "country"):
                rec = data.get(field) or {}
                iso = rec.get("iso_code")
                if iso and iso not in names:
                    names[iso] = (rec.get("names") or {}).get("en", iso)
        COUNTRY_NAMES       = names
        COUNTRY_NAME_TO_ISO = {n.lower(): iso for iso, n in names.items()}
    finally:
        db_asn.close()
        db_country.close()
    CACHE_READY = True
    log.info("Cache warmup complete in %.1fs", time.monotonic() - t0)


async def startup():
    global DB_ASN, DB_CITY, DB_COUNTRY, START_TIME
    START_TIME = time.time()
    DB_ASN     = maxminddb.open_database("./GeoLite2-ASN.mmdb")
    DB_CITY    = maxminddb.open_database("./GeoLite2-City.mmdb")
    DB_COUNTRY = maxminddb.open_database("./GeoLite2-Country.mmdb")
    asyncio.create_task(asyncio.to_thread(_build_caches))


def shutdown():
    for db in (DB_ASN, DB_CITY, DB_COUNTRY):
        if db:
            db.close()


# --- Data helpers ---

def lookup_ip(ip: str) -> dict:
    try:
        asn_data, asn_prefix_len = DB_ASN.get_with_prefix_len(ip)
        if asn_data and asn_prefix_len:
            asn_net = ipaddress.ip_network(f"{ip}/{asn_prefix_len}", strict=False)
            asn_prefix = str(asn_net)
            asn_prefix_addr = str(asn_net.network_address)
        else:
            asn_prefix = asn_prefix_addr = ""
        return {
            "asn":             asn_data,
            "asn_prefix":      asn_prefix,
            "asn_prefix_addr": asn_prefix_addr,
            "city":            DB_CITY.get(ip),
            "country":         DB_COUNTRY.get(ip),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid IP or lookup error: {e}")


def get_segment(ip: str, segment: str):
    data   = lookup_ip(ip)
    result = data.get(segment)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No {segment} data for {ip}")
    return result


def _asn_int(raw: str) -> int:
    try:
        return int(raw.lstrip("ASas"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid AS number: {raw}")


# --- HTML renderer helpers ---

def _en(obj, *keys):
    if obj is None:
        return ""
    for k in keys:
        if not isinstance(obj, dict):
            return ""
        obj = obj.get(k)
    if isinstance(obj, dict):
        return obj.get("en", "")
    return str(obj) if obj is not None else ""


def _val(obj, *keys):
    if obj is None:
        return ""
    for k in keys:
        if not isinstance(obj, dict):
            return ""
        obj = obj.get(k)
    return str(obj) if obj is not None else ""


def flatten_for_html(ip: str, data: dict) -> dict:
    asn     = data.get("asn") or {}
    city    = data.get("city") or {}
    country = data.get("country") or {}
    subdivs = city.get("subdivisions") or []

    lat = _val(city, "location", "latitude")
    lon = _val(city, "location", "longitude")
    acc = _val(city, "location", "accuracy_radius")
    coords     = f"{lat}, {lon}" if (lat and lon) else "—"
    coords_acc = f"± {acc} km" if acc else ""

    country_name = _en(city, "country", "names") or _en(country, "country", "names")
    country_iso  = _val(city, "country", "iso_code") or _val(country, "country", "iso_code")
    reg_name     = _en(city, "registered_country", "names") or _en(country, "registered_country", "names")
    reg_iso      = _val(city, "registered_country", "iso_code") or _val(country, "registered_country", "iso_code")

    is_eu_raw = _val(city, "country", "is_in_european_union") or _val(country, "country", "is_in_european_union")
    is_eu = "Yes" if str(is_eu_raw).lower() == "true" else ("No" if is_eu_raw != "" else "—")

    return dict(
        ip=ip,
        asn_number    = _val(asn, "autonomous_system_number") or "—",
        asn_org       = _val(asn, "autonomous_system_organization") or "—",
        asn_org_url   = quote_plus(_val(asn, "autonomous_system_organization") or ""),
        asn_prefix    = data.get("asn_prefix", "") or "—",
        asn_prefix_addr = data.get("asn_prefix_addr", ""),
        continent     = _en(city, "continent", "names") or "—",
        country_name  = country_name or "—",
        country_iso   = country_iso or "—",
        registered_country     = reg_name or "—",
        registered_country_iso = reg_iso or "—",
        subdivision     = _en(subdivs[0], "names") if subdivs else "—",
        subdivision_iso = _val(subdivs[0], "iso_code") if subdivs else "",
        city_name     = _en(city, "city", "names") or "—",
        postal        = _val(city, "postal", "code") or "—",
        coords        = coords,
        coords_acc    = coords_acc,
        timezone      = _val(city, "location", "time_zone") or "—",
        is_eu         = is_eu,
    )


# --- Route handlers ---

async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


async def subnet(request: Request):
    return templates.TemplateResponse("subnet.html", {
        "request": request,
        "breadcrumbs": [("Home", "/"), ("Subnet Divider", None)],
    })


async def ip_lookup(request: Request):
    ip   = request.path_params["ip"].split("/")[0]
    data = lookup_ip(ip)
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse("ip.html", {
            "request": request,
            "breadcrumbs": [("Home", "/"), ("IP Lookup", None)],
            **flatten_for_html(ip, data),
        })
    return JSONResponse(data)


async def myip(request: Request):
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    if not ip:
        raise HTTPException(status_code=400, detail="Could not determine client IP")
    return RedirectResponse(url=f"/ip/{ip}", status_code=302)


async def asn_view(request: Request):
    if not CACHE_READY:
        raise HTTPException(status_code=503, detail="warming up")
    asn_int = _asn_int(request.path_params["asn"])
    entry   = ASN_CACHE.get(asn_int)
    if not entry:
        raise HTTPException(status_code=404, detail=f"No networks found for AS{asn_int}")

    if "text/html" in request.headers.get("accept", ""):
        countries = [{"iso": iso, "name": COUNTRY_NAMES.get(iso, iso)} for iso in entry.get("countries", [])]
        return templates.TemplateResponse("asn.html", {
            "request": request,
            "breadcrumbs": [("Home", "/"), (f"AS{asn_int}", None)],
            "asn_number": asn_int,
            "asn_org": entry["org"],
            "asn_org_url": quote_plus(entry["org"]),
            "network_count": len(entry["networks"]),
            "networks": entry["networks"],
            "countries": countries,
        })
    return JSONResponse({
        "asn": asn_int,
        "organization": entry["org"],
        "network_count": len(entry["networks"]),
        "networks": entry["networks"],
    })


async def country_view(request: Request):
    if not CACHE_READY:
        raise HTTPException(status_code=503, detail="warming up")
    iso     = request.path_params["iso"].upper()
    entries = COUNTRY_ASN_MAP.get(iso)
    if not entries:
        raise HTTPException(status_code=404, detail=f"No data for country: {iso}")

    name = COUNTRY_NAMES.get(iso, iso)

    if "text/html" in request.headers.get("accept", ""):
        network_entries = [
            {"cidr": cidr, "asn": asn_int, "org": org, "org_url": quote_plus(org), "is_v6": ":" in cidr}
            for cidr, asn_int, org in entries
        ]
        return templates.TemplateResponse("country.html", {
            "request": request,
            "breadcrumbs": [("Home", "/"), (name, None)],
            "iso": iso,
            "country_name": name,
            "network_count": len(entries),
            "entries": network_entries,
        })
    return JSONResponse({
        "iso":           iso,
        "country":       name,
        "network_count": len(entries),
        "networks":      [{"cidr": c, "asn": a, "org": o} for c, a, o in entries],
    })


async def country_search(request: Request):
    if not CACHE_READY:
        raise HTTPException(status_code=503, detail="warming up")
    q = request.query_params.get("q", "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Missing query parameter q")

    if len(q) == 2:
        iso = q.upper()
    else:
        iso = COUNTRY_NAME_TO_ISO.get(q.lower())
        if not iso:
            # partial match fallback
            ql = q.lower()
            for name, code in COUNTRY_NAME_TO_ISO.items():
                if ql in name:
                    iso = code
                    break

    if not iso or iso not in COUNTRY_ASN_MAP:
        raise HTTPException(status_code=404, detail=f"Country not found: {q}")

    return RedirectResponse(url=f"/country/{iso}", status_code=302)


async def search(request: Request):
    if not CACHE_READY:
        raise HTTPException(status_code=503, detail="warming up")
    q       = request.query_params.get("q", "").strip()
    q_lower = q.lower()
    results = []

    if q:
        results = sorted(
            [{"asn": asn, "organization": e["org"], "org_url": quote_plus(e["org"])}
             for asn, e in ASN_CACHE.items()
             if q_lower in e["org"].lower()],
            key=lambda r: r["organization"].lower(),
        )

    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse("search.html", {
            "request": request,
            "breadcrumbs": [("Home", "/"), ("Org Search", None)],
            "query": q,
            "result_count": len(results),
            "results": results,
        })
    return JSONResponse({"query": q, "result_count": len(results), "results": [{"asn": r["asn"], "organization": r["organization"]} for r in results]})


async def cidr_view(request: Request):
    prefix = request.path_params["prefix"]
    try:
        net = ipaddress.ip_network(prefix, strict=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid prefix: {e}")

    is_v4 = isinstance(net, ipaddress.IPv4Network)
    n     = net.num_addresses

    info = dict(
        prefix=str(net),
        version=net.version,
        network_address=str(net.network_address),
        prefix_length=net.prefixlen,
        num_addresses=n,
        netmask=str(net.netmask),
        broadcast=str(net.broadcast_address) if is_v4 else None,
        wildcard=str(net.hostmask) if is_v4 else None,
        first_host=str(net.network_address + 1) if n > 2 else str(net.network_address),
        last_host=str((net.broadcast_address if is_v4 else net[-1]) - (1 if n > 2 else 0)),
        usable_hosts=max(0, n - 2) if is_v4 else n,
    )

    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse("cidr.html", {
            "request": request,
            "breadcrumbs": [("Home", "/"), ("CIDR", None), (info["prefix"], f"/subnet?q={quote_plus(info['prefix'])}")],
            "prefix":          info["prefix"],
            "version":         info["version"],
            "network_address": info["network_address"],
            "broadcast":       info["broadcast"] or "—",
            "netmask":         info["netmask"],
            "wildcard":        info["wildcard"] or "—",
            "prefix_length":   info["prefix_length"],
            "num_addresses":   f"{info['num_addresses']:,}",
            "usable_hosts":    f"{info['usable_hosts']:,}",
            "first_host":      info["first_host"],
            "last_host":       info["last_host"],
        })

    return JSONResponse(info)


async def bulk_lookup(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be a JSON array of IP strings")
    if not isinstance(body, list):
        raise HTTPException(status_code=400, detail="Body must be a JSON array")
    if len(body) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 IPs per request")

    results = []
    for ip in body:
        try:
            results.append({"ip": ip, **lookup_ip(str(ip))})
        except HTTPException as e:
            results.append({"ip": ip, "error": e.detail})
    return JSONResponse(results)


async def health(request: Request):
    return JSONResponse({
        "status": "ok",
        "cache_ready": CACHE_READY,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "databases": {
            name: {
                "file":    fname,
                "size_mb": round(Path(f"./{fname}").stat().st_size / 1_048_576, 1),
            }
            for name, fname in (
                ("asn",     "GeoLite2-ASN.mmdb"),
                ("city",    "GeoLite2-City.mmdb"),
                ("country", "GeoLite2-Country.mmdb"),
            )
        },
        "asn_cache_entries":     len(ASN_CACHE),
        "country_cache_entries": len(COUNTRY_NAMES),
    })


async def api_asn(request: Request):
    return JSONResponse(get_segment(request.path_params["ip"], "asn"))


async def api_city(request: Request):
    return JSONResponse(get_segment(request.path_params["ip"], "city"))


async def api_country(request: Request):
    return JSONResponse(get_segment(request.path_params["ip"], "country"))


async def api_asn_networks(request: Request):
    if not CACHE_READY:
        raise HTTPException(status_code=503, detail="warming up")
    asn_int = _asn_int(request.path_params["asn"])
    entry   = ASN_CACHE.get(asn_int)
    if not entry:
        raise HTTPException(status_code=404, detail=f"No networks found for AS{asn_int}")
    return JSONResponse({
        "asn":          asn_int,
        "organization": entry["org"],
        "network_count": len(entry["networks"]),
        "networks":     entry["networks"],
    })


async def asn_country_view(request: Request):
    if not CACHE_READY:
        raise HTTPException(status_code=503, detail="warming up")
    asn_int = _asn_int(request.path_params["asn"])
    iso     = request.path_params["iso"].upper()
    entry   = ASN_CACHE.get(asn_int)
    if not entry:
        raise HTTPException(status_code=404, detail=f"No networks found for AS{asn_int}")

    country_entries = COUNTRY_ASN_MAP.get(iso, [])
    networks = sorted(cidr for cidr, a, _ in country_entries if a == asn_int)
    if not networks:
        raise HTTPException(status_code=404, detail=f"AS{asn_int} has no prefixes in {iso}")

    country_name = COUNTRY_NAMES.get(iso, iso)

    if "text/html" in request.headers.get("accept", ""):
        network_items = [{"cidr": cidr, "is_v6": ":" in cidr} for cidr in networks]
        return templates.TemplateResponse("asn_country.html", {
            "request": request,
            "breadcrumbs": [("Home", "/"), (f"AS{asn_int}", f"/asn/{asn_int}"), (country_name, None)],
            "asn_number":   asn_int,
            "asn_org":      entry["org"],
            "asn_org_url":  quote_plus(entry["org"]),
            "iso":          iso,
            "country_name": country_name,
            "network_count": len(networks),
            "total_count":  len(entry["networks"]),
            "networks":     network_items,
        })
    return JSONResponse({
        "asn": asn_int,
        "organization": entry["org"],
        "country": iso,
        "country_name": country_name,
        "network_count": len(networks),
        "networks": networks,
    })


async def multi_country_search(request: Request):
    if not CACHE_READY:
        raise HTTPException(status_code=503, detail="warming up")
    q = request.query_params.get("q", "").strip()
    isos = [s.strip().upper() for s in q.split(",") if s.strip()] if q else []
    iso_set = set(isos)

    results = []
    if iso_set:
        for asn, entry in ASN_CACHE.items():
            countries = set(entry.get("countries", []))
            if iso_set <= countries and len(countries) >= 2:
                results.append({"asn": asn, "org": entry["org"], "countries": sorted(countries)})
        results.sort(key=lambda r: r["org"].lower())

    if "text/html" in request.headers.get("accept", ""):
        enriched = [
            {
                "asn": r["asn"],
                "org": r["org"],
                "org_url": quote_plus(r["org"]),
                "country_count": len(r["countries"]),
                "countries": [
                    {"iso": iso, "name": COUNTRY_NAMES.get(iso, iso), "matched": iso in iso_set}
                    for iso in r["countries"]
                ],
            }
            for r in results
        ]
        return templates.TemplateResponse("multi_country.html", {
            "request": request,
            "breadcrumbs": [("Home", "/"), ("Multi-Country Search", None)],
            "query":   q,
            "isos":    isos,
            "results": enriched,
        })
    return JSONResponse({
        "query": isos,
        "result_count": len(results),
        "results": [{"asn": r["asn"], "organization": r["org"], "countries": r["countries"]} for r in results],
    })


async def http_exception(request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# --- App ---

app = Starlette(
    debug=False,
    routes=[
        Mount("/static", StaticFiles(directory=str(HTML_DIR / "static")), name="static"),
        Route("/",                       index),
        Route("/subnet",                 subnet),
        Route("/ip/{ip:path}",           ip_lookup),
        Route("/myip",                   myip),
        Route("/asn/{asn}",              asn_view),
        Route("/country/{iso}",          country_view),
        Route("/country-search",         country_search),
        Route("/search",                 search),
        Route("/multi-country",          multi_country_search),
        Route("/asn/{asn}/country/{iso}", asn_country_view),
        Route("/cidr/{prefix:path}",     cidr_view),
        Route("/bulk",                   bulk_lookup, methods=["POST"]),
        Route("/health",                 health),
        Route("/api/asn/{ip}",           api_asn),
        Route("/api/asn-networks/{asn}", api_asn_networks),
        Route("/api/city/{ip}",          api_city),
        Route("/api/country/{ip}",       api_country),
    ],
    on_startup=[startup],
    on_shutdown=[shutdown],
    exception_handlers={HTTPException: http_exception},
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)

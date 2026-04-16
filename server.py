import ipaddress
import json
import time
from pathlib import Path
from string import Template
from urllib.parse import quote_plus
import maxminddb

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route
from starlette.exceptions import HTTPException

HTML_DIR     = Path(__file__).parent / "html"
COUNTRIES_DIR = Path(__file__).parent / "Countries"

IP_TEMPLATE      = Template((HTML_DIR / "ip.html").read_text())
ASN_TEMPLATE     = Template((HTML_DIR / "asn.html").read_text())
COUNTRY_TEMPLATE = Template((HTML_DIR / "country.html").read_text())
CIDR_TEMPLATE    = Template((HTML_DIR / "cidr.html").read_text())
SEARCH_TEMPLATE  = Template((HTML_DIR / "search.html").read_text())
INDEX_HTML       = (HTML_DIR / "index.html").read_text()
SUBNET_HTML      = (HTML_DIR / "subnet.html").read_text()


# --- DB handles & caches ---

DB_ASN     = None
DB_CITY    = None
DB_COUNTRY = None
ASN_CACHE:     dict[int, dict] = {}  # {asn: {"org": str, "networks": [str]}}
COUNTRY_NAMES: dict[str, str]  = {}  # {iso: country_name}
START_TIME: float = 0.0


def startup():
    global DB_ASN, DB_CITY, DB_COUNTRY, ASN_CACHE, COUNTRY_NAMES, START_TIME
    START_TIME = time.time()
    DB_ASN     = maxminddb.open_database("./GeoLite2-ASN.mmdb")
    DB_CITY    = maxminddb.open_database("./GeoLite2-City.mmdb")
    DB_COUNTRY = maxminddb.open_database("./GeoLite2-Country.mmdb")

    # Build ASN cache — single full scan, eliminates per-request DB iteration
    cache: dict[int, dict] = {}
    for network, data in DB_ASN:
        if not data:
            continue
        asn_int = data.get("autonomous_system_number")
        org     = data.get("autonomous_system_organization", "")
        if asn_int is None:
            continue
        if asn_int not in cache:
            cache[asn_int] = {"org": org, "networks": []}
        cache[asn_int]["networks"].append(str(network))
    for entry in cache.values():
        entry["networks"].sort()
    ASN_CACHE = cache

    # Build country name cache
    names: dict[str, str] = {}
    for _, data in DB_COUNTRY:
        if not data:
            continue
        for field in ("registered_country", "country"):
            rec = data.get(field) or {}
            iso = rec.get("iso_code")
            if iso and iso not in names:
                names[iso] = (rec.get("names") or {}).get("en", iso)
    COUNTRY_NAMES = names


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


def _prefix_list_html(networks: list[str]) -> str:
    return "\n".join(
        f'          <li class="{"v6" if ":" in n else ""}"><a href="/ip/{n.split("/")[0]}">{n}</a></li>'
        for n in networks
    )


# --- Route handlers ---

async def index(request: Request):
    return HTMLResponse(INDEX_HTML)


async def subnet(request: Request):
    return HTMLResponse(SUBNET_HTML)


async def ip_lookup(request: Request):
    ip   = request.path_params["ip"]
    data = lookup_ip(ip)
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(IP_TEMPLATE.substitute(flatten_for_html(ip, data)))
    return JSONResponse(data)


async def myip(request: Request):
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    if not ip:
        raise HTTPException(status_code=400, detail="Could not determine client IP")
    return RedirectResponse(url=f"/ip/{ip}", status_code=302)


async def asn_view(request: Request):
    asn_int = _asn_int(request.path_params["asn"])
    entry   = ASN_CACHE.get(asn_int)
    if not entry:
        raise HTTPException(status_code=404, detail=f"No networks found for AS{asn_int}")

    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(ASN_TEMPLATE.substitute(
            asn_number=asn_int,
            asn_org=entry["org"],
            network_count=len(entry["networks"]),
            networks_html=_prefix_list_html(entry["networks"]),
        ))
    return JSONResponse({
        "asn": asn_int,
        "organization": entry["org"],
        "network_count": len(entry["networks"]),
        "networks": entry["networks"],
    })


async def country_view(request: Request):
    iso  = request.path_params["iso"].upper()
    path = COUNTRIES_DIR / f"{iso}.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No data for country: {iso}")

    lines    = path.read_text().splitlines()
    networks = sorted(line.split("\t")[0] for line in lines if line.strip())
    name     = COUNTRY_NAMES.get(iso, iso)

    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(COUNTRY_TEMPLATE.substitute(
            iso=iso,
            country_name=name,
            network_count=len(networks),
            networks_html=_prefix_list_html(networks),
        ))
    return JSONResponse({
        "iso": iso,
        "country": name,
        "network_count": len(networks),
        "networks": networks,
    })


async def search(request: Request):
    q       = request.query_params.get("q", "").strip()
    q_lower = q.lower()
    results = []

    if q:
        results = sorted(
            [{"asn": asn, "organization": e["org"]}
             for asn, e in ASN_CACHE.items()
             if q_lower in e["org"].lower()],
            key=lambda r: r["organization"].lower(),
        )

    if "text/html" in request.headers.get("accept", ""):
        if results:
            rows = "\n".join(
                f'<tr><td><a class="asn-link" href="/asn/{r["asn"]}">AS{r["asn"]}</a></td>'
                f'<td>{r["organization"]}</td></tr>'
                for r in results
            )
            results_html = (
                f'<table class="results-table"><thead><tr>'
                f'<th>AS Number</th><th>Organization</th>'
                f'</tr></thead><tbody>{rows}</tbody></table>'
            )
        elif q:
            results_html = '<p class="no-results">No results found.</p>'
        else:
            results_html = ""
        return HTMLResponse(SEARCH_TEMPLATE.substitute(
            query=q,
            results_html=results_html,
            result_count=len(results),
        ))

    return JSONResponse({"query": q, "result_count": len(results), "results": results})


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
        return HTMLResponse(CIDR_TEMPLATE.substitute(
            prefix=info["prefix"],
            version=info["version"],
            network_address=info["network_address"],
            broadcast=info["broadcast"] or "—",
            netmask=info["netmask"],
            wildcard=info["wildcard"] or "—",
            prefix_length=info["prefix_length"],
            num_addresses=f"{info['num_addresses']:,}",
            usable_hosts=f"{info['usable_hosts']:,}",
            first_host=info["first_host"],
            last_host=info["last_host"],
        ))

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


async def http_exception(request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# --- App ---

app = Starlette(
    debug=False,
    routes=[
        Route("/",                       index),
        Route("/subnet",                 subnet),
        Route("/ip/{ip}",                ip_lookup),
        Route("/myip",                   myip),
        Route("/asn/{asn}",              asn_view),
        Route("/country/{iso}",          country_view),
        Route("/search",                 search),
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

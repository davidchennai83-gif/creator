"""Affiliate link detection shared by the catalogue, Autopilot and video copy.

Tamil Budget Finds started with Meesho only. The business can now take links
from Amazon, Flipkart and the common Indian link-conversion networks without
pretending that an ordinary product URL is commissionable.

The rule is deliberately strict:

* A link is commissionable only when it is a known link-conversion network,
  carries a network tracking parameter, or the owner explicitly verified it.
* A plain product URL or a search URL is still useful for a sample video, but
  it is labelled as such and never described as an affiliate link.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

# Marketplace networks need a tracking token (tag, affid, aff_id...).
# Wrapper networks are affiliate links by construction.
NETWORKS: dict[str, dict] = {
    "meesho": {
        "label": "Meesho",
        "hosts": ("meesho.com", "meesho.me"),
        # Creator Club "Get link" URLs carry aff_id/sub_id. A plain app share
        # link only has utm_source=s_cc and earns nothing, so it must stay out.
        "params": ("aff_id", "sub_id", "affiliate_id"),
        "wrapper": False,
    },
    "amazon": {
        "label": "Amazon",
        "hosts": ("amazon.in", "amazon.com", "amzn.to", "amzn.in"),
        "params": ("tag", "ascsubtag", "linkcode"),
        "wrapper": False,
    },
    "flipkart": {
        "label": "Flipkart",
        "hosts": ("flipkart.com", "fkrt.cc", "dl.flipkart.com"),
        "params": ("affid", "affiliateid", "utm_source", "utm_medium"),
        "wrapper": False,
    },
    "myntra": {
        "label": "Myntra",
        "hosts": ("myntra.com", "myntr.it"),
        "params": ("utm_source", "utm_medium", "affid"),
        "wrapper": False,
    },
    "ajio": {
        "label": "AJIO",
        "hosts": ("ajio.com", "ajio.in"),
        "params": ("utm_source", "utm_medium", "affid"),
        "wrapper": False,
    },
    "tatacliq": {
        "label": "Tata CLiQ",
        "hosts": ("tatacliq.com",),
        "params": ("utm_source", "utm_medium", "affid"),
        "wrapper": False,
    },
    "snapdeal": {
        "label": "Snapdeal",
        "hosts": ("snapdeal.com",),
        "params": ("utm_source", "utm_medium", "affid"),
        "wrapper": False,
    },
    "earnkaro": {
        "label": "EarnKaro",
        "hosts": ("earnkaro.com", "earnkaro.onelink.me"),
        "params": (),
        "wrapper": True,
    },
    "cuelinks": {
        "label": "Cuelinks",
        "hosts": ("cuelinks.com", "clnk.in", "cuelink.in"),
        "params": (),
        "wrapper": True,
    },
    "inrdeals": {
        "label": "INRDeals",
        "hosts": ("inrdeals.com", "inr.deals"),
        "params": (),
        "wrapper": True,
    },
    "vcommission": {
        "label": "vCommission",
        "hosts": ("vcommission.com", "vcommission.in", "vcommission.co.in"),
        "params": (),
        "wrapper": True,
    },
    "admitad": {
        "label": "Admitad",
        "hosts": ("admitad.com", "ad.admitad.com"),
        "params": ("subid", "sub_id", "utm_source", "utm_medium"),
        "wrapper": True,
    },
    "impact": {
        "label": "Impact",
        "hosts": ("impact.com", "sjv.io", "pxf.io", "imp.i"),
        "params": ("irgwc", "irclickid", "utm_source", "utm_medium"),
        "wrapper": True,
    },
    "optimise": {
        "label": "Optimise",
        "hosts": ("optimiseindia.com", "optimise.net"),
        "params": ("utm_source", "utm_medium", "affid"),
        "wrapper": True,
    },
}

# Generic tokens used by many small networks and shorteners.
GENERIC_TOKENS = ("aff_id", "affid", "affiliate_id", "affiliateid", "clickid",
                  "irclickid", "sub_id", "subid", "tag")

MARKETPLACE_LABEL = {
    "meesho": "Meesho", "amazon": "Amazon", "flipkart": "Flipkart",
    "myntra": "Myntra", "ajio": "AJIO", "tatacliq": "Tata CLiQ",
    "snapdeal": "Snapdeal",
}


def _host_matches(host: str, domain: str) -> bool:
    host = (host or "").lower().strip(".")
    domain = (domain or "").lower().strip(".")
    return host == domain or host.endswith("." + domain)


def detect_network(url: str) -> str:
    """Return the network key for a URL, or an empty string when unknown."""
    try:
        host = urlparse(str(url or "")).netloc.lower()
    except ValueError:
        return ""
    if not host:
        return ""
    for key, spec in NETWORKS.items():
        if any(_host_matches(host, domain) for domain in spec["hosts"]):
            return key
    return ""


def network_label(key: str) -> str:
    return NETWORKS.get(key, {}).get("label") or "Partner store"


def is_search_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or ""))
    except ValueError:
        return False
    return "/search" in parsed.path.lower() or "q=" in parsed.query.lower()


def has_tracking(url: str, network: str = "") -> bool:
    try:
        parsed = urlparse(str(url or ""))
    except ValueError:
        return False
    query = parsed.query.lower()
    path = parsed.path.lower()
    if not query and not path:
        return False
    names = set(parse_qs(parsed.query).keys())
    tokens = set(GENERIC_TOKENS)
    spec = NETWORKS.get(network) or {}
    tokens.update(spec.get("params") or ())
    if names & tokens:
        return True
    # Meesho Creator Club "Get commission link" URLs put the creator id in the
    # path: /af_invite/<creator>:<platform>:<collection>?p_id=...&ext_id=...
    if network == "meesho" and "af_invite/" in path:
        return True
    # Some networks put the tracking token in the path or a fragment.
    blob = (query + " " + path).lower()
    return any(token in blob for token in ("aff_id", "affid=", "affiliate", "irclickid", "sub_id"))


def check(url: str, demo: bool = False, commission_percent: float = 0,
          price: float = 0, verified: bool = False) -> dict:
    """Classify a product URL without guessing about commissions.

    Returns ``network``, ``label``, ``affiliate`` (tracking is present),
    ``wrapper`` and human-readable ``issues``. The caller adds price and
    commission checks so the same result drives the UI and the publish guard.
    """
    text = str(url or "").strip()
    network = detect_network(text)
    spec = NETWORKS.get(network) or {}
    label = network_label(network)
    issues: list[str] = []
    warnings: list[str] = []

    if not text:
        issues.append("Affiliate link is missing")
        return {"network": "", "label": "", "affiliate": False, "wrapper": False,
                "issues": issues, "warnings": warnings}

    try:
        parsed = urlparse(text)
    except ValueError:
        parsed = None
    if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        issues.append("Link is not a public http(s) URL")
        return {"network": network, "label": label, "affiliate": False, "wrapper": False,
                "issues": issues, "warnings": warnings}

    wrapper = bool(spec.get("wrapper"))
    tracked = wrapper or has_tracking(text, network) or bool(verified)
    if is_search_url(text):
        issues.append("Search URL, not a product link")
    if not network and not verified:
        issues.append("Unsupported shop. Use Meesho, Amazon, Flipkart, EarnKaro, Cuelinks, INRDeals or verify the link.")
    elif not tracked:
        issues.append(f"No affiliate tracking found for {label or 'this shop'}")
    if demo:
        issues.append("Sample product - no real commission link yet")
    if float(commission_percent or 0) <= 0:
        issues.append("Commission % not set")
    if float(price or 0) <= 0:
        issues.append("Price is missing")
    if not network and verified:
        warnings.append("Link marked verified by the owner; the network could not be identified")
    return {
        "network": network,
        "label": label,
        "affiliate": bool(tracked and not demo and not is_search_url(text)),
        "wrapper": wrapper,
        "issues": issues,
        "warnings": warnings,
    }


def is_affiliate_link(url: str, verified: bool = False) -> bool:
    return bool(check(url, verified=verified)["affiliate"])


def destination_url(url: str) -> str:
    """Return the shop URL hidden inside a link-converter wrapper, if present."""
    try:
        parsed = urlparse(str(url or ""))
        params = parse_qs(parsed.query)
    except ValueError:
        return ""
    for key in ("url", "u", "target", "redirect", "redirect_url", "deeplink", "dl", "link"):
        for value in params.get(key, []):
            candidate = str(value or "").strip()
            if candidate.lower().startswith(("http://", "https://")):
                return candidate
    return ""


def order_label(url: str, default: str = "the store") -> str:
    """The shop a viewer actually orders from (unwraps EarnKaro/Cuelinks)."""
    inner = destination_url(url)
    if inner:
        inner_network = detect_network(inner)
        if inner_network and not NETWORKS.get(inner_network, {}).get("wrapper"):
            return network_label(inner_network)
    network = detect_network(url)
    return MARKETPLACE_LABEL.get(network) or network_label(network) or default

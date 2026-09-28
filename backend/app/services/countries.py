"""Deterministic country derivation from URL/domain TLD (Radar-style, no AI), plus
ISO-2 names and map centroids. 'Better no data than a wrong color': non-country
TLDs (.com/.org/.io…) return None rather than guessing.
"""
from urllib.parse import urlparse

TLD_EXCEPTIONS = {"uk": "gb", "su": "ru", "tp": "tl", "an": "nl"}
NOT_A_COUNTRY = {"com", "org", "net", "io", "co", "ai", "tv", "gov", "edu", "int",
                 "info", "biz", "app", "dev", "xyz", "me", "us"}

# ISO-2 -> (English name, lat, lon centroid)
COUNTRY = {
    "us": ("United States", 39.8, -98.6), "gb": ("United Kingdom", 54.0, -2.0),
    "ca": ("Canada", 56.1, -106.3), "au": ("Australia", -25.3, 133.8),
    "de": ("Germany", 51.2, 10.5), "fr": ("France", 46.6, 2.4),
    "es": ("Spain", 40.0, -3.7), "it": ("Italy", 41.9, 12.6),
    "nl": ("Netherlands", 52.1, 5.3), "be": ("Belgium", 50.5, 4.5),
    "ch": ("Switzerland", 46.8, 8.2), "at": ("Austria", 47.5, 14.6),
    "se": ("Sweden", 60.1, 18.6), "no": ("Norway", 60.5, 8.5),
    "dk": ("Denmark", 56.3, 9.5), "fi": ("Finland", 61.9, 25.7),
    "ie": ("Ireland", 53.4, -8.2), "pt": ("Portugal", 39.4, -8.2),
    "pl": ("Poland", 51.9, 19.1), "ru": ("Russia", 61.5, 105.3),
    "ua": ("Ukraine", 48.4, 31.2), "gr": ("Greece", 39.1, 21.8),
    "cz": ("Czechia", 49.8, 15.5), "ro": ("Romania", 45.9, 24.9),
    "tr": ("Turkey", 39.0, 35.2), "in": ("India", 20.6, 79.0),
    "cn": ("China", 35.9, 104.2), "jp": ("Japan", 36.2, 138.3),
    "kr": ("South Korea", 35.9, 127.8), "id": ("Indonesia", -0.8, 113.9),
    "my": ("Malaysia", 4.2, 101.9), "sg": ("Singapore", 1.35, 103.8),
    "th": ("Thailand", 15.9, 100.9), "ph": ("Philippines", 12.9, 121.8),
    "vn": ("Vietnam", 14.1, 108.3), "pk": ("Pakistan", 30.4, 69.3),
    "bd": ("Bangladesh", 23.7, 90.4), "hk": ("Hong Kong", 22.3, 114.2),
    "tw": ("Taiwan", 23.7, 121.0), "ae": ("UAE", 23.4, 53.8),
    "sa": ("Saudi Arabia", 23.9, 45.1), "il": ("Israel", 31.0, 34.9),
    "qa": ("Qatar", 25.4, 51.2), "eg": ("Egypt", 26.8, 30.8),
    "za": ("South Africa", -30.6, 22.9), "ng": ("Nigeria", 9.1, 8.7),
    "ke": ("Kenya", -0.0, 37.9), "ma": ("Morocco", 31.8, -7.1),
    "br": ("Brazil", -14.2, -51.9), "mx": ("Mexico", 23.6, -102.6),
    "ar": ("Argentina", -38.4, -63.6), "cl": ("Chile", -35.7, -71.5),
    "co": ("Colombia", 4.6, -74.3), "pe": ("Peru", -9.2, -75.0),
    "nz": ("New Zealand", -40.9, 174.9),
}


# GDELT uses FIPS 10-4 country codes (differ from ISO-2 for many countries)
FIPS_TO_ISO2 = {
    "US": "us", "UK": "gb", "CA": "ca", "AS": "au", "GM": "de", "FR": "fr", "SP": "es",
    "IT": "it", "NL": "nl", "BE": "be", "SZ": "ch", "AU": "at", "SW": "se", "NO": "no",
    "DA": "dk", "FI": "fi", "EI": "ie", "PO": "pt", "PL": "pl", "RS": "ru", "UP": "ua",
    "GR": "gr", "EZ": "cz", "RO": "ro", "TU": "tr", "IN": "in", "CH": "cn", "JA": "jp",
    "KS": "kr", "ID": "id", "MY": "my", "SN": "sg", "TH": "th", "RP": "ph", "VM": "vn",
    "PK": "pk", "BG": "bd", "HK": "hk", "TW": "tw", "AE": "ae", "SA": "sa", "IS": "il",
    "QA": "qa", "EG": "eg", "SF": "za", "NI": "ng", "KE": "ke", "MO": "ma", "BR": "br",
    "MX": "mx", "AR": "ar", "CI": "cl", "CO": "co", "PE": "pe", "NZ": "nz",
}


def fips_to_iso2(fips: str) -> str | None:
    iso = FIPS_TO_ISO2.get((fips or "").upper())
    return iso if iso in COUNTRY else None


def _tld_to_iso2(tld: str) -> str | None:
    tld = tld.lower()
    if tld in NOT_A_COUNTRY:
        return None
    tld = TLD_EXCEPTIONS.get(tld, tld)
    return tld if tld in COUNTRY else None


def country_from_domain(domain: str) -> str | None:
    if not domain:
        return None
    tld = domain.rsplit(".", 1)[-1]
    return _tld_to_iso2(tld)


def country_from_url(url: str) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc
    except Exception:  # noqa: BLE001
        return None
    return country_from_domain(host)


def country_name(iso2: str | None) -> str | None:
    return COUNTRY.get((iso2 or "").lower(), (None,))[0] if iso2 else None


def centroid(iso2: str | None):
    c = COUNTRY.get((iso2 or "").lower())
    return (c[1], c[2]) if c else None

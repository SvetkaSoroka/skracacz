# Helper functions that don't depend on Cloudflare, so they can be tested locally.

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

# No 0/O and 1/l/I, they are easy to mix up
ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6
MAX_URL_LENGTH = 2048
CHART_DAYS = 30


class BadUrl(Exception):
    pass


def new_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def new_key():
    return secrets.token_urlsafe(18)


def hash_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


def check_key(key, key_hash):
    if not key:
        return False
    return hmac.compare_digest(hash_key(key), key_hash)


def is_valid_code(code):
    return re.fullmatch(r"[A-Za-z0-9]{4,16}", code) is not None


def clean_url(url, own_host=None):
    """Returns a normalized URL or raises BadUrl. Error texts are shown in the UI."""
    if not isinstance(url, str) or not url.strip():
        raise BadUrl("Paste a link to shorten.")
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise BadUrl(f"That link is longer than {MAX_URL_LENGTH} characters.")
    if " " in url or "\n" in url or "\t" in url:
        raise BadUrl("A link can't contain spaces.")
    if "://" not in url:
        url = "https://" + url

    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise BadUrl("Only http and https links can be shortened.")
    host = (parts.hostname or "").lower()
    if "." not in host:
        raise BadUrl("That doesn't look like a web address.")
    if own_host and host == own_host.lower():
        raise BadUrl("That link already points to this shortener.")
    return url


def referer_domain(referer):
    """https://www.instagram.com/p/123 -> instagram.com"""
    if not referer:
        return None
    try:
        host = (urlsplit(referer).hostname or "").lower()
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def first_chart_day(today=None):
    today = today or datetime.now(timezone.utc)
    return (today - timedelta(days=CHART_DAYS - 1)).strftime("%Y-%m-%d")


def last_30_days(counts, today=None):
    """Makes a list of 30 days, with 0 for days without clicks."""
    today = today or datetime.now(timezone.utc)
    days = []
    for i in range(CHART_DAYS - 1, -1, -1):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        days.append({"day": day, "clicks": counts.get(day, 0)})
    return days


def all_24_hours(counts):
    return [{"hour": h, "clicks": counts.get(h, 0)} for h in range(24)]

# End-to-end test over HTTP: creates a link, clicks it, checks stats, deletes it.
# Usage: python3 tests/smoke.py http://localhost:8787

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8787"
failed = 0


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # we want to see the 302 itself, not follow it
    def redirect_request(self, *args, **kwargs):
        return None


opener = urllib.request.build_opener(NoRedirect)


def call(method, path, body=None, key=None, referer=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    req.add_header("user-agent", "smoke-test")
    if key:
        req.add_header("authorization", "Bearer " + key)
    if referer:
        req.add_header("referer", referer)
    try:
        with opener.open(req) as res:
            return res.status, res.headers, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def check(name, ok):
    global failed
    print("ok  " if ok else "FAIL", name)
    if not ok:
        failed += 1


status, _, body = call("POST", "/api/links", {"url": "https://example.com/smoke-test"})
check("POST /api/links -> 201", status == 201)
link = json.loads(body)
code, key = link["code"], link["key"]

status, headers, _ = call("GET", "/" + code, referer="https://www.instagram.com/p/x")
check("GET /{code} -> 302", status == 302)
check("Location is the long URL", headers.get("Location") == "https://example.com/smoke-test")
call("GET", "/" + code)
status, _, _ = call("HEAD", "/" + code)
check("HEAD /{code} -> 302 (not counted)", status == 302)

status, _, body = call("GET", f"/api/links/{code}", key=key)
check("GET /api/links/{code} -> 200, 2 clicks", status == 200 and json.loads(body)["clicks"] == 2)

status, _, body = call("GET", f"/api/links/{code}/stats", key=key)
stats = json.loads(body)
check("GET stats -> 200", status == 200)
check("total = 2", stats["total"] == 2)
check("instagram.com is a source", any(s["source"] == "instagram.com" for s in stats["by_source"]))
check("30 days in by_day", len(stats["by_day"]) == 30)
check("country saved", len(stats["by_country"]) >= 1)

status, _, _ = call("GET", f"/api/links/{code}/stats", key="wrong-key")
check("wrong key -> 403", status == 403)
status, _, _ = call("GET", f"/api/links/{code}/stats")
check("no key -> 403", status == 403)
status, _, _ = call("POST", "/api/links", {"url": "ftp://nope"})
check("bad URL -> 422", status == 422)
status, _, body = call("GET", "/zzzzzzzz")
check("unknown code -> 404 page", status == 404 and b"No link at this address" in body)

status, _, _ = call("DELETE", f"/api/links/{code}", key="wrong-key")
check("DELETE with wrong key -> 403", status == 403)
status, _, _ = call("DELETE", f"/api/links/{code}", key=key)
check("DELETE -> 204", status == 204)
status, _, _ = call("GET", "/" + code)
check("deleted link -> 404", status == 404)

print()
print("all passed" if failed == 0 else f"{failed} failed", "against", BASE)
sys.exit(1 if failed else 0)

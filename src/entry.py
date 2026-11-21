# Cloudflare Worker: API, redirects and click logging.
# HTML/CSS/JS files from public/ are served by Cloudflare (static assets),
# this code only runs for /api/... and for short codes like /a7Kx2q.

import json
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint

import utils


def json_response(data, status=200):
    headers = {"content-type": "application/json; charset=utf-8", "cache-control": "no-store"}
    return Response(json.dumps(data), status=status, headers=headers)


def error(status, message):
    return json_response({"error": message}, status)


def get_key(request):
    # Private endpoints expect "Authorization: Bearer <key>"
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


class Default(WorkerEntrypoint):

    async def fetch(self, request):
        url = urlsplit(request.url)
        origin = f"{url.scheme}://{url.netloc}"
        parts = [p for p in url.path.split("/") if p]
        method = request.method

        try:
            if parts == ["api", "links"] and method == "POST":
                return await self.create_link(request, url.hostname, origin)

            if parts[:2] == ["api", "links"] and len(parts) == 3:
                if method == "GET":
                    return await self.get_link(request, parts[2], origin)
                if method == "DELETE":
                    return await self.delete_link(request, parts[2])

            if parts[:2] == ["api", "links"] and len(parts) == 4 and parts[3] == "stats" and method == "GET":
                return await self.get_stats(request, parts[2])

            if parts[:1] == ["api"]:
                return error(404, "Unknown endpoint.")

            if len(parts) == 1 and method in ("GET", "HEAD"):
                return await self.redirect(request, parts[0], origin)

            return await self.not_found(origin)
        except Exception as e:
            print("error:", repr(e))
            return error(500, "Something went wrong on our side. Try again in a moment.")

    # --- database helpers ---

    async def db_all(self, sql, *params):
        result = await self.env.DB.prepare(sql).bind(*params).all()
        if hasattr(result, "to_py"):
            result = result.to_py()
        return result["results"]

    async def db_first(self, sql, *params):
        row = await self.env.DB.prepare(sql).bind(*params).first()
        if hasattr(row, "to_py"):
            row = row.to_py()
        return row

    async def db_run(self, sql, *params):
        await self.env.DB.prepare(sql).bind(*params).run()

    # --- POST /api/links ---

    async def create_link(self, request, own_host, origin):
        try:
            body = await request.json()
            long_url = utils.clean_url(body.get("url"), own_host)
        except utils.BadUrl as e:
            return error(422, str(e))
        except Exception:
            return error(400, 'Send JSON like {"url": "https://..."}.')

        key = utils.new_key()
        created_at = utils.now_utc()

        # A random code can already exist, so try a few times
        for attempt in range(5):
            code = utils.new_code()
            try:
                await self.db_run(
                    "INSERT INTO links (code, url, created_at, key_hash) VALUES (?, ?, ?, ?)",
                    code, long_url, created_at, utils.hash_key(key),
                )
                break
            except Exception as e:
                if "UNIQUE" not in str(e).upper():
                    raise
        else:
            return error(503, "Couldn't find a free code. Try again.")

        return json_response({
            "code": code,
            "url": long_url,
            "created_at": created_at,
            "short_url": f"{origin}/{code}",
            "key": key,
            # the key goes after "#", so the browser never sends it to the server in the URL
            "stats_url": f"{origin}/stats?code={code}#key={key}",
        }, 201)

    # --- key check for private endpoints ---

    async def find_link(self, request, code):
        """Returns (link, None) if the key is right, otherwise (None, error response)."""
        link = None
        if utils.is_valid_code(code):
            link = await self.db_first("SELECT * FROM links WHERE code = ?", code)
        if not link:
            return None, error(404, "No link with that code. It may have been deleted.")
        if not utils.check_key(get_key(request), link["key_hash"]):
            return None, error(403, "This private key doesn't match the link.")
        return link, None

    # --- GET /api/links/{code} ---

    async def get_link(self, request, code, origin):
        link, err = await self.find_link(request, code)
        if err:
            return err
        row = await self.db_first("SELECT COUNT(*) AS n FROM clicks WHERE code = ?", code)
        return json_response({
            "code": code,
            "url": link["url"],
            "created_at": link["created_at"],
            "short_url": f"{origin}/{code}",
            "clicks": row["n"],
        })

    # --- GET /api/links/{code}/stats ---

    async def get_stats(self, request, code):
        link, err = await self.find_link(request, code)
        if err:
            return err

        total = await self.db_first(
            "SELECT COUNT(*) AS n, MAX(clicked_at) AS last FROM clicks WHERE code = ?", code)

        countries = await self.db_all(
            "SELECT country, COUNT(*) AS clicks FROM clicks WHERE code = ? "
            "GROUP BY country ORDER BY clicks DESC LIMIT 50", code)

        sources = await self.db_all(
            "SELECT referer AS source, COUNT(*) AS clicks FROM clicks WHERE code = ? "
            "GROUP BY referer ORDER BY clicks DESC LIMIT 20", code)

        # clicked_at looks like 2026-11-20T09:33:41Z, so the first 10 chars are the day
        days = await self.db_all(
            "SELECT substr(clicked_at, 1, 10) AS day, COUNT(*) AS clicks FROM clicks "
            "WHERE code = ? AND clicked_at >= ? GROUP BY day", code, utils.first_chart_day())

        # ...and chars 12-13 are the hour
        hours = await self.db_all(
            "SELECT CAST(substr(clicked_at, 12, 2) AS INTEGER) AS hour, COUNT(*) AS clicks "
            "FROM clicks WHERE code = ? GROUP BY hour", code)

        recent = await self.db_all(
            "SELECT clicked_at, country, referer AS source FROM clicks WHERE code = ? "
            "ORDER BY id DESC LIMIT 15", code)

        return json_response({
            "code": code,
            "url": link["url"],
            "created_at": link["created_at"],
            "total": total["n"],
            "last_click": total["last"],
            "by_country": countries,
            "by_source": sources,
            "by_day": utils.last_30_days({d["day"]: d["clicks"] for d in days}),
            "by_hour": utils.all_24_hours({h["hour"]: h["clicks"] for h in hours}),
            "recent": recent,
        })

    # --- DELETE /api/links/{code} ---

    async def delete_link(self, request, code):
        link, err = await self.find_link(request, code)
        if err:
            return err
        await self.db_run("DELETE FROM clicks WHERE code = ?", code)
        await self.db_run("DELETE FROM links WHERE code = ?", code)
        return Response("", status=204)

    # --- GET /{code}: redirect and save the click ---

    async def redirect(self, request, code, origin):
        link = None
        if utils.is_valid_code(code):
            link = await self.db_first("SELECT url FROM links WHERE code = ?", code)
        if not link:
            return await self.not_found(origin)

        # HEAD requests and browser prefetch are not real clicks
        is_prefetch = "prefetch" in (request.headers.get("sec-purpose") or "")
        if request.method == "GET" and not is_prefetch:
            # Cloudflare adds the visitor's country to every request
            country = getattr(request.cf, "country", None) if request.cf else None
            await self.db_run(
                "INSERT INTO clicks (code, clicked_at, country, referer) VALUES (?, ?, ?, ?)",
                code,
                utils.now_utc(),
                country or "XX",
                utils.referer_domain(request.headers.get("referer")),
            )

        return Response("", status=302, headers={"location": link["url"], "cache-control": "no-store"})

    async def not_found(self, origin):
        page = await self.env.ASSETS.fetch(f"{origin}/404")
        html = await page.text()
        return Response(html, status=404, headers={"content-type": "text/html; charset=utf-8"})

#!/usr/bin/env python3
"""storyarc — a command-line client for Autodesk Project StoryArc.

StoryArc (https://project-storyarc.autodesk.com) has no public API key. The
web app signs in through Autodesk OAuth and then keeps the session in a
browser cookie; every /api/ call is sent with that cookie. This CLI works the
same way: you copy your logged-in session cookie out of the browser once, hand
it to the CLI (via the STORYARC_COOKIE environment variable or --cookie), and
the CLI replays it against the same endpoints.

See README.md in this directory for how to grab the cookie.

No third-party dependencies — standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE_URL = "https://project-storyarc.autodesk.com"


class StoryArcError(Exception):
    """A problem talking to StoryArc (auth, network, or an HTTP error)."""


class Client:
    """Thin authenticated wrapper over the StoryArc /api surface."""

    def __init__(self, base_url: str, cookie: str | None, token: str | None,
                 timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.cookie = cookie
        self.token = token
        self.timeout = timeout
        if not cookie and not token:
            raise StoryArcError(
                "No credentials. Set STORYARC_COOKIE (your browser session "
                "cookie) or STORYARC_TOKEN, or pass --cookie / --token. "
                "See cli/README.md for how to copy the cookie."
            )

    def request(self, method: str, path: str, *,
                query: dict | None = None, data: object = None) -> "Response":
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = self.base_url + "/" + path.lstrip("/")
        if query:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(query)

        headers = {"Accept": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.token:
            headers["Authorization"] = (
                self.token if self.token.lower().startswith("bearer ")
                else "Bearer " + self.token
            )

        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url, data=body, method=method.upper(), headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return Response(resp.status, dict(resp.headers), raw)
        except urllib.error.HTTPError as e:
            raw = e.read()
            resp = Response(e.code, dict(e.headers), raw)
            if e.code == 401:
                raise StoryArcError(
                    "401 Not authenticated. Your session cookie is missing or "
                    "expired — log in again at " + self.base_url + " and copy "
                    "a fresh cookie. (See cli/README.md.)"
                ) from None
            if e.code in (302, 303, 307) or (
                resp.header("location", "").find("/login") != -1
            ):
                raise StoryArcError(
                    "Redirected to login — the session cookie is not valid. "
                    "Grab a fresh one from the browser."
                ) from None
            detail = resp.json_or_none()
            msg = detail.get("error") if isinstance(detail, dict) else None
            raise StoryArcError(
                f"HTTP {e.code} on {method.upper()} {path}"
                + (f": {msg}" if msg else "")
            ) from None
        except urllib.error.URLError as e:
            raise StoryArcError(f"Network error reaching {url}: {e.reason}") from None


class Response:
    def __init__(self, status: int, headers: dict, raw: bytes):
        self.status = status
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.raw = raw

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)

    def json_or_none(self):
        if not self.raw:
            return None
        try:
            return json.loads(self.raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def text(self) -> str:
        try:
            return self.raw.decode("utf-8")
        except UnicodeDecodeError:
            return repr(self.raw)


def emit(resp: "Response", raw: bool) -> None:
    """Print a response to stdout as pretty JSON when possible."""
    if raw:
        sys.stdout.write(resp.text())
        if resp.raw and not resp.text().endswith("\n"):
            sys.stdout.write("\n")
        return
    parsed = resp.json_or_none()
    if parsed is None:
        sys.stdout.write(resp.text())
        if resp.raw and not resp.text().endswith("\n"):
            sys.stdout.write("\n")
    else:
        print(json.dumps(parsed, indent=2, ensure_ascii=False))


def parse_pairs(pairs: list[str] | None) -> dict:
    out: dict = {}
    for item in pairs or []:
        if "=" not in item:
            raise StoryArcError(f"Expected key=value, got: {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out


def load_data(args) -> object:
    """Resolve a JSON request body from --data or --data-file."""
    if getattr(args, "data_file", None):
        if args.data_file == "-":
            text = sys.stdin.read()
        else:
            with open(args.data_file, "r", encoding="utf-8") as f:
                text = f.read()
    elif getattr(args, "data", None) is not None:
        text = args.data
    else:
        return None
    try:
        return json.loads(text)
    except ValueError as e:
        raise StoryArcError(f"--data is not valid JSON: {e}") from None


def build_client(args) -> Client:
    cookie = args.cookie or os.environ.get("STORYARC_COOKIE")
    token = args.token or os.environ.get("STORYARC_TOKEN")
    base = args.base_url or os.environ.get("STORYARC_BASE_URL") or DEFAULT_BASE_URL
    return Client(base, cookie, token)


# --- command handlers -------------------------------------------------------

def cmd_whoami(c: Client, args) -> "Response":
    return c.request("GET", "/api/auth/me")


def cmd_features(c: Client, args) -> "Response":
    return c.request("GET", "/api/settings/features")


def cmd_projects(c: Client, args) -> "Response":
    return c.request("GET", "/api/projects")


def cmd_assets(c: Client, args) -> "Response":
    return c.request("GET", "/api/assets")


def cmd_doc(c: Client, args) -> "Response":
    doc = args.document_id
    base = f"/api/document/{urllib.parse.quote(doc)}"
    routes = {
        "storylines": ("GET", f"{base}/storylines"),
        "story-nodes": ("GET", f"{base}/story-nodes"),
        "story-edges": ("GET", f"{base}/story-edges"),
        "storyboard-images": ("GET", f"{base}/storyboard/images"),
    }
    method, path = routes[args.resource]
    return c.request(method, path)


def cmd_request(c: Client, args) -> "Response":
    return c.request(
        args.method, args.path,
        query=parse_pairs(args.query),
        data=load_data(args),
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="storyarc",
        description="Command-line client for Autodesk Project StoryArc.",
    )
    p.add_argument("--base-url", help="Override base URL (default: %s)" % DEFAULT_BASE_URL)
    p.add_argument("--cookie", help="Session cookie (else $STORYARC_COOKIE).")
    p.add_argument("--token", help="Bearer token (else $STORYARC_TOKEN).")
    p.add_argument("--raw", action="store_true", help="Print the raw response body, unformatted.")

    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("whoami", help="Show the signed-in user (GET /api/auth/me).").set_defaults(func=cmd_whoami)
    sub.add_parser("features", help="Show feature flags (GET /api/settings/features).").set_defaults(func=cmd_features)
    sub.add_parser("projects", help="List projects (GET /api/projects).").set_defaults(func=cmd_projects)
    sub.add_parser("assets", help="List assets (GET /api/assets).").set_defaults(func=cmd_assets)

    d = sub.add_parser("doc", help="Read a document's story data.")
    d.add_argument("document_id", help="The document id.")
    d.add_argument("resource", choices=["storylines", "story-nodes", "story-edges", "storyboard-images"])
    d.set_defaults(func=cmd_doc)

    r = sub.add_parser("request", help="Make an arbitrary authenticated API call.")
    r.add_argument("method", help="HTTP method, e.g. GET or POST.")
    r.add_argument("path", help="API path, e.g. /api/projects.")
    r.add_argument("-q", "--query", action="append", metavar="K=V", help="Query parameter (repeatable).")
    r.add_argument("--data", help="JSON request body as a string.")
    r.add_argument("--data-file", help="Read JSON request body from a file, or - for stdin.")
    r.set_defaults(func=cmd_request)

    args = p.parse_args(argv)

    try:
        client = build_client(args)
        resp = args.func(client, args)
        emit(resp, args.raw)
        return 0
    except StoryArcError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())

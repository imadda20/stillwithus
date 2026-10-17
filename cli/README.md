# storyarc CLI

A command-line client for [Autodesk Project StoryArc](https://project-storyarc.autodesk.com).

StoryArc has no public API key. Its web app signs in through Autodesk OAuth and
then keeps your session in a **browser cookie**; every `/api/` request is sent
with that cookie. This CLI authenticates the same way — you copy your
logged-in session cookie out of the browser once and give it to the CLI.

Requires Python 3.9+. No third-party packages.

## Get your session cookie

1. In Chrome or Edge, log in at <https://project-storyarc.autodesk.com>.
2. Open DevTools: press **F12** (or right-click the page → **Inspect**).
3. In DevTools, open the **Network** tab. If you don't see it, click the
   **»** button at the end of the tab row and pick **Network**.
4. Click something in the app (open a project or a menu) so requests appear.
   Click the **Fetch/XHR** filter, then click any request whose name starts
   with `api/`.
5. In the details pane, open **Headers** and scroll to **Request Headers**.
6. Find the line beginning with **`cookie:`**. Right-click its value and choose
   **Copy value** (or select it and press Ctrl+C / Cmd+C).

> The cookie is like a temporary password for your account. Keep it private and
> don't commit it. It expires after a while — when the CLI starts returning
> `401`, repeat these steps to get a fresh one.

## Use it

Give the CLI the cookie via the `STORYARC_COOKIE` environment variable:

```bash
export STORYARC_COOKIE='paste-the-cookie-value-here'

python3 cli/storyarc.py whoami            # who am I (GET /api/auth/me)
python3 cli/storyarc.py features          # feature flags
python3 cli/storyarc.py projects          # list projects
python3 cli/storyarc.py assets            # list assets
```

Read a document's story data:

```bash
python3 cli/storyarc.py doc <documentId> storylines
python3 cli/storyarc.py doc <documentId> story-nodes
python3 cli/storyarc.py doc <documentId> story-edges
python3 cli/storyarc.py doc <documentId> storyboard-images
```

Call any endpoint directly with `request`:

```bash
# GET with query parameters
python3 cli/storyarc.py request GET /api/projects -q limit=10

# POST with a JSON body
python3 cli/storyarc.py request POST /api/bug-reports --data '{"title":"test"}'

# POST reading the body from a file (or - for stdin)
python3 cli/storyarc.py request POST /api/projects/import --data-file body.json
```

Add `--raw` to print the response body unformatted instead of pretty JSON.

## Options

| Flag | Environment variable | Default |
|------|----------------------|---------|
| `--cookie` | `STORYARC_COOKIE` | — |
| `--token` | `STORYARC_TOKEN` | — (sent as `Authorization: Bearer …`) |
| `--base-url` | `STORYARC_BASE_URL` | `https://project-storyarc.autodesk.com` |

`--token` is there in case StoryArc issues a bearer token for your account; the
normal path is the session cookie.

## Notes

- The CLI never stores your cookie; it reads it from the environment or the
  flag each run.
- Known endpoints were read from the app's own client code. The `request`
  command lets you reach anything the convenience commands don't cover,
  including the `/api/document/{id}/...` storyboard, character, and metadata
  routes.

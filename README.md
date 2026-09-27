# LuxirClient

A lightweight Python client for [Luxir](https://luxir.org/), a hybrid
search engine (BM25 + vector + facets, all in one request). This client
talks to Luxir's HTTP API.

- [Installation](#installation)
- [Quickstart](#quickstart)
- [Concepts](#concepts)
- [Guide](#guide)
  - [Connecting](#connecting)
  - [Collections](#collections)
  - [Schema](#schema)
  - [Indexing](#indexing)
  - [Searching](#searching)
  - [Faceting](#faceting)
  - [Fetching a single document](#fetching-a-single-document)
  - [Deleting](#deleting)
  - [Stats and health](#stats-and-health)
- [Error handling](#error-handling)
- [Gotchas](#gotchas)
- [What's not here yet](#whats-not-here-yet)
- [Development](#development)

## Installation

This isn't published to PyPI yet — install it from a local checkout:

```bash
pip install -e /path/to/LuxirClient
```

It depends only on `requests`.

## Quickstart

```python
from luxir_client import LuxirClient

client = LuxirClient("http://localhost:9400")

# Collections auto-create on first write — no setup step required.
client.index("books", [
    {"id": "b1", "title_t": "Dune", "year_i": 1965},
    {"id": "b2", "title_t": "Dune Messiah", "year_i": 1969},
])

res = client.search("books", {
    "query": "title_t:dune",
    "get_number": True,
    "get_scores": True,
})
print(res.get_num_found())   # 2
print(res.get_docs())        # [{'id': 'b1', ...}, {'id': 'b2', ...}]
```

## Concepts

A few Luxir ideas that shape how you'll use this client:

- **Collections auto-create.** There's no required "create collection"
  step — the first `index()` call into a new name creates it. Use
  `client.collections.create(...)` only when you want to install a
  schema *before* any documents land.
- **Field names carry their type.** Luxir infers a field's type from a
  naming suffix instead of requiring an upfront schema:

  | Suffix | Meaning |
  |---|---|
  | `_t` | full-text, stemmed/analyzed |
  | `_s` | exact-match string |
  | `_i` / `_is` | int, single or multi-valued |
  | `_f` / `_fs` | float |
  | `_dt` | date |
  | `_v` | vector |
  | `_name` | text with folding, no stemming |

  So `{"id": "b1", "title_t": "Dune", "year_i": 1965}` is enough — no
  schema declaration needed. Declare one later with `client.schema` if
  you want tighter control.
- **Queries are either strings or structured dicts.** `"query":
  "title_t:dune AND year_i:>=1960"` and `"query": {"match": {"field":
  "title_t", "val": "dune"}}` are both valid — this client just passes
  whatever you give it straight through as JSON.
- **Facets and metrics live under `ops`, not a separate facet param.**
  Search, facets, and analytics all execute in a single request.

## Guide

### Connecting

```python
client = LuxirClient("http://localhost:9400")
```

Pass a list of hosts to get automatic failover to the next host if one
is unreachable:

```python
client = LuxirClient(["http://search-a:9400", "http://search-b:9400"])
```

### Collections

```python
client.collections.list()                 # ['books', 'main']
client.collections.exists("books")         # True
client.collections.create("reviews")       # explicit create, no schema
client.collections.create("reviews", schema={...})  # create with a schema
client.collections.delete("reviews")
client.collections.stats("books")          # per-collection stats
client.collections.stats("books", segments=True)
```

### Schema

```python
client.schema.get("books")                  # authored schema
client.schema.get("books", resolved=True)   # expanded/physical view
client.schema.set_fields("books", {
    "title": {"type": "text", "stored": True},
})
client.schema.replace_all("books", {"fields": {...}})
client.schema.does_field_exist("books", "title_t")
```

### Indexing

```python
# Convenience wrapper — commits by default.
client.index("books", [
    {"id": "b1", "title_t": "Dune", "year_i": 1965},
])

# Index without committing immediately (visibility delayed).
client.index("books", docs, commit=False)

# Full control via update(): mix upserts and deletes in one request.
client.update("books",
    docs=[{"id": "b3", "title_t": "Children of Dune"}],
    delete_ids=["b1"],
    commit={},
)
```

### Searching

```python
res = client.search("books", {
    "query": "title_t:(dune OR messiah) AND year_i:>=1965",
    "filter": ["stock_i:>0"],       # non-scoring, ANDed with query
    "limit": 10,
    "get_number": True,             # populates res.get_num_found()
    "get_scores": True,             # populates res.get_scores()
    "fields": ["id", "title_t", "year_i"],
})

res.get_docs()          # list of doc dicts
res.get_results_count() # len(docs) in this response
res.get_num_found()     # exact total match count (needs get_number=True)
res.get_scores()        # {doc_id: score} (needs get_scores=True)
res.get_json()          # raw response as a JSON string
```

Omit `"query"` entirely to match every document (useful for
count-only or facet-only requests with `"limit": 0`).

`search_raw()` returns the plain parsed dict instead of a
`LuxirResponse`, if you'd rather work with it directly.

### Faceting

Facets are requested under `ops` and read back the same way:

```python
res = client.search("books", {
    "limit": 0,  # don't need docs, just the facet
    "ops": {
        "by_genre": {"field_facet": {"field": "genre_s"}},
    },
})
res.get_facet_buckets("by_genre")
# [{'val': 'scifi', 'count': 2}, {'val': 'romance', 'count': 1}]

res.get_ops()             # the whole `ops` block
res.get_ops("by_genre")   # just this op's result
```

Range facets, date histograms, and per-bucket metrics (`avg`, `min`,
...) all go through the same `ops` mechanism — see [Luxir's faceting
docs](https://luxir.org/docs/latest/guide/faceting/) for the full
request shapes. This client doesn't wrap them individually; pass
whatever `ops` dict you need.

### Fetching a single document

```python
doc = client.get("books", "b1")   # raises NotFoundError if missing
```

Luxir has no dedicated realtime-get endpoint, so this is sugar over a
`search()` filtered to that id — not a separate, cheaper code path.

### Deleting

```python
client.delete_by_id("books", "b1")             # single id
client.delete_by_id("books", ["b1", "b2"])      # multiple ids
client.delete_by_id("books", "b1", commit=False)
```

There's no `delete_by_query` — Luxir doesn't implement one.

### Stats and health

```python
client.health()             # {'status': 'ok'}
client.stats()               # node-wide stats
client.stats("books")        # per-collection stats
```

## Error handling

Every failure — whether the server returned an HTTP error status or a
200 with an error embedded in the body (Luxir does both, depending on
the endpoint) — raises a typed exception from `luxir_client.exceptions`,
all inheriting from `LuxirError`:

```python
from luxir_client.exceptions import NotFoundError, AlreadyExistsError

try:
    client.search("does_not_exist", {})
except NotFoundError as e:
    print(e.kind, e.code, e.message)
    # not_found collection_not_found "collection 'does_not_exist' does not exist"
```

| Exception | Luxir `kind` | Typical cause |
|---|---|---|
| `InvalidRequestError` | `invalid_request` | Malformed query/payload |
| `NotFoundError` | `not_found` | Missing collection/document |
| `AlreadyExistsError` | `already_exists` | Duplicate collection create |
| `FailedPreconditionError` | `failed_precondition` | State conflict |
| `ResourceExhaustedError` | `resource_exhausted` | Rate-limited (HTTP 429) — safe to retry with backoff |
| `UnavailableError` | `unavailable` | Server temporarily unavailable — safe to retry |
| `InternalError` | `internal` | Server-side bug |
| `ConnectionError` | — | Couldn't reach any configured host at all |

An unrecognized `kind` still raises, as the base `LuxirError`, so new
server-side error kinds fail loudly instead of silently.

## Gotchas

Things confirmed by hand against a live instance that are easy to trip
over:

- **`"query": "*"` is not match-all.** Omit the `query` key entirely to
  match everything. A bare `*` raises `InvalidRequestError` (unfielded
  term).
- **Search errors can come back as HTTP 200.** The error envelope
  (`{"error": {...}}`) can be embedded in a 200 response body just as
  often as a 4xx/5xx status — this client checks for the `error` key
  before looking at the status code, so you don't need to handle this
  yourself, but don't assume `response.status_code == 200` means
  success if you're bypassing the client.
- **`collections.list()`'s response key (`collections`) isn't
  documented**, just inferred from behavior — flag it if a future
  Luxir version changes the field name.

## What's not here yet

This is deliberately a lightweight first cut. Not implemented, add as
needed:

- gRPC transport (`luxir.Indexer`/`luxir.Searcher`/`luxir.Admin`)
- NDJSON bulk streaming for indexing (currently one bounded JSON
  request per `update()`/`index()` call)
- A structured query-builder helper (`Q.match(...)`, `Q.boolean(...)`, etc.)
- kind-aware retry/backoff (currently: no automatic retries at all,
  other than failing over to the next host on connection errors)
- An async client

## Development

```bash
pip install -e ".[test]"
pytest
```

Tests run against a mocked `requests.Session` — no live Luxir instance
required.

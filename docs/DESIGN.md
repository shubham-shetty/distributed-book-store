# Design

## Architecture

This is a multi-tiered, microservice-based system: a presentation tier (front-end), an
application tier (catalog and order services), and a database tier (per-service JSON files).

```
Client (HTTP) --> Front-End Service (HTTP) --> gRPC --> Catalog Service --> database.json
                                             \-> gRPC --> Order Service x3 --> order_database_<port>.json
                                                            |
                                             Catalog <--HTTP PUT /invalidate--- (cache push)
```

The system is written in Python: an HTTP server (`http.server.ThreadingHTTPServer`) is the
client-facing interface, and gRPC is used for all internal service-to-service communication.
Proto definitions live alongside each service under `src/protos/`.

## Front-End Service

Exposes a REST API to clients and translates each request into one or more gRPC calls to the
catalog/order services:

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/products/<title>` | Returns price/stock for a book. Served from an in-memory cache if present, otherwise forwarded to the catalog service and cached. |
| `POST` | `/orders` | Places an order (`{"name": ..., "quantity": ...}`), forwarded to the current order-service leader. |
| `GET` | `/orders/<order_number>` | Looks up a past order from the order-service leader. |
| `PUT` | `/invalidate/<title>` | Internal only — the catalog service calls this after every purchase or restock to evict a stale cache entry. |

**Leader discovery**: on startup, and again any time a gRPC call to the order service fails, the
front-end health-checks each configured order-service replica (highest port first) and picks the
first one that responds as the leader, notifying the other replicas of that choice. This makes
order-service crashes transparent to clients — a failed request simply triggers re-discovery and
a retry.

## Catalog Service

Owns the book inventory. Backed by a JSON file (`database.json`), with an in-memory copy guarded
by a `threading.Lock` for concurrent reads/writes from the gRPC thread pool.

**RPCs**
- `Query(productName) -> price, quantity` — returns `-1, -1` if the title isn't stocked.
- `Update(productName, quantity) -> response` — decrements stock on a purchase.
  `-1` = not stocked, `0` = out of stock, `1` = success. On success, pushes a cache invalidation
  to the front-end.

A background timer restocks any title at 0 quantity back to 100 every 10 seconds, and pushes a
cache invalidation for each restocked title.

## Order Service

Owns order records and executes purchases: on `Buy`, it calls the catalog service's `Update`
RPC, and on success appends the new order to its local JSON database and replicates it to the
other replicas.

Run as 3 replicas for fault tolerance. There is no formal leader-election protocol — the
front-end elects the leader externally (see above) — but replicas do reconcile state with each
other:

**RPCs**
- `Buy(productName, quantity) -> orderNumber`
- `OrderQuery(orderNumber) -> productName, quantity`
- `HealthCheck()` — used by the front-end's leader discovery.
- `Notify(leader)` — informs a replica which peer is currently the leader.
- `Sync(orderNumber, productName?, productQty?) -> stream of SyncResponse` — used both at
  startup and after a crash recovery: a replica compares its highest order number against a peer
  and either streams back the orders it's missing ("back-sync"), or accepts an order pushed to it
  by a peer that's ahead.

## Database Layer

Two JSON-file "databases," one per data domain:

```
database.json:
{
  "<book title>": {"price": <float>, "quantity": <int>}
}

order_database_<port>.json (one per order-service replica):
{
  "<order number>": {"product": "<book title>", "quantity": <int>}
}
```

## Testing

`test/test_catalog.py` and `test/test_order.py` use `pytest-grpc` to exercise each gRPC service
against a fake server; `test/test_front_end.py` exercises the HTTP layer. Some tests call out to
a peer service synchronously (e.g. a purchase call from the order service to the catalog
service) and only pass when the full stack is already running via `build.sh` — they aren't fully
isolated unit tests.

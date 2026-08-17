# Distributed Book Store

A distributed e-commerce backend built to explore core distributed-systems concepts:
microservices over gRPC, an HTTP front door, in-memory caching with server-push invalidation,
primary-backup replication, and crash fault tolerance. Written in Python 3.

## Architecture

Three independently-run microservices plus a client:

```
Client (HTTP) --> Front-End Service (HTTP) --> gRPC --> Catalog Service
                                             \-> gRPC --> Order Service (x3 replicas)
                                                            |
                                             Catalog <--HTTP PUT /invalidate--- (cache push)
```

- **Front-End Service** (`src/front_end/`) -- the only component clients talk to directly.
- **Catalog Service** (`src/catalog/`) -- owns book inventory.
- **Order Service** (`src/order/`) -- owns order records, run as 3 replicas for fault tolerance.
- **Client** (`src/client/`) -- a standalone HTTP client for manual use and load generation.

See [docs/DESIGN.md](docs/DESIGN.md) for the full design writeup (RPCs, message formats,
database layout).

## Features

- **Caching**: the front-end caches product queries in memory. The catalog service pushes cache
  invalidations to the front-end after every purchase or restock, so cached data never goes
  stale.
- **Replication**: the order service runs as 3 replicas. The front-end elects a leader by
  health-checking replicas and forwards all purchase/order-lookup requests to it; the leader
  replicates each new order to the followers.
- **Fault tolerance**: if the front-end's call to the leader fails, it re-elects a leader and
  retries transparently. A replica recovering from a crash reconciles its order log with a peer
  on startup.

## REST API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/products/<title>` | Look up a book's price/stock |
| `POST` | `/orders` | Place an order: `{"name": ..., "quantity": ...}` |
| `GET` | `/orders/<order_number>` | Look up a past order |

## Running locally

Requires Python 3 and pip.

```shell
cd src
python3 -m venv venv && source venv/bin/activate
pip3 install -r requirements.txt

./build.sh $(hostname)   # regenerates gRPC stubs and starts all 5 services
```

In a second terminal:

```shell
cd src && source venv/bin/activate
python3 client/client.py --host localhost --port 12345 --t 1984 --p 0.5
```

Client options:
- `--p` / `--probability`: probability of buying a book given it's in stock
- `--t` / `--title`: book title
- `--o` / `--order_num`: order number to look up
- `--host`, `--port`: front-end address

To stop all services:

```shell
pkill -f "catalog/catalog.py"; pkill -f "order/order.py"; pkill -f "front_end/front_end.py"
```

## Running with Docker

Each service runs in its own container, addressing its peers by Docker Compose service name
instead of `localhost`.

```shell
docker compose up --build
```

This builds `catalog`, three `order` replicas, and `front-end`, and publishes the front-end on
`localhost:12345`. From a second terminal, point the client at it exactly as in local mode:

```shell
cd src && source venv/bin/activate
python3 client/client.py --host localhost --port 12345 --t 1984 --p 0.5
```

```shell
docker compose down   # stop and remove the containers
```

## Running on the cloud

`src/deploy/` provisions this onto any cloud VM you already have SSH access to (AWS, GCP,
DigitalOcean, ...) -- bring your own key and host. See
[src/deploy/README.md](src/deploy/README.md).

## Testing

See [test/README.md](test/README.md).

## License

MIT -- see [LICENSE](LICENSE).

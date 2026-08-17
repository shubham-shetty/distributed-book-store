"""
Measures the latency benefit of the front-end's product-query cache.

For each trial: invalidate the cache for a title (forcing the next GET to be
a cache miss that round-trips to the Catalog service over gRPC), time that
GET, then immediately time a second GET for the same title (a cache hit
served from the front-end's in-memory dict).

Requires the full stack to already be running (see ../src/build.sh) and the
front-end reachable at --host/--port.
"""
import argparse
import time
from http.client import HTTPConnection

TITLES = [
    "1984", "dune", "moby_dick", "the_hobbit", "frankenstein",
    "the_odyssey", "brave_new_world", "war_and_peace",
    "pride_and_prejudice", "the_great_gatsby",
]


def timed_get(host, port, path):
    conn = HTTPConnection(host, port)
    start = time.perf_counter()
    conn.request("GET", path)
    resp = conn.getresponse()
    resp.read()
    elapsed = time.perf_counter() - start
    conn.close()
    return elapsed, resp.status


def invalidate(host, port, title):
    conn = HTTPConnection(host, port)
    conn.request("PUT", f"/invalidate/{title}")
    # the front-end never sends a response for this endpoint; don't wait on one
    conn.close()


def stats(xs):
    xs_sorted = sorted(xs)
    n = len(xs_sorted)
    mean = sum(xs_sorted) / n
    p50 = xs_sorted[n // 2]
    return mean, p50


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="Front-end hostname")
    parser.add_argument("--port", type=int, default=12345, help="Front-end port")
    parser.add_argument("--trials", type=int, default=100, help="Number of cold/warm pairs to measure")
    args = parser.parse_args()

    cold_times, warm_times = [], []

    for i in range(args.trials):
        title = TITLES[i % len(TITLES)]
        invalidate(args.host, args.port, title)

        elapsed, status = timed_get(args.host, args.port, f"/products/{title}")
        assert status == 200, f"unexpected status {status} for {title}"
        cold_times.append(elapsed)

        elapsed, status = timed_get(args.host, args.port, f"/products/{title}")
        assert status == 200, f"unexpected status {status} for {title}"
        warm_times.append(elapsed)

    cold_mean, cold_p50 = stats(cold_times)
    warm_mean, warm_p50 = stats(warm_times)

    print(f"Cache-MISS (gRPC to catalog): n={len(cold_times)}  mean={cold_mean*1000:.3f}ms  p50={cold_p50*1000:.3f}ms")
    print(f"Cache-HIT  (in-memory):       n={len(warm_times)}  mean={warm_mean*1000:.3f}ms  p50={warm_p50*1000:.3f}ms")
    print(f"Latency reduction (mean): {(1 - warm_mean / cold_mean) * 100:.1f}%")
    print(f"Latency reduction (p50):  {(1 - warm_p50 / cold_p50) * 100:.1f}%")


if __name__ == "__main__":
    main()

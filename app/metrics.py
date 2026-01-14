from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=("path", "status"),
)

WEBHOOK_REQUESTS_TOTAL = Counter(
    "webhook_requests_total",
    "Webhook processing outcomes",
    labelnames=("result",),
)

REQUEST_LATENCY_MS = Histogram(
    "request_latency_ms",
    "Request latency in milliseconds",
    buckets=(25, 50, 100, 250, 500, 1000, 2500, 5000, float("inf")),
)
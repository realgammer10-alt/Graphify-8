import asyncio

from graphify.serve import _MonitoringMiddleware, _monitoring_health


def test_monitoring_tracks_endpoint_failures_and_recovery():
    state = {
        "request_count": 0,
        "failed_requests": 0,
        "last_request_at": None,
        "last_status_code": None,
        "last_duration_ms": None,
    }
    response_codes = iter([503, 204])

    async def app(scope, _receive, send):
        response_code = next(response_codes)
        await send({
            "type": "http.response.start",
            "status": response_code,
            "headers": [],
        })
        await send({"type": "http.response.body", "body": b""})

    middleware = _MonitoringMiddleware(app, state=state, mcp_path="/mcp")

    async def request():
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(_message):
            return None

        await middleware(
            {"type": "http", "method": "POST", "path": "/mcp", "headers": []},
            receive,
            send,
        )

    asyncio.run(request())
    assert _monitoring_health({**state, "graph_status": "available"}) == (
        "degraded",
        "degraded",
    )
    assert state["request_count"] == 1
    assert state["failed_requests"] == 1
    assert state["last_status_code"] == 503
    assert state["last_duration_ms"] >= 0

    asyncio.run(request())
    assert _monitoring_health({**state, "graph_status": "available"}) == (
        "ready",
        "ok",
    )
    assert state["request_count"] == 2
    assert state["failed_requests"] == 1
    assert state["last_status_code"] == 204
    assert state["last_request_at"]


def test_unavailable_graph_degrades_service_without_affecting_liveness():
    state = {
        "last_request_at": None,
        "last_status_code": None,
        "graph_status": "unavailable",
    }
    assert _monitoring_health(state) == ("ready", "degraded")

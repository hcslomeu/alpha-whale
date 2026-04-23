"""Integration tests for AlphaWhale API routes."""

from unittest.mock import MagicMock

from httpx import AsyncClient

# --- /health endpoint ---


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


async def test_health_includes_dependency_checks(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    assert "redis" in data["checks"]
    assert "pinecone" in data["checks"]


async def test_health_checks_status(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    for name, check in data["checks"].items():
        assert check["status"] == "ok", f"{name} check should be ok"
    assert data["checks"]["redis"]["detail"] == "disabled"
    assert data["checks"]["pinecone"]["detail"] == "stub"


# --- /market/{asset} endpoint ---


async def test_market_returns_ohlcv_data(client: AsyncClient, mock_supabase: MagicMock) -> None:
    response = await client.get("/market/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["date"] == "2026-03-12"


async def test_market_response_contains_ohlcv_fields(
    client: AsyncClient, mock_supabase: MagicMock
) -> None:
    response = await client.get("/market/AAPL")
    row = response.json()[0]
    for field in ("ticker", "date", "open", "high", "low", "close", "volume"):
        assert field in row, f"Missing field: {field}"


async def test_market_uppercases_ticker(client: AsyncClient, mock_supabase: MagicMock) -> None:
    await client.get("/market/aapl")
    mock_supabase.table.return_value.select.return_value.eq.assert_called_with("ticker", "AAPL")


async def test_market_default_days_limit(client: AsyncClient, mock_supabase: MagicMock) -> None:
    await client.get("/market/AAPL")
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_with(
        30
    )


async def test_market_custom_days_param(client: AsyncClient, mock_supabase: MagicMock) -> None:
    await client.get("/market/AAPL?days=5")
    mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_with(
        5
    )


async def test_market_empty_result_returns_empty_list(
    client: AsyncClient, mock_supabase_empty: MagicMock
) -> None:
    response = await client.get("/market/UNKNOWN")
    assert response.status_code == 200
    assert response.json() == []


# --- /market/{asset}/indicators endpoint ---


async def test_indicators_returns_data(
    client: AsyncClient, mock_supabase_indicators: MagicMock
) -> None:
    response = await client.get("/market/AAPL/indicators")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["date"] == "2026-03-12"


async def test_indicators_response_contains_all_fields(
    client: AsyncClient, mock_supabase_indicators: MagicMock
) -> None:
    response = await client.get("/market/AAPL/indicators")
    row = response.json()[0]
    for field in (
        "ticker",
        "date",
        "ema_8",
        "ema_80",
        "sma_200",
        "macd_value",
        "macd_signal",
        "macd_histogram",
        "rsi_14",
        "stoch_k",
        "stoch_d",
    ):
        assert field in row, f"Missing field: {field}"


async def test_indicators_uppercases_ticker(
    client: AsyncClient, mock_supabase_indicators: MagicMock
) -> None:
    await client.get("/market/aapl/indicators")
    mock_supabase_indicators.table.return_value.select.return_value.eq.assert_called_with(
        "ticker", "AAPL"
    )


async def test_indicators_default_days_limit(
    client: AsyncClient, mock_supabase_indicators: MagicMock
) -> None:
    await client.get("/market/AAPL/indicators")
    mock_supabase_indicators.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_with(
        30
    )


async def test_indicators_custom_days_param(
    client: AsyncClient, mock_supabase_indicators: MagicMock
) -> None:
    await client.get("/market/AAPL/indicators?days=5")
    mock_supabase_indicators.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_with(
        5
    )


async def test_indicators_empty_result_returns_empty_list(
    client: AsyncClient, mock_supabase_empty: MagicMock
) -> None:
    response = await client.get("/market/UNKNOWN/indicators")
    assert response.status_code == 200
    assert response.json() == []


# --- /chat/stream endpoint ---


async def test_chat_stream_returns_event_stream(client: AsyncClient, mock_graph: None) -> None:
    response = await client.post(
        "/chat/stream",
        json={"message": "What is Bitcoin?"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


async def test_chat_stream_contains_tokens(client: AsyncClient, mock_graph: None) -> None:
    response = await client.post(
        "/chat/stream",
        json={"message": "What is Bitcoin?"},
    )
    body = response.text
    assert '"token"' in body
    assert "Hello" in body
    assert "Whale" in body


async def test_chat_stream_ends_with_done_sentinel(client: AsyncClient, mock_graph: None) -> None:
    response = await client.post(
        "/chat/stream",
        json={"message": "What is Bitcoin?"},
    )
    assert "[DONE]" in response.text


async def test_chat_stream_empty_message_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/chat/stream",
        json={"message": ""},
    )
    assert response.status_code == 422


async def test_chat_stream_missing_message_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/chat/stream",
        json={},
    )
    assert response.status_code == 422


async def test_chat_stream_no_body_returns_422(client: AsyncClient) -> None:
    response = await client.post("/chat/stream")
    assert response.status_code == 422

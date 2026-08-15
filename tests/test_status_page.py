"""Testy stron pomocniczych (`/`, `/robots.txt`) — SPEC.md, sekcja "Endpointy pomocnicze". Nie są częścią
kontraktu Primo, więc świadomie osobno od tests/test_contract.py (który testuje wyłącznie to, czego
oczekuje prawdziwy OmnisClient).
"""

import httpx
import pytest

from omnis_mock.main import app


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock.local") as http_client:
        yield http_client


async def test_status_page_returns_html_with_key_info(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "omnis-mock" in body
    assert "github.com/theundefined/omnis-mock" in body
    assert "nie</strong> jest oficjalna sieć OMNIS" in body
    assert "noindex" in body


async def test_status_page_shows_demo_credentials(client: httpx.AsyncClient) -> None:
    from omnis_mock import data

    response = await client.get("/")
    body = response.text
    assert data.DEMO_USERNAME in body
    assert data.DEMO_PASSWORD in body


async def test_robots_txt_disallows_everything(client: httpx.AsyncClient) -> None:
    response = await client.get("/robots.txt")
    assert response.status_code == 200
    assert "Disallow: /" in response.text


async def test_status_page_base_url_defaults_to_request_host(client: httpx.AsyncClient) -> None:
    """Bez nagłówków X-Forwarded-* — base_url pochodzi wprost z requestu (tu: base_url klienta testowego),
    nie z żadnej hardkodowanej domeny (SPEC.md, "Endpointy pomocnicze")."""
    response = await client.get("/")
    assert "http://mock.local" in response.text


async def test_status_page_base_url_honors_forwarded_headers(client: httpx.AsyncClient) -> None:
    """Z X-Forwarded-Proto/-Host (tak jak ustawia je Render/Cloudflare) — base_url musi odzwierciedlać
    PRAWDZIWY zewnętrzny adres, nie surowe (wewnętrzne) request.url."""
    response = await client.get(
        "/",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "omnis-mock.example.com"},
    )
    assert "https://omnis-mock.example.com" in response.text
    assert "http://mock.local" not in response.text

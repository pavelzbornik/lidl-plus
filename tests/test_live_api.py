"""Live integration tests that validate the real Lidl Plus API endpoints.

These hit the network and are **deselected by default** (see the ``integration``
marker config in pyproject.toml). Run them explicitly with::

    uv run pytest -m integration

The public endpoints (countries, stores) need no credentials. The authenticated
endpoints need a refresh token, taken from ``LIDLPLUS_TOKEN`` or
``LIDL_REFRESH_TOKEN`` (a ``.env`` file is loaded automatically); they skip when
no token is set.

Note: using the refresh token rotates it, and these tests assert on response
*shape* rather than personal values to avoid surfacing account data.
"""

import os

import pytest

from lidlplus import LidlPlusApi

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is a core dependency
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

pytestmark = pytest.mark.integration

LANGUAGE = os.environ.get("LIDL_LANGUAGE", "de")
COUNTRY = os.environ.get("LIDL_COUNTRY", "DE")


def _refresh_token():
    return os.environ.get("LIDLPLUS_TOKEN") or os.environ.get("LIDL_REFRESH_TOKEN")


@pytest.fixture(scope="session")
def authed_client():
    """A single authenticated client shared by all authed tests.

    The refresh token rotates on first use, so the client is built once per
    session: the access token is obtained once and reused, instead of each test
    re-renewing with the (now consumed) original token and failing.
    """
    token = _refresh_token()
    if not token:
        pytest.skip("no refresh token (set LIDLPLUS_TOKEN or LIDL_REFRESH_TOKEN)")
    return LidlPlusApi(LANGUAGE, COUNTRY, refresh_token=token)


# --- public endpoints (no authentication required) ---------------------------


def test_countries_endpoint_live():
    countries = LidlPlusApi(LANGUAGE, COUNTRY).countries()
    assert isinstance(countries, list) and countries
    assert "id" in countries[0]


def test_stores_endpoint_live():
    stores = LidlPlusApi(LANGUAGE, COUNTRY).stores()
    assert isinstance(stores, list)


# --- authenticated endpoints (skip without a token) --------------------------


def test_user_info_endpoint_live(authed_client):
    info = authed_client.user_info()
    assert isinstance(info, dict)
    assert "sub" in info


def test_loyalty_id_endpoint_live(authed_client):
    loyalty = authed_client.loyalty_id()
    assert isinstance(loyalty, str)
    assert loyalty.strip()


def test_coupons_endpoint_live(authed_client):
    coupons = authed_client.coupons()
    assert isinstance(coupons, dict)
    assert "sections" in coupons


def test_tickets_endpoint_live(authed_client):
    tickets = authed_client.tickets()
    assert isinstance(tickets, list)
    if tickets:
        detail = authed_client.ticket(tickets[0]["id"])
        assert isinstance(detail, dict)
        assert "itemsLine" in detail

"""Unit tests: LangChain's standard tool tests plus our own, with the HTTP call faked."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_tests.unit_tests import ToolsUnitTests

from langchain_coworkingview import (
    CoworkingViewFindPlace,
    CoworkingViewMarketRates,
    CoworkingViewSearch,
    CoworkingViewSpace,
    CoworkingViewToolkit,
    _api,
)


class TestSearchStandard(ToolsUnitTests):
    @property
    def tool_constructor(self) -> type[CoworkingViewSearch]:
        return CoworkingViewSearch

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"city": "berlin", "workspace_type": "private_office", "max_results": 3}


class TestSpaceStandard(ToolsUnitTests):
    @property
    def tool_constructor(self) -> type[CoworkingViewSpace]:
        return CoworkingViewSpace

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"slug": "signature-potsdamer-platz-berlin"}


class TestMarketRatesStandard(ToolsUnitTests):
    @property
    def tool_constructor(self) -> type[CoworkingViewMarketRates]:
        return CoworkingViewMarketRates

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"city": "madrid"}


class TestFindPlaceStandard(ToolsUnitTests):
    @property
    def tool_constructor(self) -> type[CoworkingViewFindPlace]:
        return CoworkingViewFindPlace

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"query": "Kreuzberg"}


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Replace the HTTP call with canned bodies and record what was asked."""
    recorded: list[tuple[str, dict[str, Any]]] = []
    bodies = {
        "/v1/properties": {
            "data": [
                {
                    "slug": "a-space",
                    "title": "A Space ",
                    "zone": {"name": "Mitte"},
                    "operator": {"name": "Acme"},
                    "capacity": 20,
                    "fromPrice": {"amount": 290, "currency": "EUR"},
                    "fromBillingPeriod": "month",
                    "marketPosition": {"verdict": "below"},
                },
                {"slug": "b-space", "title": "B"},
            ],
            "meta": {"pagination": {"total": 42}},
        },
        "/v1/properties/a-space": {
            "data": {
                "title": "A Space",
                "address": "Street 1",
                "city": {"name": "Berlin "},
                "amenities": ["wifi"],
                "pricingOptions": [
                    {"optionType": "day_pass", "title": "Day", "price": {"amount": 12.5, "currency": "EUR"}, "billingPeriod": "day"},
                    {"optionType": "private_office", "title": "Office", "priceOnRequest": True, "billingPeriod": "month"},
                ],
                "webUrl": "https://coworkingview.com/en/workspace/a-space",
            }
        },
        "/v1/market/rates": {
            "data": {
                "asOf": "2026-10-28T00:00:00Z",
                "cities": [
                    {
                        "city": {"name": "Madrid"},
                        "currency": "EUR",
                        "figures": [{"optionType": "fix_desk", "median": {"amount": 260, "currency": "EUR"}, "propertyCount": 7}],
                        "dayPass": {"median": {"amount": 22, "currency": "EUR"}, "sampleSize": 11},
                    }
                ],
            }
        },
        "/v1/search/suggest": {"data": [{"kind": "zone", "slug": "kreuzberg", "label": "Kreuzberg", "propertyCount": 9}]},
    }

    def fake_get(path: str, params: dict[str, Any], base_url: str = _api.BASE_URL) -> dict[str, Any]:
        recorded.append((path, params))
        return bodies[path]

    monkeypatch.setattr(_api, "get", fake_get)
    return recorded


def test_search_shapes_results_and_sends_filters(calls: list) -> None:
    out = CoworkingViewSearch().invoke({"city": "Berlin", "workspace_type": "private_office", "district": "Mitte", "max_results": 50})
    path, params = calls[0]
    assert path == "/v1/properties"
    assert params["city"] == "berlin" and params["zone"] == "mitte"
    assert params["pricingOptionType"] == "private_office" and params["pageSize"] == 50
    assert out["total_matching"] == 42
    first, second = out["spaces"]
    assert first == {
        "slug": "a-space",
        "name": "A Space",
        "district": "Mitte",
        "operator": "Acme",
        "capacity": 20,
        "from_price": "EUR 290/month",
        "vs_city_median": "below",
        "url": "https://coworkingview.com/en/workspace/a-space",
    }
    assert second["from_price"] == "on request"


def test_max_results_over_the_api_cap_is_refused(calls: list) -> None:
    with pytest.raises(Exception, match="less than or equal to 50"):
        CoworkingViewSearch().invoke({"city": "berlin", "max_results": 99})
    assert calls == []


def test_search_omits_empty_type(calls: list) -> None:
    CoworkingViewSearch().invoke({"city": "berlin"})
    assert calls[0][1]["pricingOptionType"] is None  # dropped by _api.get, so never sent empty


def test_space_lists_every_option(calls: list) -> None:
    out = CoworkingViewSpace().invoke({"slug": "a-space"})
    assert out["city"] == "Berlin"
    assert [o["price"] for o in out["pricing_options"]] == ["EUR 12.50/day", "on request"]
    assert out["url"].endswith("/a-space")


def test_market_rates(calls: list) -> None:
    out = CoworkingViewMarketRates().invoke({"city": "madrid", "currency": "usd"})
    assert calls[0][1]["currency"] == "USD"
    assert out["monthly"] == {"fix_desk": {"median_per_month": "EUR 260", "spaces": 7}}
    assert out["day_pass"] == {"median_per_day": "EUR 22", "sample_size": 11}
    assert "CC BY 4.0" in out["source"]


def test_find_place(calls: list) -> None:
    out = CoworkingViewFindPlace().invoke({"query": " Kreuzberg "})
    assert calls[0][1]["q"] == "Kreuzberg"
    assert out["matches"][0]["slug"] == "kreuzberg"


def test_bad_input_never_reaches_the_api(calls: list) -> None:
    with pytest.raises(ValueError, match="not a slug"):
        CoworkingViewSearch().invoke({"city": "New York"})
    with pytest.raises(ValueError, match="ISO 4217"):
        CoworkingViewMarketRates().invoke({"city": "madrid", "currency": "euro"})
    assert calls == []


def test_drops_empty_params_from_the_query(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"data": []}'

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["ua"] = request.get_header("User-agent")
        return Response()

    monkeypatch.setattr(_api.urllib.request, "urlopen", fake_urlopen)
    _api.get("/v1/properties", {"city": "berlin", "pricingOptionType": None, "zone": ""})
    assert seen["url"] == "https://api.coworkingview.com/v1/properties?city=berlin"
    assert seen["ua"].startswith("langchain-coworkingview/")


def test_toolkit_has_every_tool() -> None:
    names = {tool.name for tool in CoworkingViewToolkit().get_tools()}
    assert names == {"coworkingview_find_place", "coworkingview_search", "coworkingview_space", "coworkingview_market_rates"}

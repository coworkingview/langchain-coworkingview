"""LangChain tools over the CoworkingView catalogue.

Every tool is read-only and needs no API key. Results are compact dicts meant
for a model to read: prices are formatted, each space carries the link to its
page on coworkingview.com, and market figures carry their sample size.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, Field

from langchain_coworkingview import _api

Locale = Literal["en", "de", "es"]
WorkspaceType = Literal[
    "private_office",
    "fix_desk",
    "flex_desk",
    "day_pass",
    "meeting_room",
    "virtual_office",
    "event_space",
    "membership",
    "exclusive_bereich",
]


class _Base(BaseTool):
    """Shared settings: the API origin, overridable for testing."""

    base_url: str = _api.BASE_URL


class SearchInput(BaseModel):
    city: str = Field(description='City slug, lowercase, e.g. "berlin", "madrid", "london". Use coworkingview_find_place to resolve a name.')
    workspace_type: WorkspaceType | None = Field(default=None, description="Only spaces that sell this kind of workspace.")
    district: str | None = Field(default=None, description='District slug within the city, e.g. "mitte".')
    min_capacity: int | None = Field(default=None, ge=1, description="Only spaces that fit at least this many people.")
    max_results: int = Field(default=10, ge=1, le=50, description="How many spaces to return (1-50).")
    locale: Locale = Field(default="en", description="Language of names and links.")


class CoworkingViewSearch(_Base):
    """Search coworking spaces and private offices in a city."""

    name: str = "coworkingview_search"
    description: str = (
        "Find coworking spaces, private offices, desks, day passes or meeting rooms in a city. "
        "Returns each space's name, district, operator, capacity, entry price and a link. "
        "Prices are what operators publish."
    )
    args_schema: type[BaseModel] = SearchInput

    def _run(
        self,
        city: str,
        workspace_type: str | None = None,
        district: str | None = None,
        min_capacity: int | None = None,
        max_results: int = 10,
        locale: str = "en",
        **_: Any,
    ) -> dict[str, Any]:
        body = _api.get(
            "/v1/properties",
            {
                "locale": locale,
                "city": _api.slug(city, "city"),
                "zone": _api.slug(district, "district") if district else None,
                "pricingOptionType": workspace_type,
                "minCapacity": min_capacity,
                "pageSize": max(1, min(50, int(max_results))),
            },
            self.base_url,
        )
        spaces = []
        for space in body.get("data") or []:
            price = _api.money(space.get("fromPrice"))
            spaces.append(
                {
                    "slug": space.get("slug"),
                    "name": (space.get("title") or "").strip(),
                    "district": (space.get("zone") or {}).get("name"),
                    "operator": (space.get("operator") or {}).get("name"),
                    "capacity": space.get("capacity"),
                    "from_price": f"{price}{_api.per(space.get('fromBillingPeriod'))}" if price else "on request",
                    "vs_city_median": (space.get("marketPosition") or {}).get("verdict"),
                    "url": _api.space_url(space["slug"], locale),
                }
            )
        total = ((body.get("meta") or {}).get("pagination") or {}).get("total")
        return {"city": city, "total_matching": total, "spaces": spaces}


class SpaceInput(BaseModel):
    slug: str = Field(description="The space's slug, as returned by coworkingview_search.")
    locale: Locale = Field(default="en", description="Language of the description and link.")


class CoworkingViewSpace(_Base):
    """One coworking space with every pricing option."""

    name: str = "coworkingview_space"
    description: str = (
        "Get one coworking space by slug: address, capacity, amenities, every published price "
        "(private offices, desks, day passes, meeting rooms) and a link to its page."
    )
    args_schema: type[BaseModel] = SpaceInput

    def _run(self, slug: str, locale: str = "en", **_: Any) -> dict[str, Any]:
        body = _api.get(f"/v1/properties/{_api.slug(slug, 'slug')}", {"locale": locale}, self.base_url)
        space = body.get("data") or {}
        options = []
        for option in space.get("pricingOptions") or []:
            price = _api.money(option.get("price"))
            options.append(
                {
                    "type": option.get("optionType"),
                    "name": option.get("title"),
                    "price": f"{price}{_api.per(option.get('billingPeriod'))}" if price else "on request",
                    "people": [option.get("minCapacity"), option.get("maxCapacity")],
                }
            )
        return {
            "name": (space.get("title") or "").strip(),
            "address": space.get("address"),
            "district": (space.get("zone") or {}).get("name"),
            "city": ((space.get("city") or {}).get("name") or "").strip() or None,
            "operator": (space.get("operator") or {}).get("name"),
            "capacity": space.get("capacity"),
            "amenities": space.get("amenities") or [],
            "pricing_options": options,
            "url": space.get("webUrl"),
        }


class RatesInput(BaseModel):
    city: str = Field(description='City slug, e.g. "madrid".')
    currency: str | None = Field(default=None, description='ISO 4217 code to convert to, e.g. "USD". Default: the city\'s currency.')
    locale: Locale = Field(default="en", description="Language of names.")


class CoworkingViewMarketRates(_Base):
    """What flexible workspace costs in a city."""

    name: str = "coworkingview_market_rates"
    description: str = (
        "Get the median monthly price of a private office, fixed desk and flex desk in a city, "
        "plus day pass and meeting room medians, each with how many spaces it comes from "
        "(CoworkingView Price Index, CC BY 4.0)."
    )
    args_schema: type[BaseModel] = RatesInput

    def _run(self, city: str, currency: str | None = None, locale: str = "en", **_: Any) -> dict[str, Any]:
        code = (currency or "").strip().upper() or None
        if code and (len(code) != 3 or not code.isalpha()):
            raise ValueError(f'currency "{currency}" is not an ISO 4217 code')
        body = _api.get(
            "/v1/market/rates",
            {"locale": locale, "city": _api.slug(city, "city"), "currency": code},
            self.base_url,
        )
        data = body.get("data") or {}
        cities = data.get("cities") or []
        if not cities:
            return {"city": city, "published": False, "note": "Too few published prices in this city for a fair median."}
        rates = cities[0]
        monthly = {
            figure["optionType"]: {"median_per_month": _api.money(figure.get("median")), "spaces": figure.get("propertyCount")}
            for figure in rates.get("figures") or []
            if figure.get("optionType") and figure.get("median")
        }
        extra = {}
        for key, name, unit in (("dayPass", "day_pass", "median_per_day"), ("meetingRoom", "meeting_room", "median_per_hour")):
            stat = rates.get(key)
            if stat:
                extra[name] = {unit: _api.money(stat.get("median")), "sample_size": stat.get("sampleSize")}
        return {
            "city": ((rates.get("city") or {}).get("name") or city).strip(),
            "currency": rates.get("currency"),
            "monthly": monthly,
            **extra,
            "as_of": data.get("asOf"),
            "source": "CoworkingView Price Index (CC BY 4.0), https://coworkingview.com/en/tools/price-index",
        }


class FindPlaceInput(BaseModel):
    query: str = Field(min_length=1, max_length=100, description='A city, district, brand or space name, e.g. "Kreuzberg" or "WeWork".')
    locale: Locale = Field(default="en", description="Language of the labels.")


class CoworkingViewFindPlace(_Base):
    """Resolve a free-text place or brand to the slug the other tools take."""

    name: str = "coworkingview_find_place"
    description: str = (
        "Turn a city, district, coworking brand or space name into its CoworkingView slug and kind "
        "(country, city, zone, operator or property). Use it before the other tools when unsure of a slug."
    )
    args_schema: type[BaseModel] = FindPlaceInput

    def _run(self, query: str, locale: str = "en", **_: Any) -> dict[str, Any]:
        body = _api.get("/v1/search/suggest", {"locale": locale, "q": query.strip(), "limit": 8}, self.base_url)
        return {
            "matches": [
                {
                    "kind": hit.get("kind"),
                    "slug": hit.get("slug"),
                    "label": hit.get("label"),
                    "detail": hit.get("sublabel"),
                    "spaces": hit.get("propertyCount"),
                }
                for hit in body.get("data") or []
            ]
        }


class CoworkingViewToolkit(BaseToolkit):
    """All CoworkingView tools: search, one space, market rates and place lookup."""

    base_url: str = _api.BASE_URL

    def get_tools(self) -> list[BaseTool]:
        return [
            CoworkingViewFindPlace(base_url=self.base_url),
            CoworkingViewSearch(base_url=self.base_url),
            CoworkingViewSpace(base_url=self.base_url),
            CoworkingViewMarketRates(base_url=self.base_url),
        ]

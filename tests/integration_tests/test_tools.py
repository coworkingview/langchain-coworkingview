"""Integration tests against the real API. Opt-in: COWORKINGVIEW_LIVE_TESTS=1 pytest tests/integration_tests.

They make one request per tool (plus LangChain's standard invoke checks); the API
runs on a small server, so do not loop them.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from langchain_tests.integration_tests import ToolsIntegrationTests

from langchain_coworkingview import CoworkingViewMarketRates, CoworkingViewSearch

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("COWORKINGVIEW_LIVE_TESTS") != "1", reason="live tests are opt-in"),
]


class TestSearchIntegration(ToolsIntegrationTests):
    @property
    def tool_constructor(self) -> type[CoworkingViewSearch]:
        return CoworkingViewSearch

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"city": "berlin", "workspace_type": "private_office", "max_results": 2}


class TestMarketRatesIntegration(ToolsIntegrationTests):
    @property
    def tool_constructor(self) -> type[CoworkingViewMarketRates]:
        return CoworkingViewMarketRates

    @property
    def tool_invoke_params_example(self) -> dict[str, Any]:
        return {"city": "madrid"}

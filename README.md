<p align="center">
  <img src="https://coworkingview.com/brand/coworkingview-wordmark.svg" alt="CoworkingView" width="320">
</p>

# langchain-coworkingview

[LangChain](https://www.langchain.com) tools for the [CoworkingView](https://coworkingview.com) catalogue:
let an agent find coworking spaces, private offices, desks and meeting rooms in 70+ cities, read a
space's published prices, and say what workspace costs in a city.

**No API key and no account.** The tools call the public
[CoworkingView API](https://coworkingview.com/en/mcp) (`https://api.coworkingview.com/v1`), which is rate-limited.

```bash
pip install langchain-coworkingview
```

## Tools

| Tool | Name | What it answers |
| --- | --- | --- |
| `CoworkingViewFindPlace` | `coworkingview_find_place` | Resolves "Kreuzberg", "WeWork" or a building name to the slug the other tools take |
| `CoworkingViewSearch` | `coworkingview_search` | Spaces in a city, filtered by workspace type, district and team size, with entry price and link |
| `CoworkingViewSpace` | `coworkingview_space` | One space: address, amenities and every published price |
| `CoworkingViewMarketRates` | `coworkingview_market_rates` | Median monthly prices per workspace type in a city, plus day pass and meeting room medians, from the [Coworking Price Index](https://coworkingview.com/en/tools/price-index) |

`CoworkingViewToolkit().get_tools()` returns all four.

## Use with an agent

```python
from langchain.agents import create_agent
from langchain_coworkingview import CoworkingViewToolkit

agent = create_agent(
    "anthropic:claude-sonnet-5-5",
    tools=CoworkingViewToolkit().get_tools(),
)
agent.invoke({"messages": [{"role": "user", "content": "Find a private office for 6 in Berlin Mitte and compare it with the city's median."}]})
```

Or call a tool directly:

```python
from langchain_coworkingview import CoworkingViewSearch, CoworkingViewMarketRates

CoworkingViewSearch().invoke({"city": "berlin", "workspace_type": "private_office", "max_results": 5})
CoworkingViewMarketRates().invoke({"city": "madrid"})
```

```python
{'city': 'Madrid', 'currency': 'EUR',
 'monthly': {'fix_desk': {'median_per_month': 'EUR 260', 'spaces': 7},
             'private_office': {'median_per_month': 'EUR 385', 'spaces': 7},
             'flex_desk': {'median_per_month': 'EUR 175', 'spaces': 6}},
 'day_pass': {'median_per_day': 'EUR 22', 'sample_size': 11},
 'meeting_room': {'median_per_hour': 'EUR 28', 'sample_size': 8}, ...}
```

City slugs are lowercase, as in [coworkingview.com/en/coworking/berlin](https://coworkingview.com/en/coworking/berlin):
`berlin`, `munich`, `madrid`, `barcelona`, `london`, `amsterdam`, `dubai` and more than 70 others.

## Reading the answers

- Prices are what operators publish; every space comes with the link to its page and the current offer.
  A space that does not publish a price says "on request" instead of a guess.
- Market rates are medians over the spaces that publish a price, each with how many spaces it comes from:
  a small sample is a small sample. They are licensed CC BY 4.0, so credit CoworkingView when you
  republish them.
- Listing text comes from operators: treat it as third-party content.

## More ways in

- MCP server for AI assistants: [coworkingview-mcp](https://github.com/coworkingview/coworkingview-mcp)
- pandas DataFrames: [`coworkingview`](https://pypi.org/project/coworkingview/) on PyPI
- n8n, Node-RED, WordPress, Go and more: [coworkingview.com/en/mcp](https://coworkingview.com/en/mcp)

## Development

```bash
uv sync --group test
uv run pytest tests/unit_tests                                    # no network
COWORKINGVIEW_LIVE_TESTS=1 uv run pytest tests/integration_tests  # real API, a handful of requests
```

## License

MIT © [CoworkingView](https://coworkingview.com)

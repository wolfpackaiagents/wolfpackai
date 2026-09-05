"""02 - Toolkit grouping: register several related tools under one name.

A `Toolkit` is a named registry of functions. Subclass it and register methods
(or plain callables) in `__init__`; then pass the whole toolk it to the Agent in
`tools=[...]`. This keeps related capabilities together and makes it trivial to
reuse a group of tools.

Here `DataTools` exposes two simulated market-data functions. The agent must call
both of them to answer the question.

Run:
    uv run python examples/02_tools/02_toolkit_example.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfpack import Agent, Toolkit, get_model_from_env


class DataTools(Toolkit):
    """Grouped tooling for market data."""

    def __init__(self) -> None:
        super().__init__(name="data_tools")
        self.register(self.get_stock_price, description="Returns the current price of a stock ticker.")
        self.register(self.get_company_news, description="Returns the latest news headlines for a company.")

    @staticmethod
    def get_stock_price(ticker: str) -> str:
        """Returns the current mock price for a stock ticker.

        Args:
            ticker: the stock ticker symbol, e.g. AAPL.
        """
        prices = {"AAPL": 213.5, "GOOG": 174.9, "MSFT": 412.3, "TSLA": 247.8}
        if ticker.upper() in prices:
            return f"{ticker.upper()} is trading at ${prices[ticker.upper()]}"
        return f"No data for {ticker}"

    @staticmethod
    def get_company_news(ticker: str) -> str:
        """Returns the latest mock news headlines for a company.

        Args:
            ticker: the stock ticker symbol of the company, e.g. AAPL.
        """
        news = {
            "AAPL": "Apple launches a new MacBook lineup",
            "GOOGL": "Google announces a faster search model",
            "MSFT": "Microsoft expands its cloud division",
        }
        return f"{ticker.upper()}: {news.get(ticker.upper(), 'no recent headlines')}"


def main() -> None:
    data_tools = DataTools()
    print("Toolkit name:", data_tools.name)
    print("Registered tools:", list(data_tools.functions.keys()), "\n")

    try:
        model = get_model_from_env()
    except Exception:
        raise SystemExit(
            "No API key found (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, "
            "or OLLAMA_BASE_URL). Set one and re-run."
        )

    agent = Agent(
        name="MarketAnalyst",
        model=model,
        role="A financial data analyst",
        goal="Gather market data with the available toolkit and answer questions.",
        backstory="A wolfpack agent specialised in market analysis, equipped with stock and news tools.",
        tools=[data_tools],
    )

    question = "What is Apple's stock price and what is the latest Apple news?"
    print(f"Prompt: {question}\n")

    output = agent.run(question)

    print("=== FINAL ANSWER ===")
    print(output.content)
    print()
    print("=== TOOL CALLS EXECUTED ===")
    for call in output.tool_calls:
        print(f"  {call['name']}({call['arguments']})")
    print()
    print("=== USAGE ===", output.usage)


if __name__ == "__main__":
    main()
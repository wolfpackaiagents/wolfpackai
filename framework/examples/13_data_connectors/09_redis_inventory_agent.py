"""Use Redis inventory values as a bounded Agent tool."""

import os

import redis

from wolfpack import Agent, DataAccessPolicy, RedisToolkit, get_model_from_env


client = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
inventory = RedisToolkit(
    client,
    policy=DataAccessPolicy(source_id="warehouse-inventory", allowed_key_prefixes={"inventory:"}),
)
print("APPROVED KEY DATA:", inventory.get("inventory:sku-42"))
agent = Agent(
    name="inventory-assistant",
    model=get_model_from_env(),
    system="For SKU 42, call get with exactly 'inventory:sku-42' before answering.",
    tools=[inventory],
    tool_allowlist=["get"],
)
result = agent.run("How many units are available for SKU 42?")
print("AGENT RESULT:", result.content)
print("Tools used:", [call["name"] for call in result.tool_calls])

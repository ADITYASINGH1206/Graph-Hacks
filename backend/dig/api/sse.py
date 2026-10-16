"""Server-Sent Events (SSE) formatter for text/event-stream responses."""

import json
from collections.abc import AsyncGenerator

from dig.agent.agent import AgentEvent


async def format_sse_stream(
    generator: AsyncGenerator[AgentEvent, None],
) -> AsyncGenerator[str, None]:
    """Format AgentEvent objects into standard SSE data frames."""
    async for item in generator:
        data_json = json.dumps(item.data, ensure_ascii=False)
        yield f"event: {item.event}\ndata: {data_json}\n\n"

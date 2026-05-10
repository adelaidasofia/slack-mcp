"""Tool modules. Each exports register(mcp) which wires its tools to the FastMCP instance."""

from . import (
    channels,
    edits,
    marks,
    messages,
    reactions,
    send,
    threads,
    users,
    workspaces,
)


def register_all(mcp) -> None:
    """Wire every tool module's tools to the given FastMCP server instance."""
    workspaces.register(mcp)
    channels.register(mcp)
    threads.register(mcp)
    users.register(mcp)
    messages.register(mcp)
    send.register(mcp)
    reactions.register(mcp)
    marks.register(mcp)
    edits.register(mcp)

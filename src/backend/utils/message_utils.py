"""Utility functions for message formatting and processing."""

from typing import Any, List
import re
from langchain_core.messages import HumanMessage

# Number of recent messages to keep for context
RECENT_MESSAGES_COUNT = 3


def get_recent_messages(messages: List[Any], exclude_last: bool = False) -> List[Any]:
    """Get the most recent messages for context.

    Args:
        messages: List of messages
        exclude_last: Whether to exclude the last message (useful for context)

    Returns:
        List of recent messages, optionally excluding the last one
    """
    if not messages:
        return []

    recent = (
        messages[-RECENT_MESSAGES_COUNT:]
        if len(messages) > RECENT_MESSAGES_COUNT
        else messages
    )
    return recent[:-1] if exclude_last else recent


def format_conversation_history(messages: List[Any]) -> str:
    """Format conversation history for context.

    Args:
        messages: List of LangChain messages to format

    Returns:
        Formatted conversation history as string with USER/ASSISTANT prefixes
    """
    formatted_messages = []
    for msg in messages:
        prefix = "USER" if isinstance(msg, HumanMessage) else "ASSISTANT"
        clean_content = re.sub(r"\n+", "\n", msg.content.strip())
        formatted_messages.append(f"{prefix}: {clean_content}")
    return "\n".join(formatted_messages)

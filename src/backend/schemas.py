"""Pydantic models for the chat application."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Model for chat messages."""

    role: Literal["user", "assistant", "tool_message"]
    content: str


class ConversationResponse(BaseModel):
    """Response model for conversation data."""

    messages: list[Message] = Field(default_factory=list)


class ConversationInfo(BaseModel):
    """Schema for individual conversation information."""

    thread_id: str = Field(description="Unique identifier for the conversation thread")
    created_at: datetime = Field(
        description="Timestamp when the conversation was created"
    )


class ConversationListResponse(BaseModel):
    """Schema for the list of conversations response."""

    conversations: list[ConversationInfo] = Field(
        default_factory=list, description="List of available conversations"
    )


class MessageRequest(BaseModel):
    """Request model for chat messages."""

    message: str = Field(..., description="The message content to send")


class DeleteResponse(BaseModel):
    """Response model for delete operations."""

    success: bool
    message: str


class APIResponse(BaseModel):
    """Generic API response model."""

    status: str
    message: str


class RunIdResponse(BaseModel):
    """Response model for run ID."""

    run_id: str = Field(..., description="The unique identifier of the run")


class NewThreadResponse(BaseModel):
    """Response model for new thread creation."""

    thread_id: str = Field(..., description="The unique identifier of the new thread")

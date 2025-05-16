"""API routes for the LangGraph chat agent.

This module contains the route handlers for the chat interface, handling session management
and message processing using LangGraph.
"""

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse
from langgraph_sdk import get_client

from src.backend.exceptions import ConflictError, InternalServerError, NotFoundError
from src.backend.utils.document_ingestion import ingest_file
from src.backend.schemas import (
    APIResponse,
    ConversationListResponse,
    ConversationResponse,
    DeleteResponse,
    Message,
    MessageRequest,
    NewThreadResponse,
    RunIdResponse,
)

# Initialize the router
router = APIRouter()

# Initialize the LangGraph client
langgraph_client = get_client()


@router.get("/", response_model=APIResponse)
async def root() -> APIResponse:
    """Get API status.

    Returns:
        APIResponse: Status message indicating the API is running

    Example:
        ```
        GET /
        Response: {"status": "success", "message": "LangGraph Chat API is running"}
        ```
    """
    return APIResponse(status="success", message="LangGraph Chat API is running")


@router.post("/upload-document/", response_model=Dict[str, Any])
async def upload_document_route(file: UploadFile = File(...)):
    """
    Upload a document for ingestion into the vector store.
    Supports .txt, .md, .pdf (PDF requires additional parsing logic not yet implemented).
    """
    temp_dir = None
    try:
        # Create a temporary directory to store the uploaded file asynchronously
        temp_dir = await asyncio.to_thread(tempfile.mkdtemp)
        temp_file_path = os.path.join(temp_dir, file.filename)

        # Save the uploaded file to the temporary path asynchronously
        with open(
            temp_file_path, "wb"
        ) as buffer:  # open() is sync, but usually acceptable for temp files
            await asyncio.to_thread(shutil.copyfileobj, file.file, buffer)

        # Ingest the file
        # Note: ingest_file expects .txt or .md. PDF/DOCX would need text extraction first.
        # For now, we assume the file content is directly readable as text.
        # If file.content_type is 'application/pdf', we'd need PyPDF2 or similar.
        # If 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', python-docx.

        # For simplicity, this example directly calls ingest_file.
        # Production systems should handle different file types and extract text accordingly.
        if not file.filename.endswith((".txt", ".md")):
            # Basic check, can be expanded
            # For PDF/DOCX, you would extract text here before passing to ingest_document
            # For now, we'll raise an error for unsupported types if not txt/md
            # but ingest_file itself might handle it or error out.
            # Let's assume ingest_file can handle the path for now.
            pass

        result = await ingest_file(temp_file_path)

        if result.get("status") == "error":
            # Propagate error more clearly if needed
            if "File not found" in result.get("error", ""):
                raise NotFoundError(
                    detail=result["error"], code="FILE_NOT_FOUND_INGESTION"
                )
            raise InternalServerError(
                detail=result.get("error", "Failed to ingest document"),
                code="INGESTION_ERROR",
            )

        return result

    except Exception as e:
        # Log the exception for debugging
        logging.error(f"Error during file upload and ingestion: {e}", exc_info=True)
        raise InternalServerError(
            detail=f"An unexpected error occurred during file upload: {str(e)}",
            code="UPLOAD_PROCESSING_ERROR",
        )
    finally:
        # Clean up the temporary directory asynchronously
        if temp_dir and os.path.exists(temp_dir):
            await asyncio.to_thread(shutil.rmtree, temp_dir)
        if hasattr(file, "file") and hasattr(file.file, "close"):
            # file.file.close() can also be blocking, though often quick.
            # For strict non-blocking, it could also be wrapped if it becomes an issue.
            # However, FastAPI typically handles closing the UploadFile stream.
            pass  # FastAPI handles closing file.file


@router.get("/new-thread", response_model=NewThreadResponse)
async def new_thread() -> NewThreadResponse:
    """Create a new conversation thread.

    Returns:
        NewThreadResponse: The ID of the newly created thread

    Example:
        ```
        GET /new-thread
        Response: {"thread_id": "123e4567-e89b-12d3-a456-426614174000"}
        ```
    """
    thread_id = str(uuid.uuid4())
    return NewThreadResponse(thread_id=thread_id)


@router.get("/conversations-list", response_model=ConversationListResponse)
async def get_conversations() -> ConversationListResponse:
    """Get all available conversations.

    Returns:
        List of conversations with their creation timestamps and thread IDs

    Example:
        ```
        GET /conversations-list
        Response: [
            {
                "thread_id": "123e4567-e89b-12d3-a456-426614174000",
                "created_at": "2024-03-13T14:30:00"
            }
        ]
        ```
    """
    try:
        # Search for all threads (with a high limit to get all)
        threads = await langgraph_client.threads.search(limit=1000)

        # Extract thread info and sort by creation time
        conversations = []
        for thread in threads:
            thread_id = thread["thread_id"]
            metadata = thread.get("metadata", {})
            created_at = metadata.get("created_at")

            if created_at:
                conversations.append({"thread_id": thread_id, "created_at": created_at})

        # Sort conversations by creation time, newest first
        conversations.sort(key=lambda x: x["created_at"], reverse=True)
        return ConversationListResponse(conversations=conversations)

    except Exception as e:
        raise ConflictError(
            detail=f"Failed to fetch conversations: {str(e)}",
            code="CONVERSATIONS_ERROR",
        )


@router.get("/conversations/{thread_id}", response_model=ConversationResponse)
async def conversation(thread_id: str) -> ConversationResponse:
    """Get a specific conversation and its messages.

    Args:
        thread_id: The unique identifier of the thread

    Returns:
        ConversationResponse: The conversation data and messages

    Raises:
        NotFoundError: If the thread doesn't exist
    """
    try:
        # Create thread if it doesn't exist
        await langgraph_client.threads.create(
            thread_id=thread_id,
            if_exists="do_nothing",
            metadata={"created_at": str(datetime.now())},
        )

        # Get thread state
        state = await langgraph_client.threads.get_state(thread_id)
        values = state["values"]

        # Extract messages
        if isinstance(values, list) and values:
            raw_messages = values[-1].get("messages", [])
        else:
            raw_messages = values.get("messages", [])

        # Convert messages
        messages: list[Message] = []
        tool_call_buffer = {}  # Buffer to store tool calls until we find their results

        for msg in raw_messages:
            msg_type = msg.get("type", "")
            content = msg.get("content", "")

            # Handle content lists
            if isinstance(content, list):
                content = "".join(
                    c["text"] for c in content if isinstance(c, dict) and c.get("text")
                )

            # Map message types
            if msg_type == "human":
                messages.append(Message(role="user", content=content))
            elif msg_type in ["ai", "assistant"] and content:
                messages.append(Message(role="assistant", content=content))
            # Handle tool calls
            elif msg_type == "ai" and msg.get("tool_calls"):
                for tool_call in msg.get("tool_calls", []):
                    tool_name = tool_call.get("name", "unknown_tool")
                    tool_args = tool_call.get("args", {})
                    # Store in buffer for later combination with result
                    tool_call_buffer[tool_name] = {
                        "name": tool_name,
                        "arguments": tool_args,
                    }
            # Handle tool results
            elif msg_type in ["tool", "function"]:
                tool_name = msg.get("name", "unknown_tool")
                # Check if we have a matching call in the buffer
                if tool_name in tool_call_buffer:
                    # Combine tool call and result
                    messages.append(
                        Message(
                            role="tool_message",
                            content=json.dumps(
                                {
                                    "type": "tool_combined",
                                    "name": tool_name,
                                    "call": {
                                        "name": tool_call_buffer[tool_name]["name"],
                                        "arguments": tool_call_buffer[tool_name][
                                            "arguments"
                                        ],
                                    },
                                    "result": content,
                                }
                            ),
                        )
                    )
                    # Remove from buffer
                    del tool_call_buffer[tool_name]
                else:
                    # If no matching call, create standalone result
                    messages.append(
                        Message(
                            role="tool_message",
                            content=json.dumps(
                                {
                                    "type": "tool_result",
                                    "name": tool_name,
                                    "result": content,
                                }
                            ),
                        )
                    )

        # Add any remaining tool calls that didn't get results
        for tool_name, call_data in tool_call_buffer.items():
            messages.append(
                Message(
                    role="tool_message",
                    content=json.dumps(
                        {
                            "type": "tool_call",
                            "name": tool_name,
                            "arguments": call_data["arguments"],
                        }
                    ),
                )
            )

        return ConversationResponse(messages=messages)

    except Exception as e:
        raise NotFoundError(
            detail=f"Error accessing thread {thread_id}", code="THREAD_ERROR"
        ) from e


@router.post("/conversations/{thread_id}/send-message", response_model=RunIdResponse)
async def send_message(thread_id: str, request: MessageRequest) -> dict[str, Any]:
    """Send a message in a conversation.

    Args:
        thread_id: The unique identifier of the thread
        request: The message request containing the message content

    Returns:
        RunIdResponse: Contains run_id for subsequent streaming
    """
    try:
        # Create a new run with the message
        run = await langgraph_client.runs.create(
            thread_id=thread_id,
            assistant_id="agent",
            input={"messages": [{"type": "human", "content": request.message}]},
            stream_mode="messages-tuple",
        )
        return {"run_id": run["run_id"]}
    except Exception as e:
        raise NotFoundError(
            detail=f"Thread {thread_id} not found or error creating run",
            code="THREAD_NOT_FOUND",
        ) from e


@router.get("/conversations/{thread_id}/stream-message")
async def stream_message(thread_id: str, run_id: str) -> StreamingResponse:
    """Stream assistant responses via SSE.

    Args:
        thread_id: The unique identifier of the thread
        run_id: The run ID to stream responses from

    Returns:
        StreamingResponse: Server-sent events stream of assistant responses
    """
    return StreamingResponse(
        message_generator(thread_id, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
            "Transfer-Encoding": "chunked",
        },
    )


@router.delete("/conversations/{thread_id}", response_model=DeleteResponse)
async def delete_thread(thread_id: str) -> DeleteResponse:
    """Delete a specific conversation thread.

    Args:
        thread_id: The unique identifier of the thread to delete

    Returns:
        DeleteResponse: Success status and message

    Raises:
        NotFoundError: If the thread doesn't exist

    Example:
        ```
        DELETE /conversations/123e4567-e89b-12d3-a456-426614174000
        Response: {"success": true, "message": "Thread deleted successfully"}
        ```
    """
    try:
        # Check if thread exists
        await langgraph_client.threads.get_state(thread_id)

        # Delete the thread
        await langgraph_client.threads.delete(thread_id)

        return DeleteResponse(
            success=True, message=f"Thread {thread_id} deleted successfully"
        )
    except Exception as e:
        raise NotFoundError(
            detail=f"Thread {thread_id} not found", code="THREAD_NOT_FOUND"
        ) from e


@router.delete("/conversations", response_model=DeleteResponse)
async def delete_all_threads() -> DeleteResponse:
    """Delete all conversation threads.

    Returns:
        DeleteResponse: Success status and message

    Example:
        ```
        DELETE /conversations
        Response: {"success": true, "message": "Successfully deleted N threads"}
        ```
    """
    try:
        # Search for all threads (with a high limit to get all)
        threads = await langgraph_client.threads.search(limit=1000)

        # Delete each thread
        deleted_count = 0
        for thread in threads:
            try:
                await langgraph_client.threads.delete(thread["thread_id"])
                deleted_count += 1
            except Exception:
                continue

        return DeleteResponse(
            success=True, message=f"Successfully deleted {deleted_count} threads"
        )
    except Exception as e:
        raise ConflictError(
            detail=f"Failed to delete all threads: {str(e)}", code="BULK_DELETE_ERROR"
        )


# Helper function to stream assistant responses via SSE
async def message_generator(thread_id: str, run_id: str) -> AsyncGenerator[str, None]:
    """Stream assistant responses via SSE."""
    # We only care about the answer node (which is now our final node) and tool calls
    current_node = None
    tool_calls_buffer = {}

    logging.info(f"Starting to stream messages for thread {thread_id}, run {run_id}")

    async for chunk in langgraph_client.runs.join_stream(
        thread_id, run_id, stream_mode="messages-tuple"
    ):
        if chunk.event == "messages":
            for chunk_msg in chunk.data:
                if isinstance(chunk_msg, dict):
                    # Track node transitions
                    if (
                        "langgraph_node" in chunk_msg
                        and chunk_msg.get("created_by") == "system"
                    ):
                        current_node = chunk_msg.get("langgraph_node")
                        # logging.info(f"Node transition: {current_node}")

                    msg_type = chunk_msg.get("type")
                    content = chunk_msg.get("content", "")

                    # Handle tool calls
                    if (
                        "additional_kwargs" in chunk_msg
                        and "tool_calls" in chunk_msg["additional_kwargs"]
                    ):
                        tool_calls = chunk_msg["additional_kwargs"]["tool_calls"]
                        for tool_call in tool_calls:
                            if tool_call.get("function"):
                                tool_name = tool_call["function"].get("name")
                                args = tool_call["function"].get("arguments", "")

                                # Initialize buffer for new tool
                                if tool_name and tool_name not in tool_calls_buffer:
                                    tool_calls_buffer[tool_name] = {
                                        "name": tool_name,
                                        "arguments": "",
                                        "args_complete": False,
                                    }

                                # If we have args but no name, append to the last tool's arguments
                                if args and tool_calls_buffer:
                                    target_tool = (
                                        tool_name
                                        if tool_name
                                        else list(tool_calls_buffer.keys())[-1]
                                    )
                                    if not tool_calls_buffer[target_tool][
                                        "args_complete"
                                    ]:
                                        tool_calls_buffer[target_tool]["arguments"] += (
                                            args
                                        )

                                        # Check if we have complete arguments
                                        current_args = tool_calls_buffer[target_tool][
                                            "arguments"
                                        ]
                                        if current_args.strip().startswith(
                                            "{"
                                        ) and current_args.strip().endswith("}"):
                                            try:
                                                parsed_args = json.loads(current_args)
                                                tool_calls_buffer[target_tool][
                                                    "arguments"
                                                ] = parsed_args
                                                tool_calls_buffer[target_tool][
                                                    "args_complete"
                                                ] = True
                                            except json.JSONDecodeError:
                                                pass

                    # Handle tool results
                    elif msg_type in ["tool", "function"]:
                        tool_name = chunk_msg.get("name", "unknown_tool")
                        result = chunk_msg.get("content", "")

                        # Always stream tool results
                        if (
                            tool_name in tool_calls_buffer
                            and tool_calls_buffer[tool_name]["args_complete"]
                        ):
                            call_data = tool_calls_buffer[tool_name]
                            data = {
                                "role": "tool_message",
                                "content": json.dumps(
                                    {
                                        "type": "tool_combined",
                                        "name": tool_name,
                                        "call": {
                                            "name": tool_name,
                                            "arguments": call_data["arguments"],
                                        },
                                        "result": result,
                                    }
                                ),
                            }
                            yield f"event: message\ndata: {json.dumps(data)}\n\n"
                            del tool_calls_buffer[tool_name]
                        else:
                            # If no matching call or incomplete args, send just the result
                            data = {
                                "role": "tool_message",
                                "content": json.dumps(
                                    {
                                        "type": "tool_result",
                                        "name": tool_name,
                                        "result": result,
                                    }
                                ),
                            }
                            yield f"event: message\ndata: {json.dumps(data)}\n\n"

                    # Only stream content from the answer node
                    elif (
                        content
                        and content.strip()
                        and current_node == "answer"
                        and msg_type == "AIMessageChunk"
                    ):
                        # Skip marker blocks
                        if not content.startswith("[") and not any(
                            label in content
                            for label in [
                                "Confidence",
                                "Score",
                                "Reasoning",
                                "Analysis",
                                "Process",
                                "Selected",
                            ]
                        ):
                            # logging.info(f"STREAMING ANSWER: '{content}'")
                            data = {"role": "assistant", "content": content}
                            yield f"event: message\ndata: {json.dumps(data)}\n\n"

    # Send closing event
    yield "event: close\ndata:\n\n"

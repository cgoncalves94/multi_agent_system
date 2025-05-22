import pytest
from httpx import AsyncClient
from io import BytesIO
from unittest.mock import patch, MagicMock, AsyncMock, ANY # Ensure AsyncMock and ANY are imported
import json # Import json
from datetime import datetime # Import datetime
import asyncio # Required for async generator mocking

# Mark all tests in this module as asyncio tests
pytestmark = pytest.mark.asyncio

# test_read_root remains here (from previous step)
async def test_read_root(async_client: AsyncClient):
    """Test the root endpoint /api/."""
    response = await async_client.get("/api/")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "LangGraph Chat API is running"}

async def test_upload_txt_file(async_client: AsyncClient):
    """Test uploading a .txt file successfully."""
    file_content = b"This is a test text file."
    files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
    # Mock the ingest_file function to avoid actual file system operations and external dependencies
    with patch("src.backend.routes.ingest_file", new_callable=MagicMock) as mock_ingest_file:
        mock_ingest_file.return_value = {"status": "success", "message": "File ingested successfully", "doc_id": "test_doc_id"}
        response = await async_client.post("/api/upload-document/", files=files)
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "File ingested successfully", "doc_id": "test_doc_id"}
    mock_ingest_file.assert_called_once() # Verify ingest_file was called

async def test_upload_md_file(async_client: AsyncClient):
    """Test uploading a .md file successfully."""
    file_content = b"# This is a test markdown file."
    files = {"file": ("test.md", BytesIO(file_content), "text/markdown")}
    with patch("src.backend.routes.ingest_file", new_callable=MagicMock) as mock_ingest_file:
        mock_ingest_file.return_value = {"status": "success", "message": "File ingested successfully"}
        response = await async_client.post("/api/upload-document/", files=files)
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "File ingested successfully"}
    mock_ingest_file.assert_called_once()

async def test_upload_unsupported_file_type(async_client: AsyncClient):
    """Test uploading an unsupported file type (e.g., .png)."""
    file_content = b"fake png content"
    files = {"file": ("test.png", BytesIO(file_content), "image/png")}
    # No need to mock ingest_file here if the route itself or a utility function called before ingest_file
    # is expected to handle the unsupported type. However, current route implementation passes all files to ingest_file.
    # For this test, we'll mock ingest_file to simulate an error for this type if it's not caught earlier.
    # Based on the current routes.py, it seems ingest_file is called, and then its result is checked.
    # Let's assume for now that ingest_file itself might return an error or the endpoint logic handles it.
    # The current route implementation calls ingest_file for all file types and then checks its output.
    # If ingest_file is robust, it should handle this.
    # If not, the test might need adjustment based on actual behavior or planned error handling.
    # For this test, we'll assume the endpoint should ideally reject before calling ingest_file or ingest_file itself errors.
    # The provided code doesn't explicitly block .png files before calling ingest_file.
    # Let's simulate ingest_file returning an error for an unsupported type.
    with patch("src.backend.routes.ingest_file", new_callable=MagicMock) as mock_ingest_file:
        # Simulate an error from ingest_file for an unsupported type
        mock_ingest_file.return_value = {"status": "error", "error": "Unsupported file type"}
        response = await async_client.post("/api/upload-document/", files=files)

    # Expecting an InternalServerError (500) based on how errors from ingest_file are handled in routes.py
    assert response.status_code == 500 
    json_response = response.json()
    assert json_response["error"]["code"] == "INGESTION_ERROR"
    assert "Unsupported file type" in json_response["error"]["detail"]
    mock_ingest_file.assert_called_once()


async def test_upload_ingestion_error_file_not_found(async_client: AsyncClient):
    """Test error handling when ingest_file reports 'File not found'."""
    file_content = b"this file will not be found by a mocked ingest_file"
    files = {"file": ("notfound.txt", BytesIO(file_content), "text/plain")}
    with patch("src.backend.routes.ingest_file", new_callable=MagicMock) as mock_ingest_file:
        # Simulate ingest_file returning a "File not found" error
        mock_ingest_file.return_value = {"status": "error", "error": "File not found during ingestion"}
        response = await async_client.post("/api/upload-document/", files=files)
    
    assert response.status_code == 404 # Expecting NotFoundError (404)
    json_response = response.json()
    assert json_response["error"]["code"] == "FILE_NOT_FOUND_INGESTION"
    assert "File not found during ingestion" in json_response["error"]["detail"]
    mock_ingest_file.assert_called_once()

async def test_upload_ingestion_general_error(async_client: AsyncClient):
    """Test error handling when ingest_file reports a general error."""
    file_content = b"this causes a general error"
    files = {"file": ("error.txt", BytesIO(file_content), "text/plain")}
    with patch("src.backend.routes.ingest_file", new_callable=MagicMock) as mock_ingest_file:
        # Simulate ingest_file returning a general error
        mock_ingest_file.return_value = {"status": "error", "error": "Some generic ingestion failure"}
        response = await async_client.post("/api/upload-document/", files=files)

    assert response.status_code == 500 # Expecting InternalServerError (500)
    json_response = response.json()
    assert json_response["error"]["code"] == "INGESTION_ERROR"
    assert "Some generic ingestion failure" in json_response["error"]["detail"]
    mock_ingest_file.assert_called_once()

async def test_new_thread(async_client: AsyncClient):
    """Test the /api/new-thread endpoint."""
    response = await async_client.get("/api/new-thread")
    assert response.status_code == 200
    json_response = response.json()
    assert "thread_id" in json_response
    assert isinstance(json_response["thread_id"], str)
    # Optionally, you could add a UUID validation if the format is strictly UUID
    # import uuid
    # try:
    #     uuid.UUID(json_response["thread_id"])
    # except ValueError:
    #     pytest.fail("thread_id is not a valid UUID")

async def test_get_conversations_list_success(async_client: AsyncClient):
    """Test /api/conversations-list successfully retrieves conversations."""
    mock_threads_data = [
        {"thread_id": "thread_1", "metadata": {"created_at": "2024-03-15T10:00:00"}},
        {"thread_id": "thread_2", "metadata": {"created_at": "2024-03-14T12:00:00"}},
    ]
    expected_response_data = {
        "conversations": [
            {"thread_id": "thread_1", "created_at": "2024-03-15T10:00:00"},
            {"thread_id": "thread_2", "created_at": "2024-03-14T12:00:00"},
        ]
    }

    # Patch the langgraph_client.threads.search async method
    with patch("src.backend.routes.langgraph_client.threads.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_threads_data
        response = await async_client.get("/api/conversations-list")

    assert response.status_code == 200
    assert response.json() == expected_response_data
    mock_search.assert_called_once_with(limit=1000)

async def test_get_conversations_list_empty(async_client: AsyncClient):
    """Test /api/conversations-list when no conversations exist."""
    with patch("src.backend.routes.langgraph_client.threads.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [] # No threads
        response = await async_client.get("/api/conversations-list")

    assert response.status_code == 200
    assert response.json() == {"conversations": []}
    mock_search.assert_called_once_with(limit=1000)

async def test_get_conversations_list_client_error(async_client: AsyncClient):
    """Test /api/conversations-list when langgraph_client raises an error."""
    with patch("src.backend.routes.langgraph_client.threads.search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = Exception("LangGraph client error")
        response = await async_client.get("/api/conversations-list")

    assert response.status_code == 409 # ConflictError
    json_response = response.json()
    assert json_response["error"]["code"] == "CONVERSATIONS_ERROR"
    assert "Failed to fetch conversations: LangGraph client error" in json_response["error"]["detail"]
    mock_search.assert_called_once_with(limit=1000)

async def test_get_conversation_by_id_success_and_message_parsing(async_client: AsyncClient):
    """Test /api/conversations/{thread_id} successfully retrieves and parses messages."""
    thread_id = "test_thread_123"
    mock_thread_state_values = {
        "messages": [
            {"type": "human", "content": "Hello there!"},
            {"type": "ai", "content": "General Kenobi!"},
            {
                "type": "ai", 
                "content": "", 
                "tool_calls": [{"name": "search_tool", "args": {"query": "Star Wars"}}],
            },
            {"type": "tool", "name": "search_tool", "content": "Result for Star Wars"},
            {
                "type": "ai",
                "content": "",
                "tool_calls": [{"name": "another_tool", "args": {"param": "value"}}],
            }
        ]
    }
    expected_messages = [
        {"role": "user", "content": "Hello there!"},
        {"role": "assistant", "content": "General Kenobi!"},
        {
            "role": "tool_message",
            "content": json.dumps({ 
                "type": "tool_combined",
                "name": "search_tool",
                "call": {"name": "search_tool", "arguments": {"query": "Star Wars"}},
                "result": "Result for Star Wars",
            }),
        },
        {
            "role": "tool_message",
            "content": json.dumps({
                "type": "tool_call",
                "name": "another_tool",
                "arguments": {"param": "value"},
            })
        }
    ]

    with patch("src.backend.routes.langgraph_client.threads.create", new_callable=AsyncMock) as mock_create, \
         patch("src.backend.routes.langgraph_client.threads.get_state", new_callable=AsyncMock) as mock_get_state:
        
        mock_create.return_value = None 
        mock_get_state.return_value = {"values": mock_thread_state_values}

        response = await async_client.get(f"/api/conversations/{thread_id}")

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["messages"] == expected_messages

    # Check the call to 'create'
    # The metadata created_at will be a string representation of datetime.now()
    # We can use unittest.mock.ANY for the metadata argument if exact datetime matching is too fragile.
    # Or, more precisely, check that 'created_at' is a key and its value is a string.
    mock_create.assert_called_once_with(
        thread_id=thread_id, 
        if_exists="do_nothing", 
        metadata=ANY 
    )
    # Further check on metadata if needed:
    assert "created_at" in mock_create.call_args[1]['metadata']
    assert isinstance(mock_create.call_args[1]['metadata']['created_at'], str)
    
    mock_get_state.assert_called_once_with(thread_id)

async def test_get_conversation_by_id_empty_messages(async_client: AsyncClient):
    """Test /api/conversations/{thread_id} when a thread has no messages."""
    thread_id = "empty_thread_456"
    mock_thread_state_values = {"messages": []} # No messages

    with patch("src.backend.routes.langgraph_client.threads.create", new_callable=AsyncMock) as mock_create, \
         patch("src.backend.routes.langgraph_client.threads.get_state", new_callable=AsyncMock) as mock_get_state:
        
        mock_create.return_value = None
        mock_get_state.return_value = {"values": mock_thread_state_values}

        response = await async_client.get(f"/api/conversations/{thread_id}")

    assert response.status_code == 200
    assert response.json() == {"messages": []}
    mock_create.assert_called_once_with(
        thread_id=thread_id,
        if_exists="do_nothing",
        metadata=ANY
    )
    assert "created_at" in mock_create.call_args[1]['metadata']
    mock_get_state.assert_called_once_with(thread_id)

async def test_delete_all_threads_success(async_client: AsyncClient):
    """Test DELETE /api/conversations successfully deletes all threads."""
    mock_threads_found = [
        {"thread_id": "thread_to_delete_1"},
        {"thread_id": "thread_to_delete_2"},
        {"thread_id": "thread_to_delete_3"},
    ]
    
    with patch("src.backend.routes.langgraph_client.threads.search", new_callable=AsyncMock) as mock_search,          patch("src.backend.routes.langgraph_client.threads.delete", new_callable=AsyncMock) as mock_delete:
        
        mock_search.return_value = mock_threads_found
        # mock_delete.return_value = None # Default AsyncMock behavior is fine for successful deletion

        response = await async_client.delete("/api/conversations")

    assert response.status_code == 200
    json_response = response.json()
    assert json_response == {"success": True, "message": f"Successfully deleted {len(mock_threads_found)} threads"}
    
    mock_search.assert_called_once_with(limit=1000)
    assert mock_delete.call_count == len(mock_threads_found)
    for thread in mock_threads_found:
        mock_delete.assert_any_call(thread["thread_id"])

async def test_delete_all_threads_no_threads_exist(async_client: AsyncClient):
    """Test DELETE /api/conversations when no threads exist."""
    with patch("src.backend.routes.langgraph_client.threads.search", new_callable=AsyncMock) as mock_search,          patch("src.backend.routes.langgraph_client.threads.delete", new_callable=AsyncMock) as mock_delete:
        
        mock_search.return_value = [] # No threads found
        
        response = await async_client.delete("/api/conversations")

    assert response.status_code == 200
    json_response = response.json()
    assert json_response == {"success": True, "message": "Successfully deleted 0 threads"}
    
    mock_search.assert_called_once_with(limit=1000)
    mock_delete.assert_not_called()

async def test_delete_all_threads_search_fails(async_client: AsyncClient):
    """Test DELETE /api/conversations when langgraph_client.threads.search fails."""
    with patch("src.backend.routes.langgraph_client.threads.search", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = Exception("LangGraph client error during search")
        
        response = await async_client.delete("/api/conversations")

    assert response.status_code == 409 # ConflictError from the route's exception handling
    json_response = response.json()
    assert json_response["error"]["code"] == "BULK_DELETE_ERROR"
    assert "Failed to delete all threads: LangGraph client error during search" in json_response["error"]["detail"]
    
    mock_search.assert_called_once_with(limit=1000)

async def test_delete_all_threads_one_delete_fails(async_client: AsyncClient):
    """Test DELETE /api/conversations when one of the delete calls fails (should still continue)."""
    mock_threads_found = [
        {"thread_id": "thread_ok_1"},
        {"thread_id": "thread_fail_2"}, # This one will fail
        {"thread_id": "thread_ok_3"},
    ]
    
    # Expected successful deletions = 2
    expected_deleted_count = 2 

    with patch("src.backend.routes.langgraph_client.threads.search", new_callable=AsyncMock) as mock_search,          patch("src.backend.routes.langgraph_client.threads.delete", new_callable=AsyncMock) as mock_delete:
        
        mock_search.return_value = mock_threads_found
        
        # Configure mock_delete to fail for a specific thread_id
        async def delete_side_effect(thread_id):
            if thread_id == "thread_fail_2":
                raise Exception("Simulated delete failure for thread_fail_2")
            return None # Successful deletion for others
        mock_delete.side_effect = delete_side_effect
        
        response = await async_client.delete("/api/conversations")

    assert response.status_code == 200 # Endpoint itself succeeds even if some individual deletes fail
    json_response = response.json()
    # The message reflects the count of *successful* deletions based on current routes.py logic
    assert json_response == {"success": True, "message": f"Successfully deleted {expected_deleted_count} threads"}
    
    mock_search.assert_called_once_with(limit=1000)
    assert mock_delete.call_count == len(mock_threads_found) # Delete is attempted for all
    mock_delete.assert_any_call("thread_ok_1")
    mock_delete.assert_any_call("thread_fail_2") # Attempted
    mock_delete.assert_any_call("thread_ok_3")

async def test_delete_thread_success(async_client: AsyncClient):
    """Test DELETE /api/conversations/{thread_id} successfully deletes a thread."""
    thread_id = "thread_to_delete_123"

    with patch("src.backend.routes.langgraph_client.threads.get_state", new_callable=AsyncMock) as mock_get_state, \
         patch("src.backend.routes.langgraph_client.threads.delete", new_callable=AsyncMock) as mock_delete:
        
        mock_get_state.return_value = {"values": {"messages": []}} # Simulate thread exists
        mock_delete.return_value = None # Simulate successful deletion
        
        response = await async_client.delete(f"/api/conversations/{thread_id}")

    assert response.status_code == 200
    json_response = response.json()
    assert json_response == {"success": True, "message": f"Thread {thread_id} deleted successfully"}
    
    mock_get_state.assert_called_once_with(thread_id)
    mock_delete.assert_called_once_with(thread_id)

async def test_delete_thread_not_found_explicit_assert_not_called(async_client: AsyncClient):
    """Test DELETE /api/conversations/{thread_id} when thread is not found (explicitly check delete not called)."""
    thread_id = "non_existent_thread_789"

    with patch("src.backend.routes.langgraph_client.threads.get_state", new_callable=AsyncMock) as mock_get_state, \
         patch("src.backend.routes.langgraph_client.threads.delete", new_callable=AsyncMock) as mock_delete:
        
        mock_get_state.side_effect = Exception("LangGraph: Thread not found")
        
        response = await async_client.delete(f"/api/conversations/{thread_id}")

    assert response.status_code == 404
    json_response = response.json()
    assert json_response["error"]["code"] == "THREAD_NOT_FOUND"
    assert f"Thread {thread_id} not found" in json_response["error"]["detail"]
    
    mock_get_state.assert_called_once_with(thread_id)
    mock_delete.assert_not_called() # Explicitly check that delete was not called

async def test_stream_message_success_and_logic(async_client: AsyncClient):
    """Test GET /api/conversations/{thread_id}/stream-message with various event types."""
    thread_id = "streaming_thread_123"
    run_id = "streaming_run_456"

    # Define the mock data that join_stream will yield
    # This needs to simulate the structure of chunks from langgraph_client.runs.join_stream
    async def mock_join_stream_generator(*args, **kwargs):
        # Chunk 1: Transition to 'answer' node, then an AIMessageChunk from 'answer'
        yield {"event": "messages", "data": [
            {"langgraph_node": "some_previous_node", "created_by": "system"}, # Node transition
            {"type": "AIMessageChunk", "content": "This should be ignored (not answer node).", "langgraph_node": "some_previous_node"},
        ]}
        await asyncio.sleep(0) # Allow context switching

        yield {"event": "messages", "data": [
            {"langgraph_node": "answer", "created_by": "system"}, # Transition to answer node
            {"type": "AIMessageChunk", "content": "Hello, "}, # Part 1 of answer
        ]}
        await asyncio.sleep(0)

        # Chunk 2: Continuation of AIMessageChunk from 'answer'
        yield {"event": "messages", "data": [
            {"type": "AIMessageChunk", "content": "world!"}, # Part 2 of answer
        ]}
        await asyncio.sleep(0)
        
        # Chunk 3: Tool call initiated by AI
        yield {"event": "messages", "data": [
            {"langgraph_node": "tools", "created_by": "system"}, # Transition to tools node
            {
                "type": "AIMessageChunk", # Or could be 'AssistantMessage' depending on exact LangGraph version
                "additional_kwargs": {
                    "tool_calls": [{
                        "function": {"name": "calculator", "arguments": ""} # Start of args
                    }]
                }
            }
        ]}
        await asyncio.sleep(0)

        yield {"event": "messages", "data": [
             {
                "type": "AIMessageChunk",
                "additional_kwargs": {
                    "tool_calls": [{
                        "function": {"name": None, "arguments": '{"input": 2}'} # Arg continuation
                    }]
                }
            }
        ]}
        await asyncio.sleep(0)
        
        # Chunk 4: Tool result
        yield {"event": "messages", "data": [
            {"type": "tool", "name": "calculator", "content": "4"} # Result of the tool call
        ]}
        await asyncio.sleep(0)

        # Chunk 5: Another AIMessageChunk from 'answer' node (e.g. after tool execution)
        yield {"event": "messages", "data": [
            {"langgraph_node": "answer", "created_by": "system"}, # Back to answer node
            {"type": "AIMessageChunk", "content": "Calculation done."},
        ]}
        await asyncio.sleep(0)
        
        # Chunk 6: Content with markers to be ignored by stream
        yield {"event": "messages", "data": [
             {"type": "AIMessageChunk", "content": "[Confidence Score] High"},
        ]}
        await asyncio.sleep(0)


    with patch("src.backend.routes.langgraph_client.runs.join_stream", new=mock_join_stream_generator) as mock_join_stream:
        response = await async_client.get(f"/api/conversations/{thread_id}/stream-message?run_id={run_id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

        received_events = []
        # Read the stream (httpx response.aiter_lines())
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
                if event_type == "close":
                    received_events.append({"event": "close"})
            elif line.startswith("data:"):
                data_json = line.split(":", 1)[1].strip()
                try:
                    data = json.loads(data_json)
                    received_events.append({"event": "message", "data": data})
                except json.JSONDecodeError:
                    # Handle cases where data might not be JSON (e.g. close event data is empty)
                    pass # Or add specific handling if needed

    # Define expected events based on the mock_join_stream_generator and message_generator logic
    expected_events = [
        {"event": "message", "data": {"role": "assistant", "content": "Hello, "}},
        {"event": "message", "data": {"role": "assistant", "content": "world!"}},
        # Tool message for calculator
        {"event": "message", "data": {"role": "tool_message", "content": json.dumps({
            "type": "tool_combined",
            "name": "calculator",
            "call": {"name": "calculator", "arguments": {"input": 2}},
            "result": "4"
        })}},
        {"event": "message", "data": {"role": "assistant", "content": "Calculation done."}},
        {"event": "close"} # Final close event
    ]
    
    # Debugging: Print received and expected events if they don't match
    if received_events != expected_events:
        print("Received Events:", json.dumps(received_events, indent=2))
        print("Expected Events:", json.dumps(expected_events, indent=2))

    assert received_events == expected_events
    mock_join_stream.assert_called_once_with(thread_id, run_id, stream_mode="messages-tuple")

async def test_send_message_success(async_client: AsyncClient):
    """Test POST /api/conversations/{thread_id}/send-message successfully sends a message."""
    thread_id = "active_thread_123"
    run_id = "run_abc_789"
    request_payload = {"message": "Hello, is anyone there?"}
    
    expected_langgraph_input = {"messages": [{"type": "human", "content": "Hello, is anyone there?"}]}

    with patch("src.backend.routes.langgraph_client.runs.create", new_callable=AsyncMock) as mock_runs_create:
        mock_runs_create.return_value = {"run_id": run_id} # Simulate successful run creation
        
        response = await async_client.post(f"/api/conversations/{thread_id}/send-message", json=request_payload)

    assert response.status_code == 200
    json_response = response.json()
    assert json_response == {"run_id": run_id}
    
    mock_runs_create.assert_called_once_with(
        thread_id=thread_id,
        assistant_id="agent", # As specified in routes.py
        input=expected_langgraph_input,
        stream_mode="messages-tuple" # As specified in routes.py
    )

async def test_send_message_thread_not_found_or_error(async_client: AsyncClient):
    """Test POST /api/conversations/{thread_id}/send-message when thread not found or client error."""
    thread_id = "non_existent_thread_404"
    request_payload = {"message": "This should fail."}

    with patch("src.backend.routes.langgraph_client.runs.create", new_callable=AsyncMock) as mock_runs_create:
        # Simulate an exception, e.g., if the thread doesn't exist or another client error occurs
        mock_runs_create.side_effect = Exception("LangGraph client error: Thread not found or other issue")
        
        response = await async_client.post(f"/api/conversations/{thread_id}/send-message", json=request_payload)

    assert response.status_code == 404 # NotFoundError from the route's exception handling
    json_response = response.json()
    assert json_response["error"]["code"] == "THREAD_NOT_FOUND" # Code used in the route
    assert f"Thread {thread_id} not found or error creating run" in json_response["error"]["detail"]
    
    mock_runs_create.assert_called_once() # Check it was called, even if it failed

async def test_get_conversation_by_id_get_state_error(async_client: AsyncClient):
    """Test /api/conversations/{thread_id} when langgraph_client.threads.get_state raises an error."""
    thread_id = "error_thread_789"

    with patch("src.backend.routes.langgraph_client.threads.create", new_callable=AsyncMock) as mock_create, \
         patch("src.backend.routes.langgraph_client.threads.get_state", new_callable=AsyncMock) as mock_get_state:
        
        mock_create.return_value = None
        mock_get_state.side_effect = Exception("LangGraph client error during get_state")

        response = await async_client.get(f"/api/conversations/{thread_id}")

    assert response.status_code == 404 # NotFoundError from the route's exception handling
    json_response = response.json()
    assert json_response["error"]["code"] == "THREAD_ERROR"
    assert f"Error accessing thread {thread_id}" in json_response["error"]["detail"]
    
    mock_create.assert_called_once_with(
        thread_id=thread_id,
        if_exists="do_nothing",
        metadata=ANY
    )
    assert "created_at" in mock_create.call_args[1]['metadata']
    mock_get_state.assert_called_once_with(thread_id)

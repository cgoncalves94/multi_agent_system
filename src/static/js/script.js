import API_CONFIG from './config/config.js';

// DOM element cache for better performance
const DOM = {
    chatBox: () => document.getElementById('chat-box'),
    messageInput: () => document.getElementById('message-input'),
    sendButton: () => document.getElementById('send-button'),
    errorMessage: () => document.getElementById('error-message'),
    sessionsList: () => document.getElementById('sessions-list'),
    sidebar: () => document.querySelector('.sidebar'),
    overlay: () => document.querySelector('.overlay'),
    mainContent: () => document.querySelector('.main-content'),
    inputContainer: () => document.querySelector('.input-container'),
    sidebarToggle: () => document.querySelector('.sidebar-toggle'),
    newChatBtn: () => document.getElementById('new-chat-btn'),
    deleteAllBtn: () => document.querySelector('.button-danger'),
    // Modal elements
    modal: () => document.getElementById('confirmation-modal'),
    modalClose: () => document.querySelector('.modal-close'),
    modalCancel: () => document.getElementById('modal-cancel'),
    modalConfirm: () => document.getElementById('modal-confirm'),
    modalMessage: () => document.getElementById('modal-message'),
    // Document Upload Elements
    docUploadInput: () => document.getElementById('document-upload-input'),
    docUploadButton: () => document.getElementById('upload-document-btn'),
    docUploadStatus: () => document.getElementById('upload-status'),
    // Summarize Document Elements
    summarizeFileInput: () => document.getElementById('summarize-file-input'),
    attachSummarizeButton: () => document.getElementById('attach-summarize-button'),
    stagedDocumentIndicator: () => document.getElementById('staged-document-indicator')
};

let stagedSummarizationPayload = null;
let stagedFilename = null;

// Utility functions
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

function showNotification(message, type = 'error', duration = 5000) {
    const messageDiv = DOM.errorMessage();
    messageDiv.textContent = message;
    messageDiv.className = `message ${type}`;
    messageDiv.style.display = 'block';

    clearTimeout(messageDiv._hideTimeout);
    messageDiv._hideTimeout = setTimeout(() => {
        messageDiv.style.display = 'none';
    }, duration);
}

let currentThreadId = null;
let messageQueue = [];
let isProcessing = false;

// Create a throttled version of scrollToBottom for frequent updates
const throttledScroll = throttle(scrollToBottom, 100);

// Cache markdown-it instance for better performance
const md = window.markdownit();

// Helper function to render markdown with the cached instance
function renderMarkdown(content) {
    return md.render(content || '');
}

// Get thread ID from URL or show welcome screen
async function initializeThread() {
    const urlParams = new URLSearchParams(window.location.search);
    let threadId = urlParams.get('thread');

    if (!threadId) {
        // If no thread ID, just show welcome screen
        showWelcomeScreen();
        return;
    }

    currentThreadId = threadId;
    await loadConversation();
    storeThread(currentThreadId);
}

function showWelcomeScreen() {
    const chatBox = DOM.chatBox();
    chatBox.innerHTML = `
        <div class="welcome-screen">
            <div class="welcome-content">
                <h2>Welcome to LangGraph Chat!</h2>
                <p>Start a new conversation or browse your chat history to begin.</p>
                <div class="welcome-actions">
                    <button id="welcome-new-chat" class="welcome-button">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="12" y1="5" x2="12" y2="19"></line>
                            <line x1="5" y1="12" x2="19" y2="12"></line>
                        </svg>
                        Start New Chat
                    </button>
                </div>
                <div class="welcome-features">
                    <h3>Features</h3>
                    <ul>
                        <li>Multiple chat sessions</li>
                        <li>Markdown support</li>
                        <li>Real-time responses</li>
                        <li>Session history</li>
                    </ul>
                </div>
            </div>
        </div>
    `;

    // Clear the input area when showing welcome screen
    const inputContainer = DOM.inputContainer();
    if (inputContainer) {
        inputContainer.style.display = 'none';
    }
}

async function loadConversation() {
    try {
        if (!currentThreadId) {
            showWelcomeScreen();
            return;
        }

        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.GET_CONVERSATION(currentThreadId)}`);
        const data = await response.json();

        if (!response.ok) {
            if (response.status === 404) {
                console.log('Thread not found, removing from localStorage');
                localStorage.removeItem(`thread_${currentThreadId}`);
                currentThreadId = null;
                window.history.pushState({}, '', window.location.pathname);
                showWelcomeScreen();
                showMessage('This conversation no longer exists', 'error');
            } else {
                showError('Failed to load conversation');
            }
            return;
        }

        const inputContainer = DOM.inputContainer();
        if (inputContainer) {
            inputContainer.style.display = 'flex';
        }

        const chatBox = DOM.chatBox();
        chatBox.innerHTML = ''; // Clear existing messages

        if (data.messages && data.messages.length > 0) {
            // Use DocumentFragment for better performance when adding multiple messages
            const fragment = document.createDocumentFragment();
            data.messages.forEach(message => {
                const messageEl = appendMessage(message.role, message.content);
                fragment.appendChild(messageEl);
            });
            chatBox.appendChild(fragment);
        } else {
            // Show empty session welcome message
            showEmptySessionWelcome();
        }

        scrollToBottom();
    } catch (error) {
        console.error('Error loading conversation:', error);
        showError('Failed to load conversation');
    }
}

function showEmptySessionWelcome() {
    const chatBox = DOM.chatBox();
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'empty-session-welcome';
    welcomeDiv.innerHTML = `
        <div class="welcome-content">
            <h2>Start Your Conversation</h2>
            <p>This is a new chat session. Type your message below to begin!</p>
            <div class="welcome-tips">
                <h3>Tips:</h3>
                <ul>
                    <li>Ask questions in a clear, specific manner</li>
                    <li>You can use markdown in your messages</li>
                    <li>Press Enter to send, Shift+Enter for new line</li>
                </ul>
            </div>
        </div>
    `;
    chatBox.appendChild(welcomeDiv);
}

function appendMessage(role, content, displayContentOverride = null) {
    const chatBox = DOM.chatBox();
    const displayContent = displayContentOverride !== null ? displayContentOverride : content;

    // Remove any existing welcome messages
    const welcomeMessages = chatBox.querySelectorAll('.welcome-message, .empty-session-welcome');
    welcomeMessages.forEach(msg => msg.remove());

    // Create message with DocumentFragment for better performance
    const fragment = document.createDocumentFragment();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    // Handle different message types
    if (role === 'user' || role === 'assistant') {
        // Convert markdown to HTML for user and assistant messages
        const htmlContent = renderMarkdown(displayContent); // Use displayContent for rendering

        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-header">${role === 'user' ? 'You' : 'Assistant'}</div>
                <div class="message-text">${htmlContent}</div>
            </div>
        `;
    } else if (role === 'tool_message') {
        // Parse the tool message content (actual content, not displayContent)
        try {
            const toolData = JSON.parse(content);
            const isToolCall = toolData.type === 'tool_call';
            const isToolCombined = toolData.type === 'tool_combined';

            messageDiv.innerHTML = `
                <div class="message-content">
                    <div class="tool-result collapsed">
                        <div class="tool-result-header">
                            ${isToolCombined ? 'Tool Call & Result' : (isToolCall ? 'Tool Call' : 'Tool Result')}: ${isToolCombined ? toolData.call.name : toolData.name}
                        </div>
                        <div class="tool-result-content">
                            ${isToolCombined ? `
                                <div class="tool-args">
                                    <div class="tool-section-header">Arguments:</div>
                                    <pre>${formatToolArguments(toolData.call.arguments)}</pre>
                                </div>
                                <div class="tool-output">
                                    <div class="tool-section-header">Result:</div>
                                    <pre>${formatToolResult(toolData.result)}</pre>
                                </div>
                            ` : (isToolCall ? `
                                <div class="tool-args">
                                    <div class="tool-section-header">Arguments:</div>
                                    <pre>${formatToolArguments(toolData.arguments)}</pre>
                                </div>
                            ` : `
                                <div class="tool-output">
                                    <pre>${formatToolResult(toolData.result)}</pre>
                                </div>
                            `)}
                        </div>
                    </div>
                </div>
            `;

            // Add click handler for collapse/expand
            const toolResult = messageDiv.querySelector('.tool-result');
            const header = toolResult.querySelector('.tool-result-header');
            header.addEventListener('click', () => {
                toolResult.classList.toggle('collapsed');

                // Store collapse state in localStorage
                const messageId = Date.now().toString(); // Generate a unique ID for the message
                localStorage.setItem(`tool_message_${messageId}`, toolResult.classList.contains('collapsed'));
            });

        } catch (e) {
            console.error('Error parsing tool message:', e);
            messageDiv.innerHTML = `
                <div class="message-content">
                    <div class="tool-result collapsed">
                        <div class="tool-result-header">Tool Message Error</div>
                        <div class="tool-result-content">
                            <pre>Error displaying tool message</pre>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    // Append to fragment first, then to DOM (single operation)
    fragment.appendChild(messageDiv);
    chatBox.appendChild(fragment);
    scrollToBottom();

    return messageDiv;
}

// Helper function to format tool results
function formatToolResult(result) {
    try {
        if (typeof result === 'string' && (result.startsWith('[') || result.startsWith('{'))) {
            const parsed = JSON.parse(result);
            return JSON.stringify(parsed, null, 2);
        }
        return result;
    } catch (e) {
        return result;
    }
}

// Helper function to format tool arguments
function formatToolArguments(args) {
    return Object.entries(args)
        .map(([key, value]) => `${key.charAt(0).toUpperCase() + key.slice(1)}: ${JSON.stringify(value)}`)
        .join('\n');
}

// Scroll to bottom of chat box
function scrollToBottom(force = false) {
    const chatBox = DOM.chatBox();
    if (!chatBox) return;

    // Use a single requestAnimationFrame for better performance
    requestAnimationFrame(() => {
        chatBox.scrollTop = chatBox.scrollHeight;

        // Double check after a small delay (only if needed)
        setTimeout(() => chatBox.scrollTop = chatBox.scrollHeight, 50);
    });
}

// Update the streaming part in processMessageQueue
async function processMessageQueue() {
    if (isProcessing || messageQueue.length === 0) return;
    isProcessing = true;

    const messageData = messageQueue.shift(); // Now an object { fullPayload, displayPayload }
    const fullPayload = messageData.fullPayload;
    const displayPayloadForUserBubble = messageData.displayPayload;

    try {
        // Add user message to chat, using the displayPayload
        appendMessage('user', fullPayload, displayPayloadForUserBubble); // Pass both
        scrollToBottom(); // Scroll after user message

        // Add loading indicator as a message
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant';
        loadingDiv.innerHTML = `
            <div class="message-content loading-indicator">
                <div class="spinner"></div>
                <div class="loading-text">AI is thinking...</div>
            </div>
        `;
        DOM.chatBox().appendChild(loadingDiv);
        scrollToBottom(); // Scroll to show loading

        // First, send the message (fullPayload) and get the run_id
        const sendResponse = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.SEND_MESSAGE(currentThreadId)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: fullPayload }) // Send the full payload
        });

        if (!sendResponse.ok) {
            const errorData = await sendResponse.json();
            const errorMessage = errorData.error?.detail || 'Failed to send message';
            showError(errorMessage);
            loadingDiv.remove();
            return;
        }

        const { run_id } = await sendResponse.json();

        // Then start streaming the response
        const streamResponse = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.STREAM_MESSAGE(currentThreadId, run_id)}`);
        if (!streamResponse.ok) {
            const errorData = await streamResponse.json();
            const errorMessage = errorData.error?.detail || 'Failed to stream response';
            showError(errorMessage);
            loadingDiv.remove();
            return;
        }

        const reader = streamResponse.body.getReader();
        const decoder = new TextDecoder();
        let currentAssistantMessage = '';
        let hasStartedReceivingResponse = false;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            // Remove loading indicator on first response
            if (!hasStartedReceivingResponse) {
                loadingDiv.remove();
                hasStartedReceivingResponse = true;
            }

            const chunk = decoder.decode(value);
            const events = chunk.split('\n\n').filter(Boolean);

            for (const eventText of events) {
                const eventLines = eventText.split('\n');
                const eventType = eventLines[0].slice(7);
                const data = eventLines[1].slice(6);

                if (eventType === 'message' && data) {
                    try {
                        const messageData = JSON.parse(data);
                        const role = messageData.role;
                        const content = messageData.content;

                        if (role === 'tool_message') {
                            if (currentAssistantMessage) {
                                appendMessage('assistant', currentAssistantMessage);
                                currentAssistantMessage = '';
                            }
                            appendMessage('tool_message', content);
                            scrollToBottom(); // Scroll after tool message
                        } else if (role === 'assistant') {
                            // Add space if needed between numbers and text
                            if (currentAssistantMessage && content) {
                                const lastChar = currentAssistantMessage[currentAssistantMessage.length - 1];
                                const firstChar = content[0];
                                // Add space if we're transitioning between number and letter or vice versa
                                if (
                                    (lastChar && /\d/.test(lastChar) && /[a-zA-Z]/.test(firstChar)) ||
                                    (lastChar && /[a-zA-Z]/.test(lastChar) && /\d/.test(firstChar))
                                ) {
                                    currentAssistantMessage += ' ';
                                }
                            }
                            currentAssistantMessage += content;
                            const lastMessage = document.querySelector('.message.assistant:last-child');
                            if (lastMessage) {
                                const messageText = lastMessage.querySelector('.message-text');
                                messageText.innerHTML = renderMarkdown(currentAssistantMessage);
                                throttledScroll(); // Use throttled scroll for frequent updates
                            } else {
                                appendMessage('assistant', currentAssistantMessage);
                                scrollToBottom(); // Scroll after new message
                            }
                        }
                    } catch (e) {
                        console.error('Error parsing message data:', e);
                    }
                } else if (eventType === 'close') {
                    // If there's any remaining assistant message, append it
                    if (currentAssistantMessage) {
                        const lastMessage = document.querySelector('.message.assistant:last-child');
                        if (lastMessage) {
                            const messageText = lastMessage.querySelector('.message-text');
                            messageText.innerHTML = renderMarkdown(currentAssistantMessage);
                        }
                        currentAssistantMessage = '';
                    }
                    break;
                }
            }
        }

        // Final scroll after everything is done
        setTimeout(() => scrollToBottom(), 100);

    } catch (error) {
        console.error('Error in message processing:', error);
        showError('Failed to process message');
    } finally {
        isProcessing = false;
        if (messageQueue.length > 0) {
            await processMessageQueue();
        }
    }
}

async function sendMessage() {
    const input = DOM.messageInput();
    const typedMessage = input.value.trim();
    let messageToSend = typedMessage;
    let displayMessageForUserBubble = typedMessage;

    if (stagedSummarizationPayload) {
        messageToSend = stagedSummarizationPayload; // This is the "SUMMARIZE DOCUMENT:..."
        if (typedMessage) {
            // If user typed something, append it to the hidden payload
            messageToSend += `\n\n${typedMessage}`;
            // For display, show "Summarize: [filename]" and then what they typed
            displayMessageForUserBubble = `Summarizing: ${stagedFilename}\n\n${typedMessage}`;
        } else {
            // If user typed nothing, just display "Summarize: [filename]"
            displayMessageForUserBubble = `Summarizing: ${stagedFilename}`;
        }
    }

    if (!messageToSend && !typedMessage && !stagedSummarizationPayload) { // Nothing to send
        return;
    }

    // If only typed message and no staged doc, displayPayload is same as messageToSend
    if (!stagedSummarizationPayload && typedMessage) {
        displayMessageForUserBubble = typedMessage;
    }


    // Push an object to the queue
    messageQueue.push({ fullPayload: messageToSend, displayPayload: displayMessageForUserBubble });

    input.value = ''; // Clear main input
    input.style.height = 'auto'; // Reset height
    input.style.height = `${input.scrollHeight}px`;


    if (stagedSummarizationPayload) {
        removeStagedDocument(); // Clear staged document info
    }

    await processMessageQueue();
}

function showError(message) {
    showNotification(message, 'error');
}

// New Chat functionality
async function startNewChat() {
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.NEW_THREAD}`);
        const data = await response.json();

        // Update URL without page refresh
        window.history.pushState({}, '', `?thread=${data.thread_id}`);

        // Update current thread ID
        currentThreadId = data.thread_id;

        // Store the new thread
        storeThread(currentThreadId);

        // Load the empty conversation (which will show the welcome message)
        await loadConversation();

        // Reload sessions to show the new one in the sidebar
        await loadSessions();

        // Ensure input container is visible
        const inputContainer = DOM.inputContainer();
        if (inputContainer) {
            inputContainer.style.display = 'flex';
        }

        // Focus the input field
        const messageInput = DOM.messageInput();
        if (messageInput) {
            messageInput.focus();
        }

        // Close the sidebar regardless of screen size
        toggleSessionsPanel(false);
    } catch (error) {
        console.error('Error creating new chat:', error);
        showError('Failed to create new chat');
    }
}

// Toggle sessions panel
async function toggleSessionsPanel(showSidebar) {
    const sidebar = DOM.sidebar();
    const overlay = DOM.overlay();
    const mainContent = DOM.mainContent();

    const shouldShow = showSidebar === undefined ?
        !sidebar.classList.contains('active') : showSidebar;

    if (shouldShow) {
        sidebar.classList.add('active');
        overlay.classList.add('active');
        mainContent.classList.add('sidebar-active');
        await loadSessions(); // Only load when opening
    } else {
        sidebar.classList.remove('active');
        overlay.classList.remove('active');
        mainContent.classList.remove('sidebar-active');
    }
}

// Load available conversations
async function loadSessions() {
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.GET_CONVERSATIONS}`);
        const data = await response.json();
        // Access the conversations array from the response
        const conversations = data.conversations;

        const sessionsList = DOM.sessionsList();
        sessionsList.innerHTML = '';

        // Group conversations by time periods
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        const groupedConversations = {
            today: [],
            yesterday: [],
            lastWeek: [],
            older: []
        };

        conversations.forEach(conversation => {
            const conversationDate = new Date(conversation.created_at);

            if (isSameDay(conversationDate, today)) {
                groupedConversations.today.push(conversation);
            } else if (isSameDay(conversationDate, yesterday)) {
                groupedConversations.yesterday.push(conversation);
            } else if (isWithinLastWeek(conversationDate, today)) {
                groupedConversations.lastWeek.push(conversation);
            } else {
                groupedConversations.older.push(conversation);
            }
        });

        // Add time period sections
        if (groupedConversations.today.length > 0) {
            addTimePeriodSection('Today', groupedConversations.today);
        }
        if (groupedConversations.yesterday.length > 0) {
            addTimePeriodSection('Yesterday', groupedConversations.yesterday);
        }
        if (groupedConversations.lastWeek.length > 0) {
            addTimePeriodSection('Last 7 Days', groupedConversations.lastWeek);
        }
        if (groupedConversations.older.length > 0) {
            addTimePeriodSection('Older', groupedConversations.older);
        }

        // If no conversations were added, show a message
        if (sessionsList.children.length === 0) {
            const noConversationsDiv = document.createElement('div');
            noConversationsDiv.className = 'no-sessions';
            noConversationsDiv.textContent = 'No conversations yet';
            sessionsList.appendChild(noConversationsDiv);
        }
    } catch (error) {
        console.error('Error loading conversations:', error);
        const sessionsList = DOM.sessionsList();
        sessionsList.innerHTML = '<div class="error-message">Failed to load conversations</div>';
    }
}

function addTimePeriodSection(title, conversations) {
    const sessionsList = DOM.sessionsList();

    // Create a document fragment for better performance
    const fragment = document.createDocumentFragment();

    // Add time period header
    const periodHeader = document.createElement('div');
    periodHeader.className = 'time-period';
    periodHeader.textContent = title;
    fragment.appendChild(periodHeader);

    // Add conversations for this period
    conversations.forEach(conversation => {
        const conversationDiv = document.createElement('div');
        conversationDiv.className = 'session-item';

        const date = new Date(conversation.created_at);
        const timeStr = date.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });

        conversationDiv.innerHTML = `
            <div class="session-content">
                <div class="session-info">
                    <div class="session-time">
                        <span class="time">${timeStr}</span>
                    </div>
                    <div class="session-id">${conversation.thread_id}</div>
                </div>
                <button class="delete-btn" data-thread-id="${conversation.thread_id}">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18"></path>
                        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        `;

        fragment.appendChild(conversationDiv);
    });

    // Append all elements at once
    sessionsList.appendChild(fragment);
}

function isSameDay(date1, date2) {
    return date1.getDate() === date2.getDate() &&
           date1.getMonth() === date2.getMonth() &&
           date1.getFullYear() === date2.getFullYear();
}

function isWithinLastWeek(date, today) {
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);
    return date > weekAgo;
}

// Delete a specific conversation
async function deleteThread(threadId) {
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.DELETE_THREAD(threadId)}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete conversation');
        }

        // If we're deleting the current thread
        if (threadId === currentThreadId) {
            // Get all available threads
            const threadsResponse = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.GET_CONVERSATIONS}`);
            const data = await threadsResponse.json();

            // Access the conversations array from the response and filter
            const remainingThreads = data.conversations.filter(conv => conv.thread_id !== threadId);

            // Clear current thread ID
            currentThreadId = null;

            if (remainingThreads.length > 0) {
                // Navigate to the most recent thread
                const mostRecentThread = remainingThreads[0];
                window.history.pushState({}, '', `?thread=${mostRecentThread.thread_id}`);
                currentThreadId = mostRecentThread.thread_id;
                await loadConversation();
            } else {
                // No threads left, show welcome screen
                window.history.pushState({}, '', window.location.pathname);
                showWelcomeScreen();
            }
        }

        // Reload conversations in sidebar
        await loadSessions();

    } catch (error) {
        console.error('Error deleting conversation:', error);
        showError('Failed to delete conversation');
    }
}

// Modal functionality
function showModal(message, confirmCallback) {
    const modal = DOM.modal();
    const modalMessage = DOM.modalMessage();

    if (message) {
        modalMessage.textContent = message;
    }

    modal.classList.add('active');

    // Store the callback for later use
    modal._confirmCallback = confirmCallback;

    // Focus the cancel button by default (safer option)
    setTimeout(() => DOM.modalCancel().focus(), 100);
}

function hideModal() {
    const modal = DOM.modal();
    modal.classList.remove('active');
    modal._confirmCallback = null;
}

function setupModalListeners() {
    // Close button
    DOM.modalClose().addEventListener('click', hideModal);

    // Cancel button
    DOM.modalCancel().addEventListener('click', hideModal);

    // Confirm button
    DOM.modalConfirm().addEventListener('click', () => {
        const modal = DOM.modal();
        if (typeof modal._confirmCallback === 'function') {
            modal._confirmCallback();
        }
        hideModal();
    });

    // Close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && DOM.modal().classList.contains('active')) {
            hideModal();
        }
    });

    // Close on outside click
    DOM.modal().addEventListener('click', (e) => {
        if (e.target === DOM.modal()) {
            hideModal();
        }
    });
}

// Delete all conversations with confirmation
async function deleteAllThreads() {
    showModal('Are you sure you want to delete all conversations? This action cannot be undone.', async () => {
        try {
            const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.DELETE_ALL_THREADS}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error('Failed to delete all conversations');
            }

            // Clear current thread and show welcome screen
            currentThreadId = null;
            window.history.pushState({}, '', window.location.pathname);
            showWelcomeScreen();

            // Reload conversations after successful deletion
            await loadSessions();

            // Show success message
            showNotification('All conversations deleted successfully', 'success');
        } catch (error) {
            console.error('Error deleting all conversations:', error);
            showError('Failed to delete all conversations');
        }
    });
}

// Replace showMessage with showNotification
function showMessage(message, type = 'error') {
    showNotification(message, type);
}

// Setup all event listeners in one place for better organization
function setupEventListeners() {
    // Message input and send
    DOM.sendButton().addEventListener('click', sendMessage);
    DOM.messageInput().addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // New chat button
    const newChatBtn = DOM.newChatBtn();
    if (newChatBtn) {
        newChatBtn.addEventListener('click', startNewChat);
    }

    // Delete all button
    const deleteAllBtn = DOM.deleteAllBtn();
    if (deleteAllBtn) {
        deleteAllBtn.addEventListener('click', deleteAllThreads);
    }

    // Sidebar toggle
    const sidebarToggle = DOM.sidebarToggle();
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => toggleSessionsPanel());
    }

    // Overlay click to close sidebar
    const overlay = DOM.overlay();
    if (overlay) {
        overlay.addEventListener('click', () => toggleSessionsPanel(false));
    }

    // Session list delegation
    const sessionsList = DOM.sessionsList();
    if (sessionsList) {
        sessionsList.addEventListener('click', async (e) => {
            // Delete button handling
            if (e.target.closest('.delete-btn')) {
                e.stopPropagation();
                const threadId = e.target.closest('.delete-btn').dataset.threadId;
                await deleteThread(threadId);
                return;
            }

            // Session selection handling
            const sessionContent = e.target.closest('.session-content');
            if (sessionContent) {
                const threadId = sessionContent.querySelector('.session-id').textContent;
                window.history.pushState({}, '', `?thread=${threadId}`);
                currentThreadId = threadId;
                await loadConversation();

                // Close sidebar on mobile
                if (window.innerWidth <= 768) {
                    toggleSessionsPanel(false);
                }
            }
        });
    }

    // ESC key to close sidebar
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            const sidebar = DOM.sidebar();
            if (sidebar.classList.contains('active')) {
                toggleSessionsPanel(false);
            }
        }
    });

    // Welcome screen new chat button
    document.addEventListener('click', (e) => {
        if (e.target.id === 'welcome-new-chat' || e.target.closest('#welcome-new-chat')) {
            startNewChat();
        }
    });

    // Setup modal listeners
    setupModalListeners();

    // Document upload button
    const docUploadButton = DOM.docUploadButton();
    if (docUploadButton) {
        docUploadButton.addEventListener('click', handleDocumentUpload);
    }

    // Attach document for summarization button
    const attachSummarizeButton = DOM.attachSummarizeButton();
    if (attachSummarizeButton) {
        attachSummarizeButton.addEventListener('click', () => {
            DOM.summarizeFileInput()?.click();
        });
    }

    // Summarize file input change
    const summarizeFileInput = DOM.summarizeFileInput();
    if (summarizeFileInput) {
        summarizeFileInput.addEventListener('change', handleSummarizeFileSelect);
    }
}

// Handle file selection for summarization
async function handleSummarizeFileSelect(event) {
    const fileInput = event.target;
    const indicator = DOM.stagedDocumentIndicator();

    if (!fileInput.files || fileInput.files.length === 0) {
        return;
    }

    const file = fileInput.files[0];
    stagedFilename = file.name; // Store filename

    if (file.type !== 'text/plain' && !file.name.endsWith('.md')) {
        showNotification('Please select a .txt or .md file for summarization.', 'error');
        stagedFilename = null;
        fileInput.value = ''; // Reset file input
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const fileContent = e.target.result;
        stagedSummarizationPayload = `SUMMARIZE DOCUMENT:\n\n${fileContent}`;

        // Update indicator
        if (indicator) {
            indicator.innerHTML = `
                <span>Attached for summarization: ${stagedFilename}</span>
                <button id="remove-staged-doc-btn" class="remove-staged-btn" title="Remove document">✖</button>
            `;
            const removeBtn = document.getElementById('remove-staged-doc-btn');
            if (removeBtn) {
                removeBtn.addEventListener('click', removeStagedDocument);
            }
        }
        DOM.messageInput()?.focus();
    };
    reader.onerror = () => {
        showNotification('Failed to read the file.', 'error');
        stagedSummarizationPayload = null;
        stagedFilename = null;
        if (indicator) indicator.innerHTML = '';
    };
    reader.readAsText(file);

    // Reset file input so the same file can be chosen again if needed
    fileInput.value = '';
}

function removeStagedDocument() {
    stagedSummarizationPayload = null;
    stagedFilename = null;
    const indicator = DOM.stagedDocumentIndicator();
    if (indicator) {
        indicator.innerHTML = '';
    }
    const summarizeInput = DOM.summarizeFileInput();
    if(summarizeInput) summarizeInput.value = ''; // Clear the actual file input as well
}

// Handle Document Upload
async function handleDocumentUpload() {
    const fileInput = DOM.docUploadInput();
    const uploadStatus = DOM.docUploadStatus();

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        uploadStatus.textContent = 'Please select a file to upload.';
        uploadStatus.className = 'upload-status-message error';
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    uploadStatus.textContent = 'Uploading and processing...';
    uploadStatus.className = 'upload-status-message loading';

    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.UPLOAD_DOCUMENT}`, {
            method: 'POST',
            body: formData,
        });

        const result = await response.json();

        if (response.ok && result.status === 'success') {
            uploadStatus.textContent = `Success: ${file.name} ingested (${result.num_chunks} chunks).`;
            uploadStatus.className = 'upload-status-message success';
            fileInput.value = ''; // Clear the file input
        } else {
            const errorDetail = result.detail || result.error || 'Unknown error during upload.';
            uploadStatus.textContent = `Error: ${errorDetail}`;
            uploadStatus.className = 'upload-status-message error';
        }
    } catch (error) {
        console.error('Error uploading document:', error);
        uploadStatus.textContent = 'Upload failed. See console for details.';
        uploadStatus.className = 'upload-status-message error';
    }

    // Clear status message after a few seconds
    setTimeout(() => {
        uploadStatus.textContent = '';
        uploadStatus.className = 'upload-status-message';
    }, 7000);
}


// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Load conversations immediately
    await loadSessions();

    await initializeThread();

    // Setup all event listeners
    setupEventListeners();
});

// Store thread ID in localStorage when created
function storeThread(threadId) {
    if (threadId) {
        localStorage.setItem(`thread_${threadId}`, Date.now().toString());
    }
}

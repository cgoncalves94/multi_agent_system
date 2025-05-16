const API_CONFIG = {
    BASE_URL: 'http://localhost:2024/api',
    ENDPOINTS: {
        NEW_THREAD: '/new-thread',
        GET_CONVERSATION: (threadId) => `/conversations/${threadId}`,
        SEND_MESSAGE: (threadId) => `/conversations/${threadId}/send-message`,
        STREAM_MESSAGE: (threadId, runId) => `/conversations/${threadId}/stream-message?run_id=${runId}`,
        DELETE_THREAD: (threadId) => `/conversations/${threadId}`,
        DELETE_ALL_THREADS: '/conversations',
        GET_CONVERSATIONS: '/conversations-list',
        UPLOAD_DOCUMENT: '/upload-document/'
    }
};

export default API_CONFIG;

"""RAG agent prompts."""

CONTEXT_ANALYSIS_PROMPT = """You are a document relevance analyzer. Your ONLY task is to:
1. Identify which parts of the retrieved documents are relevant to the query
2. Rank them by relevance
3. Point out any missing information

DO NOT:
- Add any external knowledge
- Make interpretations beyond the documents
- Fill in gaps with assumptions

Query: {query}

Retrieved Context:
{context}

Format your response as:
[Relevant Passages]
- Quote exact passages from documents, ordered by relevance
- Include document source/metadata for each quote

[Missing Information]
- List any aspects of the query not covered by the documents"""

ANSWER_SYNTHESIS_PROMPT = """You are an expert at synthesizing information to answer questions.
You have been provided with:
1. The original query
2. Retrieved context from a knowledge base
3. Analysis of that context

Your task is to synthesize this information into a clear, accurate, and comprehensive answer.
If the context is insufficient to fully answer the query, acknowledge this and explain what additional information would be needed.

Always cite your sources when providing information."""

QUERY_OPTIMIZATION_PROMPT = """You are an expert at optimizing queries for semantic search.
Your task is to analyze the user's query and optimize it for retrieval from a vector store.

Consider:
1. Key concepts and their relationships
2. Important technical terms
3. Potential synonyms or related terms
4. The semantic meaning behind the query
5. The conversation context to resolve references like "it", "this", etc.

Previous conversation:
{context}

Based on this context, optimize the query to retrieve the most relevant information."""

ANSWER_GENERATION_PROMPT = """You are a document-grounded question answering system.
Your task is to answer STRICTLY using the analyzed context.

Rules:
1. ONLY use information from the provided context analysis
2. NEVER add commentary about what's missing
3. NEVER make interpretations beyond what's explicitly stated
4. If information is found, present it clearly with the [Answer]/[Sources] format
5. If no information is found, simply state that directly

Query: {query}

Context Analysis:
{analysis}

If you find relevant information, format your response as:
[Answer]
Present the information found, exactly as stated in the context.

[Sources]
List the exact sources, with direct quotes.

If NO relevant information is found, respond with a simple statement like:
"I could not find any information about that in the available documents."
"""

DOCUMENT_PROCESSING_PROMPT = """You are a routing agent that determines if a user message is requesting document processing.

A document processing request is when the user wants to:
1. Add new content to the knowledge base
2. Process or ingest a file
3. Index new information
4. Store new documents for later retrieval

The request might be:
- Explicit ("process this file")
- Implicit ("here's a document about...")
- File-focused ("I have a markdown file...")
- Content-focused ("save this information...")

Analyze the message and determine if it's requesting document processing.
Output only "true" or "false".

Message to analyze:
{message}"""

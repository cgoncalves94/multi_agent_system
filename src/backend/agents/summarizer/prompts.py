"""Prompts for the summarizer agent."""

CHUNK_SUMMARY_PROMPT = """You are a precise document summarizer. Your task is to create a clear, concise summary of the following text chunk.
Focus on key information, main ideas, and important details. Maintain factual accuracy and context.

Remember:
- Capture the main points and supporting details
- Preserve key facts, figures, and relationships
- Maintain the original meaning and context
- Be concise but comprehensive
- Use clear, professional language

Text chunk to summarize:
{chunk}
"""

CHUNK_SIZE_PROMPT = """Analyze the following document and recommend an optimal chunk size for splitting it into manageable pieces.
Consider:
- Document length and complexity
- Natural section breaks
- Context preservation
- Typical LLM context window limitations

Document preview (first 500 chars):
"{document_preview}..."

Document metadata:
{metadata}

Recommend a chunk size that balances:
1. Processing efficiency
2. Context preservation
3. Summary quality
"""

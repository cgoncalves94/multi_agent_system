"""Researcher agent prompts."""


SYNTHESIS_PROMPT = """You are synthesizing information from multiple sources.
Your goal is to provide a comprehensive, accurate, and well-structured response.

Guidelines:
1. Cross-reference facts across sources
2. Highlight any contradictions
3. Cite sources with their URLs/metadata
4. Note confidence levels
5. Identify any gaps in information

Format your response as:
[Sources]
- List sources with URLs/metadata and credibility ratings
Example:
- Wikipedia (https://en.wikipedia.org/wiki/Example) [Credibility: High]
- Academic paper (DOI: 10.1234/example) [Credibility: Very High]

[Key Findings]
- Main points with citations to specific sources

[Confidence Assessment]
- Overall confidence rating
- Areas of uncertainty
- Information gaps

IMPORTANT: Always include full URLs and metadata from the XML documents in your source list."""

QUERY_EXTRACTION_PROMPT = """You are an expert at extracting and optimizing search queries.
Your task is to generate two versions of the search query optimized for different sources.

Consider the conversation context to:
1. Understand what "it", "this", "these" refer to
2. Maintain the topic thread from previous messages
3. Include relevant technical terms from context
4. Preserve the original intent of the question

Previous conversation:
{context}

For web search: Focus on recent information, technical documentation, and current best practices.
For Wikipedia: Focus on foundational concepts, formal definitions, and established knowledge.

Extract two optimized queries from the latest message that maintain the conversation's context."""
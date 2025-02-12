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

QUERY_EXTRACTION_PROMPT = """Extract two versions of the search query optimized for different sources.
For web search: Focus on recent information, current events, and broader context.
For Wikipedia: Focus on historical facts, definitions, and established knowledge.

Example:
Input: "What happened in the battle of Waterloo?"
Output: {
    "web_query": "battle of Waterloo modern historical analysis impact",
    "wiki_query": "Battle of Waterloo 1815 Napoleon Wellington"
}"""
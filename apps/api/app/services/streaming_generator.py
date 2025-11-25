"""
Streaming generator for large documents
Generates sections incrementally using Server-Sent Events (SSE)
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi.responses import StreamingResponse

from app.models.document import Document
from app.services.ai_pipeline.generator import SectionGenerator

logger = logging.getLogger(__name__)


class StreamingGenerator:
    """Generate large documents with streaming support"""

    def __init__(self):
        """Initialize streaming generator"""
        self.section_generator = SectionGenerator()

    async def generate_document_stream(
        self,
        document: Document,
        outline_sections: list[dict[str, Any]],
        provider: str,
        model: str,
        citation_style: str = "APA",
        humanize: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Generate document sections with streaming

        Args:
            document: Document model instance
            outline_sections: List of sections from outline
            provider: AI provider
            model: Model name
            citation_style: Citation style
            humanize: Whether to humanize

        Yields:
            JSON strings with section data
        """
        total_sections = len(outline_sections)

        # Send initial metadata
        yield f"data: {json.dumps({'type': 'start', 'total_sections': total_sections})}\n\n"

        context_sections = []

        for idx, section_info in enumerate(outline_sections, 1):
            section_title = section_info.get("title", f"Section {idx}")

            try:
                # Send progress update
                yield f"data: {json.dumps({'type': 'progress', 'section_index': idx, 'section_title': section_title, 'progress': int((idx / total_sections) * 100)})}\n\n"

                # Generate section
                section_result = await self.section_generator.generate_section(
                    document=document,
                    section_title=section_title,
                    section_index=idx,
                    provider=provider,
                    model=model,
                    citation_style=citation_style,
                    humanize=humanize,
                    context_sections=context_sections if context_sections else None,
                )

                # Add to context for next sections
                context_sections.append(
                    {
                        "title": section_title,
                        "content": section_result.get("content", ""),
                    }
                )

                # Send section data
                yield f"data: {json.dumps({'type': 'section', 'section_index': idx, 'section_title': section_title, 'data': section_result})}\n\n"

                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error generating section {idx}: {e}")
                yield f"data: {json.dumps({'type': 'error', 'section_index': idx, 'error': str(e)})}\n\n"
                continue

        # Send completion
        yield f"data: {json.dumps({'type': 'complete', 'total_sections': total_sections})}\n\n"

    def create_streaming_response(
        self, generator: AsyncGenerator[str, None]
    ) -> StreamingResponse:
        """
        Create FastAPI StreamingResponse from generator

        Args:
            generator: Async generator yielding JSON strings

        Returns:
            StreamingResponse with SSE format
        """
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

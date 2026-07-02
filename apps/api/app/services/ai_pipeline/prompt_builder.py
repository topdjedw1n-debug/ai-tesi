"""
Prompt builder for AI generation
Constructs prompts for outline and section generation
"""

from typing import Any

from app.models.document import Document

# Multilingual system prompts for AI models
SYSTEM_PROMPTS = {
    "en": "You are an expert academic writer specializing in thesis and research paper generation.",
    "it": "Sei un esperto scrittore accademico specializzato nella generazione di tesi e lavori di ricerca.",
    "es": "Eres un escritor académico experto especializado en la generación de tesis y trabajos de investigación.",
    "de": "Sie sind ein erfahrener akademischer Autor, der auf die Erstellung von Abschlussarbeiten und Forschungsarbeiten spezialisiert ist.",
    "cs": "Jste odborný akademický autor specializující se na tvorbu diplomových a výzkumných prací.",
    "fr": "Vous êtes un rédacteur académique expert spécialisé dans la génération de thèses et de travaux de recherche.",
    "uk": "Ви експерт з академічного письма, що спеціалізується на створенні дипломних та дослідницьких робіт.",
}


class PromptBuilder:
    """Build prompts for AI content generation"""

    @staticmethod
    def get_system_prompt(language: str) -> str:
        """
        Get system prompt in target language

        Args:
            language: Language code (en, it, es, de, cs, fr, uk)

        Returns:
            System prompt in specified language
        """
        return SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["en"])

    @staticmethod
    def build_section_prompt(
        document: Document,
        section_title: str,
        section_index: int,
        context_sections: list[dict[str, Any]] | None = None,
        retrieved_sources: list[str] | None = None,
        additional_requirements: str | None = None,
        source_pack_block: str | None = None,
    ) -> str:
        """
        Build prompt for section generation with RAG context

        Args:
            document: Document model instance
            section_title: Title of the section to generate
            section_index: Index of the section
            context_sections: Previously generated sections for context
            retrieved_sources: Retrieved source documents from RAG (legacy path)
            additional_requirements: Optional additional user requirements
            source_pack_block: Keyed, curated source list. When provided, the
                section is written CLOSED-BOOK against it (cite only these keys)
                and stricter anti-generic constraints apply.

        Returns:
            Formatted prompt string
        """
        context_text = ""
        if context_sections:
            context_text = "\n\nPrevious sections context:\n"
            for section in context_sections:
                context_text += f"- {section.get('title', 'Unknown')}: {section.get('content', '')[:200]}...\n"

        # Sources block + citation rules: closed-book (pack) vs legacy (top-5).
        if source_pack_block:
            sources_text = (
                "\n\nAVAILABLE SOURCES (cite ONLY these, by their [Key]):\n"
                f"{source_pack_block}\n"
            )
            citation_rules = (
                "- Cite ONLY sources from the AVAILABLE SOURCES list above, using "
                "their exact key in [Key, Year] form (e.g. [Rossi2021, 2021]).\n"
                "- NEVER invent, alter, or cite any source that is not in that "
                "list. If a statement cannot be supported by a listed source, "
                "write it WITHOUT a citation — do not fabricate one.\n"
                "- Include at least one concrete detail from the listed sources: "
                "a statistic, numeric finding, named system, or specific study "
                "result mentioned in their titles/abstracts.\n"
                "- NEVER invent numeric data. Use numbers only if they appear in "
                "the sources; otherwise state the source's concrete qualitative "
                "finding instead.\n"
            )
            style_rules = (
                "- Vary sentence length: mix short, direct sentences with longer "
                "ones; avoid a uniform rhythm.\n"
                "- Do NOT use the 'balanced approach' / 'double-edged sword' "
                "refrain, and do NOT stack connectives (moreover, furthermore, "
                "in conclusion) in every paragraph.\n"
                "- Limit hedging: verbs like 'può'/'potrebbe' (or 'may'/'might') "
                "at most once per paragraph. Where a listed source supports a "
                "claim, state it assertively with its citation instead of "
                "hedging.\n"
                "- Do NOT restate the introduction or pad with generic filler; "
                "every paragraph must add specific content.\n"
            )
        else:
            sources_text = ""
            if retrieved_sources:
                sources_text = "\n\nRelevant academic sources:\n"
                for i, source in enumerate(retrieved_sources[:5], 1):  # top 5
                    sources_text += f"{i}. {source}\n"
            citation_rules = (
                "- Appropriate citations (use [Author, Year] format for in-text "
                "citations)\n"
                "- Integration of relevant sources from the provided academic "
                "literature\n"
            )
            style_rules = "- Clear transitions between paragraphs\n"

        # Language names for clear instruction
        language_names = {
            "en": "English",
            "it": "italiano (Italian)",
            "es": "español (Spanish)",
            "de": "Deutsch (German)",
            "cs": "čeština (Czech)",
            "fr": "français (French)",
            "uk": "українська (Ukrainian)",
        }
        lang_name = language_names.get(document.language, document.language)

        prompt = f"""CRITICAL INSTRUCTION - READ CAREFULLY:
You MUST write this ENTIRE response in {lang_name}.
Using ANY other language (especially English) is STRICTLY FORBIDDEN.

Write a comprehensive academic section for a thesis with the following details:

Document Topic: {document.topic}
Section Title: {section_title}
Section Index: {section_index}
Language: {document.language}
Target Pages: {document.target_pages}
{context_text}
{sources_text}
Please write this section with:
- Academic tone and style
- Proper structure and flow
- Evidence-based arguments
{citation_rules}{style_rules}- Professional language suitable for academic publication

Additional Requirements: {additional_requirements or 'None specified'}

Please provide only the section content without any meta-commentary."""
        return prompt.strip()

    @staticmethod
    def build_humanization_prompt(
        original_text: str,
        preserve_citations: bool = True,
        language: str = "en",
        style_directive: str = "",
    ) -> str:
        """
        Build prompt for text humanization/paraphrasing

        Args:
            original_text: Original text to humanize
            preserve_citations: Whether to preserve citation markers
            language: Target language code (en, it, es, de, cs, fr, uk)

        Returns:
            Formatted prompt string
        """
        # Language names for clear instruction
        language_names = {
            "en": "English",
            "it": "italiano (Italian)",
            "es": "español (Spanish)",
            "de": "Deutsch (German)",
            "cs": "čeština (Czech)",
            "fr": "français (French)",
            "uk": "українська (Ukrainian)",
        }
        lang_name = language_names.get(language, language)

        citation_instruction = (
            "IMPORTANT: Preserve all citation markers in the format [Author, Year] exactly as they appear."
            if preserve_citations
            else "You may adjust citation formatting if needed."
        )

        prompt = f"""IMPORTANT: Keep the text strictly in {lang_name}. Do not translate to any other language.

Paraphrase and humanize the following academic text while maintaining its meaning,
academic quality, and structure. Make it sound more natural and less AI-generated.

{citation_instruction}

Original text:
{original_text}

Requirements:
- Maintain the same academic tone and quality
- Keep all key information and arguments
- Make the language flow more naturally
- Preserve the logical structure
- Ensure the text reads as if written by a human academic researcher
- {citation_instruction}
{style_directive}
Provide only the paraphrased text without any meta-commentary."""
        return prompt.strip()

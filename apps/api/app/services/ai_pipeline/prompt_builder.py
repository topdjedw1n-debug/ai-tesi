"""
Prompt builder for AI generation
Constructs prompts for outline and section generation
"""

from typing import Any

from app.models.document import Document

# Multilingual system prompts for AI models
SYSTEM_PROMPTS = {
    'en': "You are an expert academic writer specializing in thesis and research paper generation.",
    'it': "Sei un esperto scrittore accademico specializzato nella generazione di tesi e lavori di ricerca.",
    'es': "Eres un escritor académico experto especializado en la generación de tesis y trabajos de investigación.",
    'de': "Sie sind ein erfahrener akademischer Autor, der auf die Erstellung von Abschlussarbeiten und Forschungsarbeiten spezialisiert ist.",
    'cs': "Jste odborný akademický autor specializující se na tvorbu diplomových a výzkumných prací.",
    'fr': "Vous êtes un rédacteur académique expert spécialisé dans la génération de thèses et de travaux de recherche.",
    'uk': "Ви експерт з академічного письма, що спеціалізується на створенні дипломних та дослідницьких робіт."
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
        return SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS['en'])

    @staticmethod
    def build_outline_prompt(
        document: Document, additional_requirements: str | None = None
    ) -> str:
        """
        Build prompt for outline generation

        Args:
            document: Document model instance
            additional_requirements: Optional additional user requirements

        Returns:
            Formatted prompt string
        """
        # Language map for explicit instructions
        language_instructions = {
            'en': 'Write ONLY in English',
            'it': 'Scrivi SOLO in italiano',
            'de': 'Schreiben Sie NUR auf Deutsch',
            'fr': 'Écrivez UNIQUEMENT en français',
            'es': 'Escribe SOLO en español',
            'cs': 'Pište POUZE v češtině',
            'uk': 'Пишіть ТІЛЬКИ українською',
        }
        lang_instruction = language_instructions.get(document.language, f'Write ONLY in {document.language}')
        
        prompt = f"""IMPORTANT: {lang_instruction}. Do not use any other language.

Generate a detailed academic thesis outline for the following topic:

Topic: {document.topic}
Language: {document.language}
Target Pages: {document.target_pages}

Please provide a structured outline with:
1. Introduction
2. Literature Review
3. Methodology
4. Results/Analysis
5. Discussion
6. Conclusion
7. References

For each section, include:
- Main points to cover
- Sub-sections
- Estimated word count
- Key concepts to address

Additional Requirements: {additional_requirements or 'None specified'}

Please respond with a JSON structure containing the outline data."""
        return prompt.strip()

    @staticmethod
    def build_section_prompt(
        document: Document,
        section_title: str,
        section_index: int,
        context_sections: list[dict[str, Any]] | None = None,
        retrieved_sources: list[str] | None = None,
        additional_requirements: str | None = None,
    ) -> str:
        """
        Build prompt for section generation with RAG context

        Args:
            document: Document model instance
            section_title: Title of the section to generate
            section_index: Index of the section
            context_sections: Previously generated sections for context
            retrieved_sources: Retrieved source documents from RAG
            additional_requirements: Optional additional user requirements

        Returns:
            Formatted prompt string
        """
        context_text = ""
        if context_sections:
            context_text = "\n\nPrevious sections context:\n"
            for section in context_sections:
                context_text += f"- {section.get('title', 'Unknown')}: {section.get('content', '')[:200]}...\n"

        sources_text = ""
        if retrieved_sources:
            sources_text = "\n\nRelevant academic sources:\n"
            for i, source in enumerate(retrieved_sources[:5], 1):  # Limit to top 5
                sources_text += f"{i}. {source}\n"

        # Language names for clear instruction
        language_names = {
            'en': 'English',
            'it': 'italiano (Italian)',
            'es': 'español (Spanish)',
            'de': 'Deutsch (German)',
            'cs': 'čeština (Czech)',
            'fr': 'français (French)',
            'uk': 'українська (Ukrainian)'
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
- Appropriate citations (use [Author, Year] format for in-text citations)
- Clear transitions between paragraphs
- Professional language suitable for academic publication
- Integration of relevant sources from the provided academic literature

Additional Requirements: {additional_requirements or 'None specified'}

Please provide only the section content without any meta-commentary."""
        return prompt.strip()

    @staticmethod
    def build_humanization_prompt(
        original_text: str, preserve_citations: bool = True
    ) -> str:
        """
        Build prompt for text humanization/paraphrasing

        Args:
            original_text: Original text to humanize
            preserve_citations: Whether to preserve citation markers

        Returns:
            Formatted prompt string
        """
        citation_instruction = (
            "IMPORTANT: Preserve all citation markers in the format [Author, Year] exactly as they appear."
            if preserve_citations
            else "You may adjust citation formatting if needed."
        )

        prompt = f"""Paraphrase and humanize the following academic text while maintaining its meaning,
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

Provide only the paraphrased text without any meta-commentary."""
        return prompt.strip()

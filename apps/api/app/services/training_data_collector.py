"""
Training data collection service for AI self-learning
Collects successful generation patterns for future model improvements
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class TrainingDataCollector:
    """Collect training data from successful generations"""

    def __init__(self, data_dir: str | None = None):
        """
        Initialize training data collector

        Args:
            data_dir: Directory to store training data (default: /tmp/training_data)
        """
        self.data_dir = Path(data_dir) if data_dir else Path("/tmp/training_data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.enabled = getattr(settings, "TRAINING_DATA_COLLECTION_ENABLED", False)

    async def collect_generation_sample(
        self,
        document_id: int,
        section_title: str,
        prompt: str,
        generated_content: str,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Collect a successful generation sample

        Args:
            document_id: Document ID
            section_title: Section title
            prompt: Input prompt used
            generated_content: Generated content
            context: Additional context (RAG sources, etc.)
            metadata: Additional metadata (model, provider, tokens, etc.)
        """
        if not self.enabled:
            return

        try:
            sample = {
                "timestamp": datetime.utcnow().isoformat(),
                "document_id": document_id,
                "section_title": section_title,
                "prompt": prompt,
                "generated_content": generated_content,
                "context": context or {},
                "metadata": metadata or {},
            }

            # Save to file (one file per day)
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            file_path = self.data_dir / f"training_data_{date_str}.jsonl"

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

            logger.debug(f"Collected training sample for document {document_id}")

        except Exception as e:
            logger.warning(f"Error collecting training data: {e}")

    async def collect_outline_sample(
        self,
        document_id: int,
        topic: str,
        requirements: str | None,
        generated_outline: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Collect an outline generation sample

        Args:
            document_id: Document ID
            topic: Document topic
            requirements: Additional requirements
            generated_outline: Generated outline structure
            metadata: Additional metadata
        """
        if not self.enabled:
            return

        try:
            sample = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "outline",
                "document_id": document_id,
                "topic": topic,
                "requirements": requirements,
                "generated_outline": generated_outline,
                "metadata": metadata or {},
            }

            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            file_path = self.data_dir / f"training_data_{date_str}.jsonl"

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

            logger.debug(
                f"Collected outline training sample for document {document_id}"
            )

        except Exception as e:
            logger.warning(f"Error collecting outline training data: {e}")

    def get_training_stats(self) -> dict[str, Any]:
        """
        Get statistics about collected training data

        Returns:
            Dictionary with statistics
        """
        try:
            files = list(self.data_dir.glob("training_data_*.jsonl"))
            total_samples = 0

            for file_path in files:
                with open(file_path, encoding="utf-8") as f:
                    total_samples += sum(1 for _ in f)

            return {
                "enabled": self.enabled,
                "data_dir": str(self.data_dir),
                "total_files": len(files),
                "total_samples": total_samples,
            }
        except Exception as e:
            logger.error(f"Error getting training stats: {e}")
            return {
                "enabled": self.enabled,
                "error": str(e),
            }


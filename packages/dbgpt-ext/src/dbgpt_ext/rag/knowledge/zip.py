"""Zip Knowledge."""

import os
import zipfile
from typing import Any, Dict, List, Optional, Union

from dbgpt.component import logger
from dbgpt.core import Document
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    DocumentType,
    Knowledge,
    KnowledgeType,
)
from dbgpt_ext.rag.knowledge import KnowledgeFactory


class ZipKnowledge(Knowledge):
    """Zip Knowledge for handling archive files with multiple documents."""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: KnowledgeType = KnowledgeType.DOCUMENT,
        loader: Optional[Any] = None,
        extract_path: Optional[str] = None,
        metadata: Optional[Dict[str, Union[str, List[str]]]] = None,
        **kwargs: Any,
    ) -> None:
        """Create Zip Knowledge with Knowledge arguments.

        Args:
            file_path (str, optional): Path to the ZIP file
            knowledge_type (KnowledgeType, optional): Knowledge type
            loader (Any, optional): Custom loader if provided
            extract_path (str, optional): Path where to extract ZIP contents temporarily
            metadata (Dict[str, Union[str, List[str]]], optional): Additional metadata
        """
        super().__init__(
            path=file_path,
            knowledge_type=knowledge_type,
            data_loader=loader,
            metadata=metadata,
            **kwargs,
        )
        self._extract_path = extract_path or os.path.join(
            os.path.dirname(file_path), "temp_extract"
        )

    def _load(self) -> List[Document]:
        """Load documents from ZIP archive.

        Extracts supported document types from the ZIP file and processes them
        using their respective Knowledge implementations.
        """
        if self._loader:
            documents = self._loader.load()
            return [Document.langchain2doc(lc_document) for lc_document in documents]

        documents = []

        # Create temporary extraction directory if it doesn't exist
        os.makedirs(self._extract_path, exist_ok=True)

        try:
            with zipfile.ZipFile(self._path, "r") as zip_ref:
                # Extract all files
                zip_ref.extractall(self._extract_path)

                # Get all knowledge subclasses to check supported document types
                knowledge_classes = KnowledgeFactory._get_knowledge_subclasses()
                supported_extensions = {
                    cls.document_type().value
                    for cls in knowledge_classes
                    if cls.document_type() is not None
                }

                # Process all extracted files
                for root, _, files in os.walk(self._extract_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        extension = file.rsplit(".", 1)[-1].lower()

                        # Skip unsupported files
                        if extension not in supported_extensions:
                            logger.warning(f"Skipping unsupported file type: {file}")
                            continue

                        try:
                            # Create metadata with reference to original zip file
                            file_metadata = {
                                "source": self._path,
                                "original_zip": os.path.basename(self._path),
                                "extracted_file": file,
                                "zip_path": os.path.relpath(
                                    file_path, self._extract_path
                                ),
                            }
                            if self._metadata:
                                file_metadata.update(self._metadata)

                            # Use KnowledgeFactory to create
                            # appropriate knowledge object
                            knowledge = KnowledgeFactory.from_file_path(
                                file_path=file_path,
                                knowledge_type=self._type,
                                metadata=file_metadata,
                            )

                            # Load documents from the file
                            file_documents = knowledge.load()
                            documents.extend(file_documents)
                            logger.info(f"Processed {file} from ZIP archive")

                        except Exception as e:
                            logger.error(
                                f"Error processing file {file} from ZIP: {str(e)}"
                            )

        except Exception as e:
            logger.error(f"Error processing ZIP file {self._path}: {str(e)}")

        finally:
            # Clean up extracted files
            import shutil

            if os.path.exists(self._extract_path):
                shutil.rmtree(self._extract_path)

        return documents

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return support chunk strategy."""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_PARAGRAPH,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy."""
        return ChunkStrategy.CHUNK_BY_SIZE

    @classmethod
    def type(cls) -> KnowledgeType:
        """Return knowledge type."""
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        """Return document type."""
        return DocumentType.ZIP

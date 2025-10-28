"""
olmOCR JSONL Parser for RAG

Parse olmOCR JSONL output into page-level chunks with rich metadata.
Perfect for RAG workflows with citation support, language filtering, and table detection.

Author: Youssef Harby
License: Apache 2.0
"""

import json
from pathlib import Path

from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, IntInput, MessageTextInput, MultilineInput, Output, StrInput
from langflow.schema import Data, DataFrame, Message


class OlmOCRJSONLParser(Component):
    """
    olmOCR JSONL Parser

    Parse olmOCR JSONL output into RAG-ready chunks with page-level metadata.
    Supports language filtering, table detection, and multiple chunking strategies.
    """

    display_name = "olmOCR - JSONL Parser"
    description = "Parse olmOCR JSONL to page-level chunks with metadata for RAG workflows"
    documentation = "https://github.com/allenai/olmocr"
    icon = "file-json"
    name = "OlmOCRJSONLParser"

    inputs = [
        StrInput(
            name="workspace_path",
            display_name="Workspace Path",
            info="Path to olmOCR workspace (from Directory Processor processing_data.workspace)",
            required=True,
            input_types=["Text"],
        ),
        DropdownInput(
            name="chunking_strategy",
            display_name="Chunking Strategy",
            info="How to split documents into chunks",
            options=["page", "semantic", "fixed_size"],
            value="page",
            advanced=False,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size (chars)",
            info="Target chunk size for fixed_size strategy (0 = use page strategy)",
            value=1000,
            advanced=True,
        ),
        IntInput(
            name="chunk_overlap",
            display_name="Chunk Overlap (chars)",
            info="Character overlap between chunks for fixed_size strategy",
            value=200,
            advanced=True,
        ),
        MultilineInput(
            name="language_filter",
            display_name="Language Filter",
            info="Comma-separated language codes to include (e.g., 'ar,en'). Leave empty for all languages.",
            value="",
            advanced=True,
        ),
        BoolInput(
            name="include_tables",
            display_name="Include Tables",
            info="Include pages that contain tables",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="include_diagrams",
            display_name="Include Diagrams",
            info="Include pages that contain diagrams",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="min_chars_per_chunk",
            display_name="Min Characters",
            info="Minimum characters per chunk (filters out very short pages)",
            value=50,
            advanced=True,
        ),
        IntInput(
            name="max_chunks",
            display_name="Max Chunks",
            info="Maximum number of chunks to output (0 = unlimited)",
            value=0,
            advanced=True,
        ),
        BoolInput(
            name="verbose",
            display_name="Verbose Logging",
            info="Enable detailed logging",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Data",
            name="data_output",
            method="parse_jsonl",
        ),
        Output(
            display_name="DataFrame",
            name="dataframe_output",
            method="get_dataframe",
        ),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._chunks = None
        self._stats = None

    def _parse_language_filter(self) -> list[str]:
        """Parse language filter string to list."""
        if not self.language_filter or not self.language_filter.strip():
            return []
        return [lang.strip().lower() for lang in self.language_filter.split(",") if lang.strip()]
 
    def get_dataframe(self) -> DataFrame:
        """Convert the parsed chunks to a DataFrame for Loop component compatibility."""
        # First ensure we have parsed the data
        chunks = self.parse_jsonl()
        
        if not chunks:
            # Return empty DataFrame
            return DataFrame(data=[])
        
        # Convert Data objects to DataFrame rows
        rows = []
        for chunk in chunks:
            # Create a row with text and flattened metadata
            row = {
                "text": chunk.text,
                "source_file": chunk.data.get("source_file", ""),
                "page_number": chunk.data.get("page_number", 0),
                "language": chunk.data.get("language", "unknown"),
                "has_table": chunk.data.get("has_table", False),
                "has_diagram": chunk.data.get("has_diagram", False),
                "char_count": chunk.data.get("char_count", 0),
                "chunk_index": chunk.data.get("chunk_index", 0),
                "chunking_strategy": chunk.data.get("chunking_strategy", "page"),
            }
            rows.append(row)
        
        return DataFrame(data=rows)

    def _chunk_by_page(self, text: str, page_boundaries: list, metadata: dict, attributes: dict) -> list[Data]:
        """Create one chunk per page."""
        chunks = []
        language_filters = self._parse_language_filter()

        for i, (start, end, page_num) in enumerate(page_boundaries):
            # Get page metadata
            page_language = attributes["primary_language"][i] if i < len(attributes["primary_language"]) else "unknown"
            has_table = attributes["is_table"][i] if i < len(attributes["is_table"]) else False
            has_diagram = attributes["is_diagram"][i] if i < len(attributes["is_diagram"]) else False

            # Apply filters
            if language_filters and page_language not in language_filters:
                if self.verbose:
                    self.log(f"Skipping page {page_num} (language: {page_language})")
                continue

            if not self.include_tables and has_table:
                if self.verbose:
                    self.log(f"Skipping page {page_num} (contains table)")
                continue

            if not self.include_diagrams and has_diagram:
                if self.verbose:
                    self.log(f"Skipping page {page_num} (contains diagram)")
                continue

            # Extract page text
            page_text = text[start:end]

            # Apply minimum character filter
            if len(page_text) < self.min_chars_per_chunk:
                if self.verbose:
                    self.log(f"Skipping page {page_num} (too short: {len(page_text)} chars)")
                continue

            # Create chunk
            chunk_data = Data(
                text=page_text,
                data={
                    "source_file": Path(metadata.get("Source-File", "unknown")).name,
                    "source_file_full_path": metadata.get("Source-File", "unknown"),
                    "page_number": page_num,
                    "total_pages": metadata.get("pdf-total-pages", 0),
                    "language": page_language,
                    "has_table": has_table,
                    "has_diagram": has_diagram,
                    "char_start": start,
                    "char_end": end,
                    "char_count": end - start,
                    "chunk_index": len(chunks),
                    "chunking_strategy": "page",
                    "olmocr_version": metadata.get("olmocr-version", "unknown"),
                }
            )
            chunks.append(chunk_data)

        return chunks

    def _chunk_by_fixed_size(self, text: str, page_boundaries: list, metadata: dict, attributes: dict) -> list[Data]:
        """Create fixed-size chunks with overlap."""
        chunks = []
        language_filters = self._parse_language_filter()

        # Map character positions to pages
        char_to_page = {}
        for i, (start, end, page_num) in enumerate(page_boundaries):
            for pos in range(start, end):
                char_to_page[pos] = {
                    "page_num": page_num,
                    "language": attributes["primary_language"][i] if i < len(attributes["primary_language"]) else "unknown",
                    "has_table": attributes["is_table"][i] if i < len(attributes["is_table"]) else False,
                    "has_diagram": attributes["is_diagram"][i] if i < len(attributes["is_diagram"]) else False,
                }

        # Create fixed-size chunks
        pos = 0
        chunk_index = 0
        while pos < len(text):
            chunk_end = min(pos + self.chunk_size, len(text))
            chunk_text = text[pos:chunk_end]

            # Get metadata for this chunk (from first character)
            chunk_meta = char_to_page.get(pos, {
                "page_num": 0,
                "language": "unknown",
                "has_table": False,
                "has_diagram": False
            })

            # Apply filters
            if language_filters and chunk_meta["language"] not in language_filters:
                pos += self.chunk_size - self.chunk_overlap
                continue

            if not self.include_tables and chunk_meta["has_table"]:
                pos += self.chunk_size - self.chunk_overlap
                continue

            if not self.include_diagrams and chunk_meta["has_diagram"]:
                pos += self.chunk_size - self.chunk_overlap
                continue

            if len(chunk_text) < self.min_chars_per_chunk:
                pos += self.chunk_size - self.chunk_overlap
                continue

            # Create chunk
            chunk_data = Data(
                text=chunk_text,
                data={
                    "source_file": Path(metadata.get("Source-File", "unknown")).name,
                    "source_file_full_path": metadata.get("Source-File", "unknown"),
                    "page_number": chunk_meta["page_num"],
                    "total_pages": metadata.get("pdf-total-pages", 0),
                    "language": chunk_meta["language"],
                    "has_table": chunk_meta["has_table"],
                    "has_diagram": chunk_meta["has_diagram"],
                    "char_start": pos,
                    "char_end": chunk_end,
                    "char_count": len(chunk_text),
                    "chunk_index": chunk_index,
                    "chunking_strategy": "fixed_size",
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                    "olmocr_version": metadata.get("olmocr-version", "unknown"),
                }
            )
            chunks.append(chunk_data)
            chunk_index += 1

            # Move to next chunk with overlap
            pos += self.chunk_size - self.chunk_overlap

        return chunks

    def _chunk_semantic(self, text: str, page_boundaries: list, metadata: dict, attributes: dict) -> list[Data]:
        """Create semantic chunks (split by paragraphs within pages)."""
        chunks = []
        language_filters = self._parse_language_filter()

        for i, (start, end, page_num) in enumerate(page_boundaries):
            # Get page metadata
            page_language = attributes["primary_language"][i] if i < len(attributes["primary_language"]) else "unknown"
            has_table = attributes["is_table"][i] if i < len(attributes["is_table"]) else False
            has_diagram = attributes["is_diagram"][i] if i < len(attributes["is_diagram"]) else False

            # Apply filters
            if language_filters and page_language not in language_filters:
                continue
            if not self.include_tables and has_table:
                continue
            if not self.include_diagrams and has_diagram:
                continue

            # Extract page text
            page_text = text[start:end]

            # Split by paragraphs (double newline)
            paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]

            # If no paragraphs found, treat whole page as one chunk
            if not paragraphs:
                paragraphs = [page_text]

            # Create chunks from paragraphs
            for para_idx, paragraph in enumerate(paragraphs):
                if len(paragraph) < self.min_chars_per_chunk:
                    continue

                chunk_data = Data(
                    text=paragraph,
                    data={
                        "source_file": Path(metadata.get("Source-File", "unknown")).name,
                        "source_file_full_path": metadata.get("Source-File", "unknown"),
                        "page_number": page_num,
                        "total_pages": metadata.get("pdf-total-pages", 0),
                        "language": page_language,
                        "has_table": has_table,
                        "has_diagram": has_diagram,
                        "char_count": len(paragraph),
                        "chunk_index": len(chunks),
                        "paragraph_index": para_idx,
                        "chunking_strategy": "semantic",
                        "olmocr_version": metadata.get("olmocr-version", "unknown"),
                    }
                )
                chunks.append(chunk_data)

        return chunks

    def parse_jsonl(self) -> list[Data]:
        """Parse JSONL files and create chunks."""
        # Return empty list during build phase
        if not self.workspace_path or not self.workspace_path.strip():
            if self.verbose:
                self.log("Workspace path is empty - this is normal during flow build/validation")
            self.status = []
            return []

        try:
            self.log("Starting olmOCR JSONL parsing")

            # Validate workspace path
            workspace = Path(self.workspace_path).expanduser().resolve()
            if not workspace.exists():
                self.log(f"Workspace not found: {workspace}")
                self.status = []
                return []

            # Find results directory
            results_dir = workspace / "results"
            if not results_dir.exists():
                self.log(f"Results directory not found: {results_dir}")
                self.status = []
                return []

            # Find JSONL files
            jsonl_files = list(results_dir.glob("*.jsonl"))
            if not jsonl_files:
                self.log(f"No JSONL files in {results_dir}")
                self.status = []
                return []

            self.log(f"Found {len(jsonl_files)} JSONL file(s)")

            # Parse all JSONL files
            all_chunks = []
            docs_processed = 0

            for jsonl_file in jsonl_files:
                if self.verbose:
                    self.log(f"Processing: {jsonl_file.name}")

                try:
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if not line.strip():
                                continue

                            doc = json.loads(line)

                            # Extract data
                            text = doc.get('text', '')
                            metadata = doc.get('metadata', {})
                            attributes = doc.get('attributes', {})
                            page_boundaries = attributes.get('pdf_page_numbers', [])

                            if not text or not page_boundaries:
                                self.log(f"Skipping empty document in {jsonl_file.name}")
                                continue

                            # Apply chunking strategy
                            if self.chunking_strategy == "page":
                                chunks = self._chunk_by_page(text, page_boundaries, metadata, attributes)
                            elif self.chunking_strategy == "fixed_size":
                                chunks = self._chunk_by_fixed_size(text, page_boundaries, metadata, attributes)
                            elif self.chunking_strategy == "semantic":
                                chunks = self._chunk_semantic(text, page_boundaries, metadata, attributes)
                            else:
                                chunks = self._chunk_by_page(text, page_boundaries, metadata, attributes)

                            all_chunks.extend(chunks)
                            docs_processed += 1

                            if self.verbose:
                                self.log(f"Extracted {len(chunks)} chunks from document {docs_processed}")

                except json.JSONDecodeError as e:
                    self.log(f"Failed to parse {jsonl_file.name}: {e}")
                except Exception as e:
                    self.log(f"Error processing {jsonl_file.name}: {e}")

            # Apply max chunks limit
            if self.max_chunks > 0 and len(all_chunks) > self.max_chunks:
                self.log(f"Limiting output to {self.max_chunks} chunks (found {len(all_chunks)})")
                all_chunks = all_chunks[:self.max_chunks]

            # Store results
            self._chunks = all_chunks
            self._stats = {
                "total_chunks": len(all_chunks),
                "documents_processed": docs_processed,
                "jsonl_files": len(jsonl_files),
                "chunking_strategy": self.chunking_strategy,
                "workspace_path": str(workspace),
            }

            success_msg = f"✓ Parsed {docs_processed} document(s) into {len(all_chunks)} chunk(s)"
            # Set status to the actual data (official Langflow pattern)
            self.status = all_chunks
            self.log(success_msg)

            # Log sample chunk for verification
            if all_chunks and self.verbose:
                sample = all_chunks[0]
                self.log(f"Sample chunk structure:")
                self.log(f"  Text preview: {sample.text[:100]}...")
                self.log(f"  Metadata keys: {list(sample.data.keys())}")
                self.log(f"  Source: {sample.data.get('source_file')}, Page: {sample.data.get('page_number')}")

            return all_chunks

        except Exception as e:
            error_msg = f"Error parsing JSONL: {str(e)}"
            self.status = []
            self.log(error_msg)
            return []

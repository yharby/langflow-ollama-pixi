"""
olmOCR Component with Language Model Input

Connect any Language Model component (LM Studio, OpenAI, etc.) to olmOCR.
Automatically extracts the API endpoint and credentials from the connected model.

Author: Youssef Harby
License: Apache 2.0
"""

import json
import subprocess
import tempfile
from pathlib import Path

from langflow.custom import Component
from langflow.field_typing import LanguageModel
from langflow.io import BoolInput, FileInput, HandleInput, IntInput, Output
from langflow.schema import Message


class OlmOCRWithModel(Component):
    """
    olmOCR with Language Model

    Connect a Language Model component (LM Studio, OpenAI, etc.) to use for PDF conversion.
    Automatically extracts API endpoint and credentials from the connected model.
    """

    display_name = "olmOCR with Language Model"
    description = "Convert PDFs to markdown using any connected Language Model component"
    documentation = "https://github.com/allenai/olmocr"
    icon = "file-text"
    name = "OlmOCRWithModel"

    inputs = [
        FileInput(
            name="pdf_files",
            display_name="PDF Files",
            info="Upload one or more PDF files to convert",
            file_types=["pdf"],
            list=True,
            required=True,
        ),
        HandleInput(
            name="language_model",
            display_name="Language Model",
            input_types=["LanguageModel"],
            info="Connect a Language Model component (LM Studio, OpenAI, etc.)",
            required=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="Maximum time to wait for conversion (default: 300 seconds)",
            value=300,
            advanced=True,
        ),
        BoolInput(
            name="verbose",
            display_name="Verbose Logging",
            info="Enable detailed logging for troubleshooting",
            value=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Markdown Content",
            name="markdown_output",
            method="convert_to_markdown",
        ),
    ]

    def _extract_model_config(self, language_model: LanguageModel) -> dict:
        """Extract API configuration from the language model.

        Supports ChatOpenAI (LM Studio, OpenAI) and other OpenAI-compatible models.
        """
        try:
            # Extract base URL - try direct attribute access first
            base_url = None
            if hasattr(language_model, 'base_url') and language_model.base_url:
                base_url = str(language_model.base_url)
            elif hasattr(language_model, 'openai_api_base'):
                base_url = str(language_model.openai_api_base)

            # Extract API key - try direct attribute access first
            api_key = None
            if hasattr(language_model, 'api_key') and language_model.api_key:
                api_key = str(language_model.api_key)
            elif hasattr(language_model, 'openai_api_key'):
                api_key = str(language_model.openai_api_key)

            # Extract model name - try direct attribute access first
            model_name = None
            if hasattr(language_model, 'model') and language_model.model:
                model_name = str(language_model.model)
            elif hasattr(language_model, 'model_name'):
                model_name = str(language_model.model_name)

            # If direct access didn't work, try dict/dump methods as fallback
            if not all([base_url, api_key, model_name]):
                if hasattr(language_model, '_lc_kwargs'):
                    config = language_model._lc_kwargs
                elif hasattr(language_model, 'model_dump'):
                    config = language_model.model_dump()
                elif hasattr(language_model, 'dict'):
                    config = language_model.dict()
                else:
                    config = {}

                if config and self.verbose:
                    self.log(f"Fallback config keys: {list(config.keys())}")

                # Try to extract from config dict
                if not base_url:
                    base_url = config.get('base_url') or config.get('openai_api_base')
                if not api_key:
                    api_key = config.get('api_key') or config.get('openai_api_key')
                if not model_name:
                    model_name = config.get('model') or config.get('model_name')

            # Fix base_url: Remove trailing /v1 or /v1/openai if present
            # LM Studio returns http://127.0.0.1:1234/v1, but olmOCR expects http://127.0.0.1:1234
            # because it appends OpenAI-compatible paths itself
            if base_url:
                base_url = base_url.rstrip('/')
                if base_url.endswith('/v1/openai'):
                    base_url = base_url[:-len('/v1/openai')]
                elif base_url.endswith('/v1'):
                    base_url = base_url[:-len('/v1')]
                self.log(f"Using base URL: {base_url}")

            if self.verbose:
                self.log(f"Extracted - base_url: {base_url}, model: {model_name}, api_key: {'***' if api_key else None}")

            return {
                'base_url': base_url,
                'api_key': api_key,
                'model_name': model_name,
            }

        except Exception as e:
            self.log(f"Error extracting model config: {e}")
            return {'base_url': None, 'api_key': None, 'model_name': None}

    def convert_to_markdown(self) -> Message:
        """Convert PDFs to markdown using connected language model."""
        try:
            self.status = "Initializing olmOCR conversion..."
            self.log("Starting olmOCR PDF conversion with Language Model")

            # Validate PDF files input
            if not self.pdf_files:
                error_msg = "No PDF files provided. Please upload at least one PDF file."
                self.status = error_msg
                self.log(error_msg)
                raise ValueError(error_msg)

            # Validate language model input
            if not self.language_model:
                error_msg = "No Language Model connected. Please connect a Language Model component (LM Studio, OpenAI, etc.)."
                self.status = error_msg
                self.log(error_msg)
                raise ValueError(error_msg)

            # Extract model configuration
            self.status = "Extracting Language Model configuration..."
            model_config = self._extract_model_config(self.language_model)

            base_url = model_config.get('base_url')
            api_key = model_config.get('api_key')
            model_name = model_config.get('model_name')

            if not base_url:
                error_msg = (
                    "Could not extract API endpoint from Language Model. "
                    "Please ensure the connected model has a base_url configured (e.g., LM Studio, OpenAI)."
                )
                self.status = "Configuration error"
                self.log(error_msg)
                raise ValueError(error_msg)

            self.log(f"Using API endpoint: {base_url}")
            if model_name:
                self.log(f"Using model: {model_name}")

            # Create temporary workspace
            workspace = Path(tempfile.mkdtemp(prefix="olmocr_langflow_"))
            if self.verbose:
                self.log(f"Created workspace: {workspace}")
            self.status = "Preparing to convert PDFs..."

            # Validate and collect PDF paths
            pdf_paths = []
            invalid_files = []

            for file_path in self.pdf_files:
                path = Path(file_path) if isinstance(file_path, str) else Path(file_path)

                if self.verbose:
                    self.log(f"Validating file: {path.name}")

                if not path.exists():
                    invalid_files.append(f"{path.name} (file not found)")
                elif path.suffix.lower() != ".pdf":
                    invalid_files.append(f"{path.name} (not a PDF file)")
                else:
                    pdf_paths.append(str(path))

            # Log validation results
            if invalid_files:
                self.log(f"Skipped {len(invalid_files)} invalid file(s): {', '.join(invalid_files)}")

            self.log(f"Found {len(pdf_paths)} valid PDF file(s)")

            if not pdf_paths:
                error_msg = f"No valid PDF files found. Invalid files: {', '.join(invalid_files)}"
                self.status = "Validation failed"
                self.log(error_msg)
                raise ValueError(error_msg)

            # Build olmocr command
            cmd = [
                "pixi", "run",
                "--environment", "olmocr",
                "python", "-m", "olmocr.pipeline",
                str(workspace),
                "--server", base_url,
                "--markdown",
                "--pdfs"
            ] + pdf_paths

            # Add API key if available (skip for local servers or placeholder keys)
            if api_key and api_key not in ['LMSTUDIO_API_KEY', 'lm-studio', 'not-needed']:
                cmd.extend(["--api_key", api_key])

            # Add model name if available
            if model_name:
                cmd.extend(["--model", model_name])

            self.status = f"Converting {len(pdf_paths)} PDF(s) using Language Model..."

            if self.verbose:
                self.log(f"Executing command: pixi run --environment olmocr python -m olmocr.pipeline...")

            # Run olmocr
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                cwd=str(Path.cwd()),
            )

            self.log(f"Conversion process completed (exit code: {result.returncode})")

            # Log stderr output if verbose
            if self.verbose and result.stderr:
                self.log(f"Process output:\n{result.stderr}")

            # Check for errors
            if result.returncode != 0:
                error_msg = f"olmOCR conversion failed with exit code {result.returncode}: {result.stderr[:300]}"
                self.status = "Conversion failed"
                self.log(error_msg)
                raise RuntimeError(error_msg)

            # Read results from JSONL files
            results_dir = workspace / "results"
            if self.verbose:
                self.log(f"Reading results from: {results_dir}")

            if not results_dir.exists():
                error_msg = "No results directory found in workspace. Conversion may have failed silently."
                self.status = error_msg
                self.log(error_msg)
                raise RuntimeError(error_msg)

            # Read JSONL files and extract markdown content
            markdown_parts = []
            jsonl_files = list(results_dir.glob("*.jsonl"))

            self.log(f"Found {len(jsonl_files)} result file(s)")

            # Read and parse JSONL files
            for jsonl_file in jsonl_files:
                if self.verbose:
                    self.log(f"Reading: {jsonl_file.name}")

                try:
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                        if self.verbose and not file_content.strip():
                            self.log(f"WARNING: {jsonl_file.name} is empty!")

                        f.seek(0)  # Reset to beginning
                        for line_num, line in enumerate(f, 1):
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    if self.verbose:
                                        self.log(f"Line {line_num} keys: {list(data.keys())}")
                                    text_content = data.get('text', '')
                                    if text_content:
                                        markdown_parts.append(text_content)
                                        if self.verbose:
                                            self.log(f"Extracted {len(text_content)} characters from document")
                                    elif self.verbose:
                                        self.log(f"Line {line_num} has no 'text' field")
                                except json.JSONDecodeError as e:
                                    self.log(f"Failed to parse JSON on line {line_num} in {jsonl_file.name}: {e}")
                                    if self.verbose:
                                        self.log(f"Problematic line: {line[:100]}...")
                except Exception as e:
                    self.log(f"Error reading {jsonl_file.name}: {e}")

            if not markdown_parts:
                error_msg = f"No content extracted from {len(jsonl_files)} result file(s). Please check if PDFs are valid and readable."
                self.status = error_msg
                self.log(error_msg)
                raise RuntimeError(error_msg)

            # Combine all markdown
            combined_markdown = "\n\n---\n\n".join(markdown_parts)

            # Add source file info if single PDF
            if len(pdf_paths) == 1:
                pdf_name = Path(pdf_paths[0]).name
                combined_markdown = f"# {pdf_name}\n\n{combined_markdown}"

            success_msg = f"✓ Successfully converted {len(pdf_paths)} PDF(s) using Language Model"
            self.status = success_msg
            self.log(success_msg)

            return Message(
                text=combined_markdown,
                data={
                    "total_files": len(pdf_paths),
                    "extracted_documents": len(markdown_parts),
                    "model_endpoint": base_url,
                    "model_name": model_name or "unknown",
                    "workspace": str(workspace),
                },
            )

        except subprocess.TimeoutExpired:
            error_msg = f"Conversion timed out after {self.timeout} seconds. Try increasing timeout or processing fewer PDFs."
            self.status = "Timeout"
            self.log(error_msg)
            raise TimeoutError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error during conversion: {str(e)}"
            self.status = "Error occurred"
            self.log(f"Exception: {e}")
            raise

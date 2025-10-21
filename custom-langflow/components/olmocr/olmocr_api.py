"""
olmOCR Remote API Component

Use external API services (DeepInfra, self-hosted vLLM, etc.) for PDF conversion.

Author: Youssef Harby
License: Apache 2.0
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from langflow.custom import Component
from langflow.io import BoolInput, FileInput, IntInput, MessageTextInput, Output, SecretStrInput
from langflow.schema import Message


class OlmOCRAPI(Component):
    """
    olmOCR - Remote API

    Convert PDFs to markdown using external API services.
    Supports DeepInfra, self-hosted vLLM servers, and other OpenAI-compatible endpoints.
    """

    display_name = "olmOCR - Remote API"
    description = "Convert PDFs using external API (DeepInfra, self-hosted vLLM, etc.)"
    documentation = "https://github.com/allenai/olmocr"
    icon = "cloud"
    name = "OlmOCRAPI"

    inputs = [
        FileInput(
            name="pdf_files",
            display_name="PDF Files",
            info="Upload one or more PDF files to convert",
            file_types=["pdf"],
            list=True,
            required=True,
        ),
        MessageTextInput(
            name="server_url",
            display_name="API Server URL",
            info="External API endpoint (e.g., https://api.deepinfra.com/v1/openai or http://your-server:8000)",
            value=os.getenv("OLMOCR_SERVER_URL", "https://api.deepinfra.com/v1/openai"),
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="API key for external provider (leave empty for self-hosted servers without auth)",
            value=os.getenv("OLMOCR_API_KEY", ""),
            required=False,
        ),
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            info="Model to use (e.g., allenai/olmOCR-7B-1025 for DeepInfra)",
            value=os.getenv("OLMOCR_MODEL", "allenai/olmOCR-7B-1025"),
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="Maximum time to wait for conversion",
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

    def convert_to_markdown(self) -> Message:
        """Convert PDFs to markdown using remote API."""
        try:
            self.status = "Initializing olmOCR conversion..."
            self.log("Starting olmOCR PDF conversion with Remote API")

            # Validate inputs
            if not self.pdf_files:
                error_msg = "No PDF files provided. Please upload at least one PDF file."
                self.status = error_msg
                self.log(error_msg)
                raise ValueError(error_msg)

            if not self.server_url or not self.server_url.strip():
                error_msg = "API Server URL is required. Please provide an external API endpoint."
                self.status = error_msg
                self.log(error_msg)
                raise ValueError(error_msg)

            self.log(f"Using Remote API: {self.server_url}")

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
                "--server", self.server_url,
                "--markdown",
                "--pdfs"
            ] + pdf_paths

            # Add API key if provided
            if self.api_key:
                cmd.extend(["--api_key", self.api_key])

            # Add model name if provided
            if self.model_name:
                cmd.extend(["--model", self.model_name])

            self.status = f"Converting {len(pdf_paths)} PDF(s) using Remote API..."

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

            if self.verbose and result.stderr:
                self.log(f"Process output:\n{result.stderr}")

            # Check for errors
            if result.returncode != 0:
                error_msg = f"Remote API conversion failed with exit code {result.returncode}: {result.stderr[:300]}"
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

            for jsonl_file in jsonl_files:
                if self.verbose:
                    self.log(f"Reading: {jsonl_file.name}")

                try:
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    text_content = data.get('text', '')
                                    if text_content:
                                        markdown_parts.append(text_content)
                                        if self.verbose:
                                            self.log(f"Extracted {len(text_content)} characters from document")
                                except json.JSONDecodeError as e:
                                    self.log(f"Failed to parse JSON on line {line_num} in {jsonl_file.name}: {e}")
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

            success_msg = f"✓ Successfully converted {len(pdf_paths)} PDF(s) using Remote API"
            self.status = success_msg
            self.log(success_msg)

            return Message(
                text=combined_markdown,
                data={
                    "total_files": len(pdf_paths),
                    "extracted_documents": len(markdown_parts),
                    "api_endpoint": self.server_url,
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

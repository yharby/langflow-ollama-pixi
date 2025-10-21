"""
olmOCR Local GPU Component

Auto-detect and use local NVIDIA GPU for PDF conversion.
Requires NVIDIA GPU with CUDA 12.8+ and 15GB+ VRAM.

Author: Youssef Harby
License: Apache 2.0
"""

import json
import subprocess
import tempfile
from pathlib import Path

from langflow.custom import Component
from langflow.io import BoolInput, FileInput, IntInput, Output
from langflow.schema import Message


class OlmOCRLocal(Component):
    """
    olmOCR - Local GPU

    Convert PDFs to markdown using local NVIDIA GPU.
    Auto-detects CUDA GPU and runs olmOCR locally without external API.

    Requirements:
    - NVIDIA GPU with 15GB+ VRAM
    - CUDA 12.8+
    - Linux operating system (CUDA not supported on macOS/Windows)
    """

    display_name = "olmOCR - Local GPU"
    description = "Convert PDFs using local NVIDIA GPU (auto-detects CUDA)"
    documentation = "https://github.com/allenai/olmocr"
    icon = "Cpu"
    name = "OlmOCRLocal"

    inputs = [
        FileInput(
            name="pdf_files",
            display_name="PDF Files",
            info="Upload one or more PDF files to convert",
            file_types=["pdf"],
            list=True,
            required=True,
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

    def _check_cuda_available(self) -> bool:
        """Check if CUDA GPU is available in olmocr environment."""
        try:
            cmd = [
                "pixi", "run",
                "--environment", "olmocr",
                "python", "-c",
                "import torch; print('CUDA' if torch.cuda.is_available() else 'NO_CUDA')"
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(Path.cwd()),
            )

            has_cuda = "CUDA" in result.stdout
            if self.verbose:
                self.log(f"CUDA availability check: {has_cuda}")
            return has_cuda

        except Exception as e:
            self.log(f"Failed to check CUDA availability: {e}")
            return False

    def convert_to_markdown(self) -> Message:
        """Convert PDFs to markdown using local GPU."""
        try:
            self.status = "Initializing olmOCR conversion..."
            self.log("Starting olmOCR PDF conversion with Local GPU")

            # Validate inputs
            if not self.pdf_files:
                error_msg = "No PDF files provided. Please upload at least one PDF file."
                self.status = error_msg
                self.log(error_msg)
                raise ValueError(error_msg)

            # Check for CUDA availability
            self.status = "Checking for NVIDIA GPU..."
            self.log("Checking for CUDA GPU...")

            if not self._check_cuda_available():
                error_msg = (
                    "No NVIDIA GPU with CUDA detected. Local GPU mode requires NVIDIA GPU with CUDA 12.8+ and 15GB+ VRAM. "
                    "For macOS/Windows or systems without NVIDIA GPU, use 'olmOCR - Remote API' or 'olmOCR with Language Model' components instead."
                )
                self.status = "CUDA not available"
                self.log(error_msg)
                raise RuntimeError(error_msg)

            self.log("CUDA GPU detected - using local processing")

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

            # Build olmocr command for local GPU processing
            cmd = [
                "pixi", "run",
                "--environment", "olmocr",
                "python", "-m", "olmocr.pipeline",
                str(workspace),
                "--markdown",
                "--pdfs"
            ] + pdf_paths

            self.status = f"Converting {len(pdf_paths)} PDF(s) using Local GPU..."

            if self.verbose:
                self.log(f"Executing command: pixi run --environment olmocr python -m olmocr.pipeline...")

            # Run olmocr with local GPU
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
                stderr_lower = result.stderr.lower()

                if "torch not compiled with cuda" in stderr_lower or "cuda enabled" in stderr_lower:
                    error_msg = "CUDA support not available. Please ensure CUDA 12.8+ is installed and PyTorch is compiled with CUDA support."
                    self.status = "CUDA error"
                    self.log(f"{error_msg}\n{result.stderr[:200]}")
                    raise RuntimeError(error_msg)

                elif "15 gb" in stderr_lower and "ram" in stderr_lower:
                    error_msg = "Insufficient GPU memory. olmOCR requires at least 15GB of GPU VRAM for local processing."
                    self.status = "Insufficient GPU memory"
                    self.log(f"{error_msg}\n{result.stderr[:200]}")
                    raise RuntimeError(error_msg)

                else:
                    error_msg = f"Local GPU conversion failed with exit code {result.returncode}: {result.stderr[:300]}"
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

            success_msg = f"✓ Successfully converted {len(pdf_paths)} PDF(s) using Local GPU"
            self.status = success_msg
            self.log(success_msg)

            return Message(
                text=combined_markdown,
                data={
                    "total_files": len(pdf_paths),
                    "extracted_documents": len(markdown_parts),
                    "inference_mode": "Local GPU",
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

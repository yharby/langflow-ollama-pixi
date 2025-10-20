"""
olmOCR Component for Langflow

Convert PDFs to clean markdown using Vision Language Models.
Supports both external API (DeepInfra, self-hosted vLLM) and local GPU/CPU processing.

Author: Context Gem
License: Apache 2.0
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from langflow.custom import Component
from langflow.io import (
    BoolInput,
    FileInput,
    IntInput,
    MessageTextInput,
    Output,
    SecretStrInput,
)
from langflow.schema import Message


class OlmOCRSimple(Component):
    """
    olmOCR - PDF to Markdown

    Convert PDFs to clean markdown using Vision Language Models.
    Supports both local GPU/CPU processing and external API services.
    """

    display_name = "olmOCR - PDF to Markdown"
    description = "Convert PDFs to markdown using VLMs (supports local GPU/CPU and external APIs)"
    documentation = "https://github.com/allenai/olmocr"
    icon = "file-text"
    name = "OlmOCR"

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
            display_name="API Server URL (Optional)",
            info="Leave empty for auto-detect (uses local GPU if available). "
            "Or provide URL for external API: https://api.deepinfra.com/v1/openai or self-hosted vLLM server",
            value=os.getenv("OLMOCR_SERVER_URL", ""),
            required=False,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="API key for external provider (leave empty for self-hosted servers)",
            value=os.getenv("OLMOCR_API_KEY", ""),
            required=False,
        ),
        MessageTextInput(
            name="model_name",
            display_name="Model Name",
            info="Model to use. For APIs: allenai/olmOCR-7B-1025. For local: leave default",
            value=os.getenv("OLMOCR_MODEL", "allenai/olmOCR-7B-1025"),
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="Maximum time to wait for conversion (default: 300 seconds / 5 minutes)",
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

    def _log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(f"[olmOCR] {message}")

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
            self._log(f"CUDA check: {has_cuda}")
            return has_cuda

        except Exception as e:
            self._log(f"CUDA check failed: {e}")
            return False

    def convert_to_markdown(self) -> Message:
        """Convert PDFs to markdown using olmocr CLI."""
        try:
            self._log("Starting olmOCR conversion")
            self.status = "Initializing olmOCR conversion..."

            # Validate inputs
            if not self.pdf_files:
                return Message(text="Error: No PDF files provided")

            # Auto-detect inference mode
            use_external_api = False
            inference_mode = "Auto-detect"

            if self.server_url:
                # If server URL is provided, always use external API
                use_external_api = True
                inference_mode = "External API"
                self._log(f"Using External API mode (server provided): {self.server_url}")
            else:
                # No server URL provided - check if CUDA is available
                self.status = "Auto-detecting available hardware..."
                self._log("No server URL provided, checking for local GPU...")

                if self._check_cuda_available():
                    use_external_api = False
                    inference_mode = "Local GPU"
                    self._log("CUDA GPU detected - will use local processing")
                else:
                    # No CUDA, no server URL - show helpful error
                    return Message(
                        text="⚠️ Configuration Required\n\n"
                        "No NVIDIA GPU detected and no external API server configured.\n\n"
                        "Please choose ONE of the following options:\n\n"
                        "Option 1: Use External API (Recommended for macOS/Windows)\n"
                        "  • Set 'API Server URL' to: https://api.deepinfra.com/v1/openai\n"
                        "  • Set 'API Key' to your DeepInfra API key\n"
                        "  • Works on any system, no GPU required\n\n"
                        "Option 2: Use Local GPU (Linux with NVIDIA GPU only)\n"
                        "  • Requires NVIDIA GPU with 15GB+ VRAM\n"
                        "  • Requires CUDA 12.8+\n"
                        "  • Leave 'API Server URL' empty\n\n"
                        "Option 3: Self-Hosted vLLM Server\n"
                        "  • Set 'API Server URL' to your vLLM server (e.g., http://gpu-server:8000)\n"
                        "  • Leave 'API Key' empty if no authentication\n\n"
                        "💡 Tip: For testing, use DeepInfra's free tier at https://deepinfra.com"
                    )

            # Create temporary workspace
            workspace = Path(tempfile.mkdtemp(prefix="olmocr_langflow_"))
            self._log(f"Created workspace: {workspace}")
            self.status = f"Preparing to convert PDFs..."

            # Get PDF paths
            pdf_paths = []
            for file_path in self.pdf_files:
                path = Path(file_path) if isinstance(file_path, str) else Path(file_path)
                self._log(f"Checking file: {path}")
                if path.exists() and path.suffix.lower() == ".pdf":
                    pdf_paths.append(str(path))

            self._log(f"Found {len(pdf_paths)} valid PDF(s)")

            if not pdf_paths:
                return Message(text="Error: No valid PDF files found")

            # Build olmocr command using pixi run
            # This runs the command in the olmocr environment
            cmd = [
                "pixi", "run",
                "--environment", "olmocr",
                "python", "-m", "olmocr.pipeline",
                str(workspace),
                "--markdown",
                "--pdfs"
            ] + pdf_paths

            # Add mode-specific arguments
            if use_external_api:
                cmd.extend(["--server", self.server_url])
                if self.api_key:
                    cmd.extend(["--api_key", self.api_key])
                if self.model_name:
                    cmd.extend(["--model", self.model_name])
                self.status = f"Converting {len(pdf_paths)} PDF(s) using {inference_mode}..."
                self._log(f"Using external API: {self.server_url}")
            else:
                # Local processing mode
                self.status = f"Converting {len(pdf_paths)} PDF(s) using {inference_mode}..."
                self._log(f"Using local GPU processing")

            self._log(f"Running command: {' '.join(cmd[:8])}...")

            # Run olmocr in its own environment
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                cwd=str(Path.cwd()),
            )

            self._log(f"Process completed with return code: {result.returncode}")

            # Log stderr output if verbose (contains progress info)
            if self.verbose and result.stderr:
                self._log(f"Process output:\n{result.stderr}")

            # Check for errors
            if result.returncode != 0:
                # Check for specific error types and provide helpful messages
                stderr_lower = result.stderr.lower()

                if "torch not compiled with cuda" in stderr_lower or "cuda enabled" in stderr_lower:
                    error_msg = (
                        "❌ Local Processing Failed: No CUDA GPU Available\n\n"
                        "Your system does not have NVIDIA CUDA support. olmOCR requires CUDA for local processing.\n\n"
                        "Solutions:\n"
                        "1. Switch Inference Mode to 'External API'\n"
                        "2. Add your API Server URL (e.g., https://api.deepinfra.com/v1/openai)\n"
                        "3. Add your API Key if using a cloud provider\n\n"
                        "The 'External API' mode works on all systems including macOS, Windows, and Linux without GPU."
                    )
                elif "15 gb" in stderr_lower and "ram" in stderr_lower:
                    error_msg = (
                        "❌ Local Processing Failed: Insufficient GPU Memory\n\n"
                        "olmOCR requires at least 15GB of GPU VRAM for local processing.\n\n"
                        "Solutions:\n"
                        "1. Switch to 'External API' mode for serverless processing\n"
                        "2. Use a GPU server with sufficient VRAM\n"
                        "3. Set up a self-hosted vLLM server on a machine with adequate GPU"
                    )
                else:
                    error_msg = f"olmOCR conversion failed (exit code {result.returncode}):\n{result.stderr}"

                self.status = "Conversion failed"
                return Message(text=error_msg)

            # Read results from JSONL files in results directory
            results_dir = workspace / "results"
            self._log(f"Reading results from: {results_dir}")

            if not results_dir.exists():
                self.status = "No results directory found"
                return Message(
                    text=f"Error: No results directory found in workspace. "
                    f"The conversion may have failed silently."
                )

            # Read JSONL files and extract markdown content
            markdown_parts = []
            jsonl_files = list(results_dir.glob("*.jsonl"))
            self._log(f"Found {len(jsonl_files)} result file(s)")

            # Read and parse JSONL files
            for jsonl_file in jsonl_files:
                self._log(f"Reading: {jsonl_file.name}")
                try:
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            if line.strip():
                                try:
                                    data = json.loads(line)
                                    text_content = data.get('text', '')
                                    if text_content:
                                        markdown_parts.append(text_content)
                                        self._log(f"Extracted {len(text_content)} characters from document")
                                except json.JSONDecodeError as e:
                                    self._log(f"Failed to parse JSON on line {line_num}: {e}")
                except Exception as e:
                    self._log(f"Error reading {jsonl_file.name}: {e}")

            if not markdown_parts:
                self.status = "No content extracted"
                return Message(
                    text=f"Error: No content could be extracted from the result files. "
                    f"Check if the PDFs are valid and readable."
                )

            # Combine all markdown with PDF names as headers
            combined_markdown = "\n\n---\n\n".join(markdown_parts)

            # Add source file info if single PDF
            if len(pdf_paths) == 1:
                pdf_name = Path(pdf_paths[0]).name
                combined_markdown = f"# {pdf_name}\n\n{combined_markdown}"

            self.status = f"✓ Successfully converted {len(pdf_paths)} PDF(s) using {inference_mode}"

            return Message(
                text=combined_markdown,
                data={
                    "total_files": len(pdf_paths),
                    "extracted_documents": len(markdown_parts),
                    "inference_mode": inference_mode,
                    "workspace": str(workspace),
                },
            )

        except subprocess.TimeoutExpired:
            self.status = "Conversion timed out"
            return Message(
                text=f"Error: Conversion timed out after {self.timeout} seconds. "
                f"Try increasing the timeout value or processing fewer PDFs at once."
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.status = "Error occurred"
            self._log(f"Exception: {e}")
            return Message(text=error_msg)

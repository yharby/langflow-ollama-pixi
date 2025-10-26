"""
olmOCR Directory Processor

Process entire directories of PDFs and images using DeepInfra API.
Automatically discovers supported files and outputs results to a specified directory.

Author: Youssef Harby
License: Apache 2.0
"""

import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

from langflow.custom import Component
from langflow.io import BoolInput, IntInput, MessageTextInput, Output, SecretStrInput, StrInput
from langflow.schema import Data, Message


class OlmOCRDirectory(Component):
    """
    olmOCR - Directory Processor

    Process entire directories of PDFs and images using DeepInfra or other OpenAI-compatible APIs.
    Automatically discovers files, processes them in batch, and saves results to an output directory.
    """

    display_name = "olmOCR - Directory Processor"
    description = "Batch process directories of PDFs/images using DeepInfra API with directory output"
    documentation = "https://github.com/allenai/olmocr"
    icon = "folder"
    name = "OlmOCRDirectory"

    inputs = [
        StrInput(
            name="input_directory",
            display_name="Input Directory",
            info="Path to directory containing PDFs and/or images (PDF, PNG, JPG, JPEG, TIFF, BMP)",
            required=True,
            input_types=["Text"],
        ),
        MessageTextInput(
            name="file_pattern",
            display_name="File Pattern",
            info="Glob pattern to match files (e.g., '*.pdf' for PDFs only, '**/*' for all files recursively)",
            value="**/*",
            advanced=False,
        ),
        StrInput(
            name="output_directory",
            display_name="Output Directory",
            info="Directory to save converted markdown files (default: auto-generated in workspace)",
            required=False,
            input_types=["Text"],
        ),
        StrInput(
            name="workspace_directory",
            display_name="Workspace Directory",
            info="Directory for olmOCR workspace containing JSONL files with metadata (leave empty for auto-generated in current directory)",
            required=False,
            input_types=["Text"],
            value="",
        ),
        MessageTextInput(
            name="server_url",
            display_name="API Server URL",
            info="External API endpoint (e.g., https://api.deepinfra.com/v1/openai)",
            value=os.getenv("OLMOCR_SERVER_URL", "https://api.deepinfra.com/v1/openai"),
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="API key for DeepInfra or other provider",
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
            name="max_files",
            display_name="Max Files",
            info="Maximum number of files to process (0 = unlimited)",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="Maximum time to wait for conversion",
            value=600,
            advanced=True,
        ),
        BoolInput(
            name="recursive",
            display_name="Recursive Scan",
            info="Recursively scan subdirectories for files",
            value=True,
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
            display_name="Summary",
            name="summary_output",
            method="process_directory",
        ),
        Output(
            display_name="Output Directory",
            name="output_directory_path",
            method="get_output_directory",
        ),
        Output(
            display_name="Workspace Path",
            name="workspace_path",
            method="get_workspace_path",
        ),
        Output(
            display_name="Processing Data",
            name="processing_data",
            method="get_processing_data",
        ),
    ]

    # Supported file extensions for olmOCR
    SUPPORTED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Store processing results for multiple output methods
        self._output_directory = None
        self._workspace_path = None
        self._processing_data = None

    def _discover_files(self, input_dir: Path, pattern: str, recursive: bool) -> List[Path]:
        """Discover supported files in the input directory."""
        discovered_files = []

        if recursive:
            # Use rglob for recursive search
            matched_files = input_dir.rglob(pattern) if pattern != "**/*" else input_dir.rglob("*")
        else:
            # Use glob for non-recursive search
            matched_files = input_dir.glob(pattern) if pattern != "**/*" else input_dir.glob("*")

        for file_path in matched_files:
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                discovered_files.append(file_path)

        return sorted(discovered_files)

    def _save_results_to_files(self, results_dir: Path, output_dir: Path) -> dict:
        """Read JSONL results and save as individual markdown files."""
        jsonl_files = list(results_dir.glob("*.jsonl"))
        saved_files = []
        total_chars = 0

        # Always log how many JSONL files were found (critical feedback)
        self.log(f"Found {len(jsonl_files)} JSONL result file(s) in workspace")

        for jsonl_file in jsonl_files:
            if self.verbose:
                self.log(f"Processing: {jsonl_file.name}")

            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if line.strip():
                            try:
                                data = json.loads(line)
                                text_content = data.get('text', '')

                                if text_content:
                                    # Extract original filename from metadata or use jsonl filename
                                    doc_id = data.get('id', jsonl_file.stem)
                                    output_file = output_dir / f"{doc_id}.md"

                                    # Save to markdown file
                                    with open(output_file, 'w', encoding='utf-8') as out_f:
                                        out_f.write(text_content)

                                    saved_files.append(str(output_file))
                                    total_chars += len(text_content)

                                    if self.verbose:
                                        self.log(f"Saved {len(text_content)} chars to {output_file.name}")
                                    elif len(saved_files) % 5 == 0:
                                        # Log progress every 5 files in non-verbose mode
                                        self.log(f"Saved {len(saved_files)} file(s)...")

                            except json.JSONDecodeError as e:
                                self.log(f"Failed to parse JSON on line {line_num} in {jsonl_file.name}: {e}")
            except Exception as e:
                self.log(f"Error reading {jsonl_file.name}: {e}")

        return {
            "saved_files": saved_files,
            "total_files": len(saved_files),
            "total_chars": total_chars
        }

    def process_directory(self) -> Message:
        """Process all supported files in a directory using DeepInfra API."""
        # During build/validation phase, return placeholder without processing
        if not self.input_directory or not self.input_directory.strip():
            self.status = "Ready to process"
            return Message(
                text="Component ready. Configure inputs and run the flow to process files.",
                data={}
            )

        try:
            self.status = "Initializing directory processing..."
            self.log("Starting olmOCR Directory Processor with DeepInfra")

            # Validate input directory
            input_dir = Path(self.input_directory).expanduser().resolve()

            if not input_dir.exists():
                # During build/validation, return placeholder if directory doesn't exist
                self.status = "Waiting for valid input directory"
                self.log(f"Directory not found (will be validated at runtime): {input_dir}")
                return Message(
                    text=f"Ready to process. Waiting for directory: {input_dir}",
                    data={"status": "pending", "input_directory": str(input_dir)}
                )

            if not input_dir.is_dir():
                # During build/validation, return placeholder if not a directory
                self.status = "Waiting for valid directory path"
                self.log(f"Path is not a directory (will be validated at runtime): {input_dir}")
                return Message(
                    text=f"Ready to process. Path must be a directory: {input_dir}",
                    data={"status": "pending", "input_path": str(input_dir)}
                )

            # Validate API configuration
            if not self.server_url or not self.server_url.strip():
                self.status = "Waiting for API configuration"
                self.log("API Server URL not configured (will be validated at runtime)")
                return Message(
                    text="Ready to process. Please configure API Server URL.",
                    data={"status": "pending", "missing": "api_url"}
                )

            self.log(f"Scanning directory: {input_dir}")
            self.log(f"Using API: {self.server_url}")

            # Discover files
            self.status = "Discovering files..."
            discovered_files = self._discover_files(input_dir, self.file_pattern, self.recursive)

            if not discovered_files:
                # During build/validation, return placeholder if no files found
                self.status = "Waiting for files"
                self.log(f"No files found yet with pattern '{self.file_pattern}' (will be validated at runtime)")
                return Message(
                    text=f"Ready to process. No files found matching '{self.file_pattern}' in {input_dir}. Update inputs and run again.",
                    data={
                        "status": "pending",
                        "input_directory": str(input_dir),
                        "file_pattern": self.file_pattern,
                        "files_found": 0
                    }
                )

            # Apply max_files limit
            if self.max_files > 0 and len(discovered_files) > self.max_files:
                self.log(f"Limiting to {self.max_files} files (found {len(discovered_files)})")
                discovered_files = discovered_files[:self.max_files]

            self.log(f"Found {len(discovered_files)} supported file(s) to process")

            # Log file types distribution
            file_types = {}
            for f in discovered_files:
                ext = f.suffix.lower()
                file_types[ext] = file_types.get(ext, 0) + 1
            self.log(f"File types: {', '.join(f'{ext}: {count}' for ext, count in file_types.items())}")

            # Setup workspace directory
            if self.workspace_directory and self.workspace_directory.strip():
                workspace = Path(self.workspace_directory).expanduser().resolve()
                workspace.mkdir(parents=True, exist_ok=True)
                self.log(f"Using specified workspace directory: {workspace}")
            else:
                # Create persistent workspace in current directory with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                workspace = Path.cwd() / f"olmocr_workspace_{timestamp}"
                workspace.mkdir(parents=True, exist_ok=True)
                self.log(f"Created workspace directory: {workspace}")

            # Setup output directory
            if self.output_directory and self.output_directory.strip():
                output_dir = Path(self.output_directory).expanduser().resolve()
                output_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"Using output directory: {output_dir}")
            else:
                output_dir = workspace / "markdown_output"
                output_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"Created output directory: {output_dir}")

            # Build olmocr command
            file_paths = [str(f) for f in discovered_files]

            cmd = [
                "pixi", "run",
                "--environment", "olmocr",
                "python", "-m", "olmocr.pipeline",
                str(workspace),
                "--server", self.server_url,
                "--markdown",
                "--pdfs"
            ] + file_paths

            # Add API key if provided
            if self.api_key:
                cmd.extend(["--api_key", self.api_key])

            # Add model name
            if self.model_name:
                cmd.extend(["--model", self.model_name])

            self.status = f"Processing {len(discovered_files)} file(s) with DeepInfra..."

            if self.verbose:
                self.log(f"Executing: pixi run --environment olmocr python -m olmocr.pipeline...")
                self.log(f"Processing files: {', '.join(f.name for f in discovered_files[:5])}{'...' if len(discovered_files) > 5 else ''}")

            # Run olmocr
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                cwd=str(Path.cwd()),
            )

            self.log(f"Processing completed (exit code: {result.returncode})")

            # Log stdout if present
            if result.stdout and result.stdout.strip():
                self.log(f"Process stdout:\n{result.stdout}")

            # Always show stderr output (olmOCR writes all progress to stderr)
            if result.stderr:
                # Show full output in verbose mode, truncated otherwise
                if self.verbose:
                    self.log(f"Process stderr:\n{result.stderr}")
                else:
                    # Show last 10 lines to see progress and any errors
                    stderr_lines = result.stderr.strip().split('\n')
                    if len(stderr_lines) > 10:
                        self.log(f"Process stderr (last 10 lines):\n" + '\n'.join(stderr_lines[-10:]))
                    else:
                        self.log(f"Process stderr:\n{result.stderr}")

            # Check for errors
            if result.returncode != 0:
                error_msg = f"olmOCR processing failed with exit code {result.returncode}: {result.stderr[:300]}"
                self.status = "Processing failed"
                self.log(error_msg)
                raise RuntimeError(error_msg)

            # Verify results directory
            results_dir = workspace / "results"
            if not results_dir.exists():
                error_msg = "No results directory found. Processing may have failed silently."
                self.status = error_msg
                self.log(error_msg)
                raise RuntimeError(error_msg)

            self.log(f"Reading results from: {results_dir}")

            # Save results to markdown files
            self.status = "Saving results to markdown files..."
            save_results = self._save_results_to_files(results_dir, output_dir)

            self.log(f"Saved {save_results['total_files']} markdown file(s) to {output_dir}")

            if save_results["total_files"] == 0:
                error_msg = "No content extracted from files. Please verify files are valid and readable."
                self.status = error_msg
                self.log(error_msg)
                raise RuntimeError(error_msg)

            # Create summary
            success_msg = (
                f"✓ Successfully processed {len(discovered_files)} file(s)\n"
                f"✓ Generated {save_results['total_files']} markdown file(s)\n"
                f"✓ Output directory: {output_dir}"
            )

            self.status = f"Completed: {save_results['total_files']} files processed"
            self.log(success_msg)

            # Store results for output methods
            self._output_directory = str(output_dir)
            self._workspace_path = str(workspace)
            self._processing_data = {
                "output_directory": str(output_dir),
                "input_directory": str(input_dir),
                "input_files": [str(f) for f in discovered_files],
                "output_files": save_results["saved_files"],
                "total_input_files": len(discovered_files),
                "total_output_files": save_results["total_files"],
                "total_characters": save_results["total_chars"],
                "file_types": file_types,
                "api_endpoint": self.server_url,
                "model_name": self.model_name,
                "workspace": str(workspace),
            }

            return Message(
                text=success_msg,
                data=self._processing_data,
            )

        except subprocess.TimeoutExpired:
            error_msg = f"Processing timed out after {self.timeout} seconds. Try increasing timeout or reducing file count."
            self.status = "Timeout"
            self.log(error_msg)
            raise TimeoutError(error_msg)

        except Exception as e:
            error_msg = f"Unexpected error during processing: {str(e)}"
            self.status = "Error occurred"
            self.log(f"Exception: {e}")
            raise

    def get_output_directory(self) -> str:
        """Return the output directory path as a string.

        This output can be connected to downstream components that need
        the directory path (e.g., file loaders, directory components).
        """
        if not self._output_directory:
            # Trigger processing if not done yet
            self.process_directory()

        return self._output_directory

    def get_workspace_path(self) -> str:
        """Return the workspace path as a string.

        This output can be connected directly to olmOCR JSONL Parser
        for easy RAG workflow setup. The workspace contains the JSONL
        files with rich metadata.
        """
        if not self._workspace_path:
            # Trigger processing if not done yet
            self.process_directory()

        return self._workspace_path

    def get_processing_data(self) -> Data:
        """Return complete processing metadata as a Data object.

        This output provides structured data about the processing results
        including file lists, statistics, and configuration details.
        """
        if not self._processing_data:
            # Trigger processing if not done yet
            self.process_directory()

        return Data(data=self._processing_data)

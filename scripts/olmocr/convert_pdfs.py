#!/usr/bin/env python3
"""
olmOCR PDF Converter with Cross-Platform Device Detection

This script automatically detects available hardware (CUDA GPU, Apple MPS, CPU)
and uses the appropriate inference mode:
- Local GPU inference (if CUDA GPU available and vllm installed)
- External API mode (fallback for CPU-only or when GPU extras not installed)

Environment Variables:
- OLMOCR_SERVER_URL: URL of external vLLM server (e.g., http://hostname:8000)
- OLMOCR_API_KEY: API key for external provider (e.g., DeepInfra)
- OLMOCR_MODEL: Model name to use (default: allenai/olmOCR-7B-0825-FP8)
- OLMOCR_WORKSPACE: Workspace directory (default: ./olmocr_workspace)
- OLMOCR_PDF_DIR: Directory containing PDFs (default: ./pdf)
"""

import os
import sys
import subprocess
import platform
import glob as glob_module
from pathlib import Path
from typing import Tuple, Optional


class DeviceDetector:
    """Detect available compute devices across platforms."""

    def __init__(self):
        self.device_type = None
        self.has_cuda = False
        self.has_mps = False
        self.has_vllm = False
        self._detect()

    def _detect(self):
        """Detect available devices and dependencies."""
        try:
            import torch
            self.has_cuda = torch.cuda.is_available()
            self.has_mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

            if self.has_cuda:
                self.device_type = "cuda"
                gpu_count = torch.cuda.device_count()
                gpu_name = torch.cuda.get_device_name(0) if gpu_count > 0 else "Unknown"
                print(f"✓ CUDA GPU detected: {gpu_name} (Count: {gpu_count})")

                # Check VRAM
                if gpu_count > 0:
                    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    print(f"  GPU VRAM: {vram_gb:.1f} GB")
                    if vram_gb < 15:
                        print(f"  ⚠ Warning: olmOCR recommends at least 15GB VRAM (you have {vram_gb:.1f}GB)")

            elif self.has_mps:
                self.device_type = "mps"
                print(f"✓ Apple Metal (MPS) detected")
                print(f"  ⚠ Note: vLLM doesn't support MPS. Will use external API mode.")

            else:
                self.device_type = "cpu"
                print(f"✓ CPU-only mode detected")

        except ImportError:
            print("⚠ PyTorch not found. Installing base olmocr dependencies...")
            self.device_type = "cpu"

        # Check if vllm is installed (GPU extras)
        try:
            import vllm
            self.has_vllm = True
            print(f"✓ vLLM installed (version: {vllm.__version__})")
        except ImportError:
            self.has_vllm = False

    def can_use_local_gpu(self) -> bool:
        """Check if local GPU inference is possible."""
        return self.has_cuda and self.has_vllm

    def get_recommendation(self) -> str:
        """Get recommendation based on detected hardware."""
        if self.has_cuda and self.has_vllm:
            return "local_gpu"
        elif self.has_cuda and not self.has_vllm:
            return "install_gpu_extras"
        else:
            return "external_api"

    def print_summary(self):
        """Print device detection summary."""
        print("\n" + "="*70)
        print("Device Detection Summary")
        print("="*70)
        print(f"Platform: {platform.system()} {platform.machine()}")
        print(f"Device Type: {self.device_type.upper()}")
        print(f"CUDA Available: {'Yes' if self.has_cuda else 'No'}")
        print(f"MPS Available: {'Yes' if self.has_mps else 'No'}")
        print(f"vLLM Installed: {'Yes' if self.has_vllm else 'No'}")
        print(f"Recommended Mode: {self.get_recommendation().replace('_', ' ').title()}")
        print("="*70 + "\n")


class OlmOCRRunner:
    """Run olmOCR with appropriate configuration."""

    def __init__(self):
        self.detector = DeviceDetector()
        self.workspace = Path(os.getenv("OLMOCR_WORKSPACE", "./olmocr_workspace"))
        self.pdf_dir = Path(os.getenv("OLMOCR_PDF_DIR", "./pdf"))
        self.server_url = os.getenv("OLMOCR_SERVER_URL")
        self.api_key = os.getenv("OLMOCR_API_KEY")
        self.model = os.getenv("OLMOCR_MODEL", "allenai/olmOCR-7B-0825-FP8")

    def install_gpu_extras(self) -> bool:
        """Install GPU extras for local inference."""
        print("\n" + "="*70)
        print("Installing GPU extras (vLLM and CUDA dependencies)...")
        print("="*70 + "\n")

        try:
            # Install GPU extras with CUDA 12.8 support
            cmd = [
                sys.executable, "-m", "pip", "install",
                "olmocr[gpu]",
                "--extra-index-url", "https://download.pytorch.org/whl/cu128"
            ]

            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(result.stdout)

            # Optionally install flash-infer for faster inference
            print("\nInstalling flash-infer for faster inference...")
            flash_cmd = [
                sys.executable, "-m", "pip", "install",
                "flashinfer_python",
                "--extra-index-url", "https://download.pytorch.org/whl/cu128"
            ]
            subprocess.run(flash_cmd, check=False)  # Optional, don't fail if it doesn't work

            print("\n✓ GPU extras installed successfully!")
            return True

        except subprocess.CalledProcessError as e:
            print(f"\n✗ Failed to install GPU extras: {e}")
            print(f"Error output: {e.stderr}")
            return False

    def run_local_gpu(self, pdf_patterns: list[str]) -> int:
        """Run olmOCR with local GPU inference."""
        print("\n" + "="*70)
        print("Running olmOCR with LOCAL GPU inference")
        print("="*70 + "\n")

        cmd = [
            sys.executable, "-m", "olmocr.pipeline",
            str(self.workspace),
            "--markdown",
            "--pdfs"
        ] + pdf_patterns

        print(f"Command: {' '.join(cmd)}\n")

        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            print(f"\n✗ olmOCR failed with return code {e.returncode}")
            return e.returncode

    def run_external_api(self, pdf_patterns: list[str]) -> int:
        """Run olmOCR with external API."""
        print("\n" + "="*70)
        print("Running olmOCR with EXTERNAL API")
        print("="*70 + "\n")

        if not self.server_url:
            print("✗ Error: OLMOCR_SERVER_URL environment variable not set!")
            print("\nTo use external API mode, set one of the following:\n")
            print("1. Self-hosted vLLM server:")
            print("   export OLMOCR_SERVER_URL=http://your-server:8000\n")
            print("2. DeepInfra (or other provider):")
            print("   export OLMOCR_SERVER_URL=https://api.deepinfra.com/v1/openai")
            print("   export OLMOCR_API_KEY=your-api-key")
            print(f"   export OLMOCR_MODEL=allenai/olmOCR-7B-0825\n")
            return 1

        cmd = [
            sys.executable, "-m", "olmocr.pipeline",
            str(self.workspace),
            "--server", self.server_url,
            "--markdown",
            "--pdfs"
        ] + pdf_patterns

        # Add API key if provided
        if self.api_key:
            cmd.extend(["--api_key", self.api_key])

        # Add model if not default
        if self.model and "deepinfra" in self.server_url.lower():
            cmd.extend(["--model", self.model])

        print(f"Server URL: {self.server_url}")
        if self.api_key:
            print(f"API Key: {'*' * 20}{self.api_key[-4:]}")
        print(f"Model: {self.model}")
        print(f"Command: {' '.join([c if c != self.api_key else '***' for c in cmd])}\n")

        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            print(f"\n✗ olmOCR failed with return code {e.returncode}")
            return e.returncode

    def run(self, pdf_patterns: Optional[list[str]] = None) -> int:
        """Main entry point to run olmOCR."""
        # Print device detection summary
        self.detector.print_summary()

        # Default PDF patterns
        if not pdf_patterns:
            if self.pdf_dir.exists():
                pdf_patterns = [str(self.pdf_dir / "*.pdf")]
                print(f"Using default PDF directory: {self.pdf_dir}\n")
            else:
                print(f"✗ Error: PDF directory not found: {self.pdf_dir}")
                print(f"Set OLMOCR_PDF_DIR environment variable or create ./pdf directory\n")
                return 1

        # Expand glob patterns to actual file paths
        expanded_pdfs = []
        for pattern in pdf_patterns:
            matches = glob_module.glob(pattern)
            if matches:
                expanded_pdfs.extend(matches)
            else:
                # If no matches, keep the original (might be a direct file path)
                expanded_pdfs.append(pattern)

        if not expanded_pdfs:
            print(f"✗ Error: No PDF files found matching patterns: {pdf_patterns}")
            return 1

        print(f"Found {len(expanded_pdfs)} PDF file(s) to convert\n")
        pdf_patterns = expanded_pdfs

        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Determine which mode to use
        recommendation = self.detector.get_recommendation()

        if recommendation == "local_gpu":
            return self.run_local_gpu(pdf_patterns)

        elif recommendation == "install_gpu_extras":
            print("\n" + "="*70)
            print("GPU detected but vLLM not installed")
            print("="*70)
            print("\nYou have two options:\n")
            print("1. Install GPU extras for local inference (recommended for CUDA GPUs):")
            print("   Run this script with --install-gpu flag\n")
            print("2. Use external API mode:")
            print("   Set OLMOCR_SERVER_URL environment variable\n")

            # Ask user
            response = input("Install GPU extras now? [y/N]: ").strip().lower()
            if response == 'y':
                if self.install_gpu_extras():
                    print("\nGPU extras installed! Please run the script again.")
                    return 0
                else:
                    print("\nFailed to install GPU extras. Please install manually or use external API mode.")
                    return 1
            else:
                print("\nUsing external API mode...")
                return self.run_external_api(pdf_patterns)

        else:  # external_api
            return self.run_external_api(pdf_patterns)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="olmOCR PDF Converter with cross-platform device detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "pdfs",
        nargs="*",
        help="PDF files or patterns to convert (default: ./pdf/*.pdf)"
    )

    parser.add_argument(
        "--install-gpu",
        action="store_true",
        help="Install GPU extras (vLLM) for local inference"
    )

    parser.add_argument(
        "--detect-only",
        action="store_true",
        help="Only detect device capabilities, don't run conversion"
    )

    args = parser.parse_args()

    runner = OlmOCRRunner()

    if args.detect_only:
        runner.detector.print_summary()
        return 0

    if args.install_gpu:
        success = runner.install_gpu_extras()
        return 0 if success else 1

    return runner.run(args.pdfs if args.pdfs else None)


if __name__ == "__main__":
    sys.exit(main())

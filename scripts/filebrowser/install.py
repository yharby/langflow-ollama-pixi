#!/usr/bin/env python3
"""
Filebrowser Auto-Installer

Automatically detects OS/architecture and downloads the appropriate
filebrowser binary from the latest GitHub release.

Usage:
    python install.py [--version VERSION]

Examples:
    python install.py                    # Install latest version
    python install.py --version v0.8.9-beta  # Install specific version
"""

import argparse
import json
import os
import platform
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path


def detect_platform() -> tuple[str, str]:
    """
    Detect the current OS and architecture.

    Returns:
        Tuple of (os_name, architecture) matching GitHub release naming:
        - darwin/linux/windows
        - amd64/arm64/armv6/armv7
    """
    # Detect OS
    system = platform.system().lower()
    if system == "darwin":
        os_name = "darwin"
    elif system == "linux":
        os_name = "linux"
    elif system == "windows":
        os_name = "windows"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    # Detect architecture
    machine = platform.machine().lower()
    if machine in ["x86_64", "amd64"]:
        arch = "amd64"
    elif machine in ["arm64", "aarch64"]:
        arch = "arm64"
    elif machine.startswith("armv7"):
        arch = "armv7"
    elif machine.startswith("armv6"):
        arch = "armv6"
    else:
        # Default to amd64 for unknown architectures
        arch = "amd64"
        print(f"Warning: Unknown architecture '{machine}', defaulting to amd64")

    return os_name, arch


def get_binary_name(os_name: str, arch: str) -> str:
    """
    Construct the binary name based on OS and architecture.

    Args:
        os_name: Operating system (darwin/linux/windows)
        arch: Architecture (amd64/arm64/armv6/armv7)

    Returns:
        Binary filename from GitHub release
    """
    if os_name == "windows":
        return "filebrowser.exe"
    else:
        return f"{os_name}-{arch}-filebrowser"


def fetch_release_info(version: str = "latest") -> dict:
    """
    Fetch release information from GitHub API.

    Args:
        version: Release version (e.g., "latest", "v0.8.9-beta")

    Returns:
        Release data as dictionary
    """
    if version == "latest":
        url = "https://api.github.com/repos/gtsteffaniak/filebrowser/releases/latest"
    else:
        url = f"https://api.github.com/repos/gtsteffaniak/filebrowser/releases/tags/{version}"

    print(f"Fetching release info from: {url}")

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"Release '{version}' not found")
        raise RuntimeError(f"Failed to fetch release info: {e}")


def download_binary(url: str, output_path: Path) -> None:
    """
    Download binary from URL with progress indicator.

    Args:
        url: Download URL
        output_path: Where to save the binary
    """
    print(f"Downloading from: {url}")
    print(f"Saving to: {output_path}")

    # Create parent directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Download with progress
    def progress_hook(block_num, block_size, total_size):
        if total_size > 0:
            downloaded = block_num * block_size
            percent = min(100, (downloaded * 100) / total_size)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(f"\rProgress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="")

    try:
        urllib.request.urlretrieve(url, output_path, progress_hook)
        print()  # New line after progress
        print(f"✓ Downloaded successfully")
    except Exception as e:
        raise RuntimeError(f"Failed to download binary: {e}")


def make_executable(path: Path) -> None:
    """
    Make the binary executable on Unix-like systems.

    Args:
        path: Path to the binary
    """
    if platform.system() != "Windows":
        current_permissions = os.stat(path).st_mode
        os.chmod(path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"✓ Made executable: {path}")


def verify_binary(path: Path) -> bool:
    """
    Verify the downloaded binary works.

    Args:
        path: Path to the binary

    Returns:
        True if binary is working
    """
    try:
        result = subprocess.run(
            [str(path), "version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_output = result.stdout.strip()
            print(f"✓ Binary verified: {version_output}")
            return True
        else:
            print(f"Warning: Binary returned non-zero exit code")
            return False
    except Exception as e:
        print(f"Warning: Could not verify binary: {e}")
        return False


def install_filebrowser(version: str = "latest", install_dir: Path = None) -> Path:
    """
    Main installation function.

    Args:
        version: Version to install ("latest" or specific version tag)
        install_dir: Directory to install to (default: ./bin)

    Returns:
        Path to installed binary
    """
    # Set default install directory
    if install_dir is None:
        install_dir = Path.cwd() / "bin"

    # Detect platform
    print("🔍 Detecting platform...")
    os_name, arch = detect_platform()
    print(f"   OS: {os_name}")
    print(f"   Architecture: {arch}")

    # Get binary name
    binary_name = get_binary_name(os_name, arch)
    print(f"   Binary: {binary_name}")

    # Fetch release info
    print(f"\n📦 Fetching release info...")
    release_data = fetch_release_info(version)
    tag_name = release_data.get("tag_name", "unknown")
    print(f"   Version: {tag_name}")

    # Find matching asset
    assets = release_data.get("assets", [])
    matching_asset = None
    for asset in assets:
        if asset["name"] == binary_name:
            matching_asset = asset
            break

    if not matching_asset:
        available = [a["name"] for a in assets]
        raise RuntimeError(
            f"No binary found for {os_name}-{arch}.\n"
            f"Available binaries: {', '.join(available)}"
        )

    download_url = matching_asset["browser_download_url"]
    size_mb = matching_asset["size"] / (1024 * 1024)
    print(f"   Size: {size_mb:.1f} MB")

    # Download binary
    print(f"\n⬇️  Downloading...")
    output_path = install_dir / "filebrowser"
    if os_name == "windows":
        output_path = install_dir / "filebrowser.exe"

    download_binary(download_url, output_path)

    # Make executable
    make_executable(output_path)

    # Verify
    print(f"\n✅ Verifying installation...")
    verify_binary(output_path)

    print(f"\n🎉 Installation complete!")
    print(f"   Binary location: {output_path.absolute()}")
    print(f"\n💡 Run with: {output_path.absolute()}")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Install filebrowser binary for your platform"
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="Version to install (default: latest)"
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=None,
        help="Installation directory (default: ./bin)"
    )

    args = parser.parse_args()

    try:
        install_filebrowser(
            version=args.version,
            install_dir=args.install_dir
        )
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

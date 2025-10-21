#!/usr/bin/env python3
"""
Filebrowser Runner

Automatically installs (if needed) and runs filebrowser.

Usage:
    python run.py [FILEBROWSER_ARGS...]

Examples:
    python run.py                        # Run with defaults
    python run.py -p 8080 -r /path       # Custom port and root
    python run.py --help                 # Show filebrowser help
"""

import subprocess
import sys
from pathlib import Path

# Import from the install script
sys.path.insert(0, str(Path(__file__).parent))
from install import install_filebrowser, detect_platform


def get_binary_path() -> Path:
    """Get the expected path to the filebrowser binary."""
    os_name, _ = detect_platform()
    bin_dir = Path.cwd() / "bin"

    if os_name == "windows":
        return bin_dir / "filebrowser.exe"
    else:
        return bin_dir / "filebrowser"


def ensure_installed() -> Path:
    """
    Ensure filebrowser is installed, install if not.

    Returns:
        Path to the binary
    """
    binary_path = get_binary_path()

    if not binary_path.exists():
        print("Filebrowser not found. Installing...")
        binary_path = install_filebrowser()
        print()

    return binary_path


def run_filebrowser(args: list[str] = None) -> int:
    """
    Run filebrowser with optional arguments.

    Args:
        args: Command-line arguments to pass to filebrowser

    Returns:
        Exit code from filebrowser
    """
    if args is None:
        args = []

    binary_path = ensure_installed()

    # Filebrowser looks for config.yaml in current working directory
    # Copy our config to project root if it doesn't exist or is older
    source_config = Path(__file__).parent / "config.yaml"
    target_config = Path.cwd() / "config.yaml"

    if source_config.exists():
        import shutil
        # Copy config to project root (overwrite if source is newer)
        if not target_config.exists() or source_config.stat().st_mtime > target_config.stat().st_mtime:
            shutil.copy2(source_config, target_config)
            print(f"📝 Copied config from {source_config.name} to project root")

    # Ensure bin directory exists for database
    db_path = Path.cwd() / "bin" / "filebrowser.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"🚀 Starting filebrowser...")
    print(f"   Binary: {binary_path}")
    print(f"   Config: {target_config.absolute()}")
    print(f"   Database: {db_path.absolute()}")
    if args:
        print(f"   Args: {' '.join(args)}")
    print()

    try:
        result = subprocess.run([str(binary_path)] + args)
        return result.returncode
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user")
        return 0
    except Exception as e:
        print(f"\n❌ Error running filebrowser: {e}", file=sys.stderr)
        return 1


def main():
    # Pass all command-line arguments to filebrowser
    args = sys.argv[1:]
    exit_code = run_filebrowser(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

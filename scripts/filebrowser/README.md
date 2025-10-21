# Filebrowser Auto-Installer

Automatically downloads and runs [FileBrowser Quantum](https://github.com/gtsteffaniak/filebrowser) - a modern, web-based file management interface with advanced features like multi-source support, file indexing, and office integration.

## Quick Start

**Before first run, set your admin credentials:**

```bash
# Edit config to set admin username/password
nano scripts/filebrowser/config.yaml

# Change these lines:
# auth:
#   adminUsername: "admin"        → "yourusername"
#   adminPassword: "admin"        → "YourStrongPassword!"

# Install and run
pixi run -e filebrowser install
pixi run -e filebrowser run

# Access at http://localhost:8080
# Login with your credentials from config.yaml
```

## Features

- **Auto OS Detection**: Automatically detects your operating system and architecture
- **Auto Download**: Downloads the correct binary from GitHub releases
- **Auto Configuration**: Copies and manages config files automatically
- **Version Management**: Install latest or specific versions
- **Cross-Platform**: Supports macOS (Intel/ARM), Linux (x64/ARM), Windows, and FreeBSD
- **Complete Config**: 100+ configuration options with detailed comments
- **Security First**: Change admin credentials before first run

### Direct Python Usage

```bash
# Install latest version
python scripts/filebrowser/install.py

# Install specific version
python scripts/filebrowser/install.py --version v0.8.9-beta

# Run filebrowser
python scripts/filebrowser/run.py

# Run with custom options
python scripts/filebrowser/run.py -p 8080 -a 0.0.0.0 -r /path/to/files
```

## Supported Platforms

| Platform | Architectures |
|----------|--------------|
| **macOS** | Intel (amd64), Apple Silicon (arm64) |
| **Linux** | x86_64 (amd64), ARM64, ARMv7, ARMv6 |
| **Windows** | x86_64 |
| **FreeBSD** | x86_64 (amd64) |

## Available Pixi Tasks

```bash
# Installation
pixi run -e filebrowser install              # Install latest version
pixi run -e filebrowser install-version v0.8.9-beta  # Install specific version

# Running (uses config.yaml automatically)
pixi run -e filebrowser run                  # Run with config settings
pixi run -e filebrowser run-network          # Alias for run
pixi run -e filebrowser run-custom           # Alias for run

# Information
pixi run -e filebrowser version              # Show version
pixi run -e filebrowser help                 # Show help

# Note: All settings (port, network, database) are configured in config.yaml
# Edit scripts/filebrowser/config.yaml to change settings
```

## How It Works

### 1. Platform Detection

The installer automatically detects:
- **Operating System**: darwin (macOS), linux, windows, freebsd
- **Architecture**: amd64, arm64, armv7, armv6

```python
# Detected automatically
os_name, arch = detect_platform()
# Example: ("darwin", "arm64") on Apple Silicon Mac
```

### 2. Binary Download

Uses GitHub API to fetch the latest release:

```bash
# API endpoint
https://api.github.com/repos/gtsteffaniak/filebrowser/releases/latest

# Binary naming pattern
{os}-{arch}-filebrowser
# Examples:
# - darwin-arm64-filebrowser
# - linux-amd64-filebrowser
# - filebrowser.exe (Windows)
```

### 3. Configuration Setup

On first run, `run.py` automatically:
1. Copies `scripts/filebrowser/config.yaml` → `./config.yaml`
2. Creates `./bin/` directory for binary and database
3. FileBrowser finds and loads `./config.yaml` from current directory

**Why two config files?**
- `scripts/filebrowser/config.yaml` - Source of truth (tracked in git)
- `./config.yaml` - Runtime copy (ignored by git, can be customized)

### 4. Installation

Downloads to `./bin/filebrowser` (or `./bin/filebrowser.exe` on Windows):

```
langflow-pixi/
├── bin/                     # Ignored by git
│   ├── filebrowser          # Downloaded binary
│   └── filebrowser.db       # SQLite database (created on first run)
├── config.yaml              # Runtime config (copied from scripts/, ignored by git)
├── scripts/
│   └── filebrowser/
│       ├── install.py       # Installer script
│       ├── run.py           # Runner script
│       ├── config.yaml      # Source configuration (tracked in git)
│       └── README.md        # This file
└── pixi.toml                # Pixi configuration
```

**Note:** The `config.yaml` in the project root is automatically copied from `scripts/filebrowser/config.yaml` on first run. Edit the source file in `scripts/filebrowser/` to make permanent changes.

## Configuration

### Using config.yaml (Recommended)

A comprehensive `config.yaml` is provided in `scripts/filebrowser/config.yaml`. This file is automatically copied to the project root on first run.

**Before first run, edit `scripts/filebrowser/config.yaml` to change:**

```yaml
server:
  port: 8080              # Change to your preferred port
  database: "bin/filebrowser.db"  # Database location
  sources:
    - path: "."           # Project root (or any directory)
      name: "Project Files"

auth:
  adminUsername: "admin"  # ⚠️ CHANGE THIS before first run!
  adminPassword: "admin"  # ⚠️ CHANGE THIS before first run!

userDefaults:
  darkMode: true          # Enable dark mode
  permissions:
    modify: false         # Default user permissions
```

**Available configuration options:**

- **Server**: Port, database, base URL, logging, sources, TLS
- **Auth**: Admin credentials, password requirements, OIDC, proxy auth, noauth
- **User Defaults**: Preview settings, dark mode, permissions, UI preferences
- **Frontend**: Branding, styling, custom CSS, external links
- **Integrations**: OnlyOffice, FFmpeg media processing

See `scripts/filebrowser/config.yaml` for all 100+ available options with detailed comments.

### Command-Line User Management

Create users via CLI before or after first run:

```bash
# Create a new admin user
./bin/filebrowser set -u myuser,mypassword -a -c config.yaml

# Create a regular user
./bin/filebrowser set -u username,password -c config.yaml

# Create user with specific scope
./bin/filebrowser set -u username,password -s /path/to/scope -c config.yaml
```

**Note:** FileBrowser Quantum v0.8.9-beta doesn't support `-p`, `-a`, `-d` flags. All configuration must be in `config.yaml`.

## Examples

### Example 1: Install and Run Latest Version

```bash
# Install latest
pixi run -e filebrowser install

# Run on default port (8080)
pixi run -e filebrowser run
```

Then open: http://localhost:8080

### Example 2: Install Specific Version

```bash
# Install v0.8.9-beta
python scripts/filebrowser/install.py --version v0.8.9-beta

# Verify
./bin/filebrowser version
```

### Example 3: Custom Port and Multiple Sources

Edit `scripts/filebrowser/config.yaml`:

```yaml
server:
  port: 9000              # Custom port
  sources:
    - path: "."
      name: "Project Root"
    - path: "./custom-langflow"
      name: "Custom Components"
    - path: "./scripts"
      name: "Scripts"

auth:
  adminUsername: "myadmin"
  adminPassword: "StrongPassword123!"

userDefaults:
  darkMode: true
  preview:
    image: true
    video: false
    office: false
  permissions:
    modify: true
    share: true
    download: true
```

Then run:
```bash
pixi run -e filebrowser run
# Now accessible at http://localhost:9000
# Login with: myadmin / StrongPassword123!
```

### Example 4: Production Setup with Security

Edit `scripts/filebrowser/config.yaml`:

```yaml
server:
  port: 8080
  tlsCert: "/path/to/cert.pem"    # Enable HTTPS
  tlsKey: "/path/to/key.pem"

auth:
  adminUsername: "secureadmin"
  adminPassword: "VeryStrongPassword!2024"
  tokenExpirationHours: 1         # Shorter session timeout
  methods:
    password:
      enabled: true
      minLength: 10               # Require strong passwords
      enforcedOtp: true           # Require 2FA for all users

userDefaults:
  permissions:
    modify: false                 # Users can't modify by default
    share: false                  # No sharing by default
    download: true                # But can download
```

Run and configure 2FA:
```bash
pixi run -e filebrowser run
# Login → Settings → Enable Two-Factor Authentication
```

## Troubleshooting

### Config Not Loading

If filebrowser isn't using your config:

```bash
# Check if config exists in project root
ls -la config.yaml

# If missing, run.py will copy it automatically
pixi run -e filebrowser run

# Manually copy if needed
cp scripts/filebrowser/config.yaml ./config.yaml
```

### Database in Wrong Location

If you have an old `database.db` file in the project root:

```bash
# Remove old database
rm database.db

# Database will be created in ./bin/filebrowser.db (as configured)
pixi run -e filebrowser run
```

### Permission Denied on macOS

macOS may block the downloaded binary:

```bash
# Remove quarantine attribute
xattr -d com.apple.quarantine bin/filebrowser

# Or allow in System Preferences → Security & Privacy
```

### Binary Not Found

If the binary isn't found after installation:

```bash
# Check if binary exists
ls -lh bin/filebrowser

# Make executable manually (Unix)
chmod +x bin/filebrowser

# Run directly
./bin/filebrowser version
```

### Platform Not Supported

If you see "Unsupported OS" or "No binary found":

```bash
# Check your platform
python3 -c "import platform; print(platform.system(), platform.machine())"

# List available binaries
curl -s https://api.github.com/repos/gtsteffaniak/filebrowser/releases/latest | grep "name"
```

### Download Fails

If download fails:

```bash
# Try manual download
# 1. Go to https://github.com/gtsteffaniak/filebrowser/releases/latest
# 2. Download the correct binary for your platform
# 3. Place in ./bin/filebrowser
# 4. Make executable: chmod +x bin/filebrowser
```

## Setting Admin Credentials

### Method 1: Edit Config Before First Run (Recommended)

Edit `scripts/filebrowser/config.yaml` **before** running filebrowser for the first time:

```yaml
auth:
  adminUsername: "yourusername"      # Your custom admin username
  adminPassword: "YourSecurePass123" # Your strong password
```

Then run:
```bash
pixi run -e filebrowser run
```

The admin user will be created with your credentials on first run.

### Method 2: Use Default Then Change Password

If you use the default credentials (admin/admin):

**Via Web UI:**
1. Login at http://localhost:8080 with admin/admin
2. Go to Settings → User Management
3. Click on admin user
4. Change password
5. Save

**Via CLI:**
```bash
# Create new admin user (will replace default)
./bin/filebrowser set -u newadmin,SecurePassword123 -a -c config.yaml
```

### Security Recommendations

⚠️ **IMPORTANT:**
- Never use admin/admin in production
- Use strong passwords (12+ characters, mixed case, numbers, symbols)
- Change default credentials immediately after first run
- Consider using OIDC authentication for production environments

## API Reference

### install.py

```bash
python scripts/filebrowser/install.py [OPTIONS]

Options:
  --version VERSION     Version to install (default: latest)
  --install-dir DIR     Installation directory (default: ./bin)

Examples:
  python scripts/filebrowser/install.py
  python scripts/filebrowser/install.py --version v0.8.9-beta
  python scripts/filebrowser/install.py --install-dir /usr/local/bin
```

### run.py

```bash
python scripts/filebrowser/run.py [FILEBROWSER_ARGS...]

Examples:
  python scripts/filebrowser/run.py
  python scripts/filebrowser/run.py -p 8080
  python scripts/filebrowser/run.py -p 9000 -a 0.0.0.0 -r /data
  python scripts/filebrowser/run.py --help
```

## Resources

- **Official Documentation**: https://filebrowserquantum.com/en/docs/
- **Filebrowser GitHub**: https://github.com/gtsteffaniak/filebrowser
- **Configuration Wiki**: https://github.com/gtsteffaniak/filebrowser/wiki/Configuration-And-Examples
- **Full Config Example**: https://github.com/gtsteffaniak/filebrowser/wiki/Full-Config-Example
- **Latest Release**: https://github.com/gtsteffaniak/filebrowser/releases/latest
- **GitHub API**: https://api.github.com/repos/gtsteffaniak/filebrowser/releases/latest

## License

The installation scripts are part of the langflow-pixi project. Filebrowser itself is licensed under the Apache License 2.0.

# olmOCR - PDF to Markdown

Convert PDFs to clean markdown using Vision Language Models with smart auto-detection.

## Overview

**Primary Use**: Langflow component for visual PDF conversion workflows

**Testing/Detection**: CLI tool for device detection and setup verification

Both support:
- ✨ VLM-powered OCR (handles complex layouts, tables, equations, scanned documents)
- 🎯 Auto-detection (automatically uses local NVIDIA GPU or external API)
- 🌍 Multi-language support (Arabic, Chinese, and more)
- 🚀 Cross-platform (macOS, Windows, Linux)

## Installation

```bash
pixi install --environment olmocr
```

---

## Part 1: Langflow Component

### Quick Start

#### 1. Add Component to Langflow
- Open Langflow visual editor
- Find **olmOCR - PDF to Markdown** in the **olmocr** category
- Drag it onto your canvas

#### 2. Configure

**Option A: External API (Recommended for macOS/Windows)**
```yaml
Server URL: https://api.deepinfra.com/v1/openai
API Key: your-api-key-here
Model: allenai/olmOCR-7B-1025
```
Get API key from [DeepInfra](https://deepinfra.com)

**Option B: Local GPU (Linux with NVIDIA GPU)**
```yaml
Server URL: (leave empty)
```
Automatically detected if you have NVIDIA GPU with 15GB+ VRAM

**Option C: Self-Hosted vLLM**
```yaml
Server URL: http://your-gpu-server:8000
API Key: (leave empty)
```

#### 3. Upload PDFs and Run

That's it! The component auto-detects the best mode and converts your PDFs.

### Example Workflows

#### Simple PDF Chat
```
[olmOCR] → [Chat Output]
```

#### RAG Pipeline
```
[olmOCR] → [Text Splitter] → [Embeddings] → [Vector Store] → [RAG Chain]
```

#### Multi-Language Processing
```
[olmOCR] → [Language Router] → [Language-Specific Pipelines]
```

### Component Configuration

**Inputs:**
- **PDF Files** (required): Upload one or more PDFs
- **API Server URL** (optional): Leave empty for auto-detect, or provide external API URL
- **API Key** (optional): Required for cloud providers like DeepInfra
- **Model Name** (advanced): Default `allenai/olmOCR-7B-1025`
- **Timeout** (advanced): Default 300 seconds
- **Verbose Logging** (advanced): Enable for troubleshooting

**Output:**
Clean markdown text with metadata (total files, mode used, workspace location)

---

## Part 2: CLI Tool (Testing & Advanced Use)

### Usage

The CLI tool at `scripts/olmocr/convert_pdfs.py` is mainly for:
- **Device detection** - Check GPU/CPU availability
- **Setup verification** - Test olmOCR installation
- **Advanced batch processing** - CLI workflows for power users

#### Detect Available Devices

```bash
pixi run --environment olmocr detect
```

Shows: Platform, device type (CUDA/MPS/CPU), vLLM availability, recommended mode

#### Test PDF Conversion (Advanced)

For advanced CLI usage:

```bash
# Set environment variables for external API
export OLMOCR_SERVER_URL=https://api.deepinfra.com/v1/openai
export OLMOCR_API_KEY=your-api-key
export OLMOCR_MODEL=allenai/olmOCR-7B-1025

# Convert specific PDF files
pixi run --environment olmocr convert-files path/to/your.pdf

# Or for local GPU (NVIDIA CUDA required)
pixi run --environment olmocr install-gpu
pixi run --environment olmocr convert-files path/to/your.pdf
```

**Note**: For regular use, the Langflow component is much easier!

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLMOCR_SERVER_URL` | External vLLM server URL | None (uses local GPU if available) |
| `OLMOCR_API_KEY` | API key for external provider | None |
| `OLMOCR_MODEL` | Model name to use | `allenai/olmOCR-7B-0825-FP8` |
| `OLMOCR_WORKSPACE` | Output workspace directory | `./olmocr_workspace` |

### Available Tasks

| Task | Command | Description |
|------|---------|-------------|
| Detect | `pixi run -e olmocr detect` | Show available devices |
| Install GPU | `pixi run -e olmocr install-gpu` | Install CUDA/vLLM for local inference |
| Convert Files | `pixi run -e olmocr convert-files [paths]` | Convert specific PDF files (advanced) |

### CLI Output

Results are saved in the workspace directory:
- **JSONL files**: `{workspace}/results/*.jsonl` (JSON Lines format with markdown content)
- Can be processed further or imported into other systems

---

## Platform Support

### Platform-Specific Dependencies

Automatically handled by pixi:

| Platform | Dependencies |
|----------|-------------|
| **linux-64** | poppler, qpdf |
| **linux-aarch64** | poppler, qpdf |
| **osx-arm64** | qpdf |
| **win-64** | qpdf |

### Device Detection Logic

- **NVIDIA GPU detected + Server URL provided** → Uses External API
- **NVIDIA GPU detected + No Server URL** → Uses Local GPU
- **No NVIDIA GPU + Server URL provided** → Uses External API
- **No NVIDIA GPU + No Server URL** → Shows configuration error

---

## Supported PDFs

✅ Scanned documents (OCR)
✅ Text-based PDFs
✅ Multi-column layouts
✅ Tables and charts
✅ Mathematical equations
✅ Multi-language documents

---

## Troubleshooting

### "Configuration Required" Error
No GPU detected and no server URL provided.
- **Solution**: Set `OLMOCR_SERVER_URL` and `OLMOCR_API_KEY` environment variables

### "Conversion timed out"
- **Solution**: Increase timeout value or process fewer PDFs at once

### "CUDA not available"
Your system doesn't have NVIDIA GPU.
- **Solution**: Use External API mode (works on all platforms)

### GPU Not Detected (Linux)
```bash
# Check CUDA installation
nvidia-smi

# Verify PyTorch CUDA support
pixi run -e olmocr python -c "import torch; print(torch.cuda.is_available())"
```

### vLLM Installation Failed
```bash
# Try manual installation
pixi shell -e olmocr
pip install olmocr[gpu] --extra-index-url https://download.pytorch.org/whl/cu128
```

### External API Connection Issues
```bash
# Test server connectivity
curl $OLMOCR_SERVER_URL/health

# Verify API key
echo $OLMOCR_API_KEY
```

---

## Performance & Cost

- **Best Quality**: Use model `allenai/olmOCR-7B-1025` or newer
- **Fastest Processing**: Local GPU is 10x faster than API (requires NVIDIA GPU with 15GB+ VRAM, CUDA 12.8+)
- **Cost Optimization**:
  - Local GPU: Free but requires hardware
  - Self-hosted vLLM: One-time GPU cost, unlimited processing
  - DeepInfra/Cloud APIs: Pay per page processed

---

## Resources

- [olmOCR GitHub](https://github.com/allenai/olmocr)
- [olmOCR Demo](https://olmocr.allenai.org/)
- [Technical Paper](https://olmocr.allenai.org/papers/olmocr.pdf)
- [DeepInfra](https://deepinfra.com/)
- [Langflow Docs](https://docs.langflow.org/components-custom-components)

## License

Apache 2.0

# Langflow + Ollama + olmOCR (Pixi)

Fully local AI workflow platform with multi-platform support.

## Features

- **100% Local**: All models and data in project directory
- **Multi-platform**: macOS ARM64, Linux x64, Windows x64, Linux ARM64
- **Isolated environments**: Ollama, Langflow, and olmOCR environments
- **PDF OCR**: Vision Language Model-based PDF to Markdown conversion
- **No external DB**: SQLite only

## Quick Start

pre-requisite: pixi

First you should copy the `.env.example` file to `.env` and edit it to your liking.

```bash
# 1. Install environments
pixi install

# 2. Start Ollama (Terminal 1)
pixi run --environment ollama serve

# 3. Pull embedding model (first time only)
pixi run --environment ollama pull-embedding

# 4. Start Langflow (Terminal 2)
pixi run --environment langflow run
```

Access:
- Langflow: http://localhost:7860
- Ollama: http://localhost:11434

## Run using tmux

To run both Ollama and Langflow in separate tmux sessions:

```bash
# Start Ollama session
tmux new-session -d -s ollama "pixi run --environment ollama serve"

# Start Langflow session
tmux new-session -d -s langflow "pixi run --environment langflow run"
```
To attach to a tmux session:
```bash
tmux attach -t ollama
tmux attach -t langflow
```

To detach from a tmux session:
```bash
ctrl+b then d alone to Detaches 
```



### Project Structure

```
.
├── pixi.toml              # Multi-env config
├── .env                   # Settings
├── custom-langflow/       # Custom components
│   └── components/olmocr/ # olmOCR component + docs
└── scripts/olmocr/        # CLI tools (testing/detection)
```

Data directories (`.pixi/`, `.ollama/`, `.langflow/`) are gitignored.

## Available Tasks

### Ollama Environment

```bash
pixi run --environment ollama serve              # Start server
pixi run --environment ollama pull-embedding     # Download model
pixi run --environment ollama list-models        # List models
pixi run --environment ollama test               # Test server
pixi run --environment ollama test-embedding     # Test embeddings
```

### Langflow Environment

```bash
pixi run --environment langflow run              # Start Langflow
pixi run --environment langflow run-dev          # With auto-reload
```

### olmOCR Environment

```bash
pixi run --environment olmocr detect             # Detect GPU/CPU
```

**For PDF conversion**: Use the olmOCR component in Langflow UI
**Documentation**: `custom-langflow/components/olmocr/README.md`

## Using Ollama in Langflow

1. Start both services (Ollama + Langflow)
2. In Langflow, add "Ollama Embeddings" component
3. Configure:
   - Base URL: `http://0.0.0.0:11434`
   - Model: `jeffh/intfloat-multilingual-e5-large-instruct:f16`

## Troubleshooting

**No models found:**
```bash
pixi run --environment ollama pull-embedding
```

**Ollama not accessible:**
```bash
pixi run --environment ollama test
```

**Change port/host:**
Edit `.env` file and change `LANGFLOW_PORT` or `LANGFLOW_HOST`.

## Production

For production, update `.env`:

```env
LANGFLOW_AUTO_LOGIN=false
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=your-secure-password
```

### More dependencies

Add pnpm to the langflow environment:
```bash
pixi add --feature langflow pnpm
```

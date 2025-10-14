# Langflow + Ollama (100% Local)

Fully local setup with multi-platform support using Pixi.

## Features

- **100% Local**: All models and data in project directory
- **Multi-platform**: macOS ARM64, Linux x64, Windows x64
- **Isolated environments**: Separate Ollama and Langflow environments
- **No external DB**: SQLite only

## Quick Start

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

## Configuration

### Environment Variables (.env)

Key settings (edit `.env` file):

```env
# Langflow
LANGFLOW_HOST=0.0.0.0
LANGFLOW_PORT=7860
LANGFLOW_DATABASE_URL=sqlite:///.langflow/langflow.db

# Ollama (set in pixi.toml tasks)
OLLAMA_MODELS=.ollama/models
OLLAMA_BASE_URL=http://0.0.0.0:11434
```

### Project Structure

```
.
├── pixi.toml           # Multi-env config
├── .env                # Langflow settings
├── .pixi/              # Pixi environments
├── .ollama/models/     # Ollama models (1+ GB)
└── .langflow/          # Langflow DB & logs
```

All data directories (`.pixi/`, `.ollama/`, `.langflow/`) are gitignored.

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

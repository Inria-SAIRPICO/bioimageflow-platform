# BioImageFlow Server

FastAPI backend for the BioImageFlow platform. Wraps the BioImageFlow library and exposes a REST + WebSocket API for tool discovery, graph validation, workflow execution, and real-time progress streaming.

## Tech Stack

- **FastAPI** with async support
- **Pydantic** v2 for request/response models
- **WebSockets** for real-time execution updates
- **uv** for dependency management
- **Python** >= 3.12

## Project Structure

```
src/bioimageflow_server/
  app.py              Application factory
  routers/
    health.py         GET /api/v1/health
    tools.py          Tool registry and package management endpoints
    dev.py            Development-only endpoints
  services/
    tool_registry.py  Tool discovery and registry
    package_installer.py  Tool package installation
  models/
    errors.py         Error response models
    execution.py      Execution state models
    graph.py          Graph/node/edge models
    settings.py       Application settings
    tools.py          Tool metadata and config models
    validation.py     Validation result models
    workflow.py       Workflow models
  ws/                 WebSocket handlers
```

## Setup

```bash
uv sync                          # Install dependencies
uv sync --extra dev              # Include dev dependencies (pytest, ruff, httpx)
```

## Running

```bash
# Development server with auto-reload
uv run uvicorn bioimageflow_server.app:create_app --factory --host 127.0.0.1 --port 8000 --reload

# Production
uv run uvicorn bioimageflow_server.app:create_app --factory --host 127.0.0.1 --port 8000
```

The OpenAPI docs are available at http://localhost:8000/docs.

## Testing

```bash
uv run pytest                    # Run all tests
uv run pytest tests/test_routers # Run router tests only
```

## API Overview

All endpoints are prefixed with `/api/v1/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/tools` | List all discovered tools |
| `GET` | `/tools/{name}/source` | Get tool source directory |
| `GET` | `/tools/packages` | List all packages with versions |
| `POST` | `/tools/packages/{name}/install` | Install a package version |
| `DELETE` | `/tools/packages/{name}` | Uninstall a package version |

## Linting

```bash
uv run ruff check .              # Lint
uv run ruff format .             # Format
```

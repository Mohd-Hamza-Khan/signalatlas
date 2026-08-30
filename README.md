# SignalAtlas

FrontierAtlas Intelligence Ingestion Engine - A production-shaped AI intelligence ingestion pipeline.

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Poetry (optional, for dependency management)

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd signal-atlas
   ```

2. Create environment file:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. Start PostgreSQL:
   ```bash
   docker compose up -d
   ```

4. Install dependencies:
   ```bash
   poetry install
   ```

5. Run the pipeline:
   ```bash
   python -m src.pipeline.runner
   ```

## Configuration

See `.env.example` for required environment variables.

### Required

- `DATABASE_URL` - PostgreSQL connection string
- `OPENROUTER_API_KEY` - OpenRouter API key for LLM access

### Optional

- `GITHUB_TOKEN` - GitHub personal access token
- `GOOGLE_SHEETS_CREDENTIALS` - Google Sheets service account JSON
- `REDIS_URL` - Redis connection string (Phase 2)

## Architecture

See `architecture.md` for detailed architecture documentation.

## License

MIT

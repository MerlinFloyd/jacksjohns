# Discord Bot + AI Agent Service

A Discord bot integrated with Google's Gemini AI for persona management and image generation.

## Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│   Discord Bot       │  HTTP   │   Python Agent      │
│   (TypeScript/Bun)  │◄───────►│   Service (FastAPI) │
└─────────────────────┘  REST   └─────────────────────┘
         │                               │
         ▼                               ▼
    Discord API                    Vertex AI APIs
                                   - Gemini 2.5 Flash
                                   - Gemini 2.5 Flash Image
                                          │
                                          ▼
                                   Firestore (Native)
                                   - Persona persistence
```

## Features

### Implemented (Features 1-3)
- **Create AI Persona**: `/persona create <name> <personality>` - Create custom AI personalities
- **List/Edit Personas**: `/persona list`, `/persona edit <name> <field> <value>` - Manage personas
- **Image Generation**: `/imagine <prompt>` - Generate images using Gemini 2.5 Flash Image

### Planned (Features 4-5)
- **Chat Channel Integration**: Assign bot to a channel for AI conversations
- **Voice Chat**: Real-time voice conversations using Vertex AI Live API

## Project Structure

```
├── agent-service/          # Python FastAPI service
│   ├── src/
│   │   ├── api/           # REST API routes
│   │   ├── config/        # Configuration
│   │   ├── domain/        # Core business logic (Clean Architecture)
│   │   └── infrastructure/# External service integrations
│   ├── Dockerfile
│   └── requirements.txt
│
├── discord-bot/           # TypeScript/Bun Discord bot
│   ├── src/
│   │   ├── commands/      # Slash command handlers
│   │   ├── services/      # Agent service client
│   │   └── types/         # TypeScript types
│   ├── Dockerfile
│   └── package.json
│
├── terraform/             # GCP Infrastructure as Code
│   ├── main.tf           # Provider configuration
│   ├── cloud_run.tf      # Cloud Run services
│   ├── firestore.tf      # Firestore database
│   ├── iam.tf            # Service accounts & permissions
│   └── artifact_registry.tf  # Container registry
│
├── docker-compose.yml     # Local development orchestration
├── build.sh              # Build and run script
└── credentials.json      # GCP service account key (gitignored)
```

## Prerequisites

- [Bun](https://bun.sh/) runtime (for Discord bot)
- Python 3.10+ (for Agent service)
- Docker & Docker Compose
- GCP Project with Vertex AI enabled
- Discord Application with Bot Token

## Setup

### 1. Configure Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` and set:
- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `DISCORD_APPLICATION_ID` - Your Discord application ID
- `GCP_PROJECT_ID` - Your Google Cloud project ID

### 2. GCP Authentication

Ensure you have a service account key at `./credentials.json` with Vertex AI permissions.

Or authenticate using gcloud CLI:
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 3. Build and Run

Using the build script:
```bash
# Build Docker images
./build.sh build

# Start services
./build.sh up

# View logs
./build.sh logs

# Stop services
./build.sh down
```

Or using docker-compose directly:
```bash
docker compose up --build
```

## API Endpoints (Agent Service)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/personas` | POST | Create persona |
| `/api/personas` | GET | List all personas |
| `/api/personas/{name}` | GET | Get persona by name |
| `/api/personas/{name}` | PATCH | Update persona |
| `/api/personas/{name}` | DELETE | Delete persona |
| `/api/images/generate` | POST | Generate image (JSON response) |
| `/api/images/generate/raw` | POST | Generate image (raw bytes) |

## Discord Commands

| Command | Description |
|---------|-------------|
| `/persona create <name> <personality>` | Create a new AI persona |
| `/persona list` | List all personas |
| `/persona edit <name> <field> <value>` | Edit an existing persona |
| `/imagine <prompt> [aspect_ratio]` | Generate an image from text |

## Deployment to GCP

### CI/CD with GitHub Actions

The project includes a GitHub Actions workflow that automatically builds and deploys to Cloud Run on every push to `main`.

#### Setup GitHub Actions CI/CD

1. **Set up Terraform infrastructure** (one-time setup):
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values including:
   # - discord_bot_token
   # - github_repository (format: owner/repo)
   terraform init
   terraform apply
   ```

2. **Note the Terraform outputs**:
   ```bash
   terraform output
   ```
   This will show you:
   - `wif_provider` - Workload Identity Provider
   - `wif_service_account` - Service Account email

3. **Add GitHub Repository Secrets** (Settings → Secrets and variables → Actions):

   | Secret Name | Value |
   |-------------|-------|
   | `WIF_PROVIDER` | Output from `terraform output wif_provider` |
   | `WIF_SERVICE_ACCOUNT` | Output from `terraform output wif_service_account` |
   | `DISCORD_APPLICATION_ID` | Your Discord Application ID (`1447797969423175742`) |

4. **Push to main branch** to trigger deployment:
   ```bash
   git add .
   git commit -m "Deploy to Cloud Run"
   git push origin main
   ```

The workflow will:
- Build Docker images for both services
- Push images to Artifact Registry
- Deploy Agent Service to Cloud Run
- Deploy Discord Bot to Cloud Run (with Secret Manager integration)

### Manual Terraform Deployment

If you prefer manual deployment without GitHub Actions:

1. Initialize Terraform:
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   terraform init
   ```

2. Build and push Docker images:
   ```bash
   # Configure Docker for Artifact Registry
   gcloud auth configure-docker us-central1-docker.pkg.dev
   
   # Build and tag images
   docker build -t us-central1-docker.pkg.dev/jacks-johns/discord-bot-repo/agent-service:latest ./agent-service
   docker build -t us-central1-docker.pkg.dev/jacks-johns/discord-bot-repo/discord-bot:latest ./discord-bot
   
   # Push to Artifact Registry
   docker push us-central1-docker.pkg.dev/jacks-johns/discord-bot-repo/agent-service:latest
   docker push us-central1-docker.pkg.dev/jacks-johns/discord-bot-repo/discord-bot:latest
   ```

3. Update `terraform.tfvars` with image paths and apply:
   ```bash
   terraform plan
   terraform apply
   ```

## Development

### Running Locally (without Docker)

**Agent Service:**
```bash
cd agent-service
pip install -r requirements.txt
python -m uvicorn src.main:app --reload --port 8000
```

**Discord Bot:**
```bash
cd discord-bot
bun install
bun run src/index.ts
```

## Technology Stack

- **Discord Bot**: TypeScript, Bun, discord.js
- **Agent Service**: Python 3.12, FastAPI, google-genai
- **AI Models**: Gemini 2.5 Flash, Gemini 2.5 Flash Image
- **Infrastructure**: Docker, GCP Cloud Run, Terraform
- **Architecture**: Clean Architecture, SOLID principles
- **Data Storage**: Firestore (Native mode) for persona persistence

## Storage

### Firestore
Persona data is persisted in Firestore (Native mode). The service automatically:
- Uses Firestore when available (production on Cloud Run)
- Falls back to in-memory storage if Firestore is unavailable (with warning logs)

**Firestore Collection Structure:**
```
personas/
  └── {persona_name_lowercase}/
      ├── name: string
      ├── personality: string
      ├── created_at: timestamp
      └── updated_at: timestamp
```

**Configuration:**
- `USE_FIRESTORE=true` (default) - Enable Firestore persistence
- `FIRESTORE_COLLECTION=personas` (default) - Collection name for personas

## License

Private project.

# Discord Bot + AI Agent Service

A Discord bot integrated with Google's Gemini AI for persona management, image generation, and conversational AI with long-term memory.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Discord Server                                │
├─────────────────────────────────────────────────────────────────────────┤
│  #general (Admin Channel)     │  📁 Personas (Category)                 │
│  ├─ /persona create           │  ├─ #wise-wizard                       │
│  ├─ /persona delete           │  │   ├─ Auto-chat (shared session)     │
│  ├─ /persona list             │  │   ├─ /persona edit                  │
│  └─ /persona rename           │  │   └─ /imagine (uses appearance)     │
│                               │  └─ #friendly-chef                      │
└───────────────────────────────┴─────────────────────────────────────────┘
                                        │
                                        ▼
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
                              ┌───────────────────────┐
                              │    GCP Services       │
                              ├───────────────────────┤
                              │ Firestore (Native)    │
                              │ - Persona persistence │
                              │ - Channel sessions    │
                              ├───────────────────────┤
                              │ Agent Engine          │
                              │ - Sessions (chat)     │
                              │ - Memory Bank         │
                              └───────────────────────┘
```

## Features

### Implemented
- **Dedicated Persona Channels**: Each persona gets its own Discord channel
- **Auto-Chat**: Just type in a persona channel - the bot responds in character
- **Selective Response**: Bot decides when to respond (doesn't spam on every message)
- **Persona Management**: Create, list, delete, rename, and edit personas
- **Image Generation**: `/imagine` with optional persona appearance integration
- **Long-Term Memory**: Personas remember conversations across sessions
- **Memory Isolation**: Each persona's memories are separate
- **Error Interpretation**: LLM-powered friendly error messages

### Planned
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

## Discord Bot Setup

### Required Bot Permissions

The bot requires the following permissions to manage persona channels:

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application
3. Navigate to **OAuth2** → **URL Generator**
4. Select scopes: `bot`, `applications.commands`
5. Select bot permissions:
   - **General Permissions**: `Manage Channels`
   - **Text Permissions**: `Send Messages`, `Read Message History`, `View Channels`
6. Use the generated URL to invite the bot to your server

### Verify Bot Role

1. Open your Discord server settings
2. Go to **Roles** and find the bot's role
3. Ensure **Manage Channels** is enabled

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
| `/api/personas/{name}` | PATCH | Update persona (personality, appearance, channel_id) |
| `/api/personas/{name}` | DELETE | Delete persona |
| `/api/personas/{name}/rename` | POST | Rename persona and migrate memories |
| `/api/images/generate` | POST | Generate image (JSON, optional persona_name) |
| `/api/images/generate/raw` | POST | Generate image (raw bytes) |
| `/api/chat` | POST | Chat with a persona (supports channel mode) |
| `/api/chat/end-session` | POST | End session and generate memories |
| `/api/chat/channel-sessions/{id}` | DELETE | Delete a channel session |
| `/api/chat/sessions` | GET | List user's sessions |
| `/api/chat/memories` | GET | List memories for persona/user |
| `/api/chat/memories` | POST | Create a memory directly |
| `/api/chat/memories/{persona}` | DELETE | Delete all memories for a persona |
| `/api/chat/interpret-error` | POST | Get LLM interpretation of an error |

## Discord Commands

### Admin Channel Commands (default: #general)

These commands must be used in the admin channel:

| Command | Description |
|---------|-------------|
| `/persona create <name> <personality> [appearance]` | Create a new persona with its own channel |
| `/persona list` | List all personas with their channels |
| `/persona delete <name> <confirm>` | Delete persona, channel, memories, and session |
| `/persona rename <current_name> <new_name>` | Rename persona and its channel |

### Persona Channel Commands

These commands work only in persona-specific channels (under the "Personas" category):

| Command | Description |
|---------|-------------|
| `/persona edit [personality] [appearance]` | Edit this channel's persona |
| `/imagine <prompt> [aspect_ratio]` | Generate image (uses persona appearance) |

### Global Commands (Any Channel)

| Command | Description |
|---------|-------------|
| `/memories <persona> [user] [search]` | View memories for a persona |

### Auto-Chat (Persona Channels)

In persona channels, you can chat naturally without commands:
- Just type a message and the bot responds in character
- Shared session per channel - all users share the conversation
- Bot decides when to respond based on context
- Memories are automatically built from conversations

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

3. **Add GitHub Repository Secrets** (Settings → Secrets and variables → Actions → Secrets):

   | Secret Name | Value |
   |-------------|-------|
   | `WIF_PROVIDER` | Output from `terraform output wif_provider` |
   | `WIF_SERVICE_ACCOUNT` | Output from `terraform output wif_service_account` |
   | `DISCORD_APPLICATION_ID` | Your Discord Application ID (`1447797969423175742`) |

4. **Add GitHub Repository Variables** (Settings → Secrets and variables → Actions → Variables):

   | Variable Name | Value |
   |---------------|-------|
   | `AGENT_ENGINE_ID` | Your Agent Engine ID (e.g., `7839847759531212800`) |

   Note: The Agent Engine ID is created automatically on first deployment if not set. Check the Cloud Run logs for the created ID, then add it as a variable to reuse the same instance.

5. **Push to main branch** to trigger deployment:
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
- **Data Storage**: 
  - Firestore (Native mode) for persona persistence
  - Agent Engine for sessions and memory bank

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
      ├── appearance: string (optional)
      ├── channel_id: string (Discord channel ID)
      ├── created_at: timestamp
      └── updated_at: timestamp

channel_sessions/
  └── {channel_id}/
      ├── channel_id: string
      ├── session_id: string (Vertex AI session ID)
      ├── persona_name: string
      ├── created_at: timestamp
      └── updated_at: timestamp
```

**Configuration:**
- `USE_FIRESTORE=true` (default) - Enable Firestore persistence
- `FIRESTORE_COLLECTION=personas` (default) - Collection name for personas

### Agent Engine (Sessions & Memory Bank)

The service uses Vertex AI Agent Engine for conversation management:

#### Sessions
Sessions maintain conversation history within a single chat session:
- Each user-persona combination can have multiple sessions
- Sessions store the chronological sequence of messages
- Sessions are automatically created when chatting with a persona

#### Memory Bank
Memory Bank stores long-term memories that persist across sessions:

**Memory Scoping Strategy:**
- **Shared Persona Memories**: `scope = {app_name: "<persona_name>"}`
  - Memories shared across ALL users for a persona
  - Example: "I am a friendly assistant who loves helping with coding"
  
- **Per-User Memories**: `scope = {app_name: "<persona_name>", user_id: "<discord_user_id>"}`
  - Personal memories specific to each user-persona relationship
  - Example: "John prefers detailed explanations with code examples"

**Memory Generation:**
- Memories are automatically extracted from conversations when sessions end
- Users can also directly teach personas facts using `/chat teach`

**Configuration:**
- `USE_AGENT_ENGINE=true` (default) - Enable sessions and memory
- `AGENT_ENGINE_ID=` - Set to reuse an existing Agent Engine instance
- `AGENT_ENGINE_DISPLAY_NAME=jacksjohns-bot-engine` - Display name for new instances

**Note:** If `AGENT_ENGINE_ID` is not set, a new Agent Engine instance will be created automatically on first run. The ID will be logged - you should set it in your environment to reuse the same instance.

## License

Private project.

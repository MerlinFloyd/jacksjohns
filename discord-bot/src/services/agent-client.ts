/**
 * HTTP client for communicating with the Agent Service.
 */

import { config } from "../config/env";
import { logger } from "../utils/logger";
import type { Persona, PersonaCreate, PersonaUpdate, PersonaRename } from "../types/persona";
import type {
  ImageGenerateRequest,
  ImageGenerateResponse,
  HealthResponse,
  ChatRequest,
  ChatResponse,
  EndSessionResponse,
  SessionInfo,
  MemoryInfo,
  DeleteMemoriesResponse,
  ErrorInterpretRequest,
  ErrorInterpretResponse,
  GenerateChannelMemoriesResponse,
} from "../types/api";

class AgentClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = config.agentService.url;
    logger.info(`Agent client initialized with base URL: ${this.baseUrl}`);
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    
    try {
      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      // Handle 204 No Content
      if (response.status === 204) {
        return undefined as T;
      }

      return await response.json();
    } catch (error) {
      logger.error(`Agent service request failed: ${method} ${path}`, error);
      throw error;
    }
  }

  // Health check
  async healthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>("GET", "/health");
  }

  // Persona operations
  async createPersona(data: PersonaCreate): Promise<Persona> {
    logger.info(`Creating persona: ${data.name}`);
    return this.request<Persona>("POST", "/api/personas", data);
  }

  async listPersonas(): Promise<Persona[]> {
    return this.request<Persona[]>("GET", "/api/personas");
  }

  async getPersona(name: string): Promise<Persona> {
    return this.request<Persona>("GET", `/api/personas/${encodeURIComponent(name)}`);
  }

  async updatePersona(name: string, data: PersonaUpdate): Promise<Persona> {
    logger.info(`Updating persona: ${name}`);
    return this.request<Persona>("PATCH", `/api/personas/${encodeURIComponent(name)}`, data);
  }

  async deletePersona(name: string): Promise<void> {
    logger.info(`Deleting persona: ${name}`);
    await this.request<void>("DELETE", `/api/personas/${encodeURIComponent(name)}`);
  }

  // Image generation
  async generateImage(data: ImageGenerateRequest): Promise<ImageGenerateResponse> {
    logger.info(`Generating image with prompt: ${data.prompt.substring(0, 50)}...`);
    return this.request<ImageGenerateResponse>("POST", "/api/images/generate", data);
  }

  // Get raw image bytes
  async generateImageRaw(data: ImageGenerateRequest): Promise<Buffer> {
    const url = `${this.baseUrl}/api/images/generate/raw`;
    
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    return Buffer.from(arrayBuffer);
  }

  // Chat operations
  async chat(data: ChatRequest): Promise<ChatResponse> {
    logger.info(`Chat request: persona=${data.persona_name}, user=${data.user_id}`);
    return this.request<ChatResponse>("POST", "/api/chat", data);
  }

  async endSession(
    personaName: string,
    userId: string,
    sessionId: string,
    generateMemories: boolean = true
  ): Promise<EndSessionResponse> {
    logger.info(`Ending session: ${sessionId}`);
    const params = new URLSearchParams({
      persona_name: personaName,
      user_id: userId,
      session_id: sessionId,
      generate_memories: generateMemories.toString(),
    });
    return this.request<EndSessionResponse>("POST", `/api/chat/end-session?${params}`);
  }

  async listSessions(personaName: string, userId: string): Promise<SessionInfo[]> {
    const params = new URLSearchParams({
      persona_name: personaName,
      user_id: userId,
    });
    return this.request<SessionInfo[]>("GET", `/api/chat/sessions?${params}`);
  }

  async listMemories(
    personaName: string,
    userId?: string,
    query?: string,
    limit: number = 20
  ): Promise<MemoryInfo[]> {
    const params = new URLSearchParams({ persona_name: personaName });
    if (userId) params.append("user_id", userId);
    if (query) params.append("query", query);
    params.append("limit", limit.toString());
    return this.request<MemoryInfo[]>("GET", `/api/chat/memories?${params}`);
  }

  async createMemory(
    personaName: string,
    fact: string,
    userId?: string
  ): Promise<MemoryInfo> {
    const params = new URLSearchParams({ persona_name: personaName, fact });
    if (userId) params.append("user_id", userId);
    return this.request<MemoryInfo>("POST", `/api/chat/memories?${params}`);
  }

  // Rename persona
  async renamePersona(name: string, newName: string): Promise<Persona> {
    logger.info(`Renaming persona: ${name} -> ${newName}`);
    return this.request<Persona>(
      "POST",
      `/api/personas/${encodeURIComponent(name)}/rename`,
      { new_name: newName }
    );
  }

  // Delete persona memories
  async deletePersonaMemories(
    personaName: string,
    userId?: string
  ): Promise<DeleteMemoriesResponse> {
    logger.info(`Deleting memories for persona: ${personaName}${userId ? `, user: ${userId}` : ""}`);
    let path = `/api/chat/memories/${encodeURIComponent(personaName)}`;
    if (userId) {
      path += `?user_id=${encodeURIComponent(userId)}`;
    }
    return this.request<DeleteMemoriesResponse>("DELETE", path);
  }

  // Delete channel session
  async deleteChannelSession(channelId: string): Promise<{ status: string; deleted: boolean }> {
    logger.info(`Deleting channel session: ${channelId}`);
    return this.request<{ status: string; deleted: boolean }>(
      "DELETE",
      `/api/chat/channel-sessions/${encodeURIComponent(channelId)}`
    );
  }

  // Generate memories from channel session (without ending the session)
  async generateChannelMemories(
    channelId: string,
    userId?: string
  ): Promise<GenerateChannelMemoriesResponse> {
    logger.info(`Generating memories from channel: ${channelId}`);
    let path = `/api/chat/channel-sessions/${encodeURIComponent(channelId)}/generate-memories`;
    if (userId) {
      path += `?user_id=${encodeURIComponent(userId)}`;
    }
    return this.request<GenerateChannelMemoriesResponse>("POST", path);
  }

  // Interpret error for user-friendly message
  async interpretError(
    errorMessage: string,
    context?: string,
    personaName?: string
  ): Promise<string> {
    try {
      const response = await this.request<ErrorInterpretResponse>(
        "POST",
        "/api/chat/interpret-error",
        {
          error_message: errorMessage,
          error_context: context,
          persona_name: personaName,
        }
      );
      return response.interpretation;
    } catch (error) {
      // If error interpretation fails, return original error
      logger.warn("Failed to interpret error:", error);
      return `Something went wrong: ${errorMessage}`;
    }
  }
}

// Export singleton instance
export const agentClient = new AgentClient();

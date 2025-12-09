/**
 * HTTP client for communicating with the Agent Service.
 */

import { config } from "../config/env";
import { logger } from "../utils/logger";
import type { Persona, PersonaCreate, PersonaUpdate } from "../types/persona";
import type { ImageGenerateRequest, ImageGenerateResponse, HealthResponse } from "../types/api";

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
}

// Export singleton instance
export const agentClient = new AgentClient();

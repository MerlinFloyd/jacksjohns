/**
 * API response types for Agent Service.
 */

export interface ImageGenerateRequest {
  prompt: string;
  aspect_ratio?: string;
}

export interface ImageGenerateResponse {
  image_base64: string;
  mime_type: string;
  prompt: string;
  text_response?: string;
}

export interface ApiError {
  detail: string;
}

export interface HealthResponse {
  status: string;
  service: string;
}

// Chat API types
export interface ChatRequest {
  persona_name: string;
  user_id: string;
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  persona_name: string;
  memories_used: number;
}

export interface EndSessionRequest {
  persona_name: string;
  user_id: string;
  session_id: string;
  generate_memories?: boolean;
}

export interface EndSessionResponse {
  status: string;
  session_id: string;
  memories_generated: number;
}

export interface SessionInfo {
  session_id: string;
  user_id: string;
  persona_name: string;
  event_count: number;
  created_at: string;
}

export interface MemoryInfo {
  id: string;
  fact: string;
  scope: Record<string, string>;
}

/**
 * API response types for Agent Service.
 */

export interface ImageGenerateRequest {
  prompt: string;
  aspect_ratio?: string;
  persona_name?: string;  // If provided, persona appearance will be prepended to prompt
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
  // New fields for channel chat mode
  user_display_name?: string;
  is_channel_chat?: boolean;
  channel_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  persona_name: string;
  memories_used: number;
  should_respond: boolean;  // Whether the bot should actually send this response
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

// Delete memories response
export interface DeleteMemoriesResponse {
  deleted_count: number;
  persona_name: string;
  user_id: string | null;
}

// Error interpretation
export interface ErrorInterpretRequest {
  error_message: string;
  error_context?: string;
  persona_name?: string;
}

export interface ErrorInterpretResponse {
  interpretation: string;
}

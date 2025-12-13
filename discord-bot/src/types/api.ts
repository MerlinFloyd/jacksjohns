/**
 * API response types for Agent Service.
 */

export interface ImageGenerateRequest {
  prompt: string;
  aspect_ratio?: string;
  persona_name?: string;  // If provided, persona appearance will be prepended to prompt
}

export interface GeneratedImageData {
  image_base64: string;
  mime_type: string;
  text_response?: string;
}

export interface ImageGenerateResponse {
  images: GeneratedImageData[];
  prompt: string;
  // Legacy fields for backward compatibility (first image)
  image_base64: string;
  mime_type: string;
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
  memories_saved: number;  // Number of memories saved during this interaction
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

// Delete single memory response
export interface DeleteSingleMemoryResponse {
  deleted: boolean;
  memory_id: string;
}

// Generate memories from channel session
export interface GenerateChannelMemoriesResponse {
  status: string;
  channel_id: string;
  session_id: string;
  persona_name: string;
  user_id: string;
  memories_generated: number;
  memories: MemoryInfo[];
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

// Settings API types
export interface SafetySettingModel {
  category: string;
  threshold: string;
}

export interface ChatSettingsModel {
  temperature: number;
  top_p: number;
  top_k: number;
  max_output_tokens: number;
  presence_penalty: number;
  frequency_penalty: number;
  stop_sequences: string[];
  safety_settings: SafetySettingModel[];
}

export interface ImageSettingsModel {
  aspect_ratio: string;
  output_mime_type: string;
  negative_prompt: string | null;
  number_of_images: number;
  temperature: number;
  person_generation: boolean;
  safety_settings: SafetySettingModel[];
}

export interface GenerationSettingsResponse {
  name: string;
  chat: ChatSettingsModel;
  image: ImageSettingsModel;
  created_at: string;
  updated_at: string;
}

export interface UpdateChatSettings {
  temperature?: number;
  top_p?: number;
  top_k?: number;
  max_output_tokens?: number;
  presence_penalty?: number;
  frequency_penalty?: number;
  stop_sequences?: string[];
  safety_settings?: SafetySettingModel[];
}

export interface UpdateImageSettings {
  aspect_ratio?: string;
  output_mime_type?: string;
  negative_prompt?: string | null;
  number_of_images?: number;
  temperature?: number;
  person_generation?: boolean;
  safety_settings?: SafetySettingModel[];
}

export interface UpdateSettingsRequest {
  chat?: UpdateChatSettings;
  image?: UpdateImageSettings;
}

export interface AvailableSettings {
  chat: Record<string, { description: string; type: Record<string, unknown> }>;
  image: Record<string, { description: string; type: Record<string, unknown> }>;
  valid_aspect_ratios: string[];
  valid_harm_categories: string[];
  valid_harm_thresholds: string[];
}

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

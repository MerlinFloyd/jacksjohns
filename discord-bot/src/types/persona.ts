/**
 * Persona types matching the Agent Service API.
 */

export interface Persona {
  name: string;
  personality: string;
  appearance: string | null;
  channel_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PersonaCreate {
  name: string;
  personality: string;
  appearance?: string;
  channel_id?: string;
}

export interface PersonaUpdate {
  // Note: name is not allowed in update - use rename endpoint instead
  personality?: string;
  appearance?: string;
  channel_id?: string;
}

export interface PersonaRename {
  new_name: string;
}

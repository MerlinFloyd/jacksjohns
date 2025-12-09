/**
 * Persona types matching the Agent Service API.
 */

export interface Persona {
  name: string;
  personality: string;
  created_at: string;
  updated_at: string;
}

export interface PersonaCreate {
  name: string;
  personality: string;
}

export interface PersonaUpdate {
  name?: string;
  personality?: string;
}

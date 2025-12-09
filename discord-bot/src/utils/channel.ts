/**
 * Discord channel management utilities for persona channels.
 */

import {
  Guild,
  TextChannel,
  CategoryChannel,
  ChannelType,
  Client,
} from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "./logger";
import type { Persona } from "../types/persona";

const PERSONAS_CATEGORY_NAME = "Personas";

/**
 * Convert persona name to Discord channel name (slug).
 * "Wise Wizard" -> "wise-wizard"
 */
export function slugifyPersonaName(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Find or create the "Personas" category in a guild.
 */
export async function getOrCreatePersonasCategory(
  guild: Guild
): Promise<CategoryChannel> {
  // Look for existing category
  const existing = guild.channels.cache.find(
    (ch) =>
      ch.type === ChannelType.GuildCategory &&
      ch.name.toLowerCase() === PERSONAS_CATEGORY_NAME.toLowerCase()
  ) as CategoryChannel | undefined;

  if (existing) {
    return existing;
  }

  // Create new category
  const category = await guild.channels.create({
    name: PERSONAS_CATEGORY_NAME,
    type: ChannelType.GuildCategory,
    reason: "Persona channels category",
  });

  logger.info(`Created "${PERSONAS_CATEGORY_NAME}" category in ${guild.name}`);
  return category;
}

/**
 * Create a text channel for a persona under the Personas category.
 */
export async function createPersonaChannel(
  guild: Guild,
  personaName: string
): Promise<TextChannel> {
  const category = await getOrCreatePersonasCategory(guild);
  const channelName = slugifyPersonaName(personaName);

  const channel = await guild.channels.create({
    name: channelName,
    type: ChannelType.GuildText,
    parent: category.id,
    topic: `Chat with ${personaName}. Use /persona edit to modify, /imagine to generate images.`,
    reason: `Persona channel for ${personaName}`,
  });

  logger.info(`Created channel #${channelName} for persona "${personaName}"`);
  return channel;
}

/**
 * Delete a persona's channel by ID.
 */
export async function deletePersonaChannel(
  guild: Guild,
  channelId: string
): Promise<boolean> {
  try {
    const channel = guild.channels.cache.get(channelId);
    if (channel) {
      await channel.delete("Persona deleted");
      logger.info(`Deleted channel ${channelId}`);
      return true;
    }
    logger.warn(`Channel ${channelId} not found in cache`);
    return false;
  } catch (error) {
    logger.error(`Failed to delete channel ${channelId}:`, error);
    return false;
  }
}

/**
 * Rename a persona's channel.
 */
export async function renamePersonaChannel(
  guild: Guild,
  channelId: string,
  newPersonaName: string
): Promise<boolean> {
  try {
    const channel = guild.channels.cache.get(channelId) as TextChannel;
    if (channel) {
      const newChannelName = slugifyPersonaName(newPersonaName);
      await channel.setName(
        newChannelName,
        `Persona renamed to ${newPersonaName}`
      );
      await channel.setTopic(
        `Chat with ${newPersonaName}. Use /persona edit to modify, /imagine to generate images.`
      );
      logger.info(`Renamed channel to #${newChannelName}`);
      return true;
    }
    logger.warn(`Channel ${channelId} not found for rename`);
    return false;
  } catch (error) {
    logger.error(`Failed to rename channel ${channelId}:`, error);
    return false;
  }
}

/**
 * Get persona for a channel (by channel_id lookup).
 * Caches the result briefly to avoid repeated API calls.
 */
const personaCache = new Map<string, { persona: Persona | null; expires: number }>();
const CACHE_TTL_MS = 30000; // 30 seconds

export async function getPersonaForChannel(
  channelId: string
): Promise<Persona | null> {
  // Check cache first
  const cached = personaCache.get(channelId);
  if (cached && cached.expires > Date.now()) {
    return cached.persona;
  }

  try {
    const personas = await agentClient.listPersonas();
    const persona = personas.find((p) => p.channel_id === channelId) || null;
    
    // Cache the result
    personaCache.set(channelId, {
      persona,
      expires: Date.now() + CACHE_TTL_MS,
    });
    
    return persona;
  } catch (error) {
    logger.error(`Failed to get persona for channel ${channelId}:`, error);
    return null;
  }
}

/**
 * Invalidate persona cache for a specific channel.
 */
export function invalidatePersonaCache(channelId?: string): void {
  if (channelId) {
    personaCache.delete(channelId);
  } else {
    personaCache.clear();
  }
}

/**
 * Check if a channel is the admin channel.
 */
export function isAdminChannel(
  channelName: string,
  adminChannelName: string
): boolean {
  return channelName.toLowerCase() === adminChannelName.toLowerCase();
}

/**
 * Check if a channel is a persona channel.
 */
export async function isPersonaChannel(channelId: string): Promise<boolean> {
  const persona = await getPersonaForChannel(channelId);
  return persona !== null;
}

/**
 * Sync persona channels on startup.
 * Creates missing channels for personas that have channel_id but the channel doesn't exist.
 */
export interface SyncResult {
  created: string[];
  errors: Array<{ persona: string; error: string }>;
}

export async function syncPersonaChannels(
  guild: Guild,
  personas: Persona[]
): Promise<SyncResult> {
  const result: SyncResult = { created: [], errors: [] };

  for (const persona of personas) {
    // If persona has a channel_id, check if it exists
    if (persona.channel_id) {
      const existingChannel = guild.channels.cache.get(persona.channel_id);
      if (!existingChannel) {
        // Channel was deleted, recreate it
        try {
          logger.info(`Recreating missing channel for persona "${persona.name}"`);
          const newChannel = await createPersonaChannel(guild, persona.name);
          await agentClient.updatePersona(persona.name, {
            channel_id: newChannel.id,
          });
          result.created.push(persona.name);
          // Invalidate cache since we updated the persona
          invalidatePersonaCache();
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : String(error);
          result.errors.push({
            persona: persona.name,
            error: `Failed to recreate channel: ${errorMsg}`,
          });
        }
      }
    }
    // Note: If persona has no channel_id, it was created before this feature
    // We don't auto-create channels for these (they can be migrated manually)
  }

  return result;
}

/**
 * Get channel by ID from client's cache, fetching if necessary.
 */
export async function getChannelById(
  client: Client,
  channelId: string
): Promise<TextChannel | null> {
  try {
    const channel = await client.channels.fetch(channelId);
    if (channel && channel.type === ChannelType.GuildText) {
      return channel as TextChannel;
    }
    return null;
  } catch {
    return null;
  }
}

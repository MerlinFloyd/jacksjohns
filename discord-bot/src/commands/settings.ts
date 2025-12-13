/**
 * Settings command handlers for managing AI generation settings.
 * 
 * Commands:
 * - /settings list [name] - List all settings or view specific settings
 * - /settings set <name> <category> <setting> <value> - Set a specific setting
 * - /settings reset <name> - Reset settings to defaults
 */

import type { ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "../utils/logger";
import type { GenerationSettingsResponse, AvailableSettings } from "../types/api";

// Format a settings object for display
function formatSettings(settings: GenerationSettingsResponse): string {
  const lines: string[] = [];
  
  lines.push(`**Settings: ${settings.name}**`);
  lines.push("");
  
  // Chat settings
  lines.push("**Chat Settings:**");
  lines.push(`  temperature: ${settings.chat.temperature}`);
  lines.push(`  top_p: ${settings.chat.top_p}`);
  lines.push(`  top_k: ${settings.chat.top_k}`);
  lines.push(`  max_output_tokens: ${settings.chat.max_output_tokens}`);
  lines.push(`  presence_penalty: ${settings.chat.presence_penalty}`);
  lines.push(`  frequency_penalty: ${settings.chat.frequency_penalty}`);
  if (settings.chat.stop_sequences.length > 0) {
    lines.push(`  stop_sequences: ${settings.chat.stop_sequences.join(", ")}`);
  }
  
  lines.push("");
  
  // Image settings
  lines.push("**Image Settings:**");
  lines.push(`  aspect_ratio: ${settings.image.aspect_ratio}`);
  lines.push(`  output_mime_type: ${settings.image.output_mime_type}`);
  lines.push(`  number_of_images: ${settings.image.number_of_images}`);
  lines.push(`  temperature: ${settings.image.temperature}`);
  lines.push(`  person_generation: ${settings.image.person_generation}`);
  if (settings.image.negative_prompt) {
    lines.push(`  negative_prompt: ${settings.image.negative_prompt}`);
  }
  
  lines.push("");
  lines.push(`_Last updated: ${new Date(settings.updated_at).toLocaleString()}_`);
  
  return lines.join("\n");
}

// Format available settings for help
function formatAvailableSettings(available: AvailableSettings): string {
  const lines: string[] = [];
  
  lines.push("**Available Settings:**");
  lines.push("");
  
  lines.push("**Chat Settings:**");
  for (const [name, info] of Object.entries(available.chat)) {
    const typeInfo = info.type as Record<string, unknown>;
    let typeStr = String(typeInfo.type || "unknown");
    if (typeInfo.min !== undefined && typeInfo.max !== undefined) {
      typeStr += ` (${typeInfo.min}-${typeInfo.max})`;
    }
    lines.push(`  \`${name}\` (${typeStr}): ${info.description}`);
  }
  
  lines.push("");
  
  lines.push("**Image Settings:**");
  for (const [name, info] of Object.entries(available.image)) {
    const typeInfo = info.type as Record<string, unknown>;
    let typeStr = String(typeInfo.type || "unknown");
    if (typeInfo.min !== undefined && typeInfo.max !== undefined) {
      typeStr += ` (${typeInfo.min}-${typeInfo.max})`;
    }
    lines.push(`  \`${name}\` (${typeStr}): ${info.description}`);
  }
  
  lines.push("");
  lines.push(`**Valid aspect ratios:** ${available.valid_aspect_ratios.join(", ")}`);
  lines.push("");
  lines.push(`**Valid harm thresholds:** ${available.valid_harm_thresholds.join(", ")}`);
  
  return lines.join("\n");
}

/**
 * Handle /settings list [name] command
 */
export async function handleSettingsList(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const name = interaction.options.getString("name");
  
  await interaction.deferReply();
  
  try {
    if (name) {
      // Get specific settings
      const settings = await agentClient.getSettings(name);
      await interaction.editReply(formatSettings(settings));
    } else {
      // List all settings
      const { settings } = await agentClient.listSettings();
      
      if (settings.length === 0) {
        await interaction.editReply(
          "No custom settings configured. All personas are using default settings.\n\n" +
          "Use `/settings set <persona_name> <category> <setting> <value>` to configure settings."
        );
        return;
      }
      
      const lines = ["**Configured Settings:**", ""];
      for (const s of settings) {
        lines.push(`- **${s.name}**: temperature=${s.chat.temperature}, aspect_ratio=${s.image.aspect_ratio}`);
      }
      lines.push("");
      lines.push("Use `/settings list <name>` to see full settings for a persona.");
      
      await interaction.editReply(lines.join("\n"));
    }
  } catch (error) {
    logger.error("Failed to list settings", error);
    await interaction.editReply(
      `Failed to list settings: ${error instanceof Error ? error.message : "Unknown error"}`
    );
  }
}

/**
 * Handle /settings available command - show all available settings
 */
export async function handleSettingsAvailable(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  await interaction.deferReply();
  
  try {
    const available = await agentClient.getAvailableSettings();
    const formatted = formatAvailableSettings(available);
    
    // Split into multiple messages if too long
    if (formatted.length > 2000) {
      const parts = formatted.match(/[\s\S]{1,1900}(?=\n|$)/g) || [formatted];
      await interaction.editReply(parts[0]);
      for (let i = 1; i < parts.length; i++) {
        await interaction.followUp(parts[i]);
      }
    } else {
      await interaction.editReply(formatted);
    }
  } catch (error) {
    logger.error("Failed to get available settings", error);
    await interaction.editReply(
      `Failed to get available settings: ${error instanceof Error ? error.message : "Unknown error"}`
    );
  }
}

/**
 * Handle /settings set <name> <category> <setting> <value> command
 */
export async function handleSettingsSet(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const name = interaction.options.getString("name", true);
  const category = interaction.options.getString("category", true) as "chat" | "image";
  const setting = interaction.options.getString("setting", true);
  const valueStr = interaction.options.getString("value", true);
  
  await interaction.deferReply();
  
  try {
    // Parse the value based on common types
    let value: unknown = valueStr;
    
    // Try to parse as number
    const numValue = parseFloat(valueStr);
    if (!isNaN(numValue)) {
      value = numValue;
    }
    // Parse boolean
    else if (valueStr.toLowerCase() === "true") {
      value = true;
    } else if (valueStr.toLowerCase() === "false") {
      value = false;
    }
    // Parse array (comma-separated)
    else if (valueStr.includes(",")) {
      value = valueStr.split(",").map(s => s.trim());
    }
    // null/none
    else if (valueStr.toLowerCase() === "null" || valueStr.toLowerCase() === "none") {
      value = null;
    }
    
    // Build update request
    const updates: { chat?: Record<string, unknown>; image?: Record<string, unknown> } = {};
    if (category === "chat") {
      updates.chat = { [setting]: value };
    } else {
      updates.image = { [setting]: value };
    }
    
    const result = await agentClient.updateSettings(name, updates);
    
    // Show the updated value
    const chatObj = result.chat as unknown as Record<string, unknown>;
    const imageObj = result.image as unknown as Record<string, unknown>;
    const updatedValue = category === "chat" 
      ? chatObj[setting]
      : imageObj[setting];
    
    await interaction.editReply(
      `Updated **${name}** setting:\n` +
      `\`${category}.${setting}\` = \`${JSON.stringify(updatedValue)}\``
    );
  } catch (error) {
    logger.error("Failed to set setting", error);
    await interaction.editReply(
      `Failed to set setting: ${error instanceof Error ? error.message : "Unknown error"}`
    );
  }
}

/**
 * Handle /settings reset <name> command
 */
export async function handleSettingsReset(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const name = interaction.options.getString("name", true);
  
  await interaction.deferReply();
  
  try {
    const settings = await agentClient.resetSettings(name);
    
    await interaction.editReply(
      `Reset settings for **${name}** to defaults:\n\n` +
      formatSettings(settings)
    );
  } catch (error) {
    logger.error("Failed to reset settings", error);
    await interaction.editReply(
      `Failed to reset settings: ${error instanceof Error ? error.message : "Unknown error"}`
    );
  }
}

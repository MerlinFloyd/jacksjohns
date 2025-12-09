/**
 * Command registry, definitions, and channel-based restrictions.
 * 
 * Command Locations:
 * - Admin channel (#general by default): /persona create, /persona delete, /persona list, /persona rename
 * - Persona channels: /persona edit, /imagine, /remember
 * - Any channel: /memories
 */

import {
  SlashCommandBuilder,
  TextChannel,
  type ChatInputCommandInteraction,
  type RESTPostAPIChatInputApplicationCommandsJSONBody,
} from "discord.js";

import { config } from "../config/env";
import { logger } from "../utils/logger";
import { getPersonaForChannel, isAdminChannel, invalidatePersonaCache } from "../utils/channel";
import { agentClient } from "../services/agent-client";
import type { Persona } from "../types/persona";

// Import handlers
import { handlePersonaCreate, handlePersonaList, handlePersonaEdit } from "./persona/create";
import { handlePersonaDelete } from "./persona/delete";
import { handlePersonaRename } from "./persona/rename";
import { handleImagine } from "./imagine";
import { handleMemories } from "./memories";
import { handleRemember } from "./remember";

// Command location restrictions
const ADMIN_CHANNEL_COMMANDS = [
  "persona create",
  "persona delete",
  "persona list",
  "persona rename",
];

const PERSONA_CHANNEL_COMMANDS = [
  "persona edit",
  "imagine",
  "remember",
];

// Command definitions
export const commands: RESTPostAPIChatInputApplicationCommandsJSONBody[] = [
  // Persona management commands
  new SlashCommandBuilder()
    .setName("persona")
    .setDescription("Manage AI personas")
    // CREATE - admin channel only
    .addSubcommand((subcommand) =>
      subcommand
        .setName("create")
        .setDescription("Create a new AI persona with its own channel")
        .addStringOption((option) =>
          option
            .setName("name")
            .setDescription("Name of the persona")
            .setRequired(true)
            .setMaxLength(100)
        )
        .addStringOption((option) =>
          option
            .setName("personality")
            .setDescription("Personality description")
            .setRequired(true)
            .setMaxLength(2000)
        )
        .addStringOption((option) =>
          option
            .setName("appearance")
            .setDescription("Physical appearance for image generation")
            .setRequired(false)
            .setMaxLength(2000)
        )
    )
    // LIST - admin channel only
    .addSubcommand((subcommand) =>
      subcommand
        .setName("list")
        .setDescription("List all personas")
    )
    // DELETE - admin channel only
    .addSubcommand((subcommand) =>
      subcommand
        .setName("delete")
        .setDescription("Delete a persona and its channel")
        .addStringOption((option) =>
          option
            .setName("name")
            .setDescription("Name of the persona to delete")
            .setRequired(true)
        )
        .addBooleanOption((option) =>
          option
            .setName("confirm")
            .setDescription("Confirm deletion (required)")
            .setRequired(true)
        )
    )
    // RENAME - admin channel only
    .addSubcommand((subcommand) =>
      subcommand
        .setName("rename")
        .setDescription("Rename a persona and its channel")
        .addStringOption((option) =>
          option
            .setName("current_name")
            .setDescription("Current name of the persona")
            .setRequired(true)
        )
        .addStringOption((option) =>
          option
            .setName("new_name")
            .setDescription("New name for the persona")
            .setRequired(true)
            .setMaxLength(100)
        )
    )
    // EDIT - persona channel only (auto-scoped to channel's persona)
    .addSubcommand((subcommand) =>
      subcommand
        .setName("edit")
        .setDescription("Edit this channel's persona")
        .addStringOption((option) =>
          option
            .setName("personality")
            .setDescription("New personality description")
            .setRequired(false)
            .setMaxLength(2000)
        )
        .addStringOption((option) =>
          option
            .setName("appearance")
            .setDescription("New physical appearance for image generation")
            .setRequired(false)
            .setMaxLength(2000)
        )
    )
    .toJSON(),

  // Image generation command - uses persona appearance in persona channels
  new SlashCommandBuilder()
    .setName("imagine")
    .setDescription("Generate an image (uses persona appearance in persona channels)")
    .addStringOption((option) =>
      option
        .setName("prompt")
        .setDescription("Description of the image to generate")
        .setRequired(true)
        .setMaxLength(4000)
    )
    .addStringOption((option) =>
      option
        .setName("aspect_ratio")
        .setDescription("Aspect ratio of the image")
        .setRequired(false)
        .addChoices(
          { name: "1:1 (Square)", value: "1:1" },
          { name: "16:9 (Landscape)", value: "16:9" },
          { name: "9:16 (Portrait)", value: "9:16" },
          { name: "4:3", value: "4:3" },
          { name: "3:4", value: "3:4" },
          { name: "3:2", value: "3:2" },
          { name: "2:3", value: "2:3" }
        )
    )
    .toJSON(),

  // Memories command - view memories (simplified from /chat memories)
  new SlashCommandBuilder()
    .setName("memories")
    .setDescription("View memories for a persona")
    .addStringOption((option) =>
      option
        .setName("persona")
        .setDescription("Name of the persona")
        .setRequired(true)
    )
    .addUserOption((option) =>
      option
        .setName("user")
        .setDescription("View memories for a specific user (default: yourself)")
        .setRequired(false)
    )
    .addStringOption((option) =>
      option
        .setName("search")
        .setDescription("Search memories containing this text")
        .setRequired(false)
    )
    .toJSON(),

  // Remember command - generate memories from conversation (persona channel only)
  new SlashCommandBuilder()
    .setName("remember")
    .setDescription("Save memories from this conversation (use in persona channels)")
    .toJSON(),
];

/**
 * Validate command is being used in the correct channel type.
 */
async function validateCommandLocation(
  interaction: ChatInputCommandInteraction
): Promise<{ valid: boolean; error?: string; persona?: Persona }> {
  const channel = interaction.channel;
  
  // Must be in a guild text channel
  if (!channel || !(channel instanceof TextChannel)) {
    return { valid: false, error: "This command must be used in a server text channel." };
  }

  const subcommand = interaction.options.getSubcommand(false);
  const fullCommand = subcommand
    ? `${interaction.commandName} ${subcommand}`
    : interaction.commandName;

  // Check admin-only commands
  if (ADMIN_CHANNEL_COMMANDS.includes(fullCommand)) {
    if (!isAdminChannel(channel.name, config.discord.adminChannelName)) {
      return {
        valid: false,
        error: `This command can only be used in #${config.discord.adminChannelName}`,
      };
    }
    return { valid: true };
  }

  // Check persona-channel-only commands
  if (PERSONA_CHANNEL_COMMANDS.includes(fullCommand)) {
    const persona = await getPersonaForChannel(channel.id);
    if (!persona) {
      return {
        valid: false,
        error: "This command can only be used in a persona channel (under the Personas category).",
      };
    }
    return { valid: true, persona };
  }

  // Other commands allowed anywhere
  return { valid: true };
}

/**
 * Main command handler with channel validation.
 */
export async function handleCommand(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const commandName = interaction.commandName;

  // Validate command location
  const validation = await validateCommandLocation(interaction);
  if (!validation.valid) {
    await interaction.reply({
      content: validation.error!,
      ephemeral: true,
    });
    return;
  }

  try {
    switch (commandName) {
      case "persona":
        await handlePersonaCommand(interaction, validation.persona);
        break;
      case "imagine":
        await handleImagine(interaction, validation.persona);
        break;
      case "memories":
        await handleMemories(interaction);
        break;
      case "remember":
        await handleRemember(interaction);
        break;
      default:
        await interaction.reply({
          content: `Unknown command: ${commandName}`,
          ephemeral: true,
        });
    }
  } catch (error) {
    logger.error(`Command execution failed: ${commandName}`, error);
    
    // Try to interpret the error for the user
    const errorMessage = error instanceof Error ? error.message : String(error);
    let userMessage = errorMessage;
    
    try {
      userMessage = await agentClient.interpretError(
        errorMessage,
        `Failed to execute /${commandName}`,
        validation.persona?.name
      );
    } catch {
      // If interpretation fails, use original message
    }

    const replyOptions = {
      content: userMessage,
      ephemeral: true,
    };

    if (interaction.replied || interaction.deferred) {
      await interaction.followUp(replyOptions);
    } else {
      await interaction.reply(replyOptions);
    }
  }
}

/**
 * Handle persona subcommands.
 */
async function handlePersonaCommand(
  interaction: ChatInputCommandInteraction,
  persona?: Persona
): Promise<void> {
  const subcommand = interaction.options.getSubcommand();

  switch (subcommand) {
    case "create":
      await handlePersonaCreate(interaction);
      // Invalidate cache after creating
      invalidatePersonaCache();
      break;
    case "list":
      await handlePersonaList(interaction);
      break;
    case "delete":
      await handlePersonaDelete(interaction);
      // Invalidate cache after deleting
      invalidatePersonaCache();
      break;
    case "rename":
      await handlePersonaRename(interaction);
      // Invalidate cache after renaming
      invalidatePersonaCache();
      break;
    case "edit":
      // Pass the auto-detected persona from the channel
      if (!persona) {
        await interaction.reply({
          content: "Could not determine persona for this channel.",
          ephemeral: true,
        });
        return;
      }
      await handlePersonaEdit(interaction, persona);
      // Invalidate cache after editing
      invalidatePersonaCache(persona.channel_id || undefined);
      break;
    default:
      await interaction.reply({
        content: `Unknown subcommand: ${subcommand}`,
        ephemeral: true,
      });
  }
}

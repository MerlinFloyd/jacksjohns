/**
 * Persona create, list, and edit command handlers.
 */

import type { ChatInputCommandInteraction, TextChannel } from "discord.js";
import { agentClient } from "../../services/agent-client";
import { logger } from "../../utils/logger";
import { createPersonaChannel } from "../../utils/channel";
import type { Persona } from "../../types/persona";

/**
 * Handle /persona create command.
 * Creates a persona in the API and a dedicated channel in Discord.
 */
export async function handlePersonaCreate(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const name = interaction.options.getString("name", true);
  const personality = interaction.options.getString("personality", true);
  const appearance = interaction.options.getString("appearance");

  await interaction.deferReply();

  const guild = interaction.guild;
  if (!guild) {
    await interaction.editReply({
      content: "This command must be used in a server.",
    });
    return;
  }

  let persona: Persona | null = null;
  let channel: TextChannel | null = null;

  try {
    // Step 1: Create persona in API (without channel_id first)
    persona = await agentClient.createPersona({
      name,
      personality,
      appearance: appearance || undefined,
    });

    // Step 2: Create Discord channel
    try {
      channel = await createPersonaChannel(guild, name);
    } catch (channelError) {
      // Channel creation failed, but persona exists
      const errorMsg = channelError instanceof Error ? channelError.message : String(channelError);
      logger.warn(`Channel creation failed for persona "${name}": ${errorMsg}`);
      
      // Try to get a user-friendly error interpretation
      let friendlyError = `Failed to create Discord channel: ${errorMsg}`;
      try {
        friendlyError = await agentClient.interpretError(
          errorMsg,
          "Failed to create Discord channel for persona",
          name
        );
      } catch {
        // If interpretation fails, use original message
      }

      await interaction.editReply({
        embeds: [
          {
            title: "Persona Created (Channel Failed)",
            color: 0xffaa00,
            description: friendlyError + "\n\nThe bot may need 'Manage Channels' permission.",
            fields: [
              { name: "Name", value: persona.name, inline: true },
              {
                name: "Personality",
                value: persona.personality.length > 200
                  ? persona.personality.substring(0, 200) + "..."
                  : persona.personality,
              },
            ],
          },
        ],
      });
      return;
    }

    // Step 3: Update persona with channel_id
    persona = await agentClient.updatePersona(name, {
      channel_id: channel.id,
    });

    // Success
    await interaction.editReply({
      embeds: [
        {
          title: "Persona Created",
          color: 0x00ff00,
          fields: [
            { name: "Name", value: persona.name, inline: true },
            { name: "Channel", value: `<#${channel.id}>`, inline: true },
            {
              name: "Personality",
              value: persona.personality.length > 200
                ? persona.personality.substring(0, 200) + "..."
                : persona.personality,
            },
            ...(persona.appearance
              ? [
                  {
                    name: "Appearance",
                    value: persona.appearance.length > 200
                      ? persona.appearance.substring(0, 200) + "..."
                      : persona.appearance,
                  },
                ]
              : []),
          ],
          footer: {
            text: "Chat with this persona by sending messages in their channel!",
          },
        },
      ],
    });

    logger.info(`Persona created: ${persona.name} with channel #${channel.name}`);
  } catch (error) {
    // Cleanup on failure
    if (channel) {
      try {
        await channel.delete("Persona creation failed");
      } catch {
        // Ignore cleanup errors
      }
    }
    if (persona) {
      try {
        await agentClient.deletePersona(name);
      } catch {
        // Ignore cleanup errors
      }
    }

    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to create persona: ${errorMessage}`);

    // Try to interpret the error
    let friendlyError = `Failed to create persona: ${errorMessage}`;
    try {
      friendlyError = await agentClient.interpretError(
        errorMessage,
        "Failed to create persona"
      );
    } catch {
      // If interpretation fails, use original message
    }

    await interaction.editReply({
      embeds: [
        {
          title: "Error",
          description: friendlyError,
          color: 0xff0000,
        },
      ],
    });
  }
}

/**
 * Handle /persona list command.
 */
export async function handlePersonaList(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  await interaction.deferReply();

  try {
    const personas = await agentClient.listPersonas();

    if (personas.length === 0) {
      await interaction.editReply({
        embeds: [
          {
            title: "Personas",
            description: "No personas found. Create one with `/persona create`.",
            color: 0x0099ff,
          },
        ],
      });
      return;
    }

    const fields = personas.map((p) => ({
      name: p.name + (p.channel_id ? ` (<#${p.channel_id}>)` : " (no channel)"),
      value:
        (p.personality.length > 100
          ? p.personality.substring(0, 100) + "..."
          : p.personality) +
        (p.appearance ? `\n*Appearance: ${p.appearance.substring(0, 50)}...*` : ""),
    }));

    await interaction.editReply({
      embeds: [
        {
          title: `Personas (${personas.length})`,
          color: 0x0099ff,
          fields,
          footer: {
            text: "Use /persona rename to rename, /persona delete to remove",
          },
        },
      ],
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to list personas: ${errorMessage}`);

    await interaction.editReply({
      embeds: [
        {
          title: "Error",
          description: `Failed to list personas: ${errorMessage}`,
          color: 0xff0000,
        },
      ],
    });
  }
}

/**
 * Handle /persona edit command (in persona channels only).
 * The persona is auto-detected from the channel.
 */
export async function handlePersonaEdit(
  interaction: ChatInputCommandInteraction,
  persona: Persona
): Promise<void> {
  const personality = interaction.options.getString("personality");
  const appearance = interaction.options.getString("appearance");

  if (!personality && !appearance) {
    await interaction.reply({
      content: "Please provide at least one field to update (`personality` or `appearance`).",
      ephemeral: true,
    });
    return;
  }

  await interaction.deferReply();

  try {
    const updateData: { personality?: string; appearance?: string } = {};
    if (personality) updateData.personality = personality;
    if (appearance) updateData.appearance = appearance;

    const updated = await agentClient.updatePersona(persona.name, updateData);

    await interaction.editReply({
      embeds: [
        {
          title: "Persona Updated",
          color: 0x00ff00,
          fields: [
            { name: "Name", value: updated.name, inline: true },
            ...(personality
              ? [
                  {
                    name: "Personality",
                    value: personality.length > 200
                      ? personality.substring(0, 200) + "..."
                      : personality,
                  },
                ]
              : []),
            ...(appearance
              ? [
                  {
                    name: "Appearance",
                    value: appearance.length > 200
                      ? appearance.substring(0, 200) + "..."
                      : appearance,
                  },
                ]
              : []),
            {
              name: "Updated",
              value: new Date(updated.updated_at).toLocaleString(),
              inline: true,
            },
          ],
        },
      ],
    });

    logger.info(`Persona updated: ${persona.name}`);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to update persona: ${errorMessage}`);

    // Try to interpret the error in character
    let friendlyError = `Failed to update persona: ${errorMessage}`;
    try {
      friendlyError = await agentClient.interpretError(
        errorMessage,
        `Failed to update persona "${persona.name}"`,
        persona.name
      );
    } catch {
      // If interpretation fails, use original message
    }

    await interaction.editReply({
      embeds: [
        {
          title: "Error",
          description: friendlyError,
          color: 0xff0000,
        },
      ],
    });
  }
}

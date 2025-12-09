/**
 * Persona delete command handler.
 */

import type { ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../../services/agent-client";
import { logger } from "../../utils/logger";
import { deletePersonaChannel } from "../../utils/channel";

/**
 * Handle /persona delete command.
 * Deletes a persona, its channel, memories, and session data.
 */
export async function handlePersonaDelete(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const name = interaction.options.getString("name", true);
  const confirm = interaction.options.getBoolean("confirm", true);

  if (!confirm) {
    await interaction.reply({
      content: "Deletion cancelled. Set `confirm` to `true` to delete the persona.",
      ephemeral: true,
    });
    return;
  }

  await interaction.deferReply();

  const guild = interaction.guild;
  if (!guild) {
    await interaction.editReply({
      content: "This command must be used in a server.",
    });
    return;
  }

  const results: string[] = [];

  try {
    // Get persona to find channel_id
    let persona;
    try {
      persona = await agentClient.getPersona(name);
    } catch (error) {
      await interaction.editReply({
        embeds: [
          {
            title: "Persona Not Found",
            description: `No persona named "${name}" was found.`,
            color: 0xff0000,
          },
        ],
      });
      return;
    }

    // 1. Delete channel session (if exists)
    if (persona.channel_id) {
      try {
        const result = await agentClient.deleteChannelSession(persona.channel_id);
        if (result.deleted) {
          results.push("Session data deleted");
        } else {
          results.push("Session: none found");
        }
      } catch (error) {
        results.push("Session: failed to delete");
        logger.warn(`Failed to delete channel session: ${error}`);
      }
    }

    // 2. Delete all memories for this persona
    try {
      const memResult = await agentClient.deletePersonaMemories(name);
      if (memResult.deleted_count > 0) {
        results.push(`${memResult.deleted_count} memories deleted`);
      } else {
        results.push("Memories: none found");
      }
    } catch (error) {
      results.push("Memories: failed to delete");
      logger.warn(`Failed to delete memories: ${error}`);
    }

    // 3. Delete Discord channel
    if (persona.channel_id) {
      const deleted = await deletePersonaChannel(guild, persona.channel_id);
      if (deleted) {
        results.push("Channel deleted");
      } else {
        results.push("Channel: not found or already deleted");
      }
    } else {
      results.push("Channel: none associated");
    }

    // 4. Delete persona from API
    await agentClient.deletePersona(name);
    results.push("Persona configuration deleted");

    await interaction.editReply({
      embeds: [
        {
          title: "Persona Deleted",
          color: 0xff6600,
          description: `**${name}** has been permanently deleted.`,
          fields: [
            {
              name: "Cleanup Results",
              value: results.map((r) => `- ${r}`).join("\n"),
            },
          ],
        },
      ],
    });

    logger.info(`Persona deleted: ${name}`);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to delete persona: ${errorMessage}`);

    // Try to interpret the error
    let friendlyError = `Failed to delete persona: ${errorMessage}`;
    try {
      friendlyError = await agentClient.interpretError(
        errorMessage,
        `Failed to delete persona "${name}"`
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
          ...(results.length > 0 && {
            fields: [
              {
                name: "Partial Results",
                value: results.map((r) => `- ${r}`).join("\n"),
              },
            ],
          }),
        },
      ],
    });
  }
}

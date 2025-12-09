/**
 * Persona rename command handler.
 */

import type { ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../../services/agent-client";
import { logger } from "../../utils/logger";
import { renamePersonaChannel } from "../../utils/channel";

/**
 * Handle /persona rename command.
 * Renames a persona, its channel, and migrates memories to new scope.
 */
export async function handlePersonaRename(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const currentName = interaction.options.getString("current_name", true);
  const newName = interaction.options.getString("new_name", true);

  await interaction.deferReply();

  const guild = interaction.guild;
  if (!guild) {
    await interaction.editReply({
      content: "This command must be used in a server.",
    });
    return;
  }

  try {
    // 1. Rename persona in API (this also migrates memories)
    const persona = await agentClient.renamePersona(currentName, newName);

    // 2. Rename Discord channel
    let channelRenamed = false;
    if (persona.channel_id) {
      channelRenamed = await renamePersonaChannel(guild, persona.channel_id, newName);
      if (!channelRenamed) {
        // Channel rename failed but persona renamed
        await interaction.editReply({
          embeds: [
            {
              title: "Persona Renamed (Channel Update Failed)",
              color: 0xffaa00,
              description: `Persona renamed to **${newName}** but the channel name could not be updated. You may need to rename the channel manually.`,
              fields: [
                { name: "Previous Name", value: currentName, inline: true },
                { name: "New Name", value: newName, inline: true },
              ],
            },
          ],
        });
        return;
      }
    }

    await interaction.editReply({
      embeds: [
        {
          title: "Persona Renamed",
          color: 0x00ff00,
          fields: [
            { name: "Previous Name", value: currentName, inline: true },
            { name: "New Name", value: newName, inline: true },
            ...(persona.channel_id
              ? [{ name: "Channel", value: `<#${persona.channel_id}>`, inline: true }]
              : []),
          ],
          footer: {
            text: "Memories have been migrated to the new name.",
          },
        },
      ],
    });

    logger.info(`Persona renamed: ${currentName} -> ${newName}`);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to rename persona: ${errorMessage}`);

    // Try to interpret the error
    let friendlyError = `Failed to rename persona: ${errorMessage}`;
    try {
      friendlyError = await agentClient.interpretError(
        errorMessage,
        `Failed to rename persona "${currentName}" to "${newName}"`
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

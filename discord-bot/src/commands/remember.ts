/**
 * Remember command handler.
 * Triggers memory generation from the current channel's conversation.
 */

import type { ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "../utils/logger";
import { getPersonaForChannel } from "../utils/channel";

/**
 * Handle /remember command.
 * Generates memories from the current channel's session without ending it.
 */
export async function handleRemember(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  await interaction.deferReply();

  const channelId = interaction.channelId;

  try {
    // Check if this is a persona channel
    const persona = await getPersonaForChannel(channelId);
    if (!persona) {
      await interaction.editReply({
        embeds: [
          {
            title: "Not a Persona Channel",
            description:
              "This command can only be used in a persona's channel. " +
              "Go to a persona channel to generate memories from that conversation.",
            color: 0xff6600,
          },
        ],
      });
      return;
    }

    // Generate memories from the channel session
    const result = await agentClient.generateChannelMemories(
      channelId,
      interaction.user.id
    );

    if (result.memories_generated === 0) {
      await interaction.editReply({
        embeds: [
          {
            title: "No New Memories",
            description:
              `${persona.name} didn't find any new memories to save from this conversation.\n\n` +
              "Try sharing more about yourself - your preferences, experiences, or interests!",
            color: 0xffcc00,
            footer: {
              text: `Session: ${result.session_id.slice(-8)}`,
            },
          },
        ],
      });
      return;
    }

    // Format the memories
    const memoryList = result.memories
      .slice(0, 10)
      .map((m, i) => `${i + 1}. ${m.fact}`)
      .join("\n");

    await interaction.editReply({
      embeds: [
        {
          title: `${persona.name} Remembered!`,
          description:
            `I've saved **${result.memories_generated}** new memories from our conversation:\n\n${memoryList}`,
          color: 0x00cc66,
          footer: {
            text:
              result.memories_generated > 10
                ? `Showing 10 of ${result.memories_generated} memories`
                : `${result.memories_generated} memories saved`,
          },
        },
      ],
    });

    logger.info(
      `Generated ${result.memories_generated} memories for channel ${channelId}, ` +
        `persona ${persona.name}, user ${interaction.user.id}`
    );
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to generate memories: ${errorMessage}`);

    // Check if it's a "no session" error
    if (errorMessage.includes("No session found")) {
      await interaction.editReply({
        embeds: [
          {
            title: "No Conversation Yet",
            description:
              "There's no conversation to remember! Start chatting first, " +
              "then use `/remember` to save what you've discussed.",
            color: 0xffcc00,
          },
        ],
      });
      return;
    }

    // Try to interpret the error
    let friendlyError = `Failed to generate memories: ${errorMessage}`;
    try {
      const persona = await getPersonaForChannel(channelId);
      friendlyError = await agentClient.interpretError(
        errorMessage,
        "Failed to generate memories from conversation",
        persona?.name
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

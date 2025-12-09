/**
 * Memories command handler.
 */

import type { ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "../utils/logger";

/**
 * Handle /memories command.
 * Lists memories for a persona, optionally filtered by user.
 */
export async function handleMemories(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const personaName = interaction.options.getString("persona", true);
  const targetUser = interaction.options.getUser("user");
  const search = interaction.options.getString("search");

  await interaction.deferReply();

  try {
    // Use target user's ID or the command invoker's ID
    const userId = targetUser?.id || interaction.user.id;
    const isOwnMemories = userId === interaction.user.id;

    const memories = await agentClient.listMemories(
      personaName,
      userId,
      search || undefined,
      20
    );

    if (memories.length === 0) {
      const whoFor = isOwnMemories
        ? "you"
        : `<@${targetUser!.id}>`;
      
      await interaction.editReply({
        embeds: [
          {
            title: `Memories for ${personaName}`,
            description: `No memories found for ${whoFor}${search ? ` matching "${search}"` : ""}.`,
            color: 0x5865f2,
          },
        ],
      });
      return;
    }

    const memoryList = memories
      .slice(0, 15)
      .map((m, i) => `${i + 1}. ${m.fact}`)
      .join("\n");

    await interaction.editReply({
      embeds: [
        {
          title: `Memories for ${personaName}`,
          color: 0x5865f2,
          description: memoryList,
          footer: {
            text: `Showing ${Math.min(memories.length, 15)} of ${memories.length} memories`,
          },
          ...(targetUser && {
            author: {
              name: `User: ${targetUser.username}`,
              icon_url: targetUser.displayAvatarURL(),
            },
          }),
          ...(search && {
            fields: [
              {
                name: "Search",
                value: search,
                inline: true,
              },
            ],
          }),
        },
      ],
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to list memories: ${errorMessage}`);

    // Try to interpret the error
    let friendlyError = `Failed to list memories: ${errorMessage}`;
    try {
      friendlyError = await agentClient.interpretError(
        errorMessage,
        `Failed to list memories for "${personaName}"`
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

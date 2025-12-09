/**
 * Forget command handler - delete memories.
 */

import type { ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "../utils/logger";

/**
 * Handle /forget command.
 * Delete memories for a persona - either a specific one by number or all.
 */
export async function handleForget(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const personaName = interaction.options.getString("persona", true);
  const memoryNumber = interaction.options.getInteger("number");
  const deleteAll = interaction.options.getBoolean("all") ?? false;

  await interaction.deferReply({ ephemeral: true });

  try {
    const userId = interaction.user.id;

    // If neither specific number nor delete all, show the list first
    if (!memoryNumber && !deleteAll) {
      const memories = await agentClient.listMemories(personaName, userId, undefined, 20);

      if (memories.length === 0) {
        await interaction.editReply({
          embeds: [
            {
              title: `No Memories Found`,
              description: `You have no memories with ${personaName}.`,
              color: 0x5865f2,
            },
          ],
        });
        return;
      }

      const memoryList = memories
        .map((m, i) => `**${i + 1}.** ${m.fact}`)
        .join("\n");

      await interaction.editReply({
        embeds: [
          {
            title: `Your Memories with ${personaName}`,
            description: memoryList,
            color: 0x5865f2,
            footer: {
              text: `To delete: /forget persona:${personaName} number:<#> or /forget persona:${personaName} all:true`,
            },
          },
        ],
      });
      return;
    }

    // Delete all memories
    if (deleteAll) {
      const result = await agentClient.deletePersonaMemories(personaName, userId);

      await interaction.editReply({
        embeds: [
          {
            title: "Memories Deleted",
            description: `Deleted ${result.deleted_count} memor${result.deleted_count === 1 ? "y" : "ies"} with ${personaName}.`,
            color: 0x57f287,
          },
        ],
      });
      return;
    }

    // Delete specific memory by number
    if (memoryNumber) {
      // First, get the list to find the memory ID
      const memories = await agentClient.listMemories(personaName, userId, undefined, 20);

      if (memoryNumber < 1 || memoryNumber > memories.length) {
        await interaction.editReply({
          embeds: [
            {
              title: "Invalid Memory Number",
              description: `Please provide a number between 1 and ${memories.length}. Use \`/forget persona:${personaName}\` to see the list.`,
              color: 0xed4245,
            },
          ],
        });
        return;
      }

      const memoryToDelete = memories[memoryNumber - 1];
      const result = await agentClient.deleteSingleMemory(memoryToDelete.id);

      if (result.deleted) {
        await interaction.editReply({
          embeds: [
            {
              title: "Memory Deleted",
              description: `Deleted memory: "${memoryToDelete.fact}"`,
              color: 0x57f287,
            },
          ],
        });
      } else {
        await interaction.editReply({
          embeds: [
            {
              title: "Memory Not Found",
              description: "The memory may have already been deleted.",
              color: 0xfee75c,
            },
          ],
        });
      }
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to delete memory: ${errorMessage}`);

    // Try to interpret the error
    let friendlyError = `Failed to delete memory: ${errorMessage}`;
    try {
      friendlyError = await agentClient.interpretError(
        errorMessage,
        `Failed to delete memory for "${personaName}"`
      );
    } catch {
      // If interpretation fails, use original message
    }

    await interaction.editReply({
      embeds: [
        {
          title: "Error",
          description: friendlyError,
          color: 0xed4245,
        },
      ],
    });
  }
}

/**
 * Chat command handlers for interacting with AI personas.
 */

import type { ChatInputCommandInteraction, Message } from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "../utils/logger";

// Store active sessions per user-persona combination
// Key format: `${userId}:${personaName}`
const activeSessions: Map<string, string> = new Map();

function getSessionKey(userId: string, personaName: string): string {
  return `${userId}:${personaName.toLowerCase()}`;
}

/**
 * Handle the /chat command - start or continue a conversation with a persona.
 */
export async function handleChat(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const personaName = interaction.options.getString("persona", true);
  const message = interaction.options.getString("message", true);
  const userId = interaction.user.id;

  await interaction.deferReply();

  try {
    // Get existing session if any
    const sessionKey = getSessionKey(userId, personaName);
    const existingSessionId = activeSessions.get(sessionKey);

    // Send chat request
    const response = await agentClient.chat({
      persona_name: personaName,
      user_id: userId,
      message,
      session_id: existingSessionId,
    });

    // Store the session for future messages
    activeSessions.set(sessionKey, response.session_id);

    // Format response with metadata
    const memoryInfo = response.memories_used > 0 
      ? `\n-# Using ${response.memories_used} memories` 
      : "";

    await interaction.editReply({
      content: `**${personaName}**: ${response.response}${memoryInfo}`,
    });

    logger.info(
      `Chat completed: persona=${personaName}, user=${userId}, session=${response.session_id}, memories=${response.memories_used}`
    );
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`Chat failed: ${errorMessage}`, error);

    await interaction.editReply({
      content: `Failed to chat with ${personaName}: ${errorMessage}`,
    });
  }
}

/**
 * Handle the /chat end command - end a conversation and generate memories.
 */
export async function handleChatEnd(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const personaName = interaction.options.getString("persona", true);
  const generateMemories = interaction.options.getBoolean("save_memories") ?? true;
  const userId = interaction.user.id;

  await interaction.deferReply({ ephemeral: true });

  try {
    const sessionKey = getSessionKey(userId, personaName);
    const sessionId = activeSessions.get(sessionKey);

    if (!sessionId) {
      await interaction.editReply({
        content: `No active session with ${personaName}. Start a conversation first with \`/chat\`.`,
      });
      return;
    }

    // End the session
    const response = await agentClient.endSession(
      personaName,
      userId,
      sessionId,
      generateMemories
    );

    // Remove from active sessions
    activeSessions.delete(sessionKey);

    const memoryMessage = response.memories_generated > 0
      ? `\nGenerated ${response.memories_generated} new memories from our conversation.`
      : "";

    await interaction.editReply({
      content: `Ended conversation with ${personaName}.${memoryMessage}`,
    });

    logger.info(
      `Session ended: persona=${personaName}, user=${userId}, memories=${response.memories_generated}`
    );
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`End session failed: ${errorMessage}`, error);

    await interaction.editReply({
      content: `Failed to end session: ${errorMessage}`,
    });
  }
}

/**
 * Handle the /chat sessions command - list active sessions.
 */
export async function handleChatSessions(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const personaName = interaction.options.getString("persona");
  const userId = interaction.user.id;

  await interaction.deferReply({ ephemeral: true });

  try {
    if (personaName) {
      // List sessions for a specific persona
      const sessions = await agentClient.listSessions(personaName, userId);

      if (sessions.length === 0) {
        await interaction.editReply({
          content: `No sessions found with ${personaName}.`,
        });
        return;
      }

      const sessionList = sessions
        .map((s) => `- Session ${s.session_id}: ${s.event_count} messages`)
        .join("\n");

      await interaction.editReply({
        content: `**Sessions with ${personaName}:**\n${sessionList}`,
      });
    } else {
      // Show all active sessions for this user
      const activeList: string[] = [];
      for (const [key, sessionId] of activeSessions.entries()) {
        if (key.startsWith(`${userId}:`)) {
          const persona = key.split(":")[1];
          activeList.push(`- **${persona}**: Session ${sessionId.slice(0, 8)}...`);
        }
      }

      if (activeList.length === 0) {
        await interaction.editReply({
          content: "No active chat sessions. Start one with `/chat`.",
        });
        return;
      }

      await interaction.editReply({
        content: `**Your Active Sessions:**\n${activeList.join("\n")}`,
      });
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`List sessions failed: ${errorMessage}`, error);

    await interaction.editReply({
      content: `Failed to list sessions: ${errorMessage}`,
    });
  }
}

/**
 * Handle the /chat memories command - view memories for a persona.
 */
export async function handleChatMemories(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const personaName = interaction.options.getString("persona", true);
  const showShared = interaction.options.getBoolean("shared") ?? false;
  const userId = interaction.user.id;

  await interaction.deferReply({ ephemeral: true });

  try {
    // Get memories - either user-specific or shared
    const memories = await agentClient.listMemories(
      personaName,
      showShared ? undefined : userId,
      undefined,
      10
    );

    if (memories.length === 0) {
      const memoryType = showShared ? "shared" : "personal";
      await interaction.editReply({
        content: `No ${memoryType} memories found for ${personaName}. Chat more to build memories!`,
      });
      return;
    }

    const memoryType = showShared ? "Shared" : "Your";
    const memoryList = memories
      .slice(0, 10)
      .map((m, i) => `${i + 1}. ${m.fact}`)
      .join("\n");

    await interaction.editReply({
      content: `**${memoryType} Memories with ${personaName}:**\n${memoryList}`,
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`List memories failed: ${errorMessage}`, error);

    await interaction.editReply({
      content: `Failed to list memories: ${errorMessage}`,
    });
  }
}

/**
 * Handle the /chat teach command - add a memory directly.
 */
export async function handleChatTeach(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const personaName = interaction.options.getString("persona", true);
  const fact = interaction.options.getString("fact", true);
  const shared = interaction.options.getBoolean("shared") ?? false;
  const userId = interaction.user.id;

  await interaction.deferReply({ ephemeral: true });

  try {
    // Create the memory
    await agentClient.createMemory(
      personaName,
      fact,
      shared ? undefined : userId
    );

    const memoryType = shared ? "shared" : "personal";
    await interaction.editReply({
      content: `Added ${memoryType} memory for ${personaName}: "${fact}"`,
    });

    logger.info(
      `Memory created: persona=${personaName}, user=${userId}, shared=${shared}`
    );
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`Create memory failed: ${errorMessage}`, error);

    await interaction.editReply({
      content: `Failed to add memory: ${errorMessage}`,
    });
  }
}

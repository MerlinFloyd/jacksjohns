/**
 * Discord Bot Entry Point
 * 
 * Main file that initializes the Discord client and handles events.
 * 
 * Features:
 * - Slash command handling with channel-based restrictions
 * - Auto-chat in persona channels (messages sent directly to bot)
 * - Startup sync to recreate missing persona channels
 */

import {
  Client,
  GatewayIntentBits,
  REST,
  Routes,
  Events,
  ChannelType,
  TextChannel,
} from "discord.js";

import { config } from "./config/env";
import { commands, handleCommand } from "./commands";
import { logger } from "./utils/logger";
import { agentClient } from "./services/agent-client";
import { getPersonaForChannel, syncPersonaChannels, isAdminChannel } from "./utils/channel";

// Health check server for Cloud Run
const PORT = process.env.PORT || 8080;
let isReady = false;

const server = Bun.serve({
  port: PORT,
  fetch(req) {
    const url = new URL(req.url);
    if (url.pathname === "/health" || url.pathname === "/") {
      if (isReady) {
        return new Response(JSON.stringify({ status: "healthy", service: "discord-bot" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ status: "starting" }), {
        status: 503,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response("Not Found", { status: 404 });
  },
});

logger.info(`Health check server listening on port ${PORT}`);

// Create Discord client with required intents
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

// Register slash commands
async function registerCommands(): Promise<void> {
  const rest = new REST({ version: "10" }).setToken(config.discord.token);

  try {
    logger.info("Registering slash commands...");
    logger.info(`Commands to register (${commands.length}):`);
    for (const cmd of commands) {
      logger.info(`  - /${cmd.name}: ${cmd.description}`);
    }

    const result = await rest.put(Routes.applicationCommands(config.discord.applicationId), {
      body: commands,
    });

    const registeredCommands = result as Array<{ name: string; id: string }>;
    logger.info(`Successfully registered ${registeredCommands.length} commands with Discord:`);
    for (const cmd of registeredCommands) {
      logger.info(`  - /${cmd.name} (id: ${cmd.id})`);
    }
  } catch (error) {
    logger.error("Failed to register commands:", error);
    throw error;
  }
}

// Handle auto-chat in persona channels
async function handlePersonaChannelMessage(message: {
  author: { id: string; bot: boolean; username: string };
  member?: { displayName: string } | null;
  channelId: string;
  content: string;
  reply: (options: { content: string; allowedMentions?: { repliedUser: boolean } }) => Promise<unknown>;
}): Promise<void> {
  // Ignore bot messages
  if (message.author.bot) return;

  // Check if this is a persona channel
  const persona = await getPersonaForChannel(message.channelId);
  if (!persona) return;

  // Don't process messages that start with / (commands)
  if (message.content.startsWith("/")) return;

  // Don't process empty messages
  if (!message.content.trim()) return;

  try {
    // Send to chat API with channel mode
    const response = await agentClient.chat({
      persona_name: persona.name,
      user_id: message.author.id,
      message: message.content,
      user_display_name: message.member?.displayName || message.author.username,
      is_channel_chat: true,
      channel_id: message.channelId,
    });

    // Only respond if the LLM decided to
    if (response.should_respond && response.response.trim()) {
      await message.reply({
        content: response.response,
        allowedMentions: { repliedUser: false },
      });
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Auto-chat error in channel ${message.channelId}:`, error);

    // Try to interpret the error in character
    try {
      const errorInterpretation = await agentClient.interpretError(
        errorMessage,
        "Failed to process your message",
        persona.name
      );
      await message.reply({
        content: errorInterpretation,
        allowedMentions: { repliedUser: false },
      });
    } catch {
      // If error interpretation fails too, send generic message
      await message.reply({
        content: "I'm having trouble responding right now. Please try again later.",
        allowedMentions: { repliedUser: false },
      });
    }
  }
}

// Event handlers
client.once(Events.ClientReady, async (readyClient) => {
  isReady = true;
  logger.info("=".repeat(50));
  logger.info(`Discord bot ready!`);
  logger.info(`Logged in as: ${readyClient.user.tag}`);
  logger.info(`Application ID: ${config.discord.applicationId}`);
  logger.info(`Agent Service: ${config.agentService.url}`);
  logger.info(`Admin Channel: #${config.discord.adminChannelName}`);
  logger.info("=".repeat(50));

  // Sync persona channels for each guild
  for (const guild of readyClient.guilds.cache.values()) {
    try {
      logger.info(`Syncing persona channels for guild: ${guild.name}`);
      const personas = await agentClient.listPersonas();
      const result = await syncPersonaChannels(guild, personas);

      if (result.created.length > 0) {
        logger.info(`Created ${result.created.length} missing channels: ${result.created.join(", ")}`);
      }
      if (result.errors.length > 0) {
        logger.warn(`Channel sync errors:`, result.errors);

        // Try to post errors to admin channel
        const adminChannel = guild.channels.cache.find(
          (ch) =>
            ch.type === ChannelType.GuildText &&
            isAdminChannel(ch.name, config.discord.adminChannelName)
        ) as TextChannel | undefined;

        if (adminChannel) {
          const errorMessages = result.errors
            .map((e) => `- **${e.persona}**: ${e.error}`)
            .join("\n");
          await adminChannel.send({
            embeds: [
              {
                title: "Persona Channel Sync Errors",
                color: 0xff6600,
                description: `Some persona channels could not be synced:\n\n${errorMessages}`,
              },
            ],
          });
        }
      }

      if (result.created.length === 0 && result.errors.length === 0) {
        logger.info(`All persona channels synced for ${guild.name}`);
      }
    } catch (error) {
      logger.error(`Failed to sync channels for guild ${guild.name}:`, error);
    }
  }
});

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  try {
    await handleCommand(interaction);
  } catch (error) {
    logger.error("Command execution failed:", error);

    const errorMessage = "An error occurred while executing this command.";

    if (interaction.replied || interaction.deferred) {
      await interaction.followUp({ content: errorMessage, ephemeral: true });
    } else {
      await interaction.reply({ content: errorMessage, ephemeral: true });
    }
  }
});

// Handle messages in persona channels (auto-chat)
client.on(Events.MessageCreate, async (message) => {
  // Ignore DMs
  if (!message.guild) return;

  await handlePersonaChannelMessage(message);
});

client.on(Events.Error, (error) => {
  logger.error("Discord client error:", error);
});

// Main startup
async function main(): Promise<void> {
  try {
    logger.info("Starting Discord bot...");

    // Register commands first
    await registerCommands();

    // Login to Discord
    await client.login(config.discord.token);
  } catch (error) {
    logger.error("Failed to start bot:", error);
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on("SIGINT", () => {
  logger.info("Received SIGINT, shutting down...");
  client.destroy();
  process.exit(0);
});

process.on("SIGTERM", () => {
  logger.info("Received SIGTERM, shutting down...");
  client.destroy();
  process.exit(0);
});

// Start the bot
main();

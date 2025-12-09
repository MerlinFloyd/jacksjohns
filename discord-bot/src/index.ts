/**
 * Discord Bot Entry Point
 * 
 * Main file that initializes the Discord client and handles events.
 */

import {
  Client,
  GatewayIntentBits,
  REST,
  Routes,
  Events,
} from "discord.js";

import { config } from "./config/env";
import { commands, handleCommand } from "./commands";
import { logger } from "./utils/logger";

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

// Event handlers
client.once(Events.ClientReady, (readyClient) => {
  isReady = true;
  logger.info("=".repeat(50));
  logger.info(`Discord bot ready!`);
  logger.info(`Logged in as: ${readyClient.user.tag}`);
  logger.info(`Application ID: ${config.discord.applicationId}`);
  logger.info(`Agent Service: ${config.agentService.url}`);
  logger.info("=".repeat(50));
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

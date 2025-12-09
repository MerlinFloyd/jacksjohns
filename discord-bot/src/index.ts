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

    await rest.put(Routes.applicationCommands(config.discord.applicationId), {
      body: commands,
    });

    logger.info(`Successfully registered ${commands.length} commands`);
  } catch (error) {
    logger.error("Failed to register commands:", error);
    throw error;
  }
}

// Event handlers
client.once(Events.ClientReady, (readyClient) => {
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

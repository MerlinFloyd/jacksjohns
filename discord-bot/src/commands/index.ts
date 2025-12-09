/**
 * Command registry and definitions.
 */

import {
  SlashCommandBuilder,
  type ChatInputCommandInteraction,
  type RESTPostAPIChatInputApplicationCommandsJSONBody,
} from "discord.js";

import { handlePersonaCreate, handlePersonaList, handlePersonaEdit } from "./persona/create";
import { handleImagine } from "./imagine";
import {
  handleChat,
  handleChatEnd,
  handleChatSessions,
  handleChatMemories,
  handleChatTeach,
} from "./chat";

// Command definitions
export const commands: RESTPostAPIChatInputApplicationCommandsJSONBody[] = [
  // Persona commands
  new SlashCommandBuilder()
    .setName("persona")
    .setDescription("Manage AI personas")
    .addSubcommand((subcommand) =>
      subcommand
        .setName("create")
        .setDescription("Create a new AI persona")
        .addStringOption((option) =>
          option
            .setName("name")
            .setDescription("Name of the persona")
            .setRequired(true)
            .setMaxLength(100)
        )
        .addStringOption((option) =>
          option
            .setName("personality")
            .setDescription("Personality description")
            .setRequired(true)
            .setMaxLength(2000)
        )
    )
    .addSubcommand((subcommand) =>
      subcommand.setName("list").setDescription("List all personas")
    )
    .addSubcommand((subcommand) =>
      subcommand
        .setName("edit")
        .setDescription("Edit an existing persona")
        .addStringOption((option) =>
          option
            .setName("name")
            .setDescription("Name of the persona to edit")
            .setRequired(true)
        )
        .addStringOption((option) =>
          option
            .setName("field")
            .setDescription("Field to edit")
            .setRequired(true)
            .addChoices(
              { name: "name", value: "name" },
              { name: "personality", value: "personality" }
            )
        )
        .addStringOption((option) =>
          option
            .setName("value")
            .setDescription("New value for the field")
            .setRequired(true)
            .setMaxLength(2000)
        )
    )
    .toJSON(),

  // Image generation command
  new SlashCommandBuilder()
    .setName("imagine")
    .setDescription("Generate an image from a text prompt")
    .addStringOption((option) =>
      option
        .setName("prompt")
        .setDescription("Description of the image to generate")
        .setRequired(true)
        .setMaxLength(4000)
    )
    .addStringOption((option) =>
      option
        .setName("aspect_ratio")
        .setDescription("Aspect ratio of the image")
        .setRequired(false)
        .addChoices(
          { name: "1:1 (Square)", value: "1:1" },
          { name: "16:9 (Landscape)", value: "16:9" },
          { name: "9:16 (Portrait)", value: "9:16" },
          { name: "4:3", value: "4:3" },
          { name: "3:4", value: "3:4" },
          { name: "3:2", value: "3:2" },
          { name: "2:3", value: "2:3" }
        )
    )
    .toJSON(),

  // Chat command - interact with personas with memory
  new SlashCommandBuilder()
    .setName("chat")
    .setDescription("Chat with AI personas - conversations with memory")
    .addSubcommand((subcommand) =>
      subcommand
        .setName("talk")
        .setDescription("Send a message to a persona")
        .addStringOption((option) =>
          option
            .setName("persona")
            .setDescription("Name of the persona to chat with")
            .setRequired(true)
        )
        .addStringOption((option) =>
          option
            .setName("message")
            .setDescription("Your message to the persona")
            .setRequired(true)
            .setMaxLength(4000)
        )
    )
    .addSubcommand((subcommand) =>
      subcommand
        .setName("end")
        .setDescription("End a conversation and save memories")
        .addStringOption((option) =>
          option
            .setName("persona")
            .setDescription("Name of the persona")
            .setRequired(true)
        )
        .addBooleanOption((option) =>
          option
            .setName("save_memories")
            .setDescription("Generate memories from this conversation (default: true)")
            .setRequired(false)
        )
    )
    .addSubcommand((subcommand) =>
      subcommand
        .setName("sessions")
        .setDescription("View your active chat sessions")
        .addStringOption((option) =>
          option
            .setName("persona")
            .setDescription("Filter by persona name (optional)")
            .setRequired(false)
        )
    )
    .addSubcommand((subcommand) =>
      subcommand
        .setName("memories")
        .setDescription("View memories a persona has about you")
        .addStringOption((option) =>
          option
            .setName("persona")
            .setDescription("Name of the persona")
            .setRequired(true)
        )
        .addBooleanOption((option) =>
          option
            .setName("shared")
            .setDescription("View shared memories instead of personal (default: false)")
            .setRequired(false)
        )
    )
    .addSubcommand((subcommand) =>
      subcommand
        .setName("teach")
        .setDescription("Teach a persona something directly")
        .addStringOption((option) =>
          option
            .setName("persona")
            .setDescription("Name of the persona")
            .setRequired(true)
        )
        .addStringOption((option) =>
          option
            .setName("fact")
            .setDescription("The fact to teach the persona")
            .setRequired(true)
            .setMaxLength(500)
        )
        .addBooleanOption((option) =>
          option
            .setName("shared")
            .setDescription("Make this a shared memory for all users (default: false)")
            .setRequired(false)
        )
    )
    .toJSON(),
];

// Command handler router
export async function handleCommand(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const commandName = interaction.commandName;

  switch (commandName) {
    case "persona":
      await handlePersonaCommand(interaction);
      break;
    case "imagine":
      await handleImagine(interaction);
      break;
    case "chat":
      await handleChatCommand(interaction);
      break;
    default:
      await interaction.reply({
        content: `Unknown command: ${commandName}`,
        ephemeral: true,
      });
  }
}

async function handlePersonaCommand(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const subcommand = interaction.options.getSubcommand();

  switch (subcommand) {
    case "create":
      await handlePersonaCreate(interaction);
      break;
    case "list":
      await handlePersonaList(interaction);
      break;
    case "edit":
      await handlePersonaEdit(interaction);
      break;
    default:
      await interaction.reply({
        content: `Unknown subcommand: ${subcommand}`,
        ephemeral: true,
      });
  }
}

async function handleChatCommand(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const subcommand = interaction.options.getSubcommand();

  switch (subcommand) {
    case "talk":
      await handleChat(interaction);
      break;
    case "end":
      await handleChatEnd(interaction);
      break;
    case "sessions":
      await handleChatSessions(interaction);
      break;
    case "memories":
      await handleChatMemories(interaction);
      break;
    case "teach":
      await handleChatTeach(interaction);
      break;
    default:
      await interaction.reply({
        content: `Unknown subcommand: ${subcommand}`,
        ephemeral: true,
      });
  }
}

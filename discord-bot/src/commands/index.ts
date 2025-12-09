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

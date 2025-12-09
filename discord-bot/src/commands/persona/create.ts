/**
 * Persona command handlers.
 */

import type { ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../../services/agent-client";
import { logger } from "../../utils/logger";

export async function handlePersonaCreate(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const name = interaction.options.getString("name", true);
  const personality = interaction.options.getString("personality", true);

  await interaction.deferReply();

  try {
    const persona = await agentClient.createPersona({ name, personality });

    await interaction.editReply({
      embeds: [
        {
          title: "Persona Created",
          color: 0x00ff00,
          fields: [
            { name: "Name", value: persona.name, inline: true },
            { name: "Personality", value: persona.personality },
            {
              name: "Created",
              value: new Date(persona.created_at).toLocaleString(),
              inline: true,
            },
          ],
        },
      ],
    });

    logger.info(`Persona created: ${persona.name}`);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`Failed to create persona: ${errorMessage}`);

    await interaction.editReply({
      embeds: [
        {
          title: "Error",
          description: `Failed to create persona: ${errorMessage}`,
          color: 0xff0000,
        },
      ],
    });
  }
}

export async function handlePersonaList(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  await interaction.deferReply();

  try {
    const personas = await agentClient.listPersonas();

    if (personas.length === 0) {
      await interaction.editReply({
        embeds: [
          {
            title: "Personas",
            description: "No personas found. Create one with `/persona create`.",
            color: 0x0099ff,
          },
        ],
      });
      return;
    }

    const fields = personas.map((p) => ({
      name: p.name,
      value: p.personality.length > 100 
        ? p.personality.substring(0, 100) + "..." 
        : p.personality,
    }));

    await interaction.editReply({
      embeds: [
        {
          title: `Personas (${personas.length})`,
          color: 0x0099ff,
          fields,
        },
      ],
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`Failed to list personas: ${errorMessage}`);

    await interaction.editReply({
      embeds: [
        {
          title: "Error",
          description: `Failed to list personas: ${errorMessage}`,
          color: 0xff0000,
        },
      ],
    });
  }
}

export async function handlePersonaEdit(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const name = interaction.options.getString("name", true);
  const field = interaction.options.getString("field", true) as "name" | "personality";
  const value = interaction.options.getString("value", true);

  await interaction.deferReply();

  try {
    const updateData = { [field]: value };
    const persona = await agentClient.updatePersona(name, updateData);

    await interaction.editReply({
      embeds: [
        {
          title: "Persona Updated",
          color: 0x00ff00,
          fields: [
            { name: "Name", value: persona.name, inline: true },
            { name: "Personality", value: persona.personality },
            {
              name: "Updated",
              value: new Date(persona.updated_at).toLocaleString(),
              inline: true,
            },
          ],
        },
      ],
    });

    logger.info(`Persona updated: ${name} -> ${field}: ${value}`);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`Failed to update persona: ${errorMessage}`);

    await interaction.editReply({
      embeds: [
        {
          title: "Error",
          description: `Failed to update persona: ${errorMessage}`,
          color: 0xff0000,
        },
      ],
    });
  }
}

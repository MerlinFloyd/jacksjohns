/**
 * Image generation command handler.
 * 
 * When used in a persona channel, the persona's appearance is automatically
 * prepended to the prompt for character consistency.
 */

import { AttachmentBuilder, type ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "../utils/logger";
import type { Persona } from "../types/persona";

/**
 * Handle /imagine command.
 * @param interaction - The Discord interaction
 * @param persona - Optional persona if called from a persona channel (appearance will be used)
 */
export async function handleImagine(
  interaction: ChatInputCommandInteraction,
  persona?: Persona
): Promise<void> {
  const prompt = interaction.options.getString("prompt", true);
  const aspectRatio = interaction.options.getString("aspect_ratio") ?? "1:1";

  // Defer reply since image generation can take time
  await interaction.deferReply();

  try {
    logger.info(`Generating image for prompt: ${prompt.substring(0, 50)}...`);
    if (persona?.appearance) {
      logger.info(`Including persona "${persona.name}" appearance in prompt`);
    }

    // Generate image via agent service
    // If persona is provided, the API will prepend appearance to the prompt
    const result = await agentClient.generateImage({
      prompt,
      aspect_ratio: aspectRatio,
      persona_name: persona?.name,
    });

    // Decode base64 image
    const imageBuffer = Buffer.from(result.image_base64, "base64");

    // Create attachment
    const attachment = new AttachmentBuilder(imageBuffer, {
      name: "generated-image.png",
      description: prompt.substring(0, 100),
    });

    // Build response embed
    const embed: {
      title: string;
      color: number;
      fields: Array<{ name: string; value: string; inline?: boolean }>;
      image: { url: string };
      footer: { text: string };
    } = {
      title: persona ? `Image by ${persona.name}` : "Generated Image",
      color: 0x9945ff,
      fields: [
        {
          name: "Prompt",
          value: prompt.length > 1000 ? prompt.substring(0, 1000) + "..." : prompt,
        },
        {
          name: "Aspect Ratio",
          value: aspectRatio,
          inline: true,
        },
      ],
      image: {
        url: "attachment://generated-image.png",
      },
      footer: {
        text: persona?.appearance
          ? `Using ${persona.name}'s appearance - Gemini 2.5 Flash`
          : "Generated with Gemini 2.5 Flash Image",
      },
    };

    // Show persona appearance if used
    if (persona?.appearance) {
      embed.fields.splice(1, 0, {
        name: "Persona Appearance",
        value: persona.appearance.length > 200
          ? persona.appearance.substring(0, 200) + "..."
          : persona.appearance,
      });
    }

    // Add model response if available
    if (result.text_response) {
      embed.fields.push({
        name: "Model Response",
        value: result.text_response.length > 500
          ? result.text_response.substring(0, 500) + "..."
          : result.text_response,
      });
    }

    await interaction.editReply({
      embeds: [embed],
      files: [attachment],
    });

    logger.info(`Image generated successfully for prompt: ${prompt.substring(0, 50)}...`);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to generate image: ${errorMessage}`);

    // Try to interpret the error (in character if persona provided)
    let friendlyError = `Failed to generate image: ${errorMessage}`;
    try {
      friendlyError = await agentClient.interpretError(
        errorMessage,
        "Failed to generate image",
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
          fields: [
            {
              name: "Prompt",
              value: prompt.length > 500 ? prompt.substring(0, 500) + "..." : prompt,
            },
          ],
        },
      ],
    });
  }
}

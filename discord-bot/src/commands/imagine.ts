/**
 * Image generation command handler.
 */

import { AttachmentBuilder, type ChatInputCommandInteraction } from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "../utils/logger";

export async function handleImagine(
  interaction: ChatInputCommandInteraction
): Promise<void> {
  const prompt = interaction.options.getString("prompt", true);
  const aspectRatio = interaction.options.getString("aspect_ratio") ?? "1:1";

  // Defer reply since image generation can take time
  await interaction.deferReply();

  try {
    logger.info(`Generating image for prompt: ${prompt.substring(0, 50)}...`);

    // Generate image via agent service
    const result = await agentClient.generateImage({
      prompt,
      aspect_ratio: aspectRatio,
    });

    // Decode base64 image
    const imageBuffer = Buffer.from(result.image_base64, "base64");

    // Create attachment
    const attachment = new AttachmentBuilder(imageBuffer, {
      name: "generated-image.png",
      description: prompt.substring(0, 100),
    });

    // Build response embed
    const embed = {
      title: "Generated Image",
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
        text: "Generated with Gemini 2.5 Flash Image",
      },
    };

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
    const errorMessage = error instanceof Error ? error.message : "Unknown error";
    logger.error(`Failed to generate image: ${errorMessage}`);

    await interaction.editReply({
      embeds: [
        {
          title: "Error",
          description: `Failed to generate image: ${errorMessage}`,
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

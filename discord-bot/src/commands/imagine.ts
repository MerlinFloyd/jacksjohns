/**
 * Image generation command handler.
 * 
 * When used in a persona channel, the persona's appearance is automatically
 * prepended to the prompt for character consistency.
 * 
 * Supports generating multiple images based on persona/default settings.
 */

import { AttachmentBuilder, type ChatInputCommandInteraction, EmbedBuilder } from "discord.js";
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

    // Generate image(s) via agent service
    // If persona is provided, the API will prepend appearance to the prompt
    // Number of images is determined by persona/default settings
    const result = await agentClient.generateImage({
      prompt,
      aspect_ratio: aspectRatio,
      persona_name: persona?.name,
    });

    // Create attachments for all generated images
    const attachments: AttachmentBuilder[] = [];
    const imageCount = result.images?.length || 1;
    
    if (result.images && result.images.length > 0) {
      // Multiple images returned
      for (let i = 0; i < result.images.length; i++) {
        const img = result.images[i];
        const imageBuffer = Buffer.from(img.image_base64, "base64");
        const extension = img.mime_type === "image/jpeg" ? "jpg" : "png";
        attachments.push(
          new AttachmentBuilder(imageBuffer, {
            name: `generated-image-${i + 1}.${extension}`,
            description: prompt.substring(0, 100),
          })
        );
      }
    } else {
      // Fallback to legacy single image field
      const imageBuffer = Buffer.from(result.image_base64, "base64");
      attachments.push(
        new AttachmentBuilder(imageBuffer, {
          name: "generated-image.png",
          description: prompt.substring(0, 100),
        })
      );
    }

    // Build response embed for the first image
    const embed = new EmbedBuilder()
      .setTitle(persona ? `Image${imageCount > 1 ? "s" : ""} by ${persona.name}` : `Generated Image${imageCount > 1 ? "s" : ""}`)
      .setColor(0x9945ff)
      .addFields({
        name: "Prompt",
        value: prompt.length > 1000 ? prompt.substring(0, 1000) + "..." : prompt,
      })
      .setImage(`attachment://${attachments[0].name}`)
      .setFooter({
        text: persona?.appearance
          ? `Using ${persona.name}'s appearance - Gemini 3 Pro Image${imageCount > 1 ? ` (${imageCount} images)` : ""}`
          : `Generated with Gemini 3 Pro Image${imageCount > 1 ? ` (${imageCount} images)` : ""}`,
      });

    // Add aspect ratio
    embed.addFields({
      name: "Aspect Ratio",
      value: aspectRatio,
      inline: true,
    });

    // Add image count if multiple
    if (imageCount > 1) {
      embed.addFields({
        name: "Images Generated",
        value: String(imageCount),
        inline: true,
      });
    }

    // Show persona appearance if used
    if (persona?.appearance) {
      embed.spliceFields(1, 0, {
        name: "Persona Appearance",
        value: persona.appearance.length > 200
          ? persona.appearance.substring(0, 200) + "..."
          : persona.appearance,
      });
    }

    // Add model response if available (from first image)
    const textResponse = result.images?.[0]?.text_response || result.text_response;
    if (textResponse) {
      embed.addFields({
        name: "Model Response",
        value: textResponse.length > 500
          ? textResponse.substring(0, 500) + "..."
          : textResponse,
      });
    }

    await interaction.editReply({
      embeds: [embed],
      files: attachments,
    });

    logger.info(`${imageCount} image(s) generated successfully for prompt: ${prompt.substring(0, 50)}...`);
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

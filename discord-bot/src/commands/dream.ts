/**
 * Video generation command handler.
 * 
 * When used in a persona channel, the persona's appearance AND personality
 * are automatically included in the prompt for character consistency.
 * 
 * Video generation is a long-running operation (1-3 minutes).
 */

import { type ChatInputCommandInteraction, EmbedBuilder } from "discord.js";
import { agentClient } from "../services/agent-client";
import { logger } from "../utils/logger";
import type { Persona } from "../types/persona";

/**
 * Handle /dream command.
 * @param interaction - The Discord interaction
 * @param persona - The persona for this channel (required - persona channel only command)
 */
export async function handleDream(
  interaction: ChatInputCommandInteraction,
  persona: Persona
): Promise<void> {
  const prompt = interaction.options.getString("prompt", true);
  const aspectRatio = interaction.options.getString("aspect_ratio") as "16:9" | "9:16" | undefined;
  const durationSeconds = interaction.options.getInteger("duration") as 4 | 6 | 8 | undefined;
  const resolution = interaction.options.getString("resolution") as "720p" | "1080p" | undefined;
  const generateAudio = interaction.options.getBoolean("audio") ?? undefined;

  // Defer reply since video generation takes 1-3 minutes
  await interaction.deferReply();

  try {
    logger.info(`Generating video for prompt: ${prompt.substring(0, 50)}...`);
    logger.info(`Persona "${persona.name}" - including appearance and personality in prompt`);

    // Show initial progress message
    await interaction.editReply({
      embeds: [
        new EmbedBuilder()
          .setTitle(`${persona.name} is dreaming...`)
          .setDescription("Video generation typically takes 1-3 minutes. Please wait...")
          .setColor(0x9945ff)
          .addFields({
            name: "Prompt",
            value: prompt.length > 500 ? prompt.substring(0, 500) + "..." : prompt,
          })
          .setFooter({ text: "Powered by Veo 3.1" }),
      ],
    });

    // Generate video via agent service
    // The API will include persona appearance and personality in the prompt
    const result = await agentClient.generateVideo({
      prompt,
      persona_name: persona.name,
      aspect_ratio: aspectRatio,
      duration_seconds: durationSeconds,
      resolution: resolution,
      generate_audio: generateAudio,
    });

    // Build response embed with video
    const embed = new EmbedBuilder()
      .setTitle(`Dream by ${persona.name}`)
      .setColor(0x9945ff)
      .addFields({
        name: "Prompt",
        value: prompt.length > 500 ? prompt.substring(0, 500) + "..." : prompt,
      })
      .setFooter({
        text: `Generated with Veo 3.1 - ${result.duration_seconds}s @ ${result.resolution}`,
      });

    // Add video details
    embed.addFields(
      {
        name: "Duration",
        value: `${result.duration_seconds}s`,
        inline: true,
      },
      {
        name: "Resolution",
        value: result.resolution,
        inline: true,
      },
      {
        name: "Aspect Ratio",
        value: result.aspect_ratio,
        inline: true,
      }
    );

    if (result.has_audio) {
      embed.addFields({
        name: "Audio",
        value: "Included",
        inline: true,
      });
    }

    // Show persona info if appearance/personality used
    if (persona.appearance) {
      embed.addFields({
        name: "Character Appearance",
        value: persona.appearance.length > 150
          ? persona.appearance.substring(0, 150) + "..."
          : persona.appearance,
      });
    }

    // Reply with video URL - Discord will embed it automatically
    await interaction.editReply({
      content: result.video_url,
      embeds: [embed],
    });

    logger.info(`Video generated successfully: ${result.video_url}`);
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    logger.error(`Failed to generate video: ${errorMessage}`);

    // Try to interpret the error (in character)
    let friendlyError = `Failed to generate video: ${errorMessage}`;
    try {
      friendlyError = await agentClient.interpretError(
        errorMessage,
        "Failed to generate video",
        persona.name
      );
    } catch {
      // If interpretation fails, use original message
    }

    await interaction.editReply({
      embeds: [
        new EmbedBuilder()
          .setTitle("Dream Failed")
          .setDescription(friendlyError)
          .setColor(0xff0000)
          .addFields({
            name: "Prompt",
            value: prompt.length > 500 ? prompt.substring(0, 500) + "..." : prompt,
          })
          .setFooter({ text: "Video generation can fail due to content policies or service issues" }),
      ],
    });
  }
}

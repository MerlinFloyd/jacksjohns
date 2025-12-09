/**
 * Environment configuration for Discord Bot.
 */

export interface Config {
  discord: {
    token: string;
    applicationId: string;
    adminChannelName: string;  // Channel name for admin commands (create, delete, list, rename)
  };
  agentService: {
    url: string;
  };
}

function getEnvVar(name: string, defaultValue?: string): string {
  const value = process.env[name] ?? defaultValue;
  if (value === undefined) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function loadConfig(): Config {
  return {
    discord: {
      token: getEnvVar("DISCORD_BOT_TOKEN"),
      applicationId: getEnvVar("DISCORD_APPLICATION_ID", "1447797969423175742"),
      adminChannelName: getEnvVar("DISCORD_ADMIN_CHANNEL", "general"),
    },
    agentService: {
      url: getEnvVar("AGENT_SERVICE_URL", "http://localhost:8000"),
    },
  };
}

export const config = loadConfig();

/**
 * Simple logger utility.
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

const LOG_LEVEL = LogLevel.INFO;

function formatTimestamp(): string {
  return new Date().toISOString();
}

function log(level: LogLevel, levelName: string, message: string, ...args: unknown[]): void {
  if (level >= LOG_LEVEL) {
    const timestamp = formatTimestamp();
    console.log(`[${timestamp}] [${levelName}] ${message}`, ...args);
  }
}

export const logger = {
  debug(message: string, ...args: unknown[]): void {
    log(LogLevel.DEBUG, "DEBUG", message, ...args);
  },

  info(message: string, ...args: unknown[]): void {
    log(LogLevel.INFO, "INFO", message, ...args);
  },

  warn(message: string, ...args: unknown[]): void {
    log(LogLevel.WARN, "WARN", message, ...args);
  },

  error(message: string, ...args: unknown[]): void {
    log(LogLevel.ERROR, "ERROR", message, ...args);
  },
};

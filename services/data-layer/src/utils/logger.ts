/**
 * Logger Configuration
 * Winston-based logging with structured output
 */
import winston from 'winston';
import { config } from '../config/environment';

// Define log levels
const logLevels = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3,
};

// Define log colors
const logColors = {
  error: 'red',
  warn: 'yellow',
  info: 'green',
  debug: 'blue',
};

winston.addColors(logColors);

// Custom format for structured logging
const structuredFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json(),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    const logObject = {
      timestamp,
      level,
      message,
      service: 'data-layer',
      environment: config.environment,
      ...meta,
    };

    return JSON.stringify(logObject);
  })
);

// Console format for development
const consoleFormat = winston.format.combine(
  winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  winston.format.errors({ stack: true }),
  winston.format.colorize({ all: true }),
  winston.format.printf(({ timestamp, level, message, ...meta }) => {
    const metaString = Object.keys(meta).length ? `\n${JSON.stringify(meta, null, 2)}` : '';
    return `${timestamp} ${level}: ${message}${metaString}`;
  })
);

// Create transports
const transports: winston.transport[] = [];

// Console transport
if (config.isDevelopment || config.isTesting) {
  transports.push(
    new winston.transports.Console({
      format: consoleFormat,
      level: config.logLevel,
    })
  );
} else {
  // Production console with structured format
  transports.push(
    new winston.transports.Console({
      format: structuredFormat,
      level: config.logLevel,
    })
  );
}

// File transport for production
if (config.isProduction) {
  transports.push(
    new winston.transports.File({
      filename: 'logs/error.log',
      level: 'error',
      format: structuredFormat,
      maxsize: 5242880, // 5MB
      maxFiles: 5,
    }),
    new winston.transports.File({
      filename: 'logs/combined.log',
      format: structuredFormat,
      maxsize: 5242880, // 5MB
      maxFiles: 5,
    })
  );
}

// Create logger instance
export const logger = winston.createLogger({
  levels: logLevels,
  level: config.logLevel,
  format: structuredFormat,
  defaultMeta: {
    service: 'data-layer',
    environment: config.environment,
  },
  transports,
  exitOnError: false,
});

// Handle uncaught exceptions and unhandled rejections
if (config.isProduction) {
  logger.exceptions.handle(
    new winston.transports.File({
      filename: 'logs/exceptions.log',
      format: structuredFormat,
    })
  );

  logger.rejections.handle(
    new winston.transports.File({
      filename: 'logs/rejections.log',
      format: structuredFormat,
    })
  );
}

// Add custom methods
export interface Logger extends winston.Logger {
  database: (message: string, meta?: any) => void;
  cache: (message: string, meta?: any) => void;
  storage: (message: string, meta?: any) => void;
  audit: (message: string, meta?: any) => void;
  security: (message: string, meta?: any) => void;
  performance: (message: string, meta?: any) => void;
}

// Extend logger with custom methods
const extendedLogger = logger as Logger;

extendedLogger.database = (message: string, meta?: any) => {
  logger.info(message, { category: 'database', ...meta });
};

extendedLogger.cache = (message: string, meta?: any) => {
  logger.info(message, { category: 'cache', ...meta });
};

extendedLogger.storage = (message: string, meta?: any) => {
  logger.info(message, { category: 'storage', ...meta });
};

extendedLogger.audit = (message: string, meta?: any) => {
  logger.info(message, { category: 'audit', ...meta });
};

extendedLogger.security = (message: string, meta?: any) => {
  logger.warn(message, { category: 'security', ...meta });
};

extendedLogger.performance = (message: string, meta?: any) => {
  logger.info(message, { category: 'performance', ...meta });
};

// Create child loggers for different modules
export const createChildLogger = (module: string) => {
  return logger.child({ module });
};

// Log correlation ID middleware helper
export const withCorrelationId = (correlationId: string) => {
  return logger.child({ correlationId });
};

// Performance timer utility
export class PerformanceTimer {
  private startTime: number;
  private logger: winston.Logger;
  private operation: string;

  constructor(operation: string, customLogger?: winston.Logger) {
    this.operation = operation;
    this.logger = customLogger || logger;
    this.startTime = Date.now();
    this.logger.debug(`Started ${operation}`);
  }

  end(additionalMeta?: any): number {
    const duration = Date.now() - this.startTime;
    this.logger.performance(`Completed ${this.operation}`, {
      duration_ms: duration,
      operation: this.operation,
      ...additionalMeta,
    });
    return duration;
  }

  checkpoint(checkpointName: string): number {
    const duration = Date.now() - this.startTime;
    this.logger.debug(`Checkpoint ${checkpointName} for ${this.operation}`, {
      duration_ms: duration,
      checkpoint: checkpointName,
      operation: this.operation,
    });
    return duration;
  }
}

// Error logging helper
export const logError = (error: Error, context?: string, additionalMeta?: any) => {
  logger.error(`Error${context ? ` in ${context}` : ''}`, {
    error: error.message,
    stack: error.stack,
    context,
    ...additionalMeta,
  });
};

// Query logging helper
export const logQuery = (query: string, parameters?: any[], duration?: number) => {
  logger.database('Database query executed', {
    query: query.replace(/\s+/g, ' ').trim(),
    parameters,
    duration_ms: duration,
  });
};

// Cache operation logging helper
export const logCacheOperation = (
  operation: 'get' | 'set' | 'delete' | 'flush',
  key: string,
  hit?: boolean,
  ttl?: number
) => {
  logger.cache(`Cache ${operation}`, {
    operation,
    key,
    hit,
    ttl,
  });
};

// Audit logging helper
export const logAudit = (
  action: string,
  userId?: string,
  resourceType?: string,
  resourceId?: string,
  additionalMeta?: any
) => {
  logger.audit('Audit event', {
    action,
    userId,
    resourceType,
    resourceId,
    ...additionalMeta,
  });
};

// Security event logging helper
export const logSecurityEvent = (
  event: string,
  severity: 'low' | 'medium' | 'high' | 'critical',
  additionalMeta?: any
) => {
  const logMethod = severity === 'critical' || severity === 'high' ? 'error' : 'warn';
  logger[logMethod](`Security event: ${event}`, {
    category: 'security',
    severity,
    ...additionalMeta,
  });
};

export { extendedLogger as logger };
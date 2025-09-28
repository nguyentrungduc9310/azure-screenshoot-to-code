/**
 * Environment Configuration
 * Loads and validates environment variables
 */
import { config as dotenvConfig } from 'dotenv';
import { z } from 'zod';
import path from 'path';

// Load environment variables
dotenvConfig();

// Environment validation schema
const environmentSchema = z.object({
  // General
  NODE_ENV: z.enum(['development', 'testing', 'staging', 'production']).default('development'),
  LOG_LEVEL: z.enum(['error', 'warn', 'info', 'debug']).default('info'),
  
  // Database
  DB_HOST: z.string().default('localhost'),
  DB_PORT: z.coerce.number().default(5432),
  DB_NAME: z.string().default('screenshot_to_code'),
  DB_USERNAME: z.string().default('postgres'),
  DB_PASSWORD: z.string().default('password'),
  DB_SSL: z.coerce.boolean().default(false),
  DB_SSL_CA: z.string().optional(),
  DB_SSL_CERT: z.string().optional(),
  DB_SSL_KEY: z.string().optional(),
  DB_MAX_CONNECTIONS: z.coerce.number().default(20),
  DB_MIN_CONNECTIONS: z.coerce.number().default(2),
  DB_SYNCHRONIZE: z.coerce.boolean().default(false),
  DB_LOGGING: z.coerce.boolean().default(false),
  
  // Redis
  REDIS_URL: z.string().optional(),
  REDIS_HOST: z.string().default('localhost'),
  REDIS_PORT: z.coerce.number().default(6379),
  REDIS_DATABASE: z.coerce.number().default(0),
  REDIS_USERNAME: z.string().optional(),
  REDIS_PASSWORD: z.string().optional(),
  REDIS_KEY_PREFIX: z.string().default('stc'),
  REDIS_CONNECT_TIMEOUT: z.coerce.number().default(10000),
  
  // Azure Blob Storage
  AZURE_STORAGE_CONNECTION_STRING: z.string().optional(),
  AZURE_STORAGE_CONTAINER_NAME: z.string().default('screenshots'),
  AZURE_STORAGE_CDN_URL: z.string().optional(),
  
  // AWS S3 Storage
  AWS_ACCESS_KEY_ID: z.string().optional(),
  AWS_SECRET_ACCESS_KEY: z.string().optional(),
  AWS_REGION: z.string().default('us-east-1'),
  AWS_S3_BUCKET: z.string().optional(),
  AWS_S3_CDN_URL: z.string().optional(),
  
  // Storage Settings
  STORAGE_BACKEND: z.enum(['local', 'azure', 's3']).default('local'),
  LOCAL_STORAGE_PATH: z.string().default('./uploads'),
  MAX_FILE_SIZE: z.coerce.number().default(50 * 1024 * 1024), // 50MB
  ALLOWED_FILE_TYPES: z.string().default('image/png,image/jpeg,image/jpg,image/webp,image/gif'),
  
  // Security
  JWT_SECRET: z.string().default('your-super-secret-jwt-key'),
  JWT_EXPIRES_IN: z.string().default('24h'),
  BCRYPT_ROUNDS: z.coerce.number().default(12),
  
  // Session
  SESSION_SECRET: z.string().default('your-super-secret-session-key'),
  SESSION_TTL: z.coerce.number().default(3600), // 1 hour
  
  // Rate Limiting
  RATE_LIMIT_WINDOW: z.coerce.number().default(900000), // 15 minutes
  RATE_LIMIT_MAX: z.coerce.number().default(100),
  
  // Monitoring
  ENABLE_METRICS: z.coerce.boolean().default(true),
  METRICS_PORT: z.coerce.number().default(9090),
  
  // Application Insights
  APPLICATIONINSIGHTS_CONNECTION_STRING: z.string().optional(),
});

// Validate environment variables
const envValidation = environmentSchema.safeParse(process.env);

if (!envValidation.success) {
  console.error('❌ Invalid environment variables:');
  console.error(envValidation.error.format());
  process.exit(1);
}

const env = envValidation.data;

// Build Redis URL if not provided
const redisUrl = env.REDIS_URL || (() => {
  const auth = env.REDIS_PASSWORD ? `:${env.REDIS_PASSWORD}@` : '';
  const username = env.REDIS_USERNAME ? `${env.REDIS_USERNAME}:` : '';
  return `redis://${username}${auth}${env.REDIS_HOST}:${env.REDIS_PORT}/${env.REDIS_DATABASE}`;
})();

// Export configuration
export const config = {
  environment: env.NODE_ENV,
  logLevel: env.LOG_LEVEL,
  
  // Database configuration
  database: {
    host: env.DB_HOST,
    port: env.DB_PORT,
    database: env.DB_NAME,
    name: env.DB_NAME,
    username: env.DB_USERNAME,
    password: env.DB_PASSWORD,
    ssl: env.DB_SSL,
    sslCa: env.DB_SSL_CA,
    sslCert: env.DB_SSL_CERT,
    sslKey: env.DB_SSL_KEY,
    maxConnections: env.DB_MAX_CONNECTIONS,
    minConnections: env.DB_MIN_CONNECTIONS,
    synchronize: env.DB_SYNCHRONIZE,
    logging: env.DB_LOGGING,
  },
  
  // Redis configuration
  redis: {
    url: redisUrl,
    host: env.REDIS_HOST,
    port: env.REDIS_PORT,
    database: env.REDIS_DATABASE,
    username: env.REDIS_USERNAME,
    password: env.REDIS_PASSWORD,
    keyPrefix: env.REDIS_KEY_PREFIX,
    connectTimeout: env.REDIS_CONNECT_TIMEOUT,
  },
  
  // Storage configuration
  storage: {
    backend: env.STORAGE_BACKEND,
    local: {
      path: path.resolve(env.LOCAL_STORAGE_PATH),
    },
    azure: {
      connectionString: env.AZURE_STORAGE_CONNECTION_STRING,
      containerName: env.AZURE_STORAGE_CONTAINER_NAME,
      cdnUrl: env.AZURE_STORAGE_CDN_URL,
    },
    s3: {
      accessKeyId: env.AWS_ACCESS_KEY_ID,
      secretAccessKey: env.AWS_SECRET_ACCESS_KEY,
      region: env.AWS_REGION,
      bucket: env.AWS_S3_BUCKET,
      cdnUrl: env.AWS_S3_CDN_URL,
    },
    maxFileSize: env.MAX_FILE_SIZE,
    allowedFileTypes: env.ALLOWED_FILE_TYPES.split(',').map(type => type.trim()),
  },
  
  // Security configuration
  security: {
    jwtSecret: env.JWT_SECRET,
    jwtExpiresIn: env.JWT_EXPIRES_IN,
    bcryptRounds: env.BCRYPT_ROUNDS,
    sessionSecret: env.SESSION_SECRET,
    sessionTtl: env.SESSION_TTL,
  },
  
  // Rate limiting
  rateLimit: {
    windowMs: env.RATE_LIMIT_WINDOW,
    max: env.RATE_LIMIT_MAX,
  },
  
  // Monitoring
  monitoring: {
    enableMetrics: env.ENABLE_METRICS,
    metricsPort: env.METRICS_PORT,
    applicationInsights: env.APPLICATIONINSIGHTS_CONNECTION_STRING,
  },
  
  // Computed properties
  isProduction: env.NODE_ENV === 'production',
  isDevelopment: env.NODE_ENV === 'development',
  isTesting: env.NODE_ENV === 'testing',
} as const;

// Validate critical configuration
export function validateConfig(): void {
  const errors: string[] = [];
  
  // Database validation
  if (!config.database.host || !config.database.name) {
    errors.push('Database configuration is incomplete');
  }
  
  // Storage validation
  if (config.storage.backend === 'azure' && !config.storage.azure.connectionString) {
    errors.push('Azure Storage connection string is required when using Azure backend');
  }
  
  if (config.storage.backend === 's3' && (!config.storage.s3.accessKeyId || !config.storage.s3.secretAccessKey || !config.storage.s3.bucket)) {
    errors.push('AWS S3 configuration is incomplete when using S3 backend');
  }
  
  // Security validation
  if (config.isProduction) {
    if (config.security.jwtSecret === 'your-super-secret-jwt-key') {
      errors.push('JWT_SECRET must be changed in production');
    }
    
    if (config.security.sessionSecret === 'your-super-secret-session-key') {
      errors.push('SESSION_SECRET must be changed in production');
    }
  }
  
  if (errors.length > 0) {
    console.error('❌ Configuration errors:');
    errors.forEach(error => console.error(`  - ${error}`));
    process.exit(1);
  }
}

// Export types
export type Config = typeof config;
export type Environment = typeof env.NODE_ENV;
export type StorageBackend = typeof env.STORAGE_BACKEND;
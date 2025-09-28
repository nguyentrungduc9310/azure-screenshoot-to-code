/**
 * Data Layer Main Entry Point
 * Exports all database, cache, and storage functionality
 */

// Configuration
export { config, validateConfig } from './config/environment';
export { 
  initializeDatabase, 
  closeDatabase, 
  checkDatabaseHealth,
  getDatabaseStats,
  AppDataSource 
} from './config/database';
export { CacheManager, cacheManager } from './config/cache';
export { StorageManager, storageManager } from './config/storage';

// Entities
export { User, UserStatus, UserRole, AuthProvider } from './entities/User';
export { Project, ProjectStatus, ProjectType } from './entities/Project';
export { 
  GeneratedCode, 
  CodeStack, 
  GenerationProvider, 
  GenerationStatus, 
  GenerationType 
} from './entities/GeneratedCode';
export { 
  GeneratedImage, 
  ImageProvider, 
  ImageSize, 
  ImageQuality, 
  ImageStyle, 
  ImageGenerationStatus 
} from './entities/GeneratedImage';
export { Session, SessionStatus, SessionType } from './entities/Session';
export { 
  AuditLog, 
  AuditAction, 
  AuditLevel, 
  AuditCategory 
} from './entities/AuditLog';

// Utilities
export { 
  logger, 
  createChildLogger, 
  withCorrelationId,
  PerformanceTimer,
  logError,
  logQuery,
  logCacheOperation,
  logAudit,
  logSecurityEvent
} from './utils/logger';

// Scripts
export { createDatabase } from './scripts/create-database';

// Services (to be implemented)
export interface DataLayerServices {
  database: {
    initialize: () => Promise<void>;
    close: () => Promise<void>;
    checkHealth: () => Promise<boolean>;
    getStats: () => Promise<Record<string, any>>;
  };
  cache: {
    initialize: () => Promise<void>;
    close: () => Promise<void>;
    checkHealth: () => Promise<boolean>;
    set: (key: string, value: any, ttl?: number) => Promise<void>;
    get: <T>(key: string) => Promise<T | null>;
    delete: (key: string) => Promise<boolean>;
    flush: () => Promise<void>;
  };
  storage: {
    initialize: () => Promise<void>;
    upload: (buffer: Buffer, key: string, contentType?: string) => Promise<string>;
    download: (key: string) => Promise<Buffer>;
    delete: (key: string) => Promise<void>;
    exists: (key: string) => Promise<boolean>;
    getUrl: (key: string) => string;
  };
}

/**
 * Initialize all data layer services
 */
export async function initializeDataLayer(): Promise<DataLayerServices> {
  logger.info('Initializing data layer services...');

  try {
    // Validate configuration
    validateConfig();
    
    // Initialize database
    await initializeDatabase();
    logger.info('Database initialized');

    // Initialize cache
    await cacheManager.initialize();
    logger.info('Cache initialized');

    // Initialize storage
    await storageManager.initialize();
    logger.info('Storage initialized');

    const services: DataLayerServices = {
      database: {
        initialize: initializeDatabase,
        close: closeDatabase,
        checkHealth: checkDatabaseHealth,
        getStats: getDatabaseStats,
      },
      cache: {
        initialize: () => cacheManager.initialize(),
        close: () => cacheManager.close(),
        checkHealth: () => cacheManager.checkHealth(),
        set: (key: string, value: any, ttl?: number) => 
          cacheManager.set(key, value, { ttl }),
        get: <T>(key: string) => cacheManager.get<T>(key),
        delete: (key: string) => cacheManager.delete(key),
        flush: () => cacheManager.flushAll(),
      },
      storage: {
        initialize: () => storageManager.initialize(),
        upload: (buffer: Buffer, key: string, contentType?: string) =>
          storageManager.upload(buffer, key, contentType),
        download: (key: string) => storageManager.download(key),
        delete: (key: string) => storageManager.delete(key),
        exists: (key: string) => storageManager.exists(key),
        getUrl: (key: string) => storageManager.getUrl(key),
      },
    };

    logger.info('Data layer services initialized successfully');
    return services;

  } catch (error) {
    logger.error('Failed to initialize data layer services', {
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined
    });
    throw error;
  }
}

/**
 * Shutdown all data layer services
 */
export async function shutdownDataLayer(): Promise<void> {
  logger.info('Shutting down data layer services...');

  try {
    // Close database connection
    await closeDatabase();
    logger.info('Database connection closed');

    // Close cache connection
    await cacheManager.close();
    logger.info('Cache connection closed');

    logger.info('Data layer services shutdown completed');

  } catch (error) {
    logger.error('Error during data layer shutdown', {
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    throw error;
  }
}

/**
 * Health check for all data layer services
 */
export async function checkDataLayerHealth(): Promise<{
  database: boolean;
  cache: boolean;
  overall: boolean;
}> {
  try {
    const [databaseHealth, cacheHealth] = await Promise.all([
      checkDatabaseHealth(),
      cacheManager.checkHealth(),
    ]);

    const overall = databaseHealth && cacheHealth;

    logger.info('Data layer health check completed', {
      database: databaseHealth,
      cache: cacheHealth,
      overall
    });

    return {
      database: databaseHealth,
      cache: cacheHealth,
      overall
    };

  } catch (error) {
    logger.error('Data layer health check failed', {
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    
    return {
      database: false,
      cache: false,
      overall: false
    };
  }
}

/**
 * Get comprehensive statistics for all data layer services
 */
export async function getDataLayerStats(): Promise<{
  database: Record<string, any>;
  cache: Record<string, any>;
  storage: {
    backend: string;
    initialized: boolean;
  };
}> {
  try {
    const [databaseStats, cacheStats] = await Promise.all([
      getDatabaseStats().catch(() => ({})),
      cacheManager.getStats().catch(() => ({})),
    ]);

    return {
      database: databaseStats,
      cache: cacheStats,
      storage: {
        backend: config.storage.backend,
        initialized: true
      }
    };

  } catch (error) {
    logger.error('Failed to get data layer statistics', {
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    throw error;
  }
}

// Default export
export default {
  initializeDataLayer,
  shutdownDataLayer,
  checkDataLayerHealth,
  getDataLayerStats,
  config,
  logger,
  AppDataSource,
  cacheManager,
  storageManager,
};
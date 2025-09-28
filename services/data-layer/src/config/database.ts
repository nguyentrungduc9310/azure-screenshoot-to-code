/**
 * Database Configuration
 * PostgreSQL connection and TypeORM configuration
 */
import { DataSource, DataSourceOptions } from 'typeorm';
import { config } from './environment';
import { logger } from '../utils/logger';

// Import entities
import { User } from '../entities/User';
import { Project } from '../entities/Project';
import { GeneratedCode } from '../entities/GeneratedCode';
import { GeneratedImage } from '../entities/GeneratedImage';
import { Session } from '../entities/Session';
import { AuditLog } from '../entities/AuditLog';

export const databaseConfig: DataSourceOptions = {
  type: 'postgres',
  host: config.database.host,
  port: config.database.port,
  username: config.database.username,
  password: config.database.password,
  database: config.database.name,
  
  // SSL configuration
  ssl: config.database.ssl ? {
    rejectUnauthorized: false, // For Azure PostgreSQL
    ca: config.database.sslCa,
    cert: config.database.sslCert,
    key: config.database.sslKey
  } : false,
  
  // Connection pool settings
  extra: {
    max: config.database.maxConnections,
    min: config.database.minConnections,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 10000,
    acquireTimeoutMillis: 60000,
  },
  
  // Entity configuration
  entities: [
    User,
    Project,
    GeneratedCode,
    GeneratedImage,
    Session,
    AuditLog
  ],
  
  // Migration configuration
  migrations: ['src/migrations/*.ts'],
  migrationsTableName: 'migrations',
  migrationsRun: false, // Don't auto-run migrations
  
  // Development settings
  synchronize: config.environment === 'development' && config.database.synchronize,
  logging: config.database.logging,
  
  // Naming strategy
  namingStrategy: {
    tableName: (className: string, customName?: string) => {
      return customName || className.toLowerCase() + 's';
    },
    columnName: (propertyName: string, customName?: string, embeddedPrefixes: string[] = []) => {
      return customName || [...embeddedPrefixes, propertyName].join('_').toLowerCase();
    },
    relationName: (propertyName: string) => propertyName,
    joinColumnName: (relationName: string, referencedColumnName: string) => {
      return relationName + '_' + referencedColumnName;
    },
    joinTableName: (firstTableName: string, secondTableName: string) => {
      return firstTableName + '_' + secondTableName;
    },
    joinTableColumnName: (tableName: string, propertyName: string, columnName?: string) => {
      return tableName + '_' + (columnName || propertyName);
    },
    classTableInheritanceParentColumnName: (parentTableName: string, parentTableIdPropertyName: string) => {
      return parentTableName + '_' + parentTableIdPropertyName;
    },
    eagerJoinRelationAlias: (alias: string, propertyPath: string) => {
      return alias + '__' + propertyPath.replace('.', '_');
    }
  }
};

// Create DataSource instance
export const AppDataSource = new DataSource(databaseConfig);

/**
 * Initialize database connection
 */
export async function initializeDatabase(): Promise<void> {
  try {
    logger.info('Initializing database connection...', {
      host: config.database.host,
      port: config.database.port,
      database: config.database.name
    });

    await AppDataSource.initialize();
    
    logger.info('Database connection established successfully');
    
    // Log connection info
    const connection = AppDataSource.driver.master;
    logger.info('Database connection details', {
      host: connection.host,
      port: connection.port,
      database: connection.database,
      user: connection.user
    });
    
  } catch (error) {
    logger.error('Failed to initialize database connection', {
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined
    });
    throw error;
  }
}

/**
 * Close database connection
 */
export async function closeDatabase(): Promise<void> {
  try {
    if (AppDataSource.isInitialized) {
      await AppDataSource.destroy();
      logger.info('Database connection closed');
    }
  } catch (error) {
    logger.error('Error closing database connection', {
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    throw error;
  }
}

/**
 * Check database health
 */
export async function checkDatabaseHealth(): Promise<boolean> {
  try {
    if (!AppDataSource.isInitialized) {
      return false;
    }
    
    // Simple query to check connection
    await AppDataSource.query('SELECT 1');
    return true;
  } catch (error) {
    logger.error('Database health check failed', {
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    return false;
  }
}

/**
 * Get database statistics
 */
export async function getDatabaseStats(): Promise<Record<string, any>> {
  try {
    if (!AppDataSource.isInitialized) {
      throw new Error('Database not initialized');
    }
    
    const stats = await AppDataSource.query(`
      SELECT 
        schemaname,
        tablename,
        attname as column_name,
        n_distinct,
        most_common_vals,
        n_tup_ins as inserts,
        n_tup_upd as updates,
        n_tup_del as deletes,
        n_live_tup as live_tuples,
        n_dead_tup as dead_tuples
      FROM pg_stat_user_tables 
      LEFT JOIN pg_stats ON pg_stat_user_tables.relname = pg_stats.tablename
      WHERE schemaname = 'public'
      ORDER BY tablename, column_name;
    `);
    
    return { tables: stats };
  } catch (error) {
    logger.error('Failed to get database statistics', {
      error: error instanceof Error ? error.message : 'Unknown error'
    });
    throw error;
  }
}
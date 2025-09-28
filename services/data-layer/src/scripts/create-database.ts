/**
 * Database Creation Script
 * Creates the database and initial setup
 */
import { Client } from 'pg';
import { config, validateConfig } from '../config/environment';
import { logger } from '../utils/logger';

async function createDatabase(): Promise<void> {
  // Validate configuration first
  validateConfig();

  // Connect to PostgreSQL server (not specific database)
  const client = new Client({
    host: config.database.host,
    port: config.database.port,
    user: config.database.username,
    password: config.database.password,
    database: 'postgres', // Connect to default postgres database
    ssl: config.database.ssl ? {
      rejectUnauthorized: false
    } : false,
  });

  try {
    await client.connect();
    logger.info('Connected to PostgreSQL server');

    // Check if database already exists
    const existsResult = await client.query(
      'SELECT 1 FROM pg_database WHERE datname = $1',
      [config.database.name]
    );

    if (existsResult.rows.length > 0) {
      logger.info(`Database '${config.database.name}' already exists`);
      return;
    }

    // Create the database
    await client.query(`CREATE DATABASE "${config.database.name}"`);
    logger.info(`Database '${config.database.name}' created successfully`);

    // Connect to the new database to set up extensions
    await client.end();
    
    const dbClient = new Client({
      host: config.database.host,
      port: config.database.port,
      user: config.database.username,
      password: config.database.password,
      database: config.database.name,
      ssl: config.database.ssl ? {
        rejectUnauthorized: false
      } : false,
    });

    await dbClient.connect();
    logger.info(`Connected to database '${config.database.name}'`);

    // Enable required extensions
    const extensions = [
      'uuid-ossp',      // For UUID generation
      'btree_gin',      // For JSONB indexing
      'pg_trgm',        // For text search
    ];

    for (const extension of extensions) {
      try {
        await dbClient.query(`CREATE EXTENSION IF NOT EXISTS "${extension}"`);
        logger.info(`Extension '${extension}' enabled`);
      } catch (error) {
        logger.warn(`Failed to enable extension '${extension}'`, {
          error: error instanceof Error ? error.message : 'Unknown error'
        });
      }
    }

    // Create custom types and functions
    await createCustomTypes(dbClient);
    await createCustomFunctions(dbClient);

    await dbClient.end();
    logger.info('Database setup completed successfully');

  } catch (error) {
    logger.error('Failed to create database', {
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined
    });
    throw error;
  } finally {
    if (client) {
      try {
        await client.end();
      } catch {
        // Ignore connection close errors
      }
    }
  }
}

async function createCustomTypes(client: Client): Promise<void> {
  logger.info('Creating custom types...');

  const types = [
    // INET type for IP addresses (already built-in, just documenting)
    
    // Create domain types for common validations
    `CREATE DOMAIN IF NOT EXISTS email AS VARCHAR(255) 
     CHECK (VALUE ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')`,
    
    `CREATE DOMAIN IF NOT EXISTS url AS TEXT 
     CHECK (VALUE ~* '^https?://[A-Za-z0-9.-]+\\.[A-Za-z]{2,}')`,
  ];

  for (const typeSQL of types) {
    try {
      await client.query(typeSQL);
      logger.debug('Custom type created', { sql: typeSQL.substring(0, 50) + '...' });
    } catch (error) {
      logger.warn('Failed to create custom type', {
        error: error instanceof Error ? error.message : 'Unknown error',
        sql: typeSQL.substring(0, 100)
      });
    }
  }
}

async function createCustomFunctions(client: Client): Promise<void> {
  logger.info('Creating custom functions...');

  const functions = [
    // Function to update updated_at timestamp
    `CREATE OR REPLACE FUNCTION update_updated_at_column()
     RETURNS TRIGGER AS $$
     BEGIN
       NEW.updated_at = CURRENT_TIMESTAMP;
       RETURN NEW;
     END;
     $$ language 'plpgsql'`,

    // Function to generate short IDs
    `CREATE OR REPLACE FUNCTION generate_short_id(length INTEGER DEFAULT 8)
     RETURNS TEXT AS $$
     DECLARE
       chars TEXT := 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
       result TEXT := '';
       i INTEGER := 0;
     BEGIN
       FOR i IN 1..length LOOP
         result := result || substr(chars, floor(random() * length(chars) + 1)::integer, 1);
       END LOOP;
       RETURN result;
     END;
     $$ LANGUAGE plpgsql`,

    // Function to calculate password strength
    `CREATE OR REPLACE FUNCTION password_strength(password TEXT)
     RETURNS INTEGER AS $$
     DECLARE
       strength INTEGER := 0;
     BEGIN
       -- Length check
       IF length(password) >= 8 THEN strength := strength + 1; END IF;
       IF length(password) >= 12 THEN strength := strength + 1; END IF;
       
       -- Character variety checks
       IF password ~ '[a-z]' THEN strength := strength + 1; END IF;
       IF password ~ '[A-Z]' THEN strength := strength + 1; END IF;
       IF password ~ '[0-9]' THEN strength := strength + 1; END IF;
       IF password ~ '[^a-zA-Z0-9]' THEN strength := strength + 1; END IF;
       
       RETURN strength;
     END;
     $$ LANGUAGE plpgsql`,

    // Function to clean old sessions
    `CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
     RETURNS INTEGER AS $$
     DECLARE
       deleted_count INTEGER;
     BEGIN
       DELETE FROM sessions 
       WHERE status = 'expired' 
          OR (status = 'active' AND expires_at < CURRENT_TIMESTAMP - INTERVAL '7 days');
       
       GET DIAGNOSTICS deleted_count = ROW_COUNT;
       RETURN deleted_count;
     END;
     $$ LANGUAGE plpgsql`,

    // Function to generate correlation IDs
    `CREATE OR REPLACE FUNCTION generate_correlation_id()
     RETURNS TEXT AS $$
     BEGIN
       RETURN lower(
         substr(md5(random()::text), 1, 8) || '-' ||
         substr(md5(random()::text), 1, 4) || '-' ||
         substr(md5(random()::text), 1, 4) || '-' ||
         substr(md5(random()::text), 1, 12)
       );
     END;
     $$ LANGUAGE plpgsql`,
  ];

  for (const functionSQL of functions) {
    try {
      await client.query(functionSQL);
      logger.debug('Custom function created', { 
        name: functionSQL.match(/FUNCTION\s+(\w+)/)?.[1] || 'unknown'
      });
    } catch (error) {
      logger.warn('Failed to create custom function', {
        error: error instanceof Error ? error.message : 'Unknown error',
        sql: functionSQL.substring(0, 100)
      });
    }
  }
}

// Run the script if called directly
if (require.main === module) {
  createDatabase()
    .then(() => {
      logger.info('Database creation completed');
      process.exit(0);
    })
    .catch((error) => {
      logger.error('Database creation failed', { error: error.message });
      process.exit(1);
    });
}

export { createDatabase };
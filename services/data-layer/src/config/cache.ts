/**
 * Cache Configuration
 * Redis connection and caching configuration
 */
import { createClient, RedisClientType, RedisClientOptions } from 'redis';
import { config } from './environment';
import { logger } from '../utils/logger';

export interface CacheOptions {
  ttl?: number; // Time to live in seconds
  prefix?: string; // Key prefix
}

export class CacheManager {
  private client: RedisClientType;
  private isConnected: boolean = false;

  constructor() {
    const redisOptions: RedisClientOptions = {
      url: config.redis.url,
      socket: {
        host: config.redis.host,
        port: config.redis.port,
        connectTimeout: config.redis.connectTimeout,
        lazyConnect: true,
      },
      database: config.redis.database,
      username: config.redis.username,
      password: config.redis.password,
    };

    this.client = createClient(redisOptions);
    this.setupEventHandlers();
  }

  /**
   * Setup Redis event handlers
   */
  private setupEventHandlers(): void {
    this.client.on('connect', () => {
      logger.info('Redis client connecting...');
    });

    this.client.on('ready', () => {
      this.isConnected = true;
      logger.info('Redis client connected and ready');
    });

    this.client.on('error', (error) => {
      this.isConnected = false;
      logger.error('Redis client error', {
        error: error.message,
        stack: error.stack
      });
    });

    this.client.on('end', () => {
      this.isConnected = false;
      logger.info('Redis client connection ended');
    });

    this.client.on('reconnecting', () => {
      logger.info('Redis client reconnecting...');
    });
  }

  /**
   * Initialize Redis connection
   */
  async initialize(): Promise<void> {
    try {
      logger.info('Initializing Redis connection...', {
        host: config.redis.host,
        port: config.redis.port,
        database: config.redis.database
      });

      await this.client.connect();
      
      // Test connection
      await this.client.ping();
      
      logger.info('Redis connection established successfully');
    } catch (error) {
      logger.error('Failed to initialize Redis connection', {
        error: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined
      });
      throw error;
    }
  }

  /**
   * Close Redis connection
   */
  async close(): Promise<void> {
    try {
      if (this.isConnected) {
        await this.client.quit();
        logger.info('Redis connection closed');
      }
    } catch (error) {
      logger.error('Error closing Redis connection', {
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      throw error;
    }
  }

  /**
   * Check Redis health
   */
  async checkHealth(): Promise<boolean> {
    try {
      if (!this.isConnected) {
        return false;
      }
      
      const pong = await this.client.ping();
      return pong === 'PONG';
    } catch (error) {
      logger.error('Redis health check failed', {
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      return false;
    }
  }

  /**
   * Set cache value
   */
  async set(key: string, value: any, options?: CacheOptions): Promise<void> {
    try {
      const finalKey = this.buildKey(key, options?.prefix);
      const serializedValue = JSON.stringify(value);
      
      if (options?.ttl) {
        await this.client.setEx(finalKey, options.ttl, serializedValue);
      } else {
        await this.client.set(finalKey, serializedValue);
      }
      
      logger.debug('Cache set', { key: finalKey, ttl: options?.ttl });
    } catch (error) {
      logger.error('Failed to set cache value', {
        key,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      throw error;
    }
  }

  /**
   * Get cache value
   */
  async get<T = any>(key: string, options?: CacheOptions): Promise<T | null> {
    try {
      const finalKey = this.buildKey(key, options?.prefix);
      const value = await this.client.get(finalKey);
      
      if (value === null) {
        return null;
      }
      
      const parsedValue = JSON.parse(value);
      logger.debug('Cache get', { key: finalKey, found: true });
      return parsedValue;
    } catch (error) {
      logger.error('Failed to get cache value', {
        key,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      return null;
    }
  }

  /**
   * Delete cache value
   */
  async delete(key: string, options?: CacheOptions): Promise<boolean> {
    try {
      const finalKey = this.buildKey(key, options?.prefix);
      const result = await this.client.del(finalKey);
      
      logger.debug('Cache delete', { key: finalKey, deleted: result > 0 });
      return result > 0;
    } catch (error) {
      logger.error('Failed to delete cache value', {
        key,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      return false;
    }
  }

  /**
   * Check if key exists
   */
  async exists(key: string, options?: CacheOptions): Promise<boolean> {
    try {
      const finalKey = this.buildKey(key, options?.prefix);
      const result = await this.client.exists(finalKey);
      return result === 1;
    } catch (error) {
      logger.error('Failed to check key existence', {
        key,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      return false;
    }
  }

  /**
   * Set expiration for key
   */
  async expire(key: string, seconds: number, options?: CacheOptions): Promise<boolean> {
    try {
      const finalKey = this.buildKey(key, options?.prefix);
      const result = await this.client.expire(finalKey, seconds);
      return result;
    } catch (error) {
      logger.error('Failed to set key expiration', {
        key,
        seconds,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      return false;
    }
  }

  /**
   * Get keys matching pattern
   */
  async keys(pattern: string, options?: CacheOptions): Promise<string[]> {
    try {
      const finalPattern = this.buildKey(pattern, options?.prefix);
      const keys = await this.client.keys(finalPattern);
      return keys;
    } catch (error) {
      logger.error('Failed to get keys', {
        pattern,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      return [];
    }
  }

  /**
   * Flush all cache
   */
  async flushAll(): Promise<void> {
    try {
      await this.client.flushAll();
      logger.info('Cache flushed successfully');
    } catch (error) {
      logger.error('Failed to flush cache', {
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      throw error;
    }
  }

  /**
   * Get cache statistics
   */
  async getStats(): Promise<Record<string, any>> {
    try {
      const info = await this.client.info();
      const memory = await this.client.info('memory');
      const stats = await this.client.info('stats');
      
      return {
        info: this.parseRedisInfo(info),
        memory: this.parseRedisInfo(memory),
        stats: this.parseRedisInfo(stats)
      };
    } catch (error) {
      logger.error('Failed to get cache statistics', {
        error: error instanceof Error ? error.message : 'Unknown error'
      });
      throw error;
    }
  }

  /**
   * Session management methods
   */
  async setSession(sessionId: string, data: any, ttl: number = 3600): Promise<void> {
    await this.set(sessionId, data, { 
      prefix: 'session:', 
      ttl 
    });
  }

  async getSession<T = any>(sessionId: string): Promise<T | null> {
    return this.get<T>(sessionId, { prefix: 'session:' });
  }

  async deleteSession(sessionId: string): Promise<boolean> {
    return this.delete(sessionId, { prefix: 'session:' });
  }

  async extendSession(sessionId: string, ttl: number = 3600): Promise<boolean> {
    return this.expire(sessionId, ttl, { prefix: 'session:' });
  }

  /**
   * Build final cache key with optional prefix
   */
  private buildKey(key: string, prefix?: string): string {
    const basePrefix = config.redis.keyPrefix;
    const finalPrefix = prefix ? `${basePrefix}:${prefix}` : basePrefix;
    return `${finalPrefix}:${key}`;
  }

  /**
   * Parse Redis INFO command output
   */
  private parseRedisInfo(info: string): Record<string, any> {
    const result: Record<string, any> = {};
    const lines = info.split('\r\n');
    
    for (const line of lines) {
      if (line.includes(':')) {
        const [key, value] = line.split(':');
        result[key] = isNaN(Number(value)) ? value : Number(value);
      }
    }
    
    return result;
  }

  /**
   * Get Redis client for advanced operations
   */
  getClient(): RedisClientType {
    return this.client;
  }

  /**
   * Check if cache is connected
   */
  isReady(): boolean {
    return this.isConnected;
  }
}

// Create singleton instance
export const cacheManager = new CacheManager();
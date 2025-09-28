/**
 * Storage Configuration
 * Multi-backend storage support (Local, Azure Blob, AWS S3)
 */
import path from 'path';
import fs from 'fs/promises';
import { BlobServiceClient } from '@azure/storage-blob';
import { config } from './environment';
import { logger } from '../utils/logger';

export interface StorageProvider {
  upload(buffer: Buffer, key: string, contentType?: string): Promise<string>;
  download(key: string): Promise<Buffer>;
  delete(key: string): Promise<void>;
  exists(key: string): Promise<boolean>;
  getUrl(key: string): string;
  generateSignedUrl?(key: string, expiresIn?: number): Promise<string>;
}

export class LocalStorageProvider implements StorageProvider {
  private basePath: string;

  constructor(basePath: string) {
    this.basePath = path.resolve(basePath);
  }

  async initialize(): Promise<void> {
    try {
      await fs.mkdir(this.basePath, { recursive: true });
      logger.storage('Local storage initialized', { basePath: this.basePath });
    } catch (error) {
      logger.error('Failed to initialize local storage', { 
        error: error instanceof Error ? error.message : 'Unknown error',
        basePath: this.basePath 
      });
      throw error;
    }
  }

  async upload(buffer: Buffer, key: string, contentType?: string): Promise<string> {
    const filePath = path.join(this.basePath, key);
    const dir = path.dirname(filePath);

    try {
      // Ensure directory exists
      await fs.mkdir(dir, { recursive: true });
      
      // Write file
      await fs.writeFile(filePath, buffer);
      
      logger.storage('File uploaded to local storage', { 
        key, 
        size: buffer.length,
        contentType 
      });
      
      return this.getUrl(key);
    } catch (error) {
      logger.error('Failed to upload file to local storage', {
        error: error instanceof Error ? error.message : 'Unknown error',
        key
      });
      throw error;
    }
  }

  async download(key: string): Promise<Buffer> {
    const filePath = path.join(this.basePath, key);

    try {
      const buffer = await fs.readFile(filePath);
      logger.storage('File downloaded from local storage', { 
        key, 
        size: buffer.length 
      });
      return buffer;
    } catch (error) {
      logger.error('Failed to download file from local storage', {
        error: error instanceof Error ? error.message : 'Unknown error',
        key
      });
      throw error;
    }
  }

  async delete(key: string): Promise<void> {
    const filePath = path.join(this.basePath, key);

    try {
      await fs.unlink(filePath);
      logger.storage('File deleted from local storage', { key });
    } catch (error) {
      if ((error as any).code !== 'ENOENT') {
        logger.error('Failed to delete file from local storage', {
          error: error instanceof Error ? error.message : 'Unknown error',
          key
        });
        throw error;
      }
      // File doesn't exist, consider it deleted
    }
  }

  async exists(key: string): Promise<boolean> {
    const filePath = path.join(this.basePath, key);

    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  getUrl(key: string): string {
    return `file://${path.join(this.basePath, key)}`;
  }
}

export class AzureBlobStorageProvider implements StorageProvider {
  private blobServiceClient: BlobServiceClient;
  private containerName: string;
  private cdnUrl?: string;

  constructor(connectionString: string, containerName: string, cdnUrl?: string) {
    this.blobServiceClient = BlobServiceClient.fromConnectionString(connectionString);
    this.containerName = containerName;
    this.cdnUrl = cdnUrl;
  }

  async initialize(): Promise<void> {
    try {
      const containerClient = this.blobServiceClient.getContainerClient(this.containerName);
      
      // Create container if it doesn't exist
      await containerClient.createIfNotExists({
        access: 'blob' // Public read access for blobs
      });
      
      logger.storage('Azure Blob Storage initialized', { 
        containerName: this.containerName 
      });
    } catch (error) {
      logger.error('Failed to initialize Azure Blob Storage', {
        error: error instanceof Error ? error.message : 'Unknown error',
        containerName: this.containerName
      });
      throw error;
    }
  }

  async upload(buffer: Buffer, key: string, contentType = 'application/octet-stream'): Promise<string> {
    try {
      const containerClient = this.blobServiceClient.getContainerClient(this.containerName);
      const blockBlobClient = containerClient.getBlockBlobClient(key);

      await blockBlobClient.upload(buffer, buffer.length, {
        blobHTTPHeaders: {
          blobContentType: contentType,
        },
      });

      logger.storage('File uploaded to Azure Blob Storage', {
        key,
        size: buffer.length,
        contentType
      });

      return this.getUrl(key);
    } catch (error) {
      logger.error('Failed to upload file to Azure Blob Storage', {
        error: error instanceof Error ? error.message : 'Unknown error',
        key
      });
      throw error;
    }
  }

  async download(key: string): Promise<Buffer> {
    try {
      const containerClient = this.blobServiceClient.getContainerClient(this.containerName);
      const blockBlobClient = containerClient.getBlockBlobClient(key);

      const downloadResponse = await blockBlobClient.download();
      const buffer = await this.streamToBuffer(downloadResponse.readableStreamBody!);

      logger.storage('File downloaded from Azure Blob Storage', {
        key,
        size: buffer.length
      });

      return buffer;
    } catch (error) {
      logger.error('Failed to download file from Azure Blob Storage', {
        error: error instanceof Error ? error.message : 'Unknown error',
        key
      });
      throw error;
    }
  }

  async delete(key: string): Promise<void> {
    try {
      const containerClient = this.blobServiceClient.getContainerClient(this.containerName);
      const blockBlobClient = containerClient.getBlockBlobClient(key);

      await blockBlobClient.deleteIfExists();
      logger.storage('File deleted from Azure Blob Storage', { key });
    } catch (error) {
      logger.error('Failed to delete file from Azure Blob Storage', {
        error: error instanceof Error ? error.message : 'Unknown error',
        key
      });
      throw error;
    }
  }

  async exists(key: string): Promise<boolean> {
    try {
      const containerClient = this.blobServiceClient.getContainerClient(this.containerName);
      const blockBlobClient = containerClient.getBlockBlobClient(key);

      return await blockBlobClient.exists();
    } catch {
      return false;
    }
  }

  getUrl(key: string): string {
    if (this.cdnUrl) {
      return `${this.cdnUrl}/${this.containerName}/${key}`;
    }
    
    const accountName = this.blobServiceClient.accountName;
    return `https://${accountName}.blob.core.windows.net/${this.containerName}/${key}`;
  }

  async generateSignedUrl(key: string, expiresIn = 3600): Promise<string> {
    try {
      const containerClient = this.blobServiceClient.getContainerClient(this.containerName);
      const blockBlobClient = containerClient.getBlockBlobClient(key);

      const expiresOn = new Date();
      expiresOn.setSeconds(expiresOn.getSeconds() + expiresIn);

      const sasUrl = await blockBlobClient.generateSasUrl({
        permissions: 'r', // read permission
        expiresOn,
      });

      return sasUrl;
    } catch (error) {
      logger.error('Failed to generate signed URL for Azure Blob', {
        error: error instanceof Error ? error.message : 'Unknown error',
        key
      });
      throw error;
    }
  }

  private async streamToBuffer(stream: NodeJS.ReadableStream): Promise<Buffer> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = [];
      stream.on('data', (chunk) => chunks.push(chunk));
      stream.on('error', reject);
      stream.on('end', () => resolve(Buffer.concat(chunks)));
    });
  }
}

export class S3StorageProvider implements StorageProvider {
  private region: string;
  private bucket: string;
  private cdnUrl?: string;

  constructor(region: string, bucket: string, cdnUrl?: string) {
    this.region = region;
    this.bucket = bucket;
    this.cdnUrl = cdnUrl;
  }

  async initialize(): Promise<void> {
    try {
      // AWS S3 client would be initialized here
      // For now, we'll just log the initialization
      logger.storage('AWS S3 Storage initialized', {
        region: this.region,
        bucket: this.bucket
      });
    } catch (error) {
      logger.error('Failed to initialize AWS S3 Storage', {
        error: error instanceof Error ? error.message : 'Unknown error',
        bucket: this.bucket
      });
      throw error;
    }
  }

  async upload(buffer: Buffer, key: string, contentType = 'application/octet-stream'): Promise<string> {
    // AWS S3 upload implementation would go here
    throw new Error('S3 provider not fully implemented yet');
  }

  async download(key: string): Promise<Buffer> {
    // AWS S3 download implementation would go here
    throw new Error('S3 provider not fully implemented yet');
  }

  async delete(key: string): Promise<void> {
    // AWS S3 delete implementation would go here
    throw new Error('S3 provider not fully implemented yet');
  }

  async exists(key: string): Promise<boolean> {
    // AWS S3 exists check implementation would go here
    throw new Error('S3 provider not fully implemented yet');
  }

  getUrl(key: string): string {
    if (this.cdnUrl) {
      return `${this.cdnUrl}/${key}`;
    }
    return `https://${this.bucket}.s3.${this.region}.amazonaws.com/${key}`;
  }

  async generateSignedUrl(key: string, expiresIn = 3600): Promise<string> {
    // AWS S3 signed URL generation would go here
    throw new Error('S3 provider not fully implemented yet');
  }
}

// Storage manager factory
export class StorageManager {
  private provider: StorageProvider;

  constructor() {
    this.provider = this.createProvider();
  }

  private createProvider(): StorageProvider {
    switch (config.storage.backend) {
      case 'local':
        return new LocalStorageProvider(config.storage.local.path);
      
      case 'azure':
        if (!config.storage.azure.connectionString) {
          throw new Error('Azure Storage connection string is required');
        }
        return new AzureBlobStorageProvider(
          config.storage.azure.connectionString,
          config.storage.azure.containerName,
          config.storage.azure.cdnUrl
        );
      
      case 's3':
        if (!config.storage.s3.bucket) {
          throw new Error('S3 bucket name is required');
        }
        return new S3StorageProvider(
          config.storage.s3.region,
          config.storage.s3.bucket,
          config.storage.s3.cdnUrl
        );
      
      default:
        throw new Error(`Unsupported storage backend: ${config.storage.backend}`);
    }
  }

  async initialize(): Promise<void> {
    await this.provider.initialize();
  }

  async upload(buffer: Buffer, key: string, contentType?: string): Promise<string> {
    return this.provider.upload(buffer, key, contentType);
  }

  async download(key: string): Promise<Buffer> {
    return this.provider.download(key);
  }

  async delete(key: string): Promise<void> {
    return this.provider.delete(key);
  }

  async exists(key: string): Promise<boolean> {
    return this.provider.exists(key);
  }

  getUrl(key: string): string {
    return this.provider.getUrl(key);
  }

  async generateSignedUrl(key: string, expiresIn?: number): Promise<string> {
    if (this.provider.generateSignedUrl) {
      return this.provider.generateSignedUrl(key, expiresIn);
    }
    // Fallback to public URL
    return this.provider.getUrl(key);
  }

  getProvider(): StorageProvider {
    return this.provider;
  }
}

// Export singleton instance
export const storageManager = new StorageManager();
/**
 * Generated Image Entity
 * Represents generated images from text prompts
 */
import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { Project } from './Project';

export enum ImageProvider {
  DALLE3 = 'dalle3',
  FLUX_SCHNELL = 'flux_schnell'
}

export enum ImageSize {
  // DALL-E 3 sizes
  DALLE3_1024x1024 = '1024x1024',
  DALLE3_1792x1024 = '1792x1024',
  DALLE3_1024x1792 = '1024x1792',
  
  // Flux Schnell sizes
  FLUX_512x512 = '512x512',
  FLUX_768x768 = '768x768',
  FLUX_1024x1024 = '1024x1024',
  FLUX_1536x1024 = '1536x1024',
  FLUX_1024x1536 = '1024x1536'
}

export enum ImageQuality {
  STANDARD = 'standard',
  HD = 'hd'
}

export enum ImageStyle {
  VIVID = 'vivid',
  NATURAL = 'natural'
}

export enum ImageGenerationStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

@Entity('generated_images')
@Index(['projectId'])
@Index(['status'])
@Index(['provider'])
@Index(['size'])
@Index(['createdAt'])
@Index(['projectId', 'status'])
@Index(['projectId', 'createdAt'])
export class GeneratedImage {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  name?: string;

  @Column({ type: 'text' })
  prompt: string;

  @Column({ type: 'text', nullable: true })
  revisedPrompt?: string;

  @Column({ 
    type: 'enum', 
    enum: ImageProvider 
  })
  provider: ImageProvider;

  @Column({ type: 'varchar', length: 100 })
  model: string;

  @Column({ 
    type: 'enum', 
    enum: ImageGenerationStatus,
    default: ImageGenerationStatus.PENDING
  })
  status: ImageGenerationStatus;

  @Column({ 
    type: 'enum', 
    enum: ImageSize,
    default: ImageSize.DALLE3_1024x1024
  })
  size: ImageSize;

  @Column({ 
    type: 'enum', 
    enum: ImageQuality,
    nullable: true
  })
  quality?: ImageQuality;

  @Column({ 
    type: 'enum', 
    enum: ImageStyle,
    nullable: true
  })
  style?: ImageStyle;

  @Column({ type: 'int', nullable: true })
  seed?: number;

  @Column({ type: 'text', nullable: true })
  imageUrl?: string;

  @Column({ type: 'text', nullable: true })
  imageBase64?: string;

  @Column({ type: 'text', nullable: true })
  thumbnailUrl?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  storageId?: string;

  @Column({ type: 'text', nullable: true })
  storageUrl?: string;

  @Column({ type: 'varchar', length: 50, nullable: true })
  mimeType?: string;

  @Column({ type: 'int', nullable: true })
  fileSize?: number;

  @Column({ type: 'int', nullable: true })
  width?: number;

  @Column({ type: 'int', nullable: true })
  height?: number;

  @Column({ type: 'jsonb', nullable: true })
  generationParams?: Record<string, any>;

  @Column({ type: 'float', nullable: true })
  generationTimeSeconds?: number;

  @Column({ type: 'text', nullable: true })
  errorMessage?: string;

  @Column({ type: 'jsonb', nullable: true })
  errorDetails?: Record<string, any>;

  @Column({ type: 'varchar', length: 255, nullable: true })
  correlationId?: string;

  @Column({ type: 'boolean', default: false })
  isFavorite: boolean;

  @Column({ type: 'int', default: 0 })
  viewCount: number;

  @Column({ type: 'int', default: 0 })
  downloadCount: number;

  @Column({ type: 'float', nullable: true })
  rating?: number;

  @Column({ type: 'jsonb', nullable: true })
  feedback?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  imageMetadata?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;

  // Foreign Keys
  @Column({ type: 'uuid' })
  projectId: string;

  // Relationships
  @ManyToOne(() => Project, project => project.generatedImages)
  @JoinColumn({ name: 'project_id' })
  project: Project;

  // Virtual properties
  get isPending(): boolean {
    return this.status === ImageGenerationStatus.PENDING;
  }

  get isProcessing(): boolean {
    return this.status === ImageGenerationStatus.PROCESSING;
  }

  get isCompleted(): boolean {
    return this.status === ImageGenerationStatus.COMPLETED;
  }

  get isFailed(): boolean {
    return this.status === ImageGenerationStatus.FAILED;
  }

  get isCancelled(): boolean {
    return this.status === ImageGenerationStatus.CANCELLED;
  }

  get hasImage(): boolean {
    return !!(this.imageUrl || this.imageBase64 || this.storageUrl);
  }

  get hasError(): boolean {
    return !!this.errorMessage;
  }

  get aspectRatio(): number | null {
    if (this.width && this.height) {
      return this.width / this.height;
    }
    return null;
  }

  get isSquare(): boolean {
    return this.aspectRatio === 1;
  }

  get isLandscape(): boolean {
    const ratio = this.aspectRatio;
    return ratio !== null && ratio > 1;
  }

  get isPortrait(): boolean {
    const ratio = this.aspectRatio;
    return ratio !== null && ratio < 1;
  }

  // Methods
  updateView(): void {
    this.viewCount += 1;
  }

  updateDownload(): void {
    this.downloadCount += 1;
  }

  setRating(rating: number): void {
    if (rating >= 1 && rating <= 5) {
      this.rating = rating;
    }
  }

  addFeedback(feedback: Record<string, any>): void {
    if (!this.feedback) {
      this.feedback = {};
    }
    this.feedback = { ...this.feedback, ...feedback };
  }

  setImageMetadata(metadata: Record<string, any>): void {
    this.imageMetadata = metadata;
  }

  getImageMetadata(key: string, defaultValue?: any): any {
    return this.imageMetadata?.[key] ?? defaultValue;
  }

  setMetadata(key: string, value: any): void {
    if (!this.metadata) {
      this.metadata = {};
    }
    this.metadata[key] = value;
  }

  getMetadata(key: string, defaultValue?: any): any {
    return this.metadata?.[key] ?? defaultValue;
  }

  // Status management
  markAsProcessing(): void {
    this.status = ImageGenerationStatus.PROCESSING;
  }

  markAsCompleted(): void {
    this.status = ImageGenerationStatus.COMPLETED;
  }

  markAsFailed(errorMessage: string, errorDetails?: Record<string, any>): void {
    this.status = ImageGenerationStatus.FAILED;
    this.errorMessage = errorMessage;
    this.errorDetails = errorDetails;
  }

  markAsCancelled(): void {
    this.status = ImageGenerationStatus.CANCELLED;
  }

  toggleFavorite(): void {
    this.isFavorite = !this.isFavorite;
  }

  // Generation performance
  setGenerationTime(startTime: Date, endTime: Date = new Date()): void {
    this.generationTimeSeconds = (endTime.getTime() - startTime.getTime()) / 1000;
  }

  // Image dimensions
  setDimensions(width: number, height: number): void {
    this.width = width;
    this.height = height;
  }

  // Storage management
  setStorageInfo(storageId: string, storageUrl: string): void {
    this.storageId = storageId;
    this.storageUrl = storageUrl;
  }

  // File info
  setFileInfo(mimeType: string, fileSize: number): void {
    this.mimeType = mimeType;
    this.fileSize = fileSize;
  }

  getFileSizeFormatted(): string {
    if (!this.fileSize) return 'Unknown';
    
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = this.fileSize;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  }

  // Serialization
  toJSON(): Partial<GeneratedImage> {
    return {
      ...this,
      project: undefined, // Exclude project relationship by default
      imageBase64: undefined, // Exclude base64 data for performance
    };
  }

  toSummaryJSON(): Partial<GeneratedImage> {
    return {
      id: this.id,
      name: this.name,
      provider: this.provider,
      model: this.model,
      status: this.status,
      size: this.size,
      quality: this.quality,
      style: this.style,
      isFavorite: this.isFavorite,
      rating: this.rating,
      viewCount: this.viewCount,
      width: this.width,
      height: this.height,
      fileSize: this.fileSize,
      generationTimeSeconds: this.generationTimeSeconds,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
    };
  }

  toPublicJSON(): Partial<GeneratedImage> {
    return {
      id: this.id,
      name: this.name,
      provider: this.provider,
      size: this.size,
      imageUrl: this.imageUrl,
      thumbnailUrl: this.thumbnailUrl,
      width: this.width,
      height: this.height,
      viewCount: this.viewCount,
      rating: this.rating,
      createdAt: this.createdAt,
    };
  }
}
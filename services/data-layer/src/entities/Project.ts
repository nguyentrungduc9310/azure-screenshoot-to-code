/**
 * Project Entity
 * Represents user projects containing screenshots and generated code
 */
import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
  Index,
} from 'typeorm';
import { User } from './User';
import { GeneratedCode } from './GeneratedCode';
import { GeneratedImage } from './GeneratedImage';

export enum ProjectStatus {
  DRAFT = 'draft',
  ACTIVE = 'active',
  COMPLETED = 'completed',
  ARCHIVED = 'archived',
  DELETED = 'deleted'
}

export enum ProjectType {
  WEBSITE = 'website',
  MOBILE_APP = 'mobile_app',
  COMPONENT = 'component',
  PROTOTYPE = 'prototype'
}

@Entity('projects')
@Index(['userId'])
@Index(['status'])
@Index(['type'])
@Index(['createdAt'])
@Index(['updatedAt'])
@Index(['userId', 'status'])
export class Project {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255 })
  name: string;

  @Column({ type: 'text', nullable: true })
  description?: string;

  @Column({ 
    type: 'enum', 
    enum: ProjectStatus, 
    default: ProjectStatus.DRAFT 
  })
  status: ProjectStatus;

  @Column({ 
    type: 'enum', 
    enum: ProjectType, 
    default: ProjectType.WEBSITE 
  })
  type: ProjectType;

  @Column({ type: 'text', nullable: true })
  originalImage?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  originalImageFilename?: string;

  @Column({ type: 'int', nullable: true })
  originalImageSize?: number;

  @Column({ type: 'varchar', length: 50, nullable: true })
  originalImageMimeType?: string;

  @Column({ type: 'text', nullable: true })
  thumbnailImage?: string;

  @Column({ type: 'jsonb', nullable: true })
  imageMetadata?: Record<string, any>;

  @Column({ type: 'text', nullable: true })
  instructions?: string;

  @Column({ type: 'jsonb', nullable: true })
  settings?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  tags?: string[];

  @Column({ type: 'boolean', default: false })
  isPublic: boolean;

  @Column({ type: 'boolean', default: false })
  isFavorite: boolean;

  @Column({ type: 'int', default: 0 })
  viewCount: number;

  @Column({ type: 'int', default: 0 })
  generationCount: number;

  @Column({ type: 'timestamp', nullable: true })
  lastGeneratedAt?: Date;

  @Column({ type: 'timestamp', nullable: true })
  lastViewedAt?: Date;

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;

  // Foreign Keys
  @Column({ type: 'uuid' })
  userId: string;

  // Relationships
  @ManyToOne(() => User, user => user.projects)
  @JoinColumn({ name: 'user_id' })
  user: User;

  @OneToMany(() => GeneratedCode, generatedCode => generatedCode.project)
  generatedCodes: GeneratedCode[];

  @OneToMany(() => GeneratedImage, generatedImage => generatedImage.project)
  generatedImages: GeneratedImage[];

  // Virtual properties
  get isActive(): boolean {
    return this.status === ProjectStatus.ACTIVE;
  }

  get isDraft(): boolean {
    return this.status === ProjectStatus.DRAFT;
  }

  get isCompleted(): boolean {
    return this.status === ProjectStatus.COMPLETED;
  }

  get isArchived(): boolean {
    return this.status === ProjectStatus.ARCHIVED;
  }

  get isDeleted(): boolean {
    return this.status === ProjectStatus.DELETED;
  }

  get hasOriginalImage(): boolean {
    return !!this.originalImage;
  }

  get hasThumbnail(): boolean {
    return !!this.thumbnailImage;
  }

  // Methods
  updateView(): void {
    this.viewCount += 1;
    this.lastViewedAt = new Date();
  }

  updateGeneration(): void {
    this.generationCount += 1;
    this.lastGeneratedAt = new Date();
  }

  addTag(tag: string): void {
    if (!this.tags) {
      this.tags = [];
    }
    if (!this.tags.includes(tag)) {
      this.tags.push(tag);
    }
  }

  removeTag(tag: string): void {
    if (this.tags) {
      this.tags = this.tags.filter(t => t !== tag);
    }
  }

  hasTag(tag: string): boolean {
    return this.tags?.includes(tag) ?? false;
  }

  setSetting(key: string, value: any): void {
    if (!this.settings) {
      this.settings = {};
    }
    this.settings[key] = value;
  }

  getSetting(key: string, defaultValue?: any): any {
    return this.settings?.[key] ?? defaultValue;
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
  markAsActive(): void {
    this.status = ProjectStatus.ACTIVE;
  }

  markAsCompleted(): void {
    this.status = ProjectStatus.COMPLETED;
  }

  markAsArchived(): void {
    this.status = ProjectStatus.ARCHIVED;
  }

  markAsDeleted(): void {
    this.status = ProjectStatus.DELETED;
  }

  toggleFavorite(): void {
    this.isFavorite = !this.isFavorite;
  }

  togglePublic(): void {
    this.isPublic = !this.isPublic;
  }

  // Serialization
  toJSON(): Partial<Project> {
    return {
      ...this,
      user: undefined, // Exclude user relationship by default
    };
  }

  toPublicJSON(): Partial<Project> {
    return {
      id: this.id,
      name: this.name,
      description: this.description,
      type: this.type,
      thumbnailImage: this.thumbnailImage,
      tags: this.tags,
      viewCount: this.viewCount,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
    };
  }
}
/**
 * Generated Code Entity
 * Represents generated code from screenshots
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

export enum CodeStack {
  HTML_TAILWIND = 'html_tailwind',
  HTML_CSS = 'html_css',
  REACT_TAILWIND = 'react_tailwind',
  VUE_TAILWIND = 'vue_tailwind',
  BOOTSTRAP = 'bootstrap',
  IONIC_TAILWIND = 'ionic_tailwind',
  SVG = 'svg'
}

export enum GenerationProvider {
  OPENAI = 'openai',
  AZURE_OPENAI = 'azure_openai',
  CLAUDE = 'claude',
  GEMINI = 'gemini'
}

export enum GenerationStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export enum GenerationType {
  CREATE = 'create',
  UPDATE = 'update',
  REFINE = 'refine'
}

@Entity('generated_codes')
@Index(['projectId'])
@Index(['status'])
@Index(['provider'])
@Index(['codeStack'])
@Index(['generationType'])
@Index(['createdAt'])
@Index(['projectId', 'status'])
@Index(['projectId', 'createdAt'])
export class GeneratedCode {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  name?: string;

  @Column({ type: 'text' })
  code: string;

  @Column({ 
    type: 'enum', 
    enum: CodeStack,
    default: CodeStack.HTML_TAILWIND
  })
  codeStack: CodeStack;

  @Column({ 
    type: 'enum', 
    enum: GenerationProvider 
  })
  provider: GenerationProvider;

  @Column({ type: 'varchar', length: 100 })
  model: string;

  @Column({ 
    type: 'enum', 
    enum: GenerationStatus,
    default: GenerationStatus.PENDING
  })
  status: GenerationStatus;

  @Column({ 
    type: 'enum', 
    enum: GenerationType,
    default: GenerationType.CREATE
  })
  generationType: GenerationType;

  @Column({ type: 'text', nullable: true })
  originalPrompt?: string;

  @Column({ type: 'text', nullable: true })
  revisedPrompt?: string;

  @Column({ type: 'text', nullable: true })
  additionalInstructions?: string;

  @Column({ type: 'text', nullable: true })
  inputImageUrl?: string;

  @Column({ type: 'text', nullable: true })
  resultImageUrl?: string;

  @Column({ type: 'jsonb', nullable: true })
  generationParams?: Record<string, any>;

  @Column({ type: 'float', nullable: true })
  temperature?: number;

  @Column({ type: 'int', nullable: true })
  maxTokens?: number;

  @Column({ type: 'int', nullable: true })
  promptTokens?: number;

  @Column({ type: 'int', nullable: true })
  completionTokens?: number;

  @Column({ type: 'int', nullable: true })
  totalTokens?: number;

  @Column({ type: 'float', nullable: true })
  generationTimeSeconds?: number;

  @Column({ type: 'text', nullable: true })
  errorMessage?: string;

  @Column({ type: 'jsonb', nullable: true })
  errorDetails?: Record<string, any>;

  @Column({ type: 'varchar', length: 255, nullable: true })
  correlationId?: string;

  @Column({ type: 'int', default: 0 })
  version: number;

  @Column({ type: 'uuid', nullable: true })
  parentId?: string;

  @Column({ type: 'boolean', default: false })
  isFavorite: boolean;

  @Column({ type: 'int', default: 0 })
  viewCount: number;

  @Column({ type: 'int', default: 0 })
  copyCount: number;

  @Column({ type: 'int', default: 0 })
  downloadCount: number;

  @Column({ type: 'float', nullable: true })
  rating?: number;

  @Column({ type: 'jsonb', nullable: true })
  feedback?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  metrics?: Record<string, any>;

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
  @ManyToOne(() => Project, project => project.generatedCodes)
  @JoinColumn({ name: 'project_id' })
  project: Project;

  // Virtual properties
  get isPending(): boolean {
    return this.status === GenerationStatus.PENDING;
  }

  get isProcessing(): boolean {
    return this.status === GenerationStatus.PROCESSING;
  }

  get isCompleted(): boolean {
    return this.status === GenerationStatus.COMPLETED;
  }

  get isFailed(): boolean {
    return this.status === GenerationStatus.FAILED;
  }

  get isCancelled(): boolean {
    return this.status === GenerationStatus.CANCELLED;
  }

  get isCreate(): boolean {
    return this.generationType === GenerationType.CREATE;
  }

  get isUpdate(): boolean {
    return this.generationType === GenerationType.UPDATE;
  }

  get isRefine(): boolean {
    return this.generationType === GenerationType.REFINE;
  }

  get codeSize(): number {
    return this.code?.length || 0;
  }

  get hasError(): boolean {
    return !!this.errorMessage;
  }

  // Methods
  updateView(): void {
    this.viewCount += 1;
  }

  updateCopy(): void {
    this.copyCount += 1;
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

  setMetric(key: string, value: any): void {
    if (!this.metrics) {
      this.metrics = {};
    }
    this.metrics[key] = value;
  }

  getMetric(key: string, defaultValue?: any): any {
    return this.metrics?.[key] ?? defaultValue;
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
    this.status = GenerationStatus.PROCESSING;
  }

  markAsCompleted(): void {
    this.status = GenerationStatus.COMPLETED;
  }

  markAsFailed(errorMessage: string, errorDetails?: Record<string, any>): void {
    this.status = GenerationStatus.FAILED;
    this.errorMessage = errorMessage;
    this.errorDetails = errorDetails;
  }

  markAsCancelled(): void {
    this.status = GenerationStatus.CANCELLED;
  }

  toggleFavorite(): void {
    this.isFavorite = !this.isFavorite;
  }

  // Token usage
  setTokenUsage(promptTokens: number, completionTokens: number): void {
    this.promptTokens = promptTokens;
    this.completionTokens = completionTokens;
    this.totalTokens = promptTokens + completionTokens;
  }

  // Generation performance
  setGenerationTime(startTime: Date, endTime: Date = new Date()): void {
    this.generationTimeSeconds = (endTime.getTime() - startTime.getTime()) / 1000;
  }

  // Code analysis
  getCodeLines(): number {
    return this.code?.split('\n').length || 0;
  }

  getCodeWords(): number {
    return this.code?.split(/\s+/).length || 0;
  }

  // Serialization
  toJSON(): Partial<GeneratedCode> {
    return {
      ...this,
      project: undefined, // Exclude project relationship by default
    };
  }

  toSummaryJSON(): Partial<GeneratedCode> {
    return {
      id: this.id,
      name: this.name,
      codeStack: this.codeStack,
      provider: this.provider,
      model: this.model,
      status: this.status,
      generationType: this.generationType,
      version: this.version,
      isFavorite: this.isFavorite,
      rating: this.rating,
      viewCount: this.viewCount,
      codeSize: this.codeSize,
      generationTimeSeconds: this.generationTimeSeconds,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
    };
  }
}
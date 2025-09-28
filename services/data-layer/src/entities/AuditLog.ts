/**
 * Audit Log Entity
 * Represents system audit logs for security and compliance
 */
import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { User } from './User';

export enum AuditAction {
  // User actions
  USER_LOGIN = 'user_login',
  USER_LOGOUT = 'user_logout',
  USER_REGISTER = 'user_register',
  USER_UPDATE_PROFILE = 'user_update_profile',
  USER_CHANGE_PASSWORD = 'user_change_password',
  USER_DELETE_ACCOUNT = 'user_delete_account',
  USER_VERIFY_EMAIL = 'user_verify_email',
  USER_RESET_PASSWORD = 'user_reset_password',

  // Project actions
  PROJECT_CREATE = 'project_create',
  PROJECT_UPDATE = 'project_update',
  PROJECT_DELETE = 'project_delete',
  PROJECT_ARCHIVE = 'project_archive',
  PROJECT_RESTORE = 'project_restore',
  PROJECT_SHARE = 'project_share',
  PROJECT_CLONE = 'project_clone',

  // Code generation actions
  CODE_GENERATE = 'code_generate',
  CODE_UPDATE = 'code_update',
  CODE_DELETE = 'code_delete',
  CODE_COPY = 'code_copy',
  CODE_DOWNLOAD = 'code_download',
  CODE_RATE = 'code_rate',

  // Image generation actions
  IMAGE_GENERATE = 'image_generate',
  IMAGE_DELETE = 'image_delete',
  IMAGE_DOWNLOAD = 'image_download',
  IMAGE_RATE = 'image_rate',

  // Session actions
  SESSION_CREATE = 'session_create',
  SESSION_EXTEND = 'session_extend',
  SESSION_REVOKE = 'session_revoke',
  SESSION_EXPIRE = 'session_expire',

  // Security actions
  SECURITY_LOGIN_FAILED = 'security_login_failed',
  SECURITY_ACCOUNT_LOCKED = 'security_account_locked',
  SECURITY_ACCOUNT_UNLOCKED = 'security_account_unlocked',
  SECURITY_SUSPICIOUS_ACTIVITY = 'security_suspicious_activity',
  SECURITY_DATA_EXPORT = 'security_data_export',
  SECURITY_PRIVACY_SETTINGS = 'security_privacy_settings',

  // Admin actions
  ADMIN_USER_CREATE = 'admin_user_create',
  ADMIN_USER_UPDATE = 'admin_user_update',
  ADMIN_USER_DELETE = 'admin_user_delete',
  ADMIN_USER_SUSPEND = 'admin_user_suspend',
  ADMIN_USER_UNSUSPEND = 'admin_user_unsuspend',
  ADMIN_SYSTEM_CONFIG = 'admin_system_config',
  ADMIN_DATA_EXPORT = 'admin_data_export',
  ADMIN_BULK_ACTION = 'admin_bulk_action',

  // System actions
  SYSTEM_STARTUP = 'system_startup',
  SYSTEM_SHUTDOWN = 'system_shutdown',
  SYSTEM_ERROR = 'system_error',
  SYSTEM_MAINTENANCE = 'system_maintenance',
  SYSTEM_BACKUP = 'system_backup',
  SYSTEM_RESTORE = 'system_restore',
}

export enum AuditLevel {
  INFO = 'info',
  WARNING = 'warning',
  ERROR = 'error',
  CRITICAL = 'critical'
}

export enum AuditCategory {
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  DATA_ACCESS = 'data_access',
  DATA_MODIFICATION = 'data_modification',
  SECURITY = 'security',
  ADMINISTRATION = 'administration',
  SYSTEM = 'system',
  COMPLIANCE = 'compliance'
}

@Entity('audit_logs')
@Index(['userId'])
@Index(['action'])
@Index(['level'])
@Index(['category'])
@Index(['createdAt'])
@Index(['resourceType'])
@Index(['resourceId'])
@Index(['userId', 'action'])
@Index(['action', 'createdAt'])
@Index(['level', 'createdAt'])
export class AuditLog {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ 
    type: 'enum', 
    enum: AuditAction 
  })
  action: AuditAction;

  @Column({ 
    type: 'enum', 
    enum: AuditLevel,
    default: AuditLevel.INFO
  })
  level: AuditLevel;

  @Column({ 
    type: 'enum', 
    enum: AuditCategory 
  })
  category: AuditCategory;

  @Column({ type: 'varchar', length: 255 })
  description: string;

  @Column({ type: 'text', nullable: true })
  details?: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  resourceType?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  resourceId?: string;

  @Column({ type: 'jsonb', nullable: true })
  oldValues?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  newValues?: Record<string, any>;

  @Column({ type: 'inet', nullable: true })
  ipAddress?: string;

  @Column({ type: 'text', nullable: true })
  userAgent?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  sessionId?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  correlationId?: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  source?: string;

  @Column({ type: 'jsonb', nullable: true })
  context?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @Column({ type: 'boolean', default: false })
  isSuccess: boolean;

  @Column({ type: 'text', nullable: true })
  errorMessage?: string;

  @Column({ type: 'int', nullable: true })
  duration?: number;

  @CreateDateColumn()
  createdAt: Date;

  // Foreign Keys
  @Column({ type: 'uuid', nullable: true })
  userId?: string;

  // Relationships
  @ManyToOne(() => User, user => user.auditLogs, { nullable: true })
  @JoinColumn({ name: 'user_id' })
  user?: User;

  // Virtual properties
  get isInfo(): boolean {
    return this.level === AuditLevel.INFO;
  }

  get isWarning(): boolean {
    return this.level === AuditLevel.WARNING;
  }

  get isError(): boolean {
    return this.level === AuditLevel.ERROR;
  }

  get isCritical(): boolean {
    return this.level === AuditLevel.CRITICAL;
  }

  get isAuthenticationAction(): boolean {
    return this.category === AuditCategory.AUTHENTICATION;
  }

  get isSecurityAction(): boolean {
    return this.category === AuditCategory.SECURITY;
  }

  get isAdminAction(): boolean {
    return this.category === AuditCategory.ADMINISTRATION;
  }

  get isSystemAction(): boolean {
    return this.category === AuditCategory.SYSTEM;
  }

  get hasError(): boolean {
    return !!this.errorMessage;
  }

  get durationMs(): number | null {
    return this.duration;
  }

  get durationSeconds(): number | null {
    return this.duration ? this.duration / 1000 : null;
  }

  // Methods
  setContext(context: Record<string, any>): void {
    this.context = context;
  }

  addContext(key: string, value: any): void {
    if (!this.context) {
      this.context = {};
    }
    this.context[key] = value;
  }

  getContext(key: string, defaultValue?: any): any {
    return this.context?.[key] ?? defaultValue;
  }

  setMetadata(metadata: Record<string, any>): void {
    this.metadata = metadata;
  }

  addMetadata(key: string, value: any): void {
    if (!this.metadata) {
      this.metadata = {};
    }
    this.metadata[key] = value;
  }

  getMetadata(key: string, defaultValue?: any): any {
    return this.metadata?.[key] ?? defaultValue;
  }

  setOldValues(values: Record<string, any>): void {
    this.oldValues = values;
  }

  setNewValues(values: Record<string, any>): void {
    this.newValues = values;
  }

  setResourceInfo(type: string, id: string): void {
    this.resourceType = type;
    this.resourceId = id;
  }

  setError(errorMessage: string): void {
    this.isSuccess = false;
    this.errorMessage = errorMessage;
    this.level = AuditLevel.ERROR;
  }

  setSuccess(): void {
    this.isSuccess = true;
    this.errorMessage = null;
  }

  setDuration(startTime: Date, endTime: Date = new Date()): void {
    this.duration = endTime.getTime() - startTime.getTime();
  }

  // Static factory methods
  static createUserAction(
    action: AuditAction,
    userId: string,
    description: string,
    options?: Partial<AuditLog>
  ): Partial<AuditLog> {
    return {
      action,
      userId,
      description,
      category: AuditCategory.AUTHENTICATION,
      level: AuditLevel.INFO,
      isSuccess: true,
      ...options,
    };
  }

  static createSecurityEvent(
    action: AuditAction,
    description: string,
    level: AuditLevel = AuditLevel.WARNING,
    options?: Partial<AuditLog>
  ): Partial<AuditLog> {
    return {
      action,
      description,
      category: AuditCategory.SECURITY,
      level,
      isSuccess: level !== AuditLevel.ERROR && level !== AuditLevel.CRITICAL,
      ...options,
    };
  }

  static createDataAction(
    action: AuditAction,
    userId: string,
    resourceType: string,
    resourceId: string,
    description: string,
    options?: Partial<AuditLog>
  ): Partial<AuditLog> {
    return {
      action,
      userId,
      resourceType,
      resourceId,
      description,
      category: AuditCategory.DATA_MODIFICATION,
      level: AuditLevel.INFO,
      isSuccess: true,
      ...options,
    };
  }

  static createSystemEvent(
    action: AuditAction,
    description: string,
    level: AuditLevel = AuditLevel.INFO,
    options?: Partial<AuditLog>
  ): Partial<AuditLog> {
    return {
      action,
      description,
      category: AuditCategory.SYSTEM,
      level,
      isSuccess: level !== AuditLevel.ERROR && level !== AuditLevel.CRITICAL,
      ...options,
    };
  }

  static createAdminAction(
    action: AuditAction,
    adminUserId: string,
    targetResourceType: string,
    targetResourceId: string,
    description: string,
    options?: Partial<AuditLog>
  ): Partial<AuditLog> {
    return {
      action,
      userId: adminUserId,
      resourceType: targetResourceType,
      resourceId: targetResourceId,
      description,
      category: AuditCategory.ADMINISTRATION,
      level: AuditLevel.INFO,
      isSuccess: true,
      ...options,
    };
  }

  // Serialization
  toJSON(): Partial<AuditLog> {
    return {
      ...this,
      user: undefined, // Exclude user relationship by default
    };
  }

  toSecureJSON(): Partial<AuditLog> {
    return {
      id: this.id,
      action: this.action,
      level: this.level,
      category: this.category,
      description: this.description,
      resourceType: this.resourceType,
      resourceId: this.resourceId,
      isSuccess: this.isSuccess,
      duration: this.duration,
      createdAt: this.createdAt,
    };
  }

  toComplianceJSON(): Partial<AuditLog> {
    return {
      id: this.id,
      action: this.action,
      level: this.level,
      category: this.category,
      description: this.description,
      details: this.details,
      resourceType: this.resourceType,
      resourceId: this.resourceId,
      userId: this.userId,
      ipAddress: this.ipAddress,
      sessionId: this.sessionId,
      correlationId: this.correlationId,
      isSuccess: this.isSuccess,
      errorMessage: this.errorMessage,
      createdAt: this.createdAt,
    };
  }
}
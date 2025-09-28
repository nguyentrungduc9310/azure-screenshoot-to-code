/**
 * User Entity
 * Represents users in the system
 */
import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
  Index,
} from 'typeorm';
import { Project } from './Project';
import { Session } from './Session';
import { AuditLog } from './AuditLog';

export enum UserStatus {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  SUSPENDED = 'suspended',
  PENDING = 'pending'
}

export enum UserRole {
  USER = 'user',
  ADMIN = 'admin',
  MODERATOR = 'moderator'
}

export enum AuthProvider {
  LOCAL = 'local',
  AZURE_AD = 'azure_ad',
  GOOGLE = 'google',
  GITHUB = 'github'
}

@Entity('users')
@Index(['email'], { unique: true })
@Index(['azureId'], { unique: true, where: 'azure_id IS NOT NULL' })
@Index(['status'])
@Index(['role'])
@Index(['lastLoginAt'])
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255, unique: true })
  email: string;

  @Column({ type: 'varchar', length: 100 })
  firstName: string;

  @Column({ type: 'varchar', length: 100 })
  lastName: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  displayName?: string;

  @Column({ type: 'text', nullable: true })
  avatar?: string;

  @Column({ type: 'varchar', length: 255, nullable: true, select: false })
  passwordHash?: string;

  @Column({ 
    type: 'enum', 
    enum: UserStatus, 
    default: UserStatus.ACTIVE 
  })
  status: UserStatus;

  @Column({ 
    type: 'enum', 
    enum: UserRole, 
    default: UserRole.USER 
  })
  role: UserRole;

  @Column({ 
    type: 'enum', 
    enum: AuthProvider, 
    default: AuthProvider.LOCAL 
  })
  authProvider: AuthProvider;

  @Column({ type: 'varchar', length: 255, nullable: true })
  azureId?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  googleId?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  githubId?: string;

  @Column({ type: 'boolean', default: false })
  emailVerified: boolean;

  @Column({ type: 'timestamp', nullable: true })
  emailVerifiedAt?: Date;

  @Column({ type: 'timestamp', nullable: true })
  lastLoginAt?: Date;

  @Column({ type: 'inet', nullable: true })
  lastLoginIp?: string;

  @Column({ type: 'text', nullable: true })
  lastLoginUserAgent?: string;

  @Column({ type: 'int', default: 0 })
  loginCount: number;

  @Column({ type: 'timestamp', nullable: true })
  passwordChangedAt?: Date;

  @Column({ type: 'varchar', length: 255, nullable: true })
  resetPasswordToken?: string;

  @Column({ type: 'timestamp', nullable: true })
  resetPasswordExpiresAt?: Date;

  @Column({ type: 'varchar', length: 255, nullable: true })
  emailVerificationToken?: string;

  @Column({ type: 'timestamp', nullable: true })
  emailVerificationExpiresAt?: Date;

  @Column({ type: 'jsonb', nullable: true })
  preferences?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;

  // Relationships
  @OneToMany(() => Project, project => project.user)
  projects: Project[];

  @OneToMany(() => Session, session => session.user)
  sessions: Session[];

  @OneToMany(() => AuditLog, auditLog => auditLog.user)
  auditLogs: AuditLog[];

  // Virtual properties
  get fullName(): string {
    return `${this.firstName} ${this.lastName}`.trim();
  }

  get isActive(): boolean {
    return this.status === UserStatus.ACTIVE;
  }

  get isAdmin(): boolean {
    return this.role === UserRole.ADMIN;
  }

  get isModerator(): boolean {
    return this.role === UserRole.MODERATOR || this.role === UserRole.ADMIN;
  }

  // Methods
  updateLastLogin(ip?: string, userAgent?: string): void {
    this.lastLoginAt = new Date();
    this.lastLoginIp = ip || null;
    this.lastLoginUserAgent = userAgent || null;
    this.loginCount += 1;
  }

  setPreference(key: string, value: any): void {
    if (!this.preferences) {
      this.preferences = {};
    }
    this.preferences[key] = value;
  }

  getPreference(key: string, defaultValue?: any): any {
    return this.preferences?.[key] ?? defaultValue;
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

  // Serialization
  toJSON(): Partial<User> {
    const { passwordHash, resetPasswordToken, emailVerificationToken, ...user } = this;
    return user;
  }
}
/**
 * Session Entity
 * Represents user sessions for authentication and tracking
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
import { User } from './User';

export enum SessionStatus {
  ACTIVE = 'active',
  EXPIRED = 'expired',
  REVOKED = 'revoked',
  INVALID = 'invalid'
}

export enum SessionType {
  WEB = 'web',
  API = 'api',
  MOBILE = 'mobile',
  DESKTOP = 'desktop'
}

@Entity('sessions')
@Index(['sessionId'], { unique: true })
@Index(['userId'])
@Index(['status'])
@Index(['type'])
@Index(['expiresAt'])
@Index(['lastActiveAt'])
@Index(['userId', 'status'])
@Index(['userId', 'type'])
export class Session {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255, unique: true })
  sessionId: string;

  @Column({ 
    type: 'enum', 
    enum: SessionStatus,
    default: SessionStatus.ACTIVE
  })
  status: SessionStatus;

  @Column({ 
    type: 'enum', 
    enum: SessionType,
    default: SessionType.WEB
  })
  type: SessionType;

  @Column({ type: 'timestamp' })
  expiresAt: Date;

  @Column({ type: 'timestamp', default: () => 'CURRENT_TIMESTAMP' })
  lastActiveAt: Date;

  @Column({ type: 'inet', nullable: true })
  ipAddress?: string;

  @Column({ type: 'text', nullable: true })
  userAgent?: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  deviceId?: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  deviceType?: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  browser?: string;

  @Column({ type: 'varchar', length: 50, nullable: true })
  browserVersion?: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  operatingSystem?: string;

  @Column({ type: 'varchar', length: 50, nullable: true })
  osVersion?: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  country?: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  city?: string;

  @Column({ type: 'varchar', length: 20, nullable: true })
  timezone?: string;

  @Column({ type: 'jsonb', nullable: true })
  sessionData?: Record<string, any>;

  @Column({ type: 'jsonb', nullable: true })
  metadata?: Record<string, any>;

  @Column({ type: 'int', default: 0 })
  requestCount: number;

  @Column({ type: 'timestamp', nullable: true })
  revokedAt?: Date;

  @Column({ type: 'varchar', length: 255, nullable: true })
  revokedReason?: string;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;

  // Foreign Keys
  @Column({ type: 'uuid' })
  userId: string;

  // Relationships
  @ManyToOne(() => User, user => user.sessions)
  @JoinColumn({ name: 'user_id' })
  user: User;

  // Virtual properties
  get isActive(): boolean {
    return this.status === SessionStatus.ACTIVE && this.expiresAt > new Date();
  }

  get isExpired(): boolean {
    return this.status === SessionStatus.EXPIRED || this.expiresAt <= new Date();
  }

  get isRevoked(): boolean {
    return this.status === SessionStatus.REVOKED;
  }

  get isValid(): boolean {
    return this.isActive && !this.isExpired && !this.isRevoked;
  }

  get remainingTime(): number {
    if (this.isExpired) return 0;
    return Math.max(0, this.expiresAt.getTime() - Date.now());
  }

  get remainingTimeHours(): number {
    return Math.floor(this.remainingTime / (1000 * 60 * 60));
  }

  get remainingTimeMinutes(): number {
    return Math.floor((this.remainingTime % (1000 * 60 * 60)) / (1000 * 60));
  }

  get isWebSession(): boolean {
    return this.type === SessionType.WEB;
  }

  get isApiSession(): boolean {
    return this.type === SessionType.API;
  }

  get isMobileSession(): boolean {
    return this.type === SessionType.MOBILE;
  }

  get duration(): number {
    return this.lastActiveAt.getTime() - this.createdAt.getTime();
  }

  get durationHours(): number {
    return Math.floor(this.duration / (1000 * 60 * 60));
  }

  // Methods
  updateActivity(): void {
    this.lastActiveAt = new Date();
    this.requestCount += 1;
  }

  extendExpiration(additionalMinutes: number = 60): void {
    const newExpiration = new Date(this.expiresAt.getTime() + (additionalMinutes * 60 * 1000));
    this.expiresAt = newExpiration;
  }

  setSessionData(key: string, value: any): void {
    if (!this.sessionData) {
      this.sessionData = {};
    }
    this.sessionData[key] = value;
  }

  getSessionData(key: string, defaultValue?: any): any {
    return this.sessionData?.[key] ?? defaultValue;
  }

  removeSessionData(key: string): void {
    if (this.sessionData && key in this.sessionData) {
      delete this.sessionData[key];
    }
  }

  clearSessionData(): void {
    this.sessionData = {};
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
  markAsExpired(): void {
    this.status = SessionStatus.EXPIRED;
  }

  revoke(reason?: string): void {
    this.status = SessionStatus.REVOKED;
    this.revokedAt = new Date();
    this.revokedReason = reason;
  }

  markAsInvalid(): void {
    this.status = SessionStatus.INVALID;
  }

  reactivate(newExpirationMinutes: number = 60): void {
    if (this.status !== SessionStatus.REVOKED) {
      this.status = SessionStatus.ACTIVE;
      this.expiresAt = new Date(Date.now() + (newExpirationMinutes * 60 * 1000));
      this.updateActivity();
    }
  }

  // Device information
  setDeviceInfo(deviceId?: string, deviceType?: string): void {
    this.deviceId = deviceId;
    this.deviceType = deviceType;
  }

  setBrowserInfo(browser?: string, browserVersion?: string): void {
    this.browser = browser;
    this.browserVersion = browserVersion;
  }

  setOperatingSystemInfo(os?: string, osVersion?: string): void {
    this.operatingSystem = os;
    this.osVersion = osVersion;
  }

  setLocationInfo(country?: string, city?: string, timezone?: string): void {
    this.country = country;
    this.city = city;
    this.timezone = timezone;
  }

  // Security checks
  validateIpAddress(currentIp: string): boolean {
    // Allow IP changes for now, but log them
    return true;
  }

  validateUserAgent(currentUserAgent: string): boolean {
    // Allow user agent changes for now, but log them
    return true;
  }

  // Serialization
  toJSON(): Partial<Session> {
    return {
      ...this,
      user: undefined, // Exclude user relationship by default
      sessionData: undefined, // Exclude sensitive session data
    };
  }

  toSecureJSON(): Partial<Session> {
    return {
      id: this.id,
      sessionId: this.sessionId,
      status: this.status,
      type: this.type,
      expiresAt: this.expiresAt,
      lastActiveAt: this.lastActiveAt,
      deviceType: this.deviceType,
      browser: this.browser,
      operatingSystem: this.operatingSystem,
      country: this.country,
      city: this.city,
      requestCount: this.requestCount,
      createdAt: this.createdAt,
      remainingTimeHours: this.remainingTimeHours,
      durationHours: this.durationHours,
    };
  }

  toAdminJSON(): Partial<Session> {
    return {
      ...this,
      user: undefined, // Exclude user relationship
    };
  }
}
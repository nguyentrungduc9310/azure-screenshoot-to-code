# Data Layer Service

A comprehensive data layer for the Screenshot to Code application, providing database, caching, and storage services.

## Features

- **PostgreSQL Database**: Full ORM with TypeORM, migrations, and connection pooling
- **Redis Caching**: Session management and data caching with clustering support
- **Multi-Storage Backend**: Local filesystem, Azure Blob Storage, and AWS S3
- **Comprehensive Logging**: Structured logging with Winston and correlation tracking
- **Type Safety**: Full TypeScript support with strict typing
- **Health Monitoring**: Built-in health checks and performance metrics

## Architecture

### Database (PostgreSQL)
- **ORM**: TypeORM with decorators and migrations
- **Entities**: User, Project, GeneratedCode, GeneratedImage, Session, AuditLog
- **Features**: Connection pooling, SSL support, query logging
- **Extensions**: UUID generation, JSONB indexing, full-text search

### Cache (Redis)
- **Session Management**: User sessions with automatic expiration
- **Data Caching**: Configurable TTL and key prefixing
- **Clustering**: Support for Redis clusters and sentinel
- **Features**: Health monitoring, statistics, cleanup utilities

### Storage
- **Local Storage**: Filesystem with directory organization
- **Azure Blob Storage**: Container-based storage with CDN support
- **AWS S3**: Bucket storage with CloudFront integration
- **Features**: Signed URLs, metadata storage, automatic cleanup

## Quick Start

### Installation

```bash
cd services/data-layer
npm install
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Database Setup

```bash
# Create database
npm run db:create

# Run migrations
npm run db:migrate

# Seed initial data
npm run db:seed
```

### Development

```bash
# Start in development mode
npm run dev

# Build for production
npm run build

# Start production
npm start
```

## Configuration

### Required Environment Variables

**Database (PostgreSQL)**:
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=screenshot_to_code
DB_USERNAME=postgres
DB_PASSWORD=password
```

**Cache (Redis)**:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Optional Configuration

**Security**:
```bash
JWT_SECRET=your-jwt-secret
SESSION_SECRET=your-session-secret
BCRYPT_ROUNDS=12
```

**Storage**:
```bash
STORAGE_BACKEND=local  # local, azure, s3
LOCAL_STORAGE_PATH=./uploads
```

**Azure Blob Storage**:
```bash
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_STORAGE_CONTAINER_NAME=screenshots
```

**AWS S3**:
```bash
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your-bucket
```

## Usage

### Basic Usage

```typescript
import { 
  initializeDataLayer, 
  shutdownDataLayer,
  AppDataSource,
  cacheManager,
  storageManager 
} from '@screenshot-to-code/data-layer';

// Initialize all services
const services = await initializeDataLayer();

// Use database
const userRepository = AppDataSource.getRepository(User);
const user = await userRepository.findOne({ where: { email: 'user@example.com' } });

// Use cache
await services.cache.set('user:123', { name: 'John' }, 3600);
const userData = await services.cache.get('user:123');

// Use storage
const imageBuffer = Buffer.from('...');
const url = await services.storage.upload(imageBuffer, 'images/photo.jpg', 'image/jpeg');

// Cleanup
await shutdownDataLayer();
```

### Entity Usage

```typescript
import { User, Project, GeneratedCode } from '@screenshot-to-code/data-layer';

// Create user
const user = new User();
user.email = 'user@example.com';
user.firstName = 'John';
user.lastName = 'Doe';
await AppDataSource.getRepository(User).save(user);

// Create project
const project = new Project();
project.name = 'My Website';
project.description = 'A beautiful website';
project.userId = user.id;
await AppDataSource.getRepository(Project).save(project);

// Generate code
const code = new GeneratedCode();
code.code = '<html>...</html>';
code.codeStack = CodeStack.HTML_TAILWIND;
code.provider = GenerationProvider.OPENAI;
code.projectId = project.id;
await AppDataSource.getRepository(GeneratedCode).save(code);
```

### Session Management

```typescript
import { cacheManager } from '@screenshot-to-code/data-layer';

// Create session
const sessionData = {
  userId: 'user-123',
  role: 'user',
  permissions: ['read', 'write']
};
await cacheManager.setSession('session-456', sessionData, 3600);

// Get session
const session = await cacheManager.getSession('session-456');

// Extend session
await cacheManager.extendSession('session-456', 7200);

// Delete session
await cacheManager.deleteSession('session-456');
```

### Audit Logging

```typescript
import { AuditLog, AuditAction, AuditLevel } from '@screenshot-to-code/data-layer';

// Create audit log
const auditLog = AuditLog.createUserAction(
  AuditAction.USER_LOGIN,
  'user-123',
  'User logged in successfully',
  {
    ipAddress: '192.168.1.1',
    userAgent: 'Mozilla/5.0...',
    correlationId: 'abc-123'
  }
);

await AppDataSource.getRepository(AuditLog).save(auditLog);
```

## Database Schema

### Users Table
- **id**: UUID primary key
- **email**: Unique email address
- **firstName/lastName**: User names
- **passwordHash**: Encrypted password
- **status**: active, inactive, suspended, pending
- **role**: user, admin, moderator
- **authProvider**: local, azure_ad, google, github
- **preferences**: JSONB user preferences
- **audit fields**: created_at, updated_at, last_login_at

### Projects Table
- **id**: UUID primary key
- **name**: Project name
- **description**: Project description
- **status**: draft, active, completed, archived, deleted
- **type**: website, mobile_app, component, prototype
- **originalImage**: Base64 or URL of screenshot
- **settings**: JSONB project settings
- **userId**: Foreign key to users

### Generated Code Table
- **id**: UUID primary key
- **code**: Generated HTML/React/Vue code
- **codeStack**: html_tailwind, react_tailwind, etc.
- **provider**: openai, claude, gemini
- **status**: pending, processing, completed, failed
- **generationType**: create, update, refine
- **projectId**: Foreign key to projects
- **metrics**: Token usage, generation time

### Generated Images Table
- **id**: UUID primary key
- **prompt**: Text prompt for image generation
- **provider**: dalle3, flux_schnell
- **imageUrl**: URL to generated image
- **size**: Image dimensions
- **projectId**: Foreign key to projects

### Sessions Table
- **id**: UUID primary key
- **sessionId**: Unique session identifier
- **status**: active, expired, revoked
- **expiresAt**: Session expiration time
- **userId**: Foreign key to users
- **ipAddress**: Client IP address
- **userAgent**: Client user agent

### Audit Logs Table
- **id**: UUID primary key
- **action**: Enumerated action type
- **level**: info, warning, error, critical
- **category**: authentication, security, data_access
- **description**: Human-readable description
- **userId**: Foreign key to users
- **context**: JSONB additional context

## Scripts

### Database Management

```bash
# Create database and extensions
npm run db:create

# Run migrations
npm run db:migrate

# Seed initial data
npm run db:seed

# Reset database (DROP and recreate)
npm run db:reset
```

### Cache Management

```bash
# Flush all cache
npm run cache:flush
```

### Storage Management

```bash
# Initialize storage backend
npm run storage:init
```

## Health Checks

The data layer provides comprehensive health monitoring:

```typescript
import { checkDataLayerHealth, getDataLayerStats } from '@screenshot-to-code/data-layer';

// Health check
const health = await checkDataLayerHealth();
console.log({
  database: health.database,  // true/false
  cache: health.cache,       // true/false
  overall: health.overall    // true/false
});

// Detailed statistics
const stats = await getDataLayerStats();
console.log({
  database: stats.database,  // Connection info, query stats
  cache: stats.cache,       // Memory usage, hit rates
  storage: stats.storage    // Backend info, usage
});
```

## Performance

### Database
- **Connection Pooling**: Configurable min/max connections
- **Query Optimization**: Indexes on frequently queried fields
- **JSONB Indexing**: GIN indexes for JSONB columns
- **Prepared Statements**: Automatic query preparation

### Cache
- **Redis Clustering**: Support for Redis clusters
- **Key Expiration**: Automatic cleanup of expired keys
- **Memory Optimization**: Compression for large values
- **Pipeline Support**: Batch operations for better performance

### Storage
- **CDN Integration**: Azure CDN and CloudFront support
- **Signed URLs**: Temporary access URLs for security
- **Compression**: Automatic compression for supported formats
- **Metadata Storage**: Rich metadata for uploaded files

## Security

### Database Security
- **SSL/TLS**: Encrypted connections
- **Connection Limits**: Protection against connection exhaustion
- **SQL Injection**: Parameterized queries with TypeORM
- **Audit Logging**: Comprehensive activity tracking

### Cache Security
- **Authentication**: Redis AUTH support
- **Encryption**: TLS encryption for Redis connections
- **Key Isolation**: Prefixed keys to prevent conflicts
- **Session Security**: Secure session token generation

### Storage Security
- **Signed URLs**: Time-limited access URLs
- **Access Control**: IAM-based access control
- **Encryption**: Server-side encryption for cloud storage
- **File Validation**: Type and size validation

## Monitoring

### Logging
- **Structured Logging**: JSON-formatted logs with Winston
- **Log Levels**: Debug, info, warn, error with filtering
- **Correlation IDs**: Request tracking across services
- **Performance Metrics**: Query times, cache hit rates

### Metrics
- **Database Metrics**: Connection pool, query performance
- **Cache Metrics**: Hit/miss rates, memory usage
- **Storage Metrics**: Upload/download counts, errors
- **Custom Metrics**: Application-specific measurements

## Development

### Project Structure

```
src/
├── config/          # Configuration files
│   ├── database.ts  # Database configuration
│   ├── cache.ts     # Redis configuration
│   ├── storage.ts   # Storage configuration
│   └── environment.ts # Environment variables
├── entities/        # TypeORM entities
│   ├── User.ts
│   ├── Project.ts
│   ├── GeneratedCode.ts
│   ├── GeneratedImage.ts
│   ├── Session.ts
│   └── AuditLog.ts
├── repositories/    # Custom repositories
├── services/        # Business logic services
├── utils/          # Utility functions
│   └── logger.ts   # Logging configuration
├── scripts/        # Database scripts
│   ├── create-database.ts
│   ├── migrate-database.ts
│   └── seed-database.ts
└── index.ts        # Main entry point
```

### Testing

```bash
# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Run tests in watch mode
npm run test:watch
```

### Code Quality

```bash
# Lint code
npm run lint

# Fix linting issues
npm run lint:fix

# Type checking
npm run typecheck
```

## Deployment

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY dist/ ./dist/
CMD ["node", "dist/index.js"]
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: data-layer
spec:
  replicas: 3
  selector:
    matchLabels:
      app: data-layer
  template:
    metadata:
      labels:
        app: data-layer
    spec:
      containers:
      - name: data-layer
        image: data-layer:latest
        env:
        - name: DB_HOST
          value: "postgres-service"
        - name: REDIS_HOST
          value: "redis-service"
```

## Troubleshooting

### Common Issues

**Database Connection Issues**:
```bash
# Check database connectivity
npm run db:create
```

**Redis Connection Issues**:
```bash
# Test Redis connection
redis-cli ping
```

**Storage Issues**:
```bash
# Test storage initialization
npm run storage:init
```

### Debugging

Enable debug logging:
```bash
LOG_LEVEL=debug npm run dev
```

Monitor health:
```bash
curl http://localhost:3000/health
```

## License

MIT License - see LICENSE file for details.
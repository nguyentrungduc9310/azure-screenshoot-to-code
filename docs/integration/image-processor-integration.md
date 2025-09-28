# Image Processor Integration Guide

This guide provides comprehensive integration examples and best practices for using the Image Processor API in different environments and programming languages.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication Setup](#authentication-setup)
3. [Integration Examples](#integration-examples)
4. [Best Practices](#best-practices)
5. [Error Handling](#error-handling)
6. [Performance Optimization](#performance-optimization)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Service Health Check

Before integrating, verify the service is running:

```bash
curl -X GET http://localhost:8001/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "image-processor",
  "version": "1.0"
}
```

### 2. Get Provider Information

Understand supported providers and their requirements:

```bash
curl -X GET http://localhost:8001/api/v1/providers \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Basic Image Processing

Process your first image:

```bash
curl -X POST http://localhost:8001/api/v1/process \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    "provider": "claude"
  }'
```

---

## Authentication Setup

### Azure AD Authentication

The Image Processor API uses Azure AD for authentication. Here's how to obtain and use tokens:

#### JavaScript/Node.js with MSAL

```javascript
import { PublicClientApplication } from '@azure/msal-browser';

const msalConfig = {
  auth: {
    clientId: 'your-client-id',
    authority: 'https://login.microsoftonline.com/your-tenant-id',
    redirectUri: window.location.origin,
  },
};

const msalInstance = new PublicClientApplication(msalConfig);

async function getAccessToken() {
  const loginRequest = {
    scopes: ['api://your-api-scope/.default'],
  };

  try {
    const response = await msalInstance.acquireTokenSilent(loginRequest);
    return response.accessToken;
  } catch (error) {
    // Fall back to interactive login
    const response = await msalInstance.acquireTokenPopup(loginRequest);
    return response.accessToken;
  }
}
```

#### Python with MSAL

```python
from msal import ConfidentialClientApplication

# Server-to-server authentication
app = ConfidentialClientApplication(
    client_id="your-client-id",
    client_credential="your-client-secret",
    authority="https://login.microsoftonline.com/your-tenant-id"
)

def get_access_token():
    result = app.acquire_token_for_client(scopes=["api://your-api-scope/.default"])
    
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Authentication failed: {result.get('error_description')}")
```

---

## Integration Examples

### JavaScript/TypeScript SDK

Create a comprehensive TypeScript SDK:

```typescript
// imageProcessor.ts
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

export interface ProcessImageOptions {
  format?: 'JPEG' | 'PNG' | 'WEBP';
  quality?: number;
  max_dimension?: number;
  preserve_transparency?: boolean;
  background_color?: string;
}

export interface ThumbnailOptions {
  maintain_aspect_ratio?: boolean;
  quality?: number;
  background_color?: string;
}

export interface ProcessImageResult {
  success: boolean;
  processed_image: string;
  original_format: string;
  processed_format: string;
  original_size: number;
  processed_size: number;
  dimensions: [number, number];
  processing_time_ms: number;
  compression_ratio: number;
  correlation_id: string;
  metadata: Record<string, any>;
}

export interface ValidationResult {
  valid: boolean;
  provider: string;
  error_message?: string;
  file_size: number;
  file_size_mb: number;
  dimensions: {
    width: number;
    height: number;
    aspect_ratio: number;
  };
  format: string;
  correlation_id: string;
}

export class ImageProcessor {
  private client: AxiosInstance;
  private tokenProvider: () => Promise<string>;

  constructor(baseURL: string, tokenProvider: () => Promise<string>) {
    this.tokenProvider = tokenProvider;
    this.client = axios.create({
      baseURL,
      timeout: 30000, // 30 second timeout
    });

    // Add request interceptor for authentication
    this.client.interceptors.request.use(async (config) => {
      const token = await this.tokenProvider();
      config.headers.Authorization = `Bearer ${token}`;
      return config;
    });

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('Image Processor API Error:', {
          status: error.response?.status,
          data: error.response?.data,
          correlationId: error.response?.data?.correlation_id,
        });
        throw error;
      }
    );
  }

  async processImage(
    imageDataUrl: string,
    provider: 'claude' | 'openai' | 'gemini',
    options?: ProcessImageOptions
  ): Promise<ProcessImageResult> {
    const response = await this.client.post('/api/v1/process', {
      image: imageDataUrl,
      provider,
      options,
    });

    return response.data;
  }

  async validateImage(
    imageDataUrl: string,
    provider: 'claude' | 'openai' | 'gemini'
  ): Promise<ValidationResult> {
    const response = await this.client.post('/api/v1/validate', {
      image: imageDataUrl,
      provider,
    });

    return response.data;
  }

  async analyzeImage(imageDataUrl: string): Promise<any> {
    const response = await this.client.post('/api/v1/analyze', {
      image: imageDataUrl,
    });

    return response.data;
  }

  async createThumbnail(
    imageDataUrl: string,
    width: number,
    height: number,
    options?: ThumbnailOptions
  ): Promise<any> {
    const response = await this.client.post('/api/v1/thumbnail', {
      image: imageDataUrl,
      width,
      height,
      options,
    });

    return response.data;
  }

  async getProviders(): Promise<any> {
    const response = await this.client.get('/api/v1/providers');
    return response.data;
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await axios.get(`${this.client.defaults.baseURL}/health`);
      return response.data.status === 'healthy';
    } catch {
      return false;
    }
  }
}

// Usage example
const imageProcessor = new ImageProcessor(
  'http://localhost:8001',
  () => getAccessToken() // Your token provider function
);

// Process image for Claude
const result = await imageProcessor.processImage(
  'data:image/png;base64,iVBORw0KGgo...',
  'claude',
  { format: 'JPEG', quality: 90 }
);

console.log(`Processed image: ${result.compression_ratio * 100}% size reduction`);
```

### React Integration

```typescript
// useImageProcessor.ts
import { useState, useCallback } from 'react';
import { ImageProcessor, ProcessImageResult } from './imageProcessor';

interface UseImageProcessorResult {
  processImage: (file: File, provider: string) => Promise<ProcessImageResult>;
  isProcessing: boolean;
  error: string | null;
  result: ProcessImageResult | null;
}

export function useImageProcessor(imageProcessor: ImageProcessor): UseImageProcessorResult {
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessImageResult | null>(null);

  const processImage = useCallback(async (file: File, provider: string) => {
    setIsProcessing(true);
    setError(null);
    setResult(null);

    try {
      // Convert file to data URL
      const dataUrl = await fileToDataUrl(file);
      
      // Validate first
      const validation = await imageProcessor.validateImage(dataUrl, provider);
      if (!validation.valid) {
        throw new Error(validation.error_message || 'Image validation failed');
      }

      // Process image
      const result = await imageProcessor.processImage(dataUrl, provider);
      setResult(result);
      return result;
    } catch (err) {
      const errorMessage = err.response?.data?.message || err.message || 'Processing failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, [imageProcessor]);

  return { processImage, isProcessing, error, result };
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// Component usage
function ImageUploadComponent() {
  const imageProcessor = new ImageProcessor(API_BASE_URL, getAccessToken);
  const { processImage, isProcessing, error, result } = useImageProcessor(imageProcessor);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      await processImage(file, 'claude');
    } catch (error) {
      console.error('Processing failed:', error);
    }
  };

  return (
    <div>
      <input type="file" accept="image/*" onChange={handleFileUpload} />
      {isProcessing && <p>Processing image...</p>}
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {result && (
        <div>
          <p>Compression: {(result.compression_ratio * 100).toFixed(1)}%</p>
          <p>Processing time: {result.processing_time_ms}ms</p>
          <img src={result.processed_image} alt="Processed" />
        </div>
      )}
    </div>
  );
}
```

### Python SDK

```python
# image_processor.py
import requests
import base64
import asyncio
import aiohttp
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum

class Provider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"

@dataclass
class ProcessingOptions:
    format: Optional[str] = None
    quality: Optional[int] = None
    max_dimension: Optional[int] = None
    preserve_transparency: Optional[bool] = None
    background_color: Optional[str] = None

@dataclass
class ProcessImageResult:
    success: bool
    processed_image: str
    original_format: str
    processed_format: str
    original_size: int
    processed_size: int
    dimensions: tuple
    processing_time_ms: float
    compression_ratio: float
    correlation_id: str
    metadata: Dict[str, Any]

class ImageProcessorError(Exception):
    def __init__(self, message: str, correlation_id: str = None, details: Dict = None):
        self.message = message
        self.correlation_id = correlation_id
        self.details = details or {}
        super().__init__(message)

class ImageProcessor:
    def __init__(self, base_url: str, token_provider: callable):
        self.base_url = base_url.rstrip('/')
        self.token_provider = token_provider
        self.session = requests.Session()
        self.session.timeout = 30

    def _get_headers(self) -> Dict[str, str]:
        token = self.token_provider()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            raise ImageProcessorError(f"Invalid JSON response: {response.text}")

        if not response.ok:
            raise ImageProcessorError(
                data.get('message', f'HTTP {response.status_code}'),
                data.get('correlation_id'),
                data.get('details', {})
            )

        return data

    def process_image(
        self,
        image_data_url: str,
        provider: Union[Provider, str],
        options: Optional[ProcessingOptions] = None
    ) -> ProcessImageResult:
        """Process an image for the specified provider."""
        
        provider_str = provider.value if isinstance(provider, Provider) else provider
        
        payload = {
            "image": image_data_url,
            "provider": provider_str
        }
        
        if options:
            payload["options"] = {
                k: v for k, v in {
                    "format": options.format,
                    "quality": options.quality,
                    "max_dimension": options.max_dimension,
                    "preserve_transparency": options.preserve_transparency,
                    "background_color": options.background_color
                }.items() if v is not None
            }

        response = self.session.post(
            f"{self.base_url}/api/v1/process",
            json=payload,
            headers=self._get_headers()
        )

        data = self._handle_response(response)
        
        return ProcessImageResult(
            success=data['success'],
            processed_image=data['processed_image'],
            original_format=data['original_format'],
            processed_format=data['processed_format'],
            original_size=data['original_size'],
            processed_size=data['processed_size'],
            dimensions=tuple(data['dimensions']),
            processing_time_ms=data['processing_time_ms'],
            compression_ratio=data['compression_ratio'],
            correlation_id=data['correlation_id'],
            metadata=data['metadata']
        )

    def validate_image(self, image_data_url: str, provider: Union[Provider, str]) -> Dict[str, Any]:
        """Validate an image against provider requirements."""
        
        provider_str = provider.value if isinstance(provider, Provider) else provider
        
        payload = {
            "image": image_data_url,
            "provider": provider_str
        }

        response = self.session.post(
            f"{self.base_url}/api/v1/validate",
            json=payload,
            headers=self._get_headers()
        )

        return self._handle_response(response)

    def analyze_image(self, image_data_url: str) -> Dict[str, Any]:
        """Analyze image content and characteristics."""
        
        payload = {"image": image_data_url}

        response = self.session.post(
            f"{self.base_url}/api/v1/analyze",
            json=payload,
            headers=self._get_headers()
        )

        return self._handle_response(response)

    def create_thumbnail(
        self,
        image_data_url: str,
        width: int,
        height: int,
        maintain_aspect_ratio: bool = True,
        quality: int = 80
    ) -> Dict[str, Any]:
        """Create a thumbnail of the specified dimensions."""
        
        payload = {
            "image": image_data_url,
            "width": width,
            "height": height,
            "options": {
                "maintain_aspect_ratio": maintain_aspect_ratio,
                "quality": quality
            }
        }

        response = self.session.post(
            f"{self.base_url}/api/v1/thumbnail",
            json=payload,
            headers=self._get_headers()
        )

        return self._handle_response(response)

    def get_providers(self) -> Dict[str, Any]:
        """Get supported providers and their requirements."""
        
        response = self.session.get(
            f"{self.base_url}/api/v1/providers",
            headers=self._get_headers()
        )

        return self._handle_response(response)

    def health_check(self) -> bool:
        """Check if the service is healthy."""
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            data = response.json()
            return data.get('status') == 'healthy'
        except:
            return False

    @staticmethod
    def file_to_data_url(file_path: str) -> str:
        """Convert a file to a data URL."""
        
        import mimetypes
        
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith('image/'):
            raise ValueError(f"Unsupported file type: {mime_type}")

        with open(file_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime_type};base64,{encoded}"

# Usage example
def get_token():
    # Your token acquisition logic
    return "your-access-token"

processor = ImageProcessor("http://localhost:8001", get_token)

# Process an image file
image_data_url = ImageProcessor.file_to_data_url("path/to/image.png")

try:
    result = processor.process_image(
        image_data_url,
        Provider.CLAUDE,
        ProcessingOptions(format="JPEG", quality=90)
    )
    
    print(f"Processing successful!")
    print(f"Compression ratio: {result.compression_ratio:.2%}")
    print(f"Processing time: {result.processing_time_ms}ms")
    print(f"Size reduction: {result.original_size - result.processed_size} bytes")
    
except ImageProcessorError as e:
    print(f"Processing failed: {e.message}")
    print(f"Correlation ID: {e.correlation_id}")
    print(f"Details: {e.details}")
```

### Async Python SDK

```python
# async_image_processor.py
import asyncio
import aiohttp
from typing import Optional, Dict, Any, Union

class AsyncImageProcessor:
    def __init__(self, base_url: str, token_provider: callable):
        self.base_url = base_url.rstrip('/')
        self.token_provider = token_provider

    async def _get_headers(self) -> Dict[str, str]:
        if asyncio.iscoroutinefunction(self.token_provider):
            token = await self.token_provider()
        else:
            token = self.token_provider()
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        headers = await self._get_headers()
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=headers,
                **kwargs
            ) as response:
                data = await response.json()
                
                if not response.ok:
                    raise ImageProcessorError(
                        data.get('message', f'HTTP {response.status}'),
                        data.get('correlation_id'),
                        data.get('details', {})
                    )
                
                return data

    async def process_image(
        self,
        image_data_url: str,
        provider: Union[Provider, str],
        options: Optional[ProcessingOptions] = None
    ) -> ProcessImageResult:
        """Async process an image for the specified provider."""
        
        provider_str = provider.value if isinstance(provider, Provider) else provider
        
        payload = {
            "image": image_data_url,
            "provider": provider_str
        }
        
        if options:
            payload["options"] = {
                k: v for k, v in {
                    "format": options.format,
                    "quality": options.quality,
                    "max_dimension": options.max_dimension,
                    "preserve_transparency": options.preserve_transparency,
                    "background_color": options.background_color
                }.items() if v is not None
            }

        data = await self._make_request("POST", "/api/v1/process", json=payload)
        
        return ProcessImageResult(
            success=data['success'],
            processed_image=data['processed_image'],
            original_format=data['original_format'],
            processed_format=data['processed_format'],
            original_size=data['original_size'],
            processed_size=data['processed_size'],
            dimensions=tuple(data['dimensions']),
            processing_time_ms=data['processing_time_ms'],
            compression_ratio=data['compression_ratio'],
            correlation_id=data['correlation_id'],
            metadata=data['metadata']
        )

    async def process_images_batch(
        self,
        images: list,
        provider: Union[Provider, str],
        options: Optional[ProcessingOptions] = None,
        max_concurrent: int = 5
    ) -> list:
        """Process multiple images concurrently."""
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_single(image_data_url):
            async with semaphore:
                return await self.process_image(image_data_url, provider, options)
        
        tasks = [process_single(img) for img in images]
        return await asyncio.gather(*tasks, return_exceptions=True)

# Usage example
async def main():
    processor = AsyncImageProcessor("http://localhost:8001", get_token)
    
    # Process single image
    result = await processor.process_image(
        image_data_url,
        Provider.CLAUDE,
        ProcessingOptions(format="JPEG", quality=90)
    )
    
    # Process multiple images
    image_urls = ["data:image/png;base64,...", "data:image/jpeg;base64,..."]
    results = await processor.process_images_batch(image_urls, Provider.CLAUDE)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Image {i} failed: {result}")
        else:
            print(f"Image {i} processed: {result.compression_ratio:.2%} compression")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Best Practices

### 1. Provider Selection Strategy

Choose providers based on image characteristics:

```typescript
function selectOptimalProvider(imageAnalysis: any): string {
  const { complexity_score, has_transparency, dimensions, size_mb } = imageAnalysis.analysis;
  
  // High-resolution images: Gemini
  if (dimensions.width > 2048 || dimensions.height > 2048) {
    return 'gemini';
  }
  
  // Images with transparency: OpenAI
  if (has_transparency) {
    return 'openai';
  }
  
  // Large files that need compression: Claude
  if (size_mb > 5) {
    return 'claude';
  }
  
  // Complex images: Gemini for better quality
  if (complexity_score > 7) {
    return 'gemini';
  }
  
  // Default to Claude for general use
  return 'claude';
}

// Usage
const analysis = await imageProcessor.analyzeImage(imageDataUrl);
const provider = selectOptimalProvider(analysis);
const result = await imageProcessor.processImage(imageDataUrl, provider);
```

### 2. Error Handling Strategy

```typescript
async function robustImageProcessing(
  imageDataUrl: string,
  preferredProvider: string
): Promise<ProcessImageResult> {
  const providers = ['claude', 'openai', 'gemini'];
  const providerOrder = [preferredProvider, ...providers.filter(p => p !== preferredProvider)];
  
  for (const provider of providerOrder) {
    try {
      // Validate first
      const validation = await imageProcessor.validateImage(imageDataUrl, provider);
      if (!validation.valid) {
        console.log(`Skipping ${provider}: ${validation.error_message}`);
        continue;
      }
      
      // Process with provider
      return await imageProcessor.processImage(imageDataUrl, provider);
      
    } catch (error) {
      console.error(`Failed with ${provider}:`, error.message);
      
      // Don't retry on authentication errors
      if (error.response?.status === 401) {
        throw error;
      }
      
      // Continue to next provider for other errors
      continue;
    }
  }
  
  throw new Error('All providers failed');
}
```

### 3. Caching Strategy

```typescript
class CachedImageProcessor {
  private cache = new Map<string, any>();
  private processor: ImageProcessor;
  
  constructor(processor: ImageProcessor) {
    this.processor = processor;
  }
  
  private getCacheKey(imageDataUrl: string, provider: string, options?: any): string {
    const hash = this.simpleHash(imageDataUrl + provider + JSON.stringify(options || {}));
    return hash;
  }
  
  private simpleHash(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash.toString();
  }
  
  async processImage(
    imageDataUrl: string,
    provider: string,
    options?: any
  ): Promise<ProcessImageResult> {
    const cacheKey = this.getCacheKey(imageDataUrl, provider, options);
    
    if (this.cache.has(cacheKey)) {
      console.log('Cache hit for image processing');
      return this.cache.get(cacheKey);
    }
    
    const result = await this.processor.processImage(imageDataUrl, provider, options);
    
    // Cache result for 1 hour
    this.cache.set(cacheKey, result);
    setTimeout(() => this.cache.delete(cacheKey), 60 * 60 * 1000);
    
    return result;
  }
}
```

### 4. Progress Tracking

```typescript
interface ProcessingProgress {
  stage: 'validating' | 'processing' | 'optimizing' | 'complete';
  progress: number; // 0-100
  message: string;
  correlation_id?: string;
}

class ProgressTrackingProcessor {
  private processor: ImageProcessor;
  private progressCallbacks = new Map<string, (progress: ProcessingProgress) => void>();
  
  constructor(processor: ImageProcessor) {
    this.processor = processor;
  }
  
  async processImageWithProgress(
    imageDataUrl: string,
    provider: string,
    options?: any,
    onProgress?: (progress: ProcessingProgress) => void
  ): Promise<ProcessImageResult> {
    const progressId = Math.random().toString(36).substr(2, 9);
    
    if (onProgress) {
      this.progressCallbacks.set(progressId, onProgress);
    }
    
    try {
      // Stage 1: Validation
      this.updateProgress(progressId, {
        stage: 'validating',
        progress: 25,
        message: 'Validating image requirements...'
      });
      
      const validation = await this.processor.validateImage(imageDataUrl, provider);
      if (!validation.valid) {
        throw new Error(validation.error_message);
      }
      
      // Stage 2: Processing
      this.updateProgress(progressId, {
        stage: 'processing',
        progress: 50,
        message: 'Processing image...'
      });
      
      const result = await this.processor.processImage(imageDataUrl, provider, options);
      
      // Stage 3: Complete
      this.updateProgress(progressId, {
        stage: 'complete',
        progress: 100,
        message: 'Processing complete',
        correlation_id: result.correlation_id
      });
      
      return result;
      
    } finally {
      this.progressCallbacks.delete(progressId);
    }
  }
  
  private updateProgress(progressId: string, progress: ProcessingProgress) {
    const callback = this.progressCallbacks.get(progressId);
    if (callback) {
      callback(progress);
    }
  }
}
```

---

## Performance Optimization

### 1. Image Size Optimization

```typescript
function optimizeImageForUpload(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    img.onload = () => {
      // Calculate optimal dimensions
      const maxDimension = 2048; // Safe for all providers
      const scale = Math.min(maxDimension / img.width, maxDimension / img.height, 1);
      
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      
      // Convert to JPEG with quality optimization
      const quality = file.size > 5 * 1024 * 1024 ? 0.7 : 0.9; // Lower quality for large files
      const dataUrl = canvas.toDataURL('image/jpeg', quality);
      
      resolve(dataUrl);
    };
    
    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
}
```

### 2. Batch Processing

```python
async def process_images_efficiently(
    processor: AsyncImageProcessor,
    image_paths: list,
    provider: str,
    max_concurrent: int = 3
) -> list:
    """Process images with optimal concurrency and error handling."""
    
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    
    async def process_with_retry(image_path: str, max_retries: int = 2):
        async with semaphore:
            for attempt in range(max_retries + 1):
                try:
                    # Pre-optimize large images
                    data_url = await optimize_image_for_provider(image_path, provider)
                    
                    result = await processor.process_image(data_url, provider)
                    return {"success": True, "path": image_path, "result": result}
                    
                except Exception as e:
                    if attempt == max_retries:
                        return {"success": False, "path": image_path, "error": str(e)}
                    
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)
    
    # Process all images
    tasks = [process_with_retry(path) for path in image_paths]
    results = await asyncio.gather(*tasks)
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    print(f"Processed {successful}/{len(results)} images successfully")
    
    return results
```

### 3. Memory Management

```typescript
class MemoryEfficientProcessor {
  private processor: ImageProcessor;
  private readonly maxMemoryMB = 100; // Maximum memory usage
  private currentMemoryMB = 0;
  
  constructor(processor: ImageProcessor) {
    this.processor = processor;
  }
  
  async processLargeImage(imageDataUrl: string, provider: string): Promise<ProcessImageResult> {
    // Estimate memory usage
    const estimatedMemoryMB = this.estimateMemoryUsage(imageDataUrl);
    
    if (this.currentMemoryMB + estimatedMemoryMB > this.maxMemoryMB) {
      // Wait for memory to free up or force garbage collection
      await this.waitForMemory(estimatedMemoryMB);
    }
    
    this.currentMemoryMB += estimatedMemoryMB;
    
    try {
      const result = await this.processor.processImage(imageDataUrl, provider);
      return result;
    } finally {
      this.currentMemoryMB -= estimatedMemoryMB;
    }
  }
  
  private estimateMemoryUsage(imageDataUrl: string): number {
    // Rough estimation: base64 length * 0.75 (for decode) * 4 (for processing)
    const base64Length = imageDataUrl.split(',')[1]?.length || 0;
    return (base64Length * 0.75 * 4) / (1024 * 1024); // Convert to MB
  }
  
  private async waitForMemory(requiredMB: number): Promise<void> {
    let attempts = 0;
    const maxAttempts = 10;
    
    while (this.currentMemoryMB + requiredMB > this.maxMemoryMB && attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
      attempts++;
    }
    
    if (attempts >= maxAttempts) {
      throw new Error('Memory limit exceeded, cannot process image');
    }
  }
}
```

---

## Testing

### Unit Testing Examples

```typescript
// imageProcessor.test.ts
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ImageProcessor } from './imageProcessor';

describe('ImageProcessor', () => {
  let processor: ImageProcessor;
  let mockTokenProvider: vi.Mock;
  
  beforeEach(() => {
    mockTokenProvider = vi.fn().mockResolvedValue('mock-token');
    processor = new ImageProcessor('http://localhost:8001', mockTokenProvider);
  });
  
  it('should process image successfully', async () => {
    const mockResponse = {
      success: true,
      processed_image: 'data:image/jpeg;base64,processed...',
      compression_ratio: 0.7,
      processing_time_ms: 150
    };
    
    // Mock axios response
    vi.spyOn(processor['client'], 'post').mockResolvedValue({ data: mockResponse });
    
    const result = await processor.processImage(
      'data:image/png;base64,original...',
      'claude'
    );
    
    expect(result.success).toBe(true);
    expect(result.compression_ratio).toBe(0.7);
    expect(mockTokenProvider).toHaveBeenCalled();
  });
  
  it('should handle validation errors', async () => {
    const mockError = {
      response: {
        status: 422,
        data: {
          success: false,
          error: 'validation_error',
          message: 'Image too large'
        }
      }
    };
    
    vi.spyOn(processor['client'], 'post').mockRejectedValue(mockError);
    
    await expect(
      processor.processImage('data:image/png;base64,large...', 'claude')
    ).rejects.toThrow();
  });
});
```

### Integration Testing

```python
# test_integration.py
import pytest
import asyncio
from async_image_processor import AsyncImageProcessor, Provider

@pytest.mark.asyncio
async def test_full_processing_workflow():
    """Test the complete image processing workflow."""
    
    processor = AsyncImageProcessor("http://localhost:8001", lambda: "test-token")
    
    # Use a small test image
    test_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    # Test validation
    validation = await processor.validate_image(test_image, Provider.CLAUDE)
    assert validation["valid"] is True
    
    # Test analysis
    analysis = await processor.analyze_image(test_image)
    assert analysis["success"] is True
    assert "analysis" in analysis
    
    # Test processing
    result = await processor.process_image(test_image, Provider.CLAUDE)
    assert result.success is True
    assert result.processed_image.startswith("data:image/")
    
    # Test thumbnail
    thumbnail = await processor.create_thumbnail(test_image, 50, 50)
    assert thumbnail["success"] is True

@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling for various failure scenarios."""
    
    processor = AsyncImageProcessor("http://localhost:8001", lambda: "invalid-token")
    
    with pytest.raises(Exception):  # Should raise authentication error
        await processor.process_image("data:image/png;base64,test", Provider.CLAUDE)

def test_provider_selection():
    """Test optimal provider selection logic."""
    
    # Mock analysis results
    high_res_analysis = {
        "analysis": {
            "dimensions": {"width": 4000, "height": 3000},
            "has_transparency": False,
            "complexity_score": 5,
            "size_mb": 8
        }
    }
    
    provider = select_optimal_provider(high_res_analysis)
    assert provider == "gemini"  # Should choose Gemini for high-res
    
    transparency_analysis = {
        "analysis": {
            "dimensions": {"width": 1000, "height": 800},
            "has_transparency": True,
            "complexity_score": 4,
            "size_mb": 2
        }
    }
    
    provider = select_optimal_provider(transparency_analysis)
    assert provider == "openai"  # Should choose OpenAI for transparency
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Authentication Failures

```typescript
// Check token validity
async function validateToken(token: string): Promise<boolean> {
  try {
    const response = await fetch('http://localhost:8001/api/v1/providers', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    return response.ok;
  } catch {
    return false;
  }
}

// Refresh token if needed
async function ensureValidToken(): Promise<string> {
  const currentToken = getCurrentToken();
  
  if (await validateToken(currentToken)) {
    return currentToken;
  }
  
  // Token is invalid, refresh it
  return await refreshToken();
}
```

#### 2. Image Size Issues

```python
def diagnose_image_issues(image_data_url: str, provider: str) -> dict:
    """Diagnose common image processing issues."""
    
    try:
        # Decode and analyze image
        header, data = image_data_url.split(',', 1)
        image_bytes = base64.b64decode(data)
        
        from PIL import Image
        import io
        
        img = Image.open(io.BytesIO(image_bytes))
        
        issues = []
        suggestions = []
        
        # Check file size
        size_mb = len(image_bytes) / (1024 * 1024)
        max_sizes = {"claude": 5, "openai": 20, "gemini": 20}
        
        if size_mb > max_sizes.get(provider, 20):
            issues.append(f"File size {size_mb:.1f}MB exceeds {provider} limit")
            suggestions.append("Reduce image quality or dimensions")
        
        # Check dimensions
        width, height = img.size
        max_dims = {"claude": 7990, "openai": 2048, "gemini": 4096}
        
        if max(width, height) > max_dims.get(provider, 4096):
            issues.append(f"Dimensions {width}x{height} exceed {provider} limit")
            suggestions.append("Resize image before processing")
        
        # Check format
        if img.format not in ['JPEG', 'PNG', 'GIF', 'WEBP']:
            issues.append(f"Unsupported format: {img.format}")
            suggestions.append("Convert to JPEG or PNG")
        
        return {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "suggestions": suggestions,
            "image_info": {
                "format": img.format,
                "size_mb": size_mb,
                "dimensions": [width, height],
                "mode": img.mode
            }
        }
        
    except Exception as e:
        return {
            "has_issues": True,
            "issues": [f"Failed to analyze image: {str(e)}"],
            "suggestions": ["Check image data URL format"],
            "image_info": None
        }
```

#### 3. Performance Issues

```typescript
// Performance monitoring
class PerformanceMonitor {
  private metrics: Map<string, number[]> = new Map();
  
  startTimer(operation: string): () => number {
    const start = performance.now();
    
    return () => {
      const duration = performance.now() - start;
      
      if (!this.metrics.has(operation)) {
        this.metrics.set(operation, []);
      }
      
      this.metrics.get(operation)!.push(duration);
      return duration;
    };
  }
  
  getStats(operation: string): { avg: number; min: number; max: number; count: number } {
    const times = this.metrics.get(operation) || [];
    
    if (times.length === 0) {
      return { avg: 0, min: 0, max: 0, count: 0 };
    }
    
    return {
      avg: times.reduce((a, b) => a + b) / times.length,
      min: Math.min(...times),
      max: Math.max(...times),
      count: times.length
    };
  }
  
  reportSlowOperations(threshold: number = 2000): void {
    this.metrics.forEach((times, operation) => {
      const avg = times.reduce((a, b) => a + b) / times.length;
      
      if (avg > threshold) {
        console.warn(`Slow operation detected: ${operation} (avg: ${avg.toFixed(1)}ms)`);
      }
    });
  }
}

// Usage
const monitor = new PerformanceMonitor();

async function monitoredProcessing(imageDataUrl: string, provider: string) {
  const endTimer = monitor.startTimer('image_processing');
  
  try {
    const result = await imageProcessor.processImage(imageDataUrl, provider);
    const duration = endTimer();
    
    console.log(`Processing completed in ${duration.toFixed(1)}ms`);
    return result;
  } catch (error) {
    endTimer();
    throw error;
  }
}
```

#### 4. Network Issues

```typescript
// Retry mechanism with exponential backoff
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      // Don't retry on client errors (4xx)
      if (error.response?.status >= 400 && error.response?.status < 500) {
        throw error;
      }
      
      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt);
        console.log(`Attempt ${attempt + 1} failed, retrying in ${delay}ms...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  throw lastError;
}

// Usage
const result = await retryWithBackoff(
  () => imageProcessor.processImage(imageDataUrl, 'claude'),
  3,
  1000
);
```

---

## Configuration Examples

### Environment Configuration

```typescript
// config.ts
export interface ImageProcessorConfig {
  baseUrl: string;
  timeout: number;
  maxRetries: number;
  defaultProvider: string;
  enableCaching: boolean;
  cacheTimeout: number;
  maxConcurrentRequests: number;
}

export const config: ImageProcessorConfig = {
  baseUrl: process.env.IMAGE_PROCESSOR_URL || 'http://localhost:8001',
  timeout: parseInt(process.env.REQUEST_TIMEOUT || '30000'),
  maxRetries: parseInt(process.env.MAX_RETRIES || '3'),
  defaultProvider: process.env.DEFAULT_PROVIDER || 'claude',
  enableCaching: process.env.ENABLE_CACHING === 'true',
  cacheTimeout: parseInt(process.env.CACHE_TIMEOUT || '3600000'),
  maxConcurrentRequests: parseInt(process.env.MAX_CONCURRENT || '5')
};
```

### Docker Compose Integration

```yaml
# docker-compose.integration.yml
version: '3.8'

services:
  app:
    build: .
    environment:
      - IMAGE_PROCESSOR_URL=http://image-processor:8001
      - AZURE_TENANT_ID=${AZURE_TENANT_ID}
      - AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
    depends_on:
      - image-processor
    networks:
      - app-network

  image-processor:
    image: screenshot-to-code/image-processor:latest
    ports:
      - "8001:8001"
    environment:
      - ENVIRONMENT=production
      - AZURE_TENANT_ID=${AZURE_TENANT_ID}
      - AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
      - APPLICATIONINSIGHTS_CONNECTION_STRING=${APPLICATIONINSIGHTS_CONNECTION_STRING}
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  app-network:
    driver: bridge
```

This comprehensive integration guide provides everything needed to successfully integrate with the Image Processor API across different platforms and programming languages. The examples demonstrate production-ready patterns for authentication, error handling, performance optimization, and testing.
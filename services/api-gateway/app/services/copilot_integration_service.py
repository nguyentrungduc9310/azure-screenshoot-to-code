"""
Copilot Integration Service
High-level service for orchestrating Screenshot-to-Code operations via Copilot Studio
"""
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class Framework(Enum):
    """Supported frameworks for code generation"""
    REACT = "react"
    HTML = "html"
    VUE = "vue"
    ANGULAR = "angular"
    SVELTE = "svelte"


class ProcessingStatus(Enum):
    """Processing status for async operations"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ImageProcessingResult:
    """Result from image processing service"""
    success: bool
    processed_image: Optional[str] = None
    analysis: Optional[Dict[str, Any]] = None
    processing_time_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class CodeGenerationResult:
    """Result from code generation service"""
    success: bool
    generated_code: Optional[Dict[str, str]] = None  # {filename: content}
    framework: Optional[str] = None
    processing_time_ms: Optional[float] = None
    preview_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ProcessingJob:
    """Async processing job tracking"""
    job_id: str
    user_id: str
    conversation_id: str
    status: ProcessingStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CopilotIntegrationService:
    """Service for orchestrating Screenshot-to-Code operations"""
    
    def __init__(self, 
                 image_processor_url: str = "http://localhost:8001",
                 code_generator_url: str = "http://localhost:8002", 
                 image_generator_url: str = "http://localhost:8003",
                 logger: Optional[StructuredLogger] = None):
        
        self.image_processor_url = image_processor_url
        self.code_generator_url = code_generator_url
        self.image_generator_url = image_generator_url
        self.logger = logger or StructuredLogger()
        
        # Job tracking
        self._active_jobs: Dict[str, ProcessingJob] = {}
        self._job_counter = 0
        
        # HTTP session for service calls
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Start the service"""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        self.logger.info("Copilot Integration Service started")
    
    async def stop(self):
        """Stop the service"""
        if self._session:
            await self._session.close()
        self.logger.info("Copilot Integration Service stopped")
    
    def _generate_job_id(self) -> str:
        """Generate unique job ID"""
        self._job_counter += 1
        return f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._job_counter}"
    
    async def process_screenshot_to_code(self,
                                       image_url: Optional[str] = None,
                                       image_data: Optional[str] = None,
                                       framework: Framework = Framework.REACT,
                                       requirements: Optional[str] = None,
                                       user_id: str = "anonymous",
                                       conversation_id: str = "unknown",
                                       async_processing: bool = False) -> Union[CodeGenerationResult, str]:
        """
        Process screenshot to code - main orchestration method
        
        Returns:
            CodeGenerationResult for sync processing
            job_id (str) for async processing
        """
        correlation_id = get_correlation_id()
        
        self.logger.info("Starting screenshot-to-code processing",
                        framework=framework.value,
                        has_image_url=bool(image_url),
                        has_image_data=bool(image_data),
                        async_processing=async_processing,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        correlation_id=correlation_id)
        
        if async_processing:
            # Create async job
            job_id = self._generate_job_id()
            job = ProcessingJob(
                job_id=job_id,
                user_id=user_id,
                conversation_id=conversation_id,
                status=ProcessingStatus.PENDING,
                created_at=datetime.now(timezone.utc)
            )
            self._active_jobs[job_id] = job
            
            # Start background processing
            asyncio.create_task(self._process_async_job(
                job_id, image_url, image_data, framework, requirements
            ))
            
            return job_id
        else:
            # Synchronous processing
            return await self._process_screenshot_sync(
                image_url, image_data, framework, requirements, user_id, conversation_id
            )
    
    async def _process_screenshot_sync(self,
                                     image_url: Optional[str],
                                     image_data: Optional[str], 
                                     framework: Framework,
                                     requirements: Optional[str],
                                     user_id: str,
                                     conversation_id: str) -> CodeGenerationResult:
        """Synchronous screenshot processing"""
        try:
            # Step 1: Process image
            image_result = await self._process_image(image_url, image_data)
            if not image_result.success:
                return CodeGenerationResult(
                    success=False,
                    error=f"Image processing failed: {image_result.error}"
                )
            
            # Step 2: Generate code
            code_result = await self._generate_code(
                image_result.processed_image,
                framework,
                requirements,
                user_id,
                conversation_id
            )
            
            return code_result
            
        except Exception as e:
            self.logger.error("Screenshot processing failed",
                            error=str(e),
                            user_id=user_id,
                            conversation_id=conversation_id)
            
            return CodeGenerationResult(
                success=False,
                error=f"Processing failed: {str(e)}"
            )
    
    async def _process_async_job(self,
                               job_id: str,
                               image_url: Optional[str],
                               image_data: Optional[str],
                               framework: Framework,
                               requirements: Optional[str]):
        """Process async job in background"""
        job = self._active_jobs.get(job_id)
        if not job:
            return
        
        try:
            # Update job status
            job.status = ProcessingStatus.PROCESSING
            
            # Process screenshot
            result = await self._process_screenshot_sync(
                image_url, image_data, framework, requirements,
                job.user_id, job.conversation_id
            )
            
            # Update job with result
            job.status = ProcessingStatus.COMPLETED if result.success else ProcessingStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.result = result.__dict__
            job.error = result.error if not result.success else None
            
            self.logger.info("Async job completed",
                           job_id=job_id,
                           status=job.status.value,
                           success=result.success)
            
        except Exception as e:
            job.status = ProcessingStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error = str(e)
            
            self.logger.error("Async job failed",
                            job_id=job_id,
                            error=str(e))
    
    async def _process_image(self,
                           image_url: Optional[str],
                           image_data: Optional[str]) -> ImageProcessingResult:
        """Process image through image processor service"""
        try:
            if not image_url and not image_data:
                return ImageProcessingResult(
                    success=False,
                    error="No image provided"
                )
            
            # Prepare request
            payload = {
                "provider": "claude",  # Default provider
                "options": {
                    "format": "JPEG",
                    "quality": 90
                }
            }
            
            if image_url:
                payload["image_url"] = image_url
            else:
                payload["image"] = image_data
            
            # Call image processor service
            async with self._session.post(
                f"{self.image_processor_url}/api/v1/process",
                json=payload
            ) as response:
                
                if response.status == 200:
                    result_data = await response.json()
                    
                    return ImageProcessingResult(
                        success=result_data.get("success", False),
                        processed_image=result_data.get("processed_image"),
                        analysis=result_data.get("metadata"),
                        processing_time_ms=result_data.get("processing_time_ms")
                    )
                else:
                    error_text = await response.text()
                    return ImageProcessingResult(
                        success=False,
                        error=f"Image processor returned {response.status}: {error_text}"
                    )
        
        except Exception as e:
            self.logger.error("Image processing service call failed", error=str(e))
            return ImageProcessingResult(
                success=False,
                error=f"Service call failed: {str(e)}"
            )
    
    async def _generate_code(self,
                           processed_image: str,
                           framework: Framework,
                           requirements: Optional[str],
                           user_id: str,
                           conversation_id: str) -> CodeGenerationResult:
        """Generate code through code generator service"""
        try:
            # Prepare request
            payload = {
                "image": processed_image,
                "framework": framework.value,
                "requirements": requirements or "",
                "user_id": user_id,
                "conversation_id": conversation_id,
                "options": {
                    "style": "modern",
                    "responsive": True,
                    "accessibility": True
                }
            }
            
            # Call code generator service
            async with self._session.post(
                f"{self.code_generator_url}/api/v1/generate",
                json=payload
            ) as response:
                
                if response.status == 200:
                    result_data = await response.json()
                    
                    return CodeGenerationResult(
                        success=result_data.get("success", False),
                        generated_code=result_data.get("generated_code"),
                        framework=result_data.get("framework"),
                        processing_time_ms=result_data.get("processing_time_ms"),
                        preview_url=result_data.get("preview_url")
                    )
                else:
                    error_text = await response.text()
                    return CodeGenerationResult(
                        success=False,
                        error=f"Code generator returned {response.status}: {error_text}"
                    )
        
        except Exception as e:
            self.logger.error("Code generation service call failed", error=str(e))
            return CodeGenerationResult(
                success=False,
                error=f"Service call failed: {str(e)}"
            )
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of async processing job"""
        job = self._active_jobs.get(job_id)
        if not job:
            return None
        
        return {
            "job_id": job.job_id,
            "user_id": job.user_id,
            "conversation_id": job.conversation_id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result,
            "error": job.error
        }
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel async processing job"""
        job = self._active_jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [ProcessingStatus.PENDING, ProcessingStatus.PROCESSING]:
            job.status = ProcessingStatus.FAILED
            job.error = "Job cancelled by user"
            job.completed_at = datetime.now(timezone.utc)
            
            self.logger.info("Job cancelled", job_id=job_id)
            return True
        
        return False
    
    async def cleanup_completed_jobs(self, max_age_hours: int = 24):
        """Clean up old completed jobs"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        jobs_to_remove = []
        for job_id, job in self._active_jobs.items():
            if (job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED] and
                job.completed_at and job.completed_at < cutoff_time):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self._active_jobs[job_id]
        
        if jobs_to_remove:
            self.logger.info("Cleaned up completed jobs", count=len(jobs_to_remove))
    
    async def get_supported_frameworks(self) -> List[Dict[str, str]]:
        """Get list of supported frameworks"""
        return [
            {
                "id": framework.value,
                "name": framework.value.title(),
                "description": f"Generate {framework.value.upper()} code"
            }
            for framework in Framework
        ]
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Get service health information"""
        # Check downstream services
        services_health = {}
        
        for service_name, url in [
            ("image_processor", self.image_processor_url),
            ("code_generator", self.code_generator_url),
            ("image_generator", self.image_generator_url)
        ]:
            try:
                async with self._session.get(f"{url}/health") as response:
                    services_health[service_name] = {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "response_time_ms": response.headers.get("X-Response-Time"),
                        "url": url
                    }
            except Exception as e:
                services_health[service_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "url": url
                }
        
        return {
            "service": "copilot_integration",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_jobs": len(self._active_jobs),
            "downstream_services": services_health
        }


# Global service instance
_copilot_service: Optional[CopilotIntegrationService] = None


async def get_copilot_service() -> CopilotIntegrationService:
    """Get copilot integration service instance"""
    global _copilot_service
    if _copilot_service is None:
        _copilot_service = CopilotIntegrationService()
        await _copilot_service.start()
    return _copilot_service
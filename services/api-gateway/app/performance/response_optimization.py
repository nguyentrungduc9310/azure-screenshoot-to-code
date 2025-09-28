"""
Response Time Optimization
Advanced response optimization with request batching, parallel processing, and intelligent routing
"""
import asyncio
import time
import json
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing
from contextlib import asynccontextmanager

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        import uuid
        return str(uuid.uuid4())[:8]


class OptimizationStrategy(Enum):
    """Response optimization strategies"""
    PARALLEL_PROCESSING = "parallel_processing"
    REQUEST_BATCHING = "request_batching"
    RESULT_STREAMING = "result_streaming"
    LAZY_LOADING = "lazy_loading"
    INTELLIGENT_CACHING = "intelligent_caching"


class ProcessingPriority(Enum):
    """Request processing priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class RequestContext:
    """Request processing context"""
    request_id: str
    correlation_id: str
    user_id: str
    priority: ProcessingPriority
    timeout_seconds: float
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_started: Optional[datetime] = None
    processing_completed: Optional[datetime] = None
    
    def get_processing_time(self) -> Optional[float]:
        """Get request processing time in seconds"""
        if self.processing_started and self.processing_completed:
            return (self.processing_completed - self.processing_started).total_seconds()
        return None
    
    def is_expired(self) -> bool:
        """Check if request has expired"""
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed > self.timeout_seconds


@dataclass
class BatchRequest:
    """Batch request container"""
    batch_id: str
    requests: List[RequestContext]
    batch_type: str
    created_at: datetime
    max_batch_size: int = 10
    max_wait_time: float = 0.5  # seconds
    
    def can_add_request(self) -> bool:
        """Check if batch can accept more requests"""
        if len(self.requests) >= self.max_batch_size:
            return False
        
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed < self.max_wait_time
    
    def get_batch_processing_priority(self) -> ProcessingPriority:
        """Get batch priority based on highest priority request"""
        if not self.requests:
            return ProcessingPriority.NORMAL
        
        return max(req.priority for req in self.requests)


@dataclass
class OptimizationMetrics:
    """Response optimization metrics"""
    total_requests: int = 0
    parallel_requests: int = 0
    batched_requests: int = 0
    cached_responses: int = 0
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    optimization_ratio: float = 0.0
    throughput_rps: float = 0.0
    
    def calculate_optimization_ratio(self) -> float:
        """Calculate optimization effectiveness ratio"""
        if self.total_requests == 0:
            return 0.0
        
        optimized = self.parallel_requests + self.batched_requests + self.cached_responses
        self.optimization_ratio = (optimized / self.total_requests) * 100
        return self.optimization_ratio


class ResponseOptimizer:
    """Advanced response time optimizer"""
    
    def __init__(self, 
                 logger: Optional[StructuredLogger] = None,
                 max_workers: int = None,
                 enable_batching: bool = True,
                 enable_parallel_processing: bool = True,
                 enable_streaming: bool = True):
        
        self.logger = logger or StructuredLogger()
        self.max_workers = max_workers or min(32, (multiprocessing.cpu_count() or 1) + 4)
        self.enable_batching = enable_batching
        self.enable_parallel_processing = enable_parallel_processing
        self.enable_streaming = enable_streaming
        
        # Processing infrastructure
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max(1, self.max_workers // 4))
        
        # Request queues and batching
        self.request_queue = asyncio.Queue()
        self.batch_queues: Dict[str, List[BatchRequest]] = {}
        self.active_batches: Dict[str, BatchRequest] = {}
        
        # Performance tracking
        self.metrics = OptimizationMetrics()
        self.response_times: List[float] = []
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        
        # Optimization configuration
        self.optimization_config = {
            "max_batch_size": 10,
            "max_batch_wait_time": 0.5,
            "parallel_threshold": 3,
            "streaming_threshold": 1.0,
            "cache_threshold": 0.1
        }
        
        # Start background processors
        self._background_tasks = []
        if self.enable_batching:
            self._background_tasks.append(asyncio.create_task(self._batch_processor()))
    
    async def process_request(self, 
                            request_data: Dict[str, Any],
                            processing_func: Callable,
                            context: Optional[RequestContext] = None,
                            optimization_strategy: Optional[OptimizationStrategy] = None) -> Any:
        """Process request with optimization"""
        
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        
        if context is None:
            context = RequestContext(
                request_id=correlation_id,
                correlation_id=correlation_id,
                user_id=request_data.get('user_id', 'anonymous'),
                priority=ProcessingPriority.NORMAL,
                timeout_seconds=30.0,
                created_at=datetime.utcnow()
            )
        
        try:
            # Determine optimal processing strategy
            if optimization_strategy is None:
                optimization_strategy = await self._determine_optimization_strategy(
                    request_data, processing_func, context
                )
            
            # Process request with selected strategy
            result = await self._execute_with_strategy(
                request_data, processing_func, context, optimization_strategy
            )
            
            # Update metrics
            processing_time = time.perf_counter() - start_time
            await self._update_metrics(processing_time, optimization_strategy)
            
            self.logger.info(
                "Request processed with optimization",
                request_id=context.request_id,
                optimization_strategy=optimization_strategy.value,
                processing_time_ms=processing_time * 1000,
                correlation_id=correlation_id
            )
            
            return result
            
        except Exception as e:
            processing_time = time.perf_counter() - start_time
            self.logger.error(
                "Request processing failed",
                request_id=context.request_id,
                error=str(e),
                processing_time_ms=processing_time * 1000,
                correlation_id=correlation_id
            )
            raise
    
    async def process_multiple_requests(self, 
                                      requests: List[Tuple[Dict[str, Any], Callable]],
                                      parallel: bool = True) -> List[Any]:
        """Process multiple requests with optimization"""
        
        if not requests:
            return []
        
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        
        if parallel and self.enable_parallel_processing and len(requests) >= self.optimization_config["parallel_threshold"]:
            # Parallel processing
            tasks = []
            for request_data, processing_func in requests:
                task = asyncio.create_task(
                    self.process_request(request_data, processing_func)
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Separate successful results from exceptions
            successful_results = []
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(
                        "Parallel request failed",
                        error=str(result),
                        correlation_id=correlation_id
                    )
                    successful_results.append(None)
                else:
                    successful_results.append(result)
            
            self.metrics.parallel_requests += len(requests)
            
        else:
            # Sequential processing
            successful_results = []
            for request_data, processing_func in requests:
                try:
                    result = await self.process_request(request_data, processing_func)
                    successful_results.append(result)
                except Exception as e:
                    self.logger.error(
                        "Sequential request failed",
                        error=str(e),
                        correlation_id=correlation_id
                    )
                    successful_results.append(None)
        
        processing_time = time.perf_counter() - start_time
        self.logger.info(
            "Multiple requests processed",
            request_count=len(requests),
            processing_time_ms=processing_time * 1000,
            parallel_processing=parallel,
            correlation_id=correlation_id
        )
        
        return successful_results
    
    async def _determine_optimization_strategy(self, 
                                             request_data: Dict[str, Any],
                                             processing_func: Callable,
                                             context: RequestContext) -> OptimizationStrategy:
        """Determine optimal processing strategy for request"""
        
        # Check if result might be cached
        if await self._is_cacheable(request_data):
            return OptimizationStrategy.INTELLIGENT_CACHING
        
        # Check if request is suitable for batching
        if self.enable_batching and await self._is_batchable(request_data, processing_func):
            return OptimizationStrategy.REQUEST_BATCHING
        
        # Check if request benefits from streaming
        if self.enable_streaming and await self._should_stream(request_data):
            return OptimizationStrategy.RESULT_STREAMING
        
        # Check if request can use parallel processing
        if self.enable_parallel_processing and await self._can_parallelize(request_data):
            return OptimizationStrategy.PARALLEL_PROCESSING
        
        return OptimizationStrategy.LAZY_LOADING
    
    async def _execute_with_strategy(self, 
                                   request_data: Dict[str, Any],
                                   processing_func: Callable,
                                   context: RequestContext,
                                   strategy: OptimizationStrategy) -> Any:
        """Execute request with specific optimization strategy"""
        
        context.processing_started = datetime.utcnow()
        
        try:
            if strategy == OptimizationStrategy.INTELLIGENT_CACHING:
                result = await self._execute_with_caching(request_data, processing_func, context)
            elif strategy == OptimizationStrategy.REQUEST_BATCHING:
                result = await self._execute_with_batching(request_data, processing_func, context)
            elif strategy == OptimizationStrategy.RESULT_STREAMING:
                result = await self._execute_with_streaming(request_data, processing_func, context)
            elif strategy == OptimizationStrategy.PARALLEL_PROCESSING:
                result = await self._execute_with_parallel(request_data, processing_func, context)
            else:  # LAZY_LOADING
                result = await self._execute_with_lazy_loading(request_data, processing_func, context)
            
            context.processing_completed = datetime.utcnow()
            return result
            
        except Exception as e:
            context.processing_completed = datetime.utcnow()
            raise
    
    async def _execute_with_caching(self, 
                                  request_data: Dict[str, Any],
                                  processing_func: Callable,
                                  context: RequestContext) -> Any:
        """Execute request with intelligent caching"""
        
        # Generate cache key
        cache_key = await self._generate_cache_key(request_data, processing_func)
        
        # Try to get from cache (mock implementation)
        cached_result = await self._get_from_cache(cache_key)
        if cached_result is not None:
            self.metrics.cached_responses += 1
            return cached_result
        
        # Execute function
        if asyncio.iscoroutinefunction(processing_func):
            result = await processing_func(request_data)
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                self.thread_executor, processing_func, request_data
            )
        
        # Store in cache
        await self._store_in_cache(cache_key, result)
        
        return result
    
    async def _execute_with_batching(self, 
                                   request_data: Dict[str, Any],
                                   processing_func: Callable,
                                   context: RequestContext) -> Any:
        """Execute request with batching optimization"""
        
        batch_type = await self._get_batch_type(request_data, processing_func)
        
        # Add request to appropriate batch
        batch = await self._add_to_batch(context, request_data, processing_func, batch_type)
        
        # Wait for batch processing result
        result = await self._wait_for_batch_result(batch.batch_id, context.request_id)
        
        self.metrics.batched_requests += 1
        return result
    
    async def _execute_with_streaming(self, 
                                    request_data: Dict[str, Any],
                                    processing_func: Callable,
                                    context: RequestContext) -> Any:
        """Execute request with result streaming"""
        
        # For streaming, we need to return an async generator or similar
        # This is a simplified implementation
        
        if asyncio.iscoroutinefunction(processing_func):
            # Check if processing function supports streaming
            if hasattr(processing_func, '__streaming__'):
                async for chunk in processing_func(request_data):
                    yield chunk
            else:
                result = await processing_func(request_data)
                return result
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                self.thread_executor, processing_func, request_data
            )
            return result
    
    async def _execute_with_parallel(self, 
                                   request_data: Dict[str, Any],
                                   processing_func: Callable,
                                   context: RequestContext) -> Any:
        """Execute request with parallel processing"""
        
        # Check if request can be decomposed into parallel tasks
        subtasks = await self._decompose_request(request_data, processing_func)
        
        if len(subtasks) > 1:
            # Execute subtasks in parallel
            tasks = []
            for subtask_data, subtask_func in subtasks:
                if asyncio.iscoroutinefunction(subtask_func):
                    task = asyncio.create_task(subtask_func(subtask_data))
                else:
                    task = asyncio.get_event_loop().run_in_executor(
                        self.thread_executor, subtask_func, subtask_data
                    )
                tasks.append(task)
            
            subtask_results = await asyncio.gather(*tasks)
            
            # Combine results
            result = await self._combine_subtask_results(subtask_results, request_data)
            
            self.metrics.parallel_requests += 1
            return result
        else:
            # Fallback to normal execution
            if asyncio.iscoroutinefunction(processing_func):
                return await processing_func(request_data)
            else:
                return await asyncio.get_event_loop().run_in_executor(
                    self.thread_executor, processing_func, request_data
                )
    
    async def _execute_with_lazy_loading(self, 
                                       request_data: Dict[str, Any],
                                       processing_func: Callable,
                                       context: RequestContext) -> Any:
        """Execute request with lazy loading optimization"""
        
        # Identify which parts of the response can be loaded lazily
        essential_data = await self._extract_essential_data(request_data)
        lazy_data_tasks = await self._identify_lazy_data(request_data)
        
        # Process essential data first
        if asyncio.iscoroutinefunction(processing_func):
            essential_result = await processing_func(essential_data)
        else:
            essential_result = await asyncio.get_event_loop().run_in_executor(
                self.thread_executor, processing_func, essential_data
            )
        
        # Start lazy data processing in background
        lazy_tasks = {}
        for task_id, (lazy_data, lazy_func) in lazy_data_tasks.items():
            if asyncio.iscoroutinefunction(lazy_func):
                task = asyncio.create_task(lazy_func(lazy_data))
            else:
                task = asyncio.get_event_loop().run_in_executor(
                    self.thread_executor, lazy_func, lazy_data
                )
            lazy_tasks[task_id] = task
        
        # Return essential result with lazy task references
        return {
            "essential": essential_result,
            "lazy_tasks": lazy_tasks,
            "request_id": context.request_id
        }
    
    async def _batch_processor(self):
        """Background batch processor"""
        
        while True:
            try:
                # Process all active batches
                for batch_type, batches in list(self.batch_queues.items()):
                    batches_to_process = []
                    
                    for batch in batches[:]:  # Copy list to avoid modification during iteration
                        # Check if batch is ready for processing
                        if not batch.can_add_request() or len(batch.requests) >= batch.max_batch_size:
                            batches_to_process.append(batch)
                            batches.remove(batch)
                    
                    # Process ready batches
                    for batch in batches_to_process:
                        asyncio.create_task(self._process_batch(batch))
                
                # Wait before next batch check
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(
                    "Batch processor error",
                    error=str(e)
                )
                await asyncio.sleep(1.0)  # Longer wait on error
    
    async def _process_batch(self, batch: BatchRequest):
        """Process a batch of requests"""
        
        start_time = time.perf_counter()
        
        try:
            # Group requests by processing function
            func_groups = {}
            for request in batch.requests:
                func_key = str(request.metadata.get('processing_func', 'default'))
                if func_key not in func_groups:
                    func_groups[func_key] = []
                func_groups[func_key].append(request)
            
            # Process each function group
            batch_results = {}
            for func_key, requests in func_groups.items():
                # Extract processing function and data
                processing_func = requests[0].metadata.get('processing_func')
                request_data_list = [req.metadata.get('request_data') for req in requests]
                
                if processing_func and hasattr(processing_func, '__batch_process__'):
                    # Function supports batch processing
                    if asyncio.iscoroutinefunction(processing_func):
                        results = await processing_func.batch_process(request_data_list)
                    else:
                        results = await asyncio.get_event_loop().run_in_executor(
                            self.thread_executor, processing_func.batch_process, request_data_list
                        )
                else:
                    # Process individually but in parallel
                    tasks = []
                    for request_data in request_data_list:
                        if asyncio.iscoroutinefunction(processing_func):
                            task = asyncio.create_task(processing_func(request_data))
                        else:
                            task = asyncio.get_event_loop().run_in_executor(
                                self.thread_executor, processing_func, request_data
                            )
                        tasks.append(task)
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Store results for each request
                for i, request in enumerate(requests):
                    batch_results[request.request_id] = results[i] if i < len(results) else None
            
            # Store batch results
            self.active_batches[batch.batch_id] = {
                'completed': True,
                'results': batch_results,
                'processing_time': time.perf_counter() - start_time
            }
            
            self.logger.info(
                "Batch processed successfully",
                batch_id=batch.batch_id,
                batch_size=len(batch.requests),
                processing_time_ms=(time.perf_counter() - start_time) * 1000
            )
            
        except Exception as e:
            # Store error result
            self.active_batches[batch.batch_id] = {
                'completed': True,
                'error': str(e),
                'processing_time': time.perf_counter() - start_time
            }
            
            self.logger.error(
                "Batch processing failed",
                batch_id=batch.batch_id,
                batch_size=len(batch.requests),
                error=str(e)
            )
    
    # Helper methods for optimization strategy determination
    async def _is_cacheable(self, request_data: Dict[str, Any]) -> bool:
        """Determine if request result can be cached"""
        # Simple heuristic: cache if request looks like it would have deterministic output
        has_user_specific_data = any(key in request_data for key in ['user_id', 'session_id'])
        has_time_sensitive_data = any(key in request_data for key in ['timestamp', 'now'])
        
        return not (has_user_specific_data or has_time_sensitive_data)
    
    async def _is_batchable(self, request_data: Dict[str, Any], processing_func: Callable) -> bool:
        """Determine if request can be batched"""
        # Check if processing function supports batching
        if hasattr(processing_func, '__batch_process__'):
            return True
        
        # Check if request type is suitable for batching
        request_type = request_data.get('type', '')
        batchable_types = ['image_processing', 'code_generation', 'analysis']
        
        return request_type in batchable_types
    
    async def _should_stream(self, request_data: Dict[str, Any]) -> bool:
        """Determine if request should use streaming"""
        expected_size = request_data.get('expected_response_size', 0)
        processing_time = request_data.get('expected_processing_time', 0)
        
        return (expected_size > 1024 * 1024 or  # Large response (>1MB)
                processing_time > self.optimization_config["streaming_threshold"])
    
    async def _can_parallelize(self, request_data: Dict[str, Any]) -> bool:
        """Determine if request can be parallelized"""
        # Check for parallelizable operations
        operations = request_data.get('operations', [])
        return len(operations) > 1 and not any(op.get('depends_on') for op in operations)
    
    # Mock implementations for caching (would integrate with actual cache)
    async def _generate_cache_key(self, request_data: Dict[str, Any], processing_func: Callable) -> str:
        """Generate cache key for request"""
        import hashlib
        key_data = f"{processing_func.__name__}:{json.dumps(request_data, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get result from cache (mock implementation)"""
        # Would integrate with actual cache manager
        return None
    
    async def _store_in_cache(self, cache_key: str, result: Any) -> None:
        """Store result in cache (mock implementation)"""
        # Would integrate with actual cache manager
        pass
    
    # Mock implementations for batching
    async def _get_batch_type(self, request_data: Dict[str, Any], processing_func: Callable) -> str:
        """Get batch type for request"""
        return f"{processing_func.__name__}:{request_data.get('type', 'default')}"
    
    async def _add_to_batch(self, 
                          context: RequestContext,
                          request_data: Dict[str, Any],
                          processing_func: Callable,
                          batch_type: str) -> BatchRequest:
        """Add request to appropriate batch"""
        
        # Store processing context
        context.metadata['processing_func'] = processing_func
        context.metadata['request_data'] = request_data
        
        # Find or create batch
        if batch_type not in self.batch_queues:
            self.batch_queues[batch_type] = []
        
        # Try to add to existing batch
        for batch in self.batch_queues[batch_type]:
            if batch.can_add_request():
                batch.requests.append(context)
                return batch
        
        # Create new batch
        batch = BatchRequest(
            batch_id=f"{batch_type}:{time.time()}",
            requests=[context],
            batch_type=batch_type,
            created_at=datetime.utcnow(),
            max_batch_size=self.optimization_config["max_batch_size"],
            max_wait_time=self.optimization_config["max_batch_wait_time"]
        )
        
        self.batch_queues[batch_type].append(batch)
        return batch
    
    async def _wait_for_batch_result(self, batch_id: str, request_id: str) -> Any:
        """Wait for batch processing result"""
        
        timeout = 30.0  # 30 second timeout
        start_time = time.perf_counter()
        
        while (time.perf_counter() - start_time) < timeout:
            if batch_id in self.active_batches:
                batch_result = self.active_batches[batch_id]
                if batch_result.get('completed'):
                    if 'error' in batch_result:
                        raise Exception(f"Batch processing failed: {batch_result['error']}")
                    
                    return batch_result.get('results', {}).get(request_id)
            
            await asyncio.sleep(0.01)  # 10ms polling interval
        
        raise TimeoutError(f"Batch processing timeout for request {request_id}")
    
    # Mock implementations for parallel processing
    async def _decompose_request(self, 
                               request_data: Dict[str, Any], 
                               processing_func: Callable) -> List[Tuple[Dict[str, Any], Callable]]:
        """Decompose request into parallel subtasks"""
        
        # Simple decomposition based on operations
        operations = request_data.get('operations', [])
        if len(operations) <= 1:
            return [(request_data, processing_func)]
        
        subtasks = []
        for operation in operations:
            subtask_data = {**request_data, 'operation': operation}
            subtasks.append((subtask_data, processing_func))
        
        return subtasks
    
    async def _combine_subtask_results(self, 
                                     subtask_results: List[Any], 
                                     original_request: Dict[str, Any]) -> Any:
        """Combine parallel subtask results"""
        
        # Simple combination strategy
        if all(isinstance(result, dict) for result in subtask_results):
            combined = {}
            for result in subtask_results:
                combined.update(result)
            return combined
        elif all(isinstance(result, list) for result in subtask_results):
            combined = []
            for result in subtask_results:
                combined.extend(result)
            return combined
        else:
            return subtask_results
    
    # Mock implementations for lazy loading
    async def _extract_essential_data(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract essential data that must be processed immediately"""
        
        essential_keys = ['type', 'priority', 'user_id', 'essential_params']
        essential_data = {}
        
        for key in essential_keys:
            if key in request_data:
                essential_data[key] = request_data[key]
        
        return essential_data
    
    async def _identify_lazy_data(self, request_data: Dict[str, Any]) -> Dict[str, Tuple[Dict[str, Any], Callable]]:
        """Identify data that can be loaded lazily"""
        
        lazy_tasks = {}
        
        # Example: large attachments can be processed lazily
        if 'attachments' in request_data:
            lazy_tasks['attachments'] = (
                {'attachments': request_data['attachments']},
                self._process_attachments
            )
        
        # Example: optional analysis can be done lazily
        if 'optional_analysis' in request_data:
            lazy_tasks['analysis'] = (
                {'analysis_params': request_data['optional_analysis']},
                self._perform_analysis
            )
        
        return lazy_tasks
    
    async def _process_attachments(self, data: Dict[str, Any]) -> Any:
        """Mock attachment processing"""
        await asyncio.sleep(0.1)  # Simulate processing
        return {"processed_attachments": len(data.get('attachments', []))}
    
    async def _perform_analysis(self, data: Dict[str, Any]) -> Any:
        """Mock analysis processing"""
        await asyncio.sleep(0.2)  # Simulate analysis
        return {"analysis_result": "completed"}
    
    async def _update_metrics(self, processing_time: float, strategy: OptimizationStrategy):
        """Update optimization metrics"""
        
        self.metrics.total_requests += 1
        self.response_times.append(processing_time)
        
        # Keep only recent response times (last 1000)
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]
        
        # Update average response time (exponential moving average)
        if self.metrics.avg_response_time == 0:
            self.metrics.avg_response_time = processing_time
        else:
            self.metrics.avg_response_time = (self.metrics.avg_response_time * 0.9) + (processing_time * 0.1)
        
        # Update P95 response time
        if len(self.response_times) >= 20:
            sorted_times = sorted(self.response_times)
            p95_index = int(0.95 * len(sorted_times))
            self.metrics.p95_response_time = sorted_times[p95_index]
        
        # Calculate throughput (requests per second)
        if len(self.response_times) >= 10:
            recent_times = self.response_times[-10:]
            time_span = max(recent_times) - min(recent_times)
            if time_span > 0:
                self.metrics.throughput_rps = len(recent_times) / time_span
        
        # Update optimization ratio
        self.metrics.calculate_optimization_ratio()
    
    async def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics"""
        
        return {
            "total_requests": self.metrics.total_requests,
            "parallel_requests": self.metrics.parallel_requests,
            "batched_requests": self.metrics.batched_requests,
            "cached_responses": self.metrics.cached_responses,
            "avg_response_time_ms": self.metrics.avg_response_time * 1000,
            "p95_response_time_ms": self.metrics.p95_response_time * 1000,
            "optimization_ratio": f"{self.metrics.optimization_ratio:.2f}%",
            "throughput_rps": f"{self.metrics.throughput_rps:.2f}",
            "active_batches": len(self.active_batches),
            "queue_sizes": {
                batch_type: len(batches) 
                for batch_type, batches in self.batch_queues.items()
            }
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        
        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        # Shutdown executors
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        
        self.logger.info("Response optimizer cleanup completed")


# Global optimizer instance
_response_optimizer: Optional[ResponseOptimizer] = None


def get_response_optimizer() -> ResponseOptimizer:
    """Get global response optimizer instance"""
    global _response_optimizer
    if _response_optimizer is None:
        _response_optimizer = ResponseOptimizer()
    return _response_optimizer


def initialize_response_optimizer(max_workers: int = None,
                                enable_batching: bool = True,
                                enable_parallel_processing: bool = True) -> ResponseOptimizer:
    """Initialize global response optimizer"""
    global _response_optimizer
    _response_optimizer = ResponseOptimizer(
        max_workers=max_workers,
        enable_batching=enable_batching,
        enable_parallel_processing=enable_parallel_processing
    )
    return _response_optimizer
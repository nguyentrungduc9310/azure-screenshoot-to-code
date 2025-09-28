"""
AI Model Optimization Layer
Advanced optimization strategies for AI model performance and cost efficiency
"""
import asyncio
import time
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import hashlib
import json

from .model_types import (
    ModelRequest, ModelResponse, GenerationOptions,
    AIModelType, ModelProvider, GenerationFramework
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


@dataclass
class OptimizationMetrics:
    """Metrics for optimization tracking"""
    cache_hit_rate: float = 0.0
    average_response_time: float = 0.0
    cost_savings: float = 0.0
    token_efficiency: float = 0.0
    batch_efficiency: float = 0.0
    prompt_compression_ratio: float = 0.0
    
    # Time-based metrics
    total_requests: int = 0
    cached_requests: int = 0
    optimized_requests: int = 0
    batch_requests: int = 0
    
    # Cost metrics
    original_cost: float = 0.0
    optimized_cost: float = 0.0
    
    def update_cache_metrics(self, hit: bool):
        """Update cache hit rate metrics"""
        self.total_requests += 1
        if hit:
            self.cached_requests += 1
        self.cache_hit_rate = self.cached_requests / self.total_requests if self.total_requests > 0 else 0.0
    
    def update_cost_metrics(self, original: float, optimized: float):
        """Update cost efficiency metrics"""
        self.original_cost += original
        self.optimized_cost += optimized
        if self.original_cost > 0:
            self.cost_savings = (self.original_cost - self.optimized_cost) / self.original_cost
    
    def update_response_time(self, response_time: float):
        """Update average response time"""
        if self.total_requests == 1:
            self.average_response_time = response_time
        else:
            # Rolling average
            self.average_response_time = (
                (self.average_response_time * (self.total_requests - 1) + response_time) / 
                self.total_requests
            )


@dataclass
class OptimizationConfig:
    """Configuration for optimization strategies"""
    enable_caching: bool = True
    enable_prompt_optimization: bool = True
    enable_response_optimization: bool = True
    enable_batch_processing: bool = True
    
    # Cache settings
    cache_ttl_seconds: int = 3600
    max_cache_entries: int = 10000
    cache_compression: bool = True
    
    # Prompt optimization settings
    max_prompt_length: int = 4000
    prompt_compression_ratio: float = 0.3
    preserve_context: bool = True
    
    # Batch processing settings
    batch_size: int = 5
    batch_timeout_seconds: int = 2.0
    enable_adaptive_batching: bool = True
    
    # Response optimization settings
    enable_streaming_optimization: bool = True
    response_compression: bool = True
    parallel_processing: bool = True


class PromptOptimizer:
    """Advanced prompt optimization for efficiency and effectiveness"""
    
    def __init__(self, config: OptimizationConfig, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self._compression_cache: Dict[str, str] = {}
        self._performance_stats = defaultdict(list)
    
    async def optimize_prompt(self, request: ModelRequest) -> ModelRequest:
        """Optimize prompt for better performance and cost efficiency"""
        if not self.config.enable_prompt_optimization:
            return request
        
        optimized_request = request
        
        try:
            # Text prompt optimization
            if request.has_text and request.text_prompt:
                optimized_text = await self._optimize_text_prompt(request.text_prompt, request.options)
                optimized_request.text_prompt = optimized_text
            
            # System context optimization
            if hasattr(request, 'system_context') and request.system_context:
                optimized_context = await self._optimize_system_context(
                    request.system_context, request.options
                )
                optimized_request.system_context = optimized_context
            
            # Track optimization performance
            await self._track_optimization_performance(request, optimized_request)
            
            self.logger.debug("Prompt optimized successfully",
                            original_length=len(request.text_prompt or ""),
                            optimized_length=len(optimized_request.text_prompt or ""),
                            request_id=request.request_id)
            
            return optimized_request
        
        except Exception as e:
            self.logger.error("Prompt optimization failed",
                            error=str(e), request_id=request.request_id)
            return request
    
    async def _optimize_text_prompt(self, text_prompt: str, options: GenerationOptions) -> str:
        """Optimize text prompt for efficiency"""
        if len(text_prompt) <= self.config.max_prompt_length:
            return text_prompt
        
        # Check cache first
        cache_key = self._generate_prompt_cache_key(text_prompt, options)
        if cache_key in self._compression_cache:
            return self._compression_cache[cache_key]
        
        # Apply compression strategies
        optimized_prompt = text_prompt
        
        # Remove redundant whitespace
        optimized_prompt = " ".join(optimized_prompt.split())
        
        # Compress repetitive instructions
        optimized_prompt = await self._compress_repetitive_content(optimized_prompt)
        
        # Framework-specific optimization
        optimized_prompt = await self._apply_framework_optimization(optimized_prompt, options)
        
        # Context-aware compression
        if self.config.preserve_context:
            optimized_prompt = await self._preserve_important_context(optimized_prompt, options)
        
        # Cache the result
        self._compression_cache[cache_key] = optimized_prompt
        
        return optimized_prompt
    
    async def _optimize_system_context(self, system_context: str, options: GenerationOptions) -> str:
        """Optimize system context for efficiency"""
        # System context is usually more structured, apply different strategies
        lines = system_context.split('\n')
        optimized_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):  # Keep non-empty, non-comment lines
                # Compress instructional text
                if len(line) > 100:
                    line = await self._compress_instruction(line, options)
                optimized_lines.append(line)
        
        return '\n'.join(optimized_lines)
    
    async def _compress_repetitive_content(self, content: str) -> str:
        """Compress repetitive content while preserving meaning"""
        # Simple deduplication
        sentences = content.split('. ')
        unique_sentences = []
        seen = set()
        
        for sentence in sentences:
            sentence_key = sentence.lower().strip()
            if sentence_key not in seen and len(sentence_key) > 10:
                seen.add(sentence_key)
                unique_sentences.append(sentence)
        
        return '. '.join(unique_sentences)
    
    async def _apply_framework_optimization(self, prompt: str, options: GenerationOptions) -> str:
        """Apply framework-specific optimizations"""
        framework = options.framework
        
        # Framework-specific keyword optimization
        framework_keywords = {
            GenerationFramework.REACT: ["component", "jsx", "hooks", "state"],
            GenerationFramework.VUE: ["component", "template", "script", "style"],
            GenerationFramework.ANGULAR: ["component", "service", "module", "directive"],
            GenerationFramework.HTML: ["semantic", "structure", "accessible"]
        }
        
        if framework in framework_keywords:
            keywords = framework_keywords[framework]
            # Ensure important keywords are present but not redundant
            for keyword in keywords:
                if keyword.lower() not in prompt.lower():
                    prompt = f"{keyword.title()} {prompt}"
        
        return prompt
    
    async def _preserve_important_context(self, prompt: str, options: GenerationOptions) -> str:
        """Preserve important context while compressing"""
        # Identify and preserve critical information
        critical_patterns = [
            r'responsive.*design',
            r'accessibility.*features',
            r'typescript',
            r'scss',
            r'specific.*requirements'
        ]
        
        import re
        preserved_parts = []
        
        for pattern in critical_patterns:
            matches = re.finditer(pattern, prompt, re.IGNORECASE)
            for match in matches:
                preserved_parts.append(match.group())
        
        # Rebuild prompt with preserved critical parts
        if preserved_parts:
            base_prompt = await self._get_base_prompt(prompt)
            return f"{base_prompt} {' '.join(preserved_parts)}"
        
        return prompt
    
    async def _compress_instruction(self, instruction: str, options: GenerationOptions) -> str:
        """Compress individual instruction while preserving intent"""
        # Simple compression - remove filler words
        filler_words = ['please', 'kindly', 'very', 'really', 'quite', 'somewhat', 'rather']
        words = instruction.split()
        compressed_words = [word for word in words if word.lower() not in filler_words]
        return ' '.join(compressed_words)
    
    async def _get_base_prompt(self, prompt: str) -> str:
        """Extract base prompt essence"""
        sentences = prompt.split('. ')
        if len(sentences) <= 2:
            return prompt
        
        # Keep first and most important sentences
        return '. '.join(sentences[:2])
    
    def _generate_prompt_cache_key(self, prompt: str, options: GenerationOptions) -> str:
        """Generate cache key for prompt optimization"""
        content = f"{prompt}|{options.framework.value}|{options.quality.value}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def _track_optimization_performance(self, original: ModelRequest, optimized: ModelRequest):
        """Track optimization performance metrics"""
        original_length = len(original.text_prompt or "")
        optimized_length = len(optimized.text_prompt or "")
        
        if original_length > 0:
            compression_ratio = (original_length - optimized_length) / original_length
            self._performance_stats['compression_ratios'].append(compression_ratio)
        
        # Keep only recent stats
        if len(self._performance_stats['compression_ratios']) > 100:
            self._performance_stats['compression_ratios'] = \
                self._performance_stats['compression_ratios'][-50:]


class ResponseOptimizer:
    """Optimize AI model responses for better performance and user experience"""
    
    def __init__(self, config: OptimizationConfig, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self._response_cache: Dict[str, ModelResponse] = {}
        self._optimization_stats = OptimizationMetrics()
    
    async def optimize_response(self, response: ModelResponse, 
                              original_request: ModelRequest) -> ModelResponse:
        """Optimize response for better delivery and user experience"""
        if not self.config.enable_response_optimization:
            return response
        
        try:
            optimized_response = response
            
            # Content optimization
            optimized_response = await self._optimize_content(optimized_response, original_request)
            
            # Code structure optimization
            optimized_response = await self._optimize_code_structure(optimized_response)
            
            # Metadata optimization
            optimized_response = await self._optimize_metadata(optimized_response)
            
            # Performance suggestions optimization
            optimized_response = await self._optimize_suggestions(optimized_response, original_request)
            
            self.logger.debug("Response optimized successfully",
                            request_id=response.request_id,
                            original_size=len(str(response.__dict__)),
                            optimized_size=len(str(optimized_response.__dict__)))
            
            return optimized_response
        
        except Exception as e:
            self.logger.error("Response optimization failed",
                            error=str(e), request_id=response.request_id)
            return response
    
    async def _optimize_content(self, response: ModelResponse, 
                              original_request: ModelRequest) -> ModelResponse:
        """Optimize generated content"""
        # HTML optimization
        if response.generated_html:
            response.generated_html = await self._optimize_html(
                response.generated_html, original_request.options
            )
        
        # CSS optimization
        if response.generated_css:
            response.generated_css = await self._optimize_css(
                response.generated_css, original_request.options
            )
        
        # JavaScript optimization
        if response.generated_js:
            response.generated_js = await self._optimize_javascript(
                response.generated_js, original_request.options
            )
        
        return response
    
    async def _optimize_html(self, html: str, options: GenerationOptions) -> str:
        """Optimize HTML content"""
        if not html:
            return html
        
        # Remove excessive whitespace but preserve structure
        import re
        
        # Remove comments if not requested
        if not options.include_comments:
            html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # Normalize whitespace
        html = re.sub(r'\s+', ' ', html)
        html = re.sub(r'>\s+<', '><', html)
        
        # Add proper formatting for readability
        html = self._format_html(html)
        
        return html.strip()
    
    async def _optimize_css(self, css: str, options: GenerationOptions) -> str:
        """Optimize CSS content"""
        if not css:
            return css
        
        import re
        
        # Remove comments if not requested
        if not options.include_comments:
            css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
        
        # Remove redundant whitespace
        css = re.sub(r'\s+', ' ', css)
        css = re.sub(r';\s*}', '}', css)
        css = re.sub(r'{\s+', '{', css)
        css = re.sub(r'\s+}', '}', css)
        
        # Optimize property ordering (put layout properties first)
        css = await self._optimize_css_properties(css)
        
        return css.strip()
    
    async def _optimize_javascript(self, js: str, options: GenerationOptions) -> str:
        """Optimize JavaScript content"""
        if not js:
            return js
        
        import re
        
        # Remove comments if not requested
        if not options.include_comments:
            js = re.sub(r'//.*$', '', js, flags=re.MULTILINE)
            js = re.sub(r'/\*.*?\*/', '', js, flags=re.DOTALL)
        
        # Remove excessive whitespace
        js = re.sub(r'\s+', ' ', js)
        
        # Basic formatting for readability
        js = self._format_javascript(js)
        
        return js.strip()
    
    async def _optimize_code_structure(self, response: ModelResponse) -> ModelResponse:
        """Optimize code structure and organization"""
        # Ensure proper separation of concerns
        if response.generated_html and response.generated_css:
            # Make sure CSS is properly separated from HTML
            response.generated_html = self._remove_inline_styles(response.generated_html)
        
        # Ensure proper JavaScript integration
        if response.generated_html and response.generated_js:
            response.generated_html = self._optimize_script_placement(response.generated_html)
        
        return response
    
    async def _optimize_metadata(self, response: ModelResponse) -> ModelResponse:
        """Optimize response metadata"""
        # Clean up detected elements
        if response.detected_elements:
            response.detected_elements = self._deduplicate_elements(response.detected_elements)
        
        # Optimize detected patterns
        if response.detected_patterns:
            response.detected_patterns = list(set(response.detected_patterns))  # Remove duplicates
            response.detected_patterns.sort()  # Sort for consistency
        
        return response
    
    async def _optimize_suggestions(self, response: ModelResponse, 
                                  original_request: ModelRequest) -> ModelResponse:
        """Optimize suggestions for relevance and usefulness"""
        if not response.suggested_improvements:
            return response
        
        # Filter suggestions based on request context
        relevant_suggestions = []
        request_context = self._extract_request_context(original_request)
        
        for suggestion in response.suggested_improvements:
            if self._is_suggestion_relevant(suggestion, request_context):
                relevant_suggestions.append(suggestion)
        
        # Prioritize suggestions
        prioritized_suggestions = self._prioritize_suggestions(relevant_suggestions, request_context)
        
        # Limit to most important suggestions
        response.suggested_improvements = prioritized_suggestions[:5]
        
        return response
    
    def _format_html(self, html: str) -> str:
        """Format HTML for better readability"""
        # Simple formatting - add newlines after closing tags
        import re
        formatted = re.sub(r'(</(div|section|article|header|footer|nav|main)>)', r'\1\n', html)
        return formatted
    
    def _format_javascript(self, js: str) -> str:
        """Format JavaScript for better readability"""
        # Simple formatting - add newlines after statements
        import re
        formatted = re.sub(r'(;|{|})', r'\1\n', js)
        return formatted
    
    async def _optimize_css_properties(self, css: str) -> str:
        """Optimize CSS property ordering"""
        # This is a simplified version - in practice, you'd use a CSS parser
        return css
    
    def _remove_inline_styles(self, html: str) -> str:
        """Remove inline styles from HTML"""
        import re
        return re.sub(r'\s*style="[^"]*"', '', html)
    
    def _optimize_script_placement(self, html: str) -> str:
        """Optimize script tag placement"""
        # Move scripts to bottom if not already there
        import re
        scripts = re.findall(r'<script[^>]*>.*?</script>', html, re.DOTALL)
        html_without_scripts = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        
        if scripts and '</body>' in html_without_scripts:
            return html_without_scripts.replace('</body>', f"{''.join(scripts)}\n</body>")
        
        return html
    
    def _deduplicate_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate elements"""
        seen = set()
        unique_elements = []
        
        for element in elements:
            element_key = f"{element.get('tag', '')}_{element.get('position', 0)}"
            if element_key not in seen:
                seen.add(element_key)
                unique_elements.append(element)
        
        return unique_elements
    
    def _extract_request_context(self, request: ModelRequest) -> Dict[str, Any]:
        """Extract context from request for suggestion filtering"""
        return {
            'framework': request.options.framework.value,
            'quality': request.options.quality.value,
            'responsive': request.options.responsive_design,
            'accessibility': request.options.accessibility_features,
            'typescript': request.options.use_typescript,
            'scss': request.options.use_scss,
            'has_image': request.has_image,
            'has_text': request.has_text
        }
    
    def _is_suggestion_relevant(self, suggestion: str, context: Dict[str, Any]) -> bool:
        """Check if suggestion is relevant to request context"""
        suggestion_lower = suggestion.lower()
        
        # Framework relevance
        if context['framework'] != 'html':
            if context['framework'].lower() not in suggestion_lower and 'html' in suggestion_lower:
                return False
        
        # Feature relevance
        if not context['responsive'] and 'responsive' in suggestion_lower:
            return False
        
        if not context['accessibility'] and 'accessibility' in suggestion_lower:
            return False
        
        if not context['typescript'] and 'typescript' in suggestion_lower:
            return False
        
        return True
    
    def _prioritize_suggestions(self, suggestions: List[str], 
                              context: Dict[str, Any]) -> List[str]:
        """Prioritize suggestions based on importance and context"""
        priority_keywords = {
            'security': 10,
            'performance': 9,
            'accessibility': 8,
            'best practices': 7,
            'optimization': 6,
            'responsive': 5,
            'maintainability': 4
        }
        
        scored_suggestions = []
        for suggestion in suggestions:
            score = 0
            suggestion_lower = suggestion.lower()
            
            for keyword, points in priority_keywords.items():
                if keyword in suggestion_lower:
                    score += points
            
            scored_suggestions.append((score, suggestion))
        
        # Sort by score (descending) and return suggestions
        scored_suggestions.sort(key=lambda x: x[0], reverse=True)
        return [suggestion for _, suggestion in scored_suggestions]


class CacheOptimizer:
    """Advanced caching optimization for AI responses"""
    
    def __init__(self, config: OptimizationConfig, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self._cache: Dict[str, Tuple[ModelResponse, datetime]] = {}
        self._cache_stats = OptimizationMetrics()
        self._access_counts: Dict[str, int] = defaultdict(int)
        self._cache_sizes: Dict[str, int] = {}
    
    async def get_cached_response(self, request: ModelRequest) -> Optional[ModelResponse]:
        """Get cached response if available"""
        if not self.config.enable_caching:
            return None
        
        cache_key = await self._generate_cache_key(request)
        
        if cache_key in self._cache:
            cached_response, cached_time = self._cache[cache_key]
            
            # Check if cache is still valid
            age = (datetime.now(timezone.utc) - cached_time).total_seconds()
            if age < self.config.cache_ttl_seconds:
                # Update access count
                self._access_counts[cache_key] += 1
                
                # Update metrics
                self._cache_stats.update_cache_metrics(hit=True)
                
                # Clone response with new request ID
                cached_response.request_id = request.request_id
                
                self.logger.debug("Cache hit",
                                request_id=request.request_id,
                                cache_key=cache_key[:8],
                                age_seconds=int(age))
                
                return cached_response
            else:
                # Remove expired entry
                await self._remove_cache_entry(cache_key)
        
        # Update metrics for cache miss
        self._cache_stats.update_cache_metrics(hit=False)
        return None
    
    async def cache_response(self, request: ModelRequest, response: ModelResponse):
        """Cache response for future use"""
        if not self.config.enable_caching or not response.success:
            return
        
        cache_key = await self._generate_cache_key(request)
        
        # Optimize response for caching
        cached_response = await self._prepare_for_caching(response)
        
        # Check cache size limits
        await self._enforce_cache_limits()
        
        # Store in cache
        self._cache[cache_key] = (cached_response, datetime.now(timezone.utc))
        self._cache_sizes[cache_key] = len(str(cached_response.__dict__))
        
        self.logger.debug("Response cached",
                        request_id=request.request_id,
                        cache_key=cache_key[:8],
                        response_size=self._cache_sizes[cache_key])
    
    async def _generate_cache_key(self, request: ModelRequest) -> str:
        """Generate cache key for request"""
        # Include all relevant request parameters
        key_components = [
            request.text_prompt or "",
            request.image_data or "",
            request.options.framework.value,
            request.options.quality.value,
            str(request.options.responsive_design),
            str(request.options.accessibility_features),
            str(request.options.use_typescript),
            str(request.options.use_scss),
            str(request.options.include_comments),
            str(request.options.optimization_level)
        ]
        
        combined = "|".join(key_components)
        
        # Use MD5 for consistent, reasonably short keys
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def _prepare_for_caching(self, response: ModelResponse) -> ModelResponse:
        """Prepare response for caching (compression, etc.)"""
        cached_response = response
        
        if self.config.cache_compression:
            # Apply compression to large text fields
            if cached_response.generated_html and len(cached_response.generated_html) > 1000:
                cached_response.generated_html = await self._compress_content(
                    cached_response.generated_html
                )
            
            if cached_response.generated_css and len(cached_response.generated_css) > 500:
                cached_response.generated_css = await self._compress_content(
                    cached_response.generated_css
                )
            
            if cached_response.generated_js and len(cached_response.generated_js) > 500:
                cached_response.generated_js = await self._compress_content(
                    cached_response.generated_js
                )
        
        return cached_response
    
    async def _compress_content(self, content: str) -> str:
        """Compress content for storage"""
        # Simple compression - remove excessive whitespace
        import re
        compressed = re.sub(r'\s+', ' ', content)
        return compressed.strip()
    
    async def _enforce_cache_limits(self):
        """Enforce cache size and entry limits"""
        # Remove entries if over limit
        if len(self._cache) >= self.config.max_cache_entries:
            # Remove least recently used entries
            await self._remove_lru_entries(self.config.max_cache_entries // 4)
    
    async def _remove_lru_entries(self, count: int):
        """Remove least recently used cache entries"""
        # Sort by access count (ascending) and age (descending)
        entries_by_usage = [
            (self._access_counts.get(key, 0), cached_time, key)
            for key, (_, cached_time) in self._cache.items()
        ]
        entries_by_usage.sort(key=lambda x: (x[0], -x[1].timestamp()))
        
        # Remove the least used entries
        for _, _, key in entries_by_usage[:count]:
            await self._remove_cache_entry(key)
    
    async def _remove_cache_entry(self, cache_key: str):
        """Remove cache entry and cleanup"""
        if cache_key in self._cache:
            del self._cache[cache_key]
        if cache_key in self._access_counts:
            del self._access_counts[cache_key]
        if cache_key in self._cache_sizes:
            del self._cache_sizes[cache_key]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_size = sum(self._cache_sizes.values())
        return {
            "total_entries": len(self._cache),
            "total_size_bytes": total_size,
            "hit_rate": self._cache_stats.cache_hit_rate,
            "total_requests": self._cache_stats.total_requests,
            "cached_requests": self._cache_stats.cached_requests
        }


class BatchOptimizer:
    """Batch processing optimization for multiple requests"""
    
    def __init__(self, config: OptimizationConfig, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self._pending_requests: List[Tuple[ModelRequest, asyncio.Future]] = []
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
    
    async def add_request(self, request: ModelRequest) -> ModelResponse:
        """Add request to batch processing queue"""
        if not self.config.enable_batch_processing:
            # Process immediately if batching disabled
            return await self._process_single_request(request)
        
        # Create future for result
        result_future = asyncio.Future()
        
        async with self._batch_lock:
            self._pending_requests.append((request, result_future))
            
            # Start batch processing if not already running
            if self._batch_task is None or self._batch_task.done():
                self._batch_task = asyncio.create_task(self._process_batch())
        
        # Wait for result
        return await result_future
    
    async def _process_batch(self):
        """Process batch of requests"""
        try:
            # Wait for batch to fill up or timeout
            await asyncio.sleep(self.config.batch_timeout_seconds)
            
            async with self._batch_lock:
                if not self._pending_requests:
                    return
                
                # Get current batch
                current_batch = self._pending_requests[:]
                self._pending_requests.clear()
            
            self.logger.debug("Processing batch",
                            batch_size=len(current_batch))
            
            # Process batch
            await self._execute_batch(current_batch)
            
        except Exception as e:
            self.logger.error("Batch processing failed", error=str(e))
            
            # Fail all pending requests
            async with self._batch_lock:
                for _, future in self._pending_requests:
                    if not future.done():
                        future.set_exception(e)
                self._pending_requests.clear()
    
    async def _execute_batch(self, batch: List[Tuple[ModelRequest, asyncio.Future]]):
        """Execute batch of requests"""
        # Group similar requests for optimization
        grouped_requests = await self._group_similar_requests(batch)
        
        # Process each group
        for group in grouped_requests:
            await self._process_request_group(group)
    
    async def _group_similar_requests(self, batch: List[Tuple[ModelRequest, asyncio.Future]]) -> List[List[Tuple[ModelRequest, asyncio.Future]]]:
        """Group similar requests for batch optimization"""
        groups = defaultdict(list)
        
        for request, future in batch:
            # Group by framework and basic options
            group_key = (
                request.options.framework,
                request.options.quality,
                request.options.responsive_design,
                request.options.accessibility_features
            )
            groups[group_key].append((request, future))
        
        return list(groups.values())
    
    async def _process_request_group(self, group: List[Tuple[ModelRequest, asyncio.Future]]):
        """Process a group of similar requests"""
        try:
            # Process requests in parallel within the group
            tasks = []
            for request, future in group:
                task = asyncio.create_task(self._process_single_request(request))
                tasks.append((task, future))
            
            # Wait for all tasks to complete
            for task, future in tasks:
                try:
                    result = await task
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
        
        except Exception as e:
            # Fail all requests in group
            for _, future in group:
                if not future.done():
                    future.set_exception(e)
    
    async def _process_single_request(self, request: ModelRequest) -> ModelResponse:
        """Process single request (placeholder - would integrate with actual processing)"""
        # This would integrate with the actual AI model processing pipeline
        # For now, return a placeholder response
        return ModelResponse(
            request_id=request.request_id,
            model_id="placeholder",
            success=True,
            generated_code="// Placeholder response"
        )


class ModelOptimizer:
    """Main optimizer coordinating all optimization strategies"""
    
    def __init__(self, config: Optional[OptimizationConfig] = None,
                 logger: Optional[StructuredLogger] = None):
        self.config = config or OptimizationConfig()
        self.logger = logger or StructuredLogger()
        
        # Initialize optimizers
        self.prompt_optimizer = PromptOptimizer(self.config, self.logger)
        self.response_optimizer = ResponseOptimizer(self.config, self.logger)
        self.cache_optimizer = CacheOptimizer(self.config, self.logger)
        self.batch_optimizer = BatchOptimizer(self.config, self.logger)
        
        # Overall metrics
        self.metrics = OptimizationMetrics()
    
    async def optimize_request(self, request: ModelRequest) -> ModelRequest:
        """Optimize request before processing"""
        start_time = time.time()
        
        try:
            # Apply prompt optimization
            optimized_request = await self.prompt_optimizer.optimize_prompt(request)
            
            # Track optimization time
            optimization_time = time.time() - start_time
            self.metrics.update_response_time(optimization_time)
            
            return optimized_request
        
        except Exception as e:
            self.logger.error("Request optimization failed",
                            error=str(e), request_id=request.request_id)
            return request
    
    async def optimize_response(self, response: ModelResponse, 
                              original_request: ModelRequest) -> ModelResponse:
        """Optimize response after processing"""
        try:
            # Apply response optimization
            optimized_response = await self.response_optimizer.optimize_response(
                response, original_request
            )
            
            # Cache optimized response
            await self.cache_optimizer.cache_response(original_request, optimized_response)
            
            return optimized_response
        
        except Exception as e:
            self.logger.error("Response optimization failed",
                            error=str(e), request_id=response.request_id)
            return response
    
    async def process_request_with_optimization(self, request: ModelRequest) -> ModelResponse:
        """Process request with full optimization pipeline"""
        # Check cache first
        cached_response = await self.cache_optimizer.get_cached_response(request)
        if cached_response:
            return cached_response
        
        # Optimize request
        optimized_request = await self.optimize_request(request)
        
        # Process through batch optimizer
        response = await self.batch_optimizer.add_request(optimized_request)
        
        # Optimize response
        optimized_response = await self.optimize_response(response, optimized_request)
        
        return optimized_response
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get comprehensive optimization statistics"""
        return {
            "overall_metrics": self.metrics.__dict__,
            "cache_stats": self.cache_optimizer.get_cache_stats(),
            "prompt_optimization": {
                "enabled": self.config.enable_prompt_optimization,
                "max_length": self.config.max_prompt_length,
                "compression_ratio": self.config.prompt_compression_ratio
            },
            "response_optimization": {
                "enabled": self.config.enable_response_optimization,
                "compression": self.config.response_compression,
                "streaming": self.config.enable_streaming_optimization
            },
            "batch_processing": {
                "enabled": self.config.enable_batch_processing,
                "batch_size": self.config.batch_size,
                "timeout_seconds": self.config.batch_timeout_seconds
            }
        }
    
    async def cleanup(self):
        """Cleanup optimizer resources"""
        # Cancel any running batch processing
        if hasattr(self.batch_optimizer, '_batch_task') and self.batch_optimizer._batch_task:
            self.batch_optimizer._batch_task.cancel()
        
        self.logger.info("Model optimizer cleanup completed")
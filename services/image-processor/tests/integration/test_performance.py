"""
Performance and load testing for Image Processor service
Tests service behavior under various load conditions
"""
import pytest
import asyncio
import time
import statistics
import base64
import io
from httpx import AsyncClient
from unittest.mock import patch
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

from app.main import create_application

class TestPerformance:
    """Performance testing suite for Image Processor service"""
    
    @pytest.fixture
    def app(self):
        """Create test application"""
        return create_application()
    
    @pytest.fixture
    async def client(self, app):
        """Create async HTTP client"""
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            yield client
    
    @pytest.fixture
    def mock_auth(self):
        """Mock authentication for testing"""
        mock_user = {
            "id": "test-user-id",
            "email": "test@example.com",
            "name": "Test User",
            "roles": ["user"]
        }
        
        with patch("shared.auth.azure_ad.get_current_user", return_value=mock_user):
            yield mock_user
    
    def create_test_image(self, width: int, height: int, format: str = "PNG") -> str:
        """Create test image data URL"""
        img = Image.new('RGB', (width, height), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        image_bytes = buffer.getvalue()
        
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/{format.lower()};base64,{image_base64}"
    
    def calculate_statistics(self, times: list) -> dict:
        """Calculate performance statistics"""
        if not times:
            return {}
        
        return {
            "count": len(times),
            "min": min(times),
            "max": max(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "p95": statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times),
            "p99": statistics.quantiles(times, n=100)[98] if len(times) >= 100 else max(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0
        }
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_single_image_processing_performance(self, client: AsyncClient, mock_auth):
        """Test single image processing performance across different sizes"""
        
        test_cases = [
            {"size": (100, 100), "name": "tiny"},
            {"size": (500, 400), "name": "small"},
            {"size": (1000, 800), "name": "medium"},
            {"size": (2000, 1500), "name": "large"}
        ]
        
        results = {}
        
        for case in test_cases:
            width, height = case["size"]
            image_data_url = self.create_test_image(width, height)
            
            # Warm up
            await client.post(
                "/api/v1/process",
                json={"image": image_data_url, "provider": "claude"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            # Measure processing times
            times = []
            for _ in range(10):  # 10 iterations for statistical significance
                start_time = time.time()
                
                response = await client.post(
                    "/api/v1/process",
                    json={"image": image_data_url, "provider": "claude"},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                end_time = time.time()
                request_time = (end_time - start_time) * 1000  # Convert to ms
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                
                times.append(request_time)
            
            results[case["name"]] = {
                "size": case["size"],
                "stats": self.calculate_statistics(times)
            }
        
        # Print results
        print("\n=== Single Image Processing Performance ===")
        for name, result in results.items():
            stats = result["stats"]
            size = result["size"]
            print(f"{name} ({size[0]}x{size[1]}): "
                  f"mean={stats['mean']:.1f}ms, "
                  f"p95={stats['p95']:.1f}ms, "
                  f"max={stats['max']:.1f}ms")
        
        # Performance assertions
        assert results["tiny"]["stats"]["mean"] < 1000, "Tiny images should process under 1s"
        assert results["small"]["stats"]["mean"] < 2000, "Small images should process under 2s"
        assert results["medium"]["stats"]["mean"] < 5000, "Medium images should process under 5s"
        assert results["large"]["stats"]["p95"] < 10000, "Large images P95 should be under 10s"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_processing_performance(self, client: AsyncClient, mock_auth):
        """Test concurrent processing performance"""
        
        image_data_url = self.create_test_image(800, 600)
        
        async def process_single_image():
            start_time = time.time()
            response = await client.post(
                "/api/v1/process",
                json={"image": image_data_url, "provider": "claude"},
                headers={"Authorization": "Bearer test-token"}
            )
            end_time = time.time()
            
            return {
                "success": response.status_code == 200,
                "time": (end_time - start_time) * 1000,
                "data": response.json() if response.status_code == 200 else None
            }
        
        # Test different concurrency levels
        concurrency_levels = [1, 3, 5, 10]
        results = {}
        
        for concurrency in concurrency_levels:
            print(f"\nTesting concurrency level: {concurrency}")
            
            # Create tasks
            tasks = [process_single_image() for _ in range(concurrency)]
            
            # Measure total time
            start_time = time.time()
            responses = await asyncio.gather(*tasks)
            end_time = time.time()
            
            total_time = (end_time - start_time) * 1000
            successful_requests = sum(1 for r in responses if r["success"])
            processing_times = [r["time"] for r in responses if r["success"]]
            
            results[concurrency] = {
                "total_time": total_time,
                "successful_requests": successful_requests,
                "success_rate": successful_requests / concurrency,
                "throughput": successful_requests / (total_time / 1000),  # requests per second
                "processing_stats": self.calculate_statistics(processing_times)
            }
        
        # Print results
        print("\n=== Concurrent Processing Performance ===")
        for concurrency, result in results.items():
            print(f"Concurrency {concurrency}: "
                  f"success_rate={result['success_rate']:.2%}, "
                  f"throughput={result['throughput']:.1f} req/s, "
                  f"mean_time={result['processing_stats']['mean']:.1f}ms")
        
        # Performance assertions
        for concurrency, result in results.items():
            assert result["success_rate"] >= 0.9, f"Success rate should be >= 90% for concurrency {concurrency}"
            assert result["throughput"] > 0.1, f"Throughput should be > 0.1 req/s for concurrency {concurrency}"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_usage_performance(self, client: AsyncClient, mock_auth):
        """Test memory usage during image processing"""
        
        # Create progressively larger images
        test_sizes = [
            (500, 400),    # Small
            (1000, 800),   # Medium
            (1500, 1200),  # Large
            (2000, 1600)   # Very large
        ]
        
        results = {}
        
        for width, height in test_sizes:
            size_name = f"{width}x{height}"
            image_data_url = self.create_test_image(width, height)
            
            # Process image and measure
            response = await client.post(
                "/api/v1/process",
                json={"image": image_data_url, "provider": "claude"},
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Calculate memory efficiency metrics
            original_size = data["original_size"]
            processed_size = data["processed_size"]
            compression_ratio = data["compression_ratio"]
            
            results[size_name] = {
                "original_size_mb": original_size / (1024 * 1024),
                "processed_size_mb": processed_size / (1024 * 1024),
                "compression_ratio": compression_ratio,
                "processing_time": data["processing_time_ms"],
                "efficiency": compression_ratio / (data["processing_time_ms"] / 1000)  # compression per second
            }
        
        # Print results
        print("\n=== Memory Usage Performance ===")
        for size_name, result in results.items():
            print(f"{size_name}: "
                  f"original={result['original_size_mb']:.1f}MB, "
                  f"processed={result['processed_size_mb']:.1f}MB, "
                  f"compression={result['compression_ratio']:.3f}, "
                  f"efficiency={result['efficiency']:.3f}")
        
        # Performance assertions
        for size_name, result in results.items():
            assert result["compression_ratio"] > 0.1, f"Should achieve compression for {size_name}"
            assert result["efficiency"] > 0.001, f"Should have reasonable efficiency for {size_name}"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_provider_performance_comparison(self, client: AsyncClient, mock_auth):
        """Compare performance across different providers"""
        
        image_data_url = self.create_test_image(1000, 800)
        providers = ["claude", "openai", "gemini"]
        
        results = {}
        
        for provider in providers:
            # Validate if provider supports this image
            validate_response = await client.post(
                "/api/v1/validate",
                json={"image": image_data_url, "provider": provider},
                headers={"Authorization": "Bearer test-token"}
            )
            
            validation = validate_response.json()
            
            if not validation["valid"]:
                results[provider] = {"status": "unsupported", "reason": validation["error_message"]}
                continue
            
            # Measure processing performance
            times = []
            compression_ratios = []
            
            for _ in range(5):  # 5 iterations
                start_time = time.time()
                
                response = await client.post(
                    "/api/v1/process",
                    json={"image": image_data_url, "provider": provider},
                    headers={"Authorization": "Bearer test-token"}
                )
                
                end_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    times.append((end_time - start_time) * 1000)
                    compression_ratios.append(data["compression_ratio"])
                else:
                    times.append(float('inf'))  # Mark as failed
            
            # Calculate statistics
            valid_times = [t for t in times if t != float('inf')]
            
            if valid_times:
                results[provider] = {
                    "status": "supported",
                    "processing_stats": self.calculate_statistics(valid_times),
                    "compression_stats": self.calculate_statistics(compression_ratios),
                    "success_rate": len(valid_times) / len(times)
                }
            else:
                results[provider] = {"status": "failed", "reason": "All processing attempts failed"}
        
        # Print comparison
        print("\n=== Provider Performance Comparison ===")
        for provider, result in results.items():
            if result["status"] == "supported":
                proc_stats = result["processing_stats"]
                comp_stats = result["compression_stats"]
                print(f"{provider}: "
                      f"time={proc_stats['mean']:.1f}ms, "
                      f"compression={comp_stats['mean']:.3f}, "
                      f"success_rate={result['success_rate']:.2%}")
            else:
                print(f"{provider}: {result['status']} - {result.get('reason', '')}")
        
        # Verify at least one provider works well
        supported_providers = [p for p, r in results.items() if r["status"] == "supported"]
        assert len(supported_providers) > 0, "At least one provider should be supported"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_api_endpoint_performance(self, client: AsyncClient, mock_auth):
        """Test performance of different API endpoints"""
        
        image_data_url = self.create_test_image(800, 600)
        
        endpoints = [
            {
                "name": "validate",
                "method": "POST",
                "url": "/api/v1/validate",
                "payload": {"image": image_data_url, "provider": "claude"}
            },
            {
                "name": "analyze",
                "method": "POST", 
                "url": "/api/v1/analyze",
                "payload": {"image": image_data_url}
            },
            {
                "name": "process",
                "method": "POST",
                "url": "/api/v1/process", 
                "payload": {"image": image_data_url, "provider": "claude"}
            },
            {
                "name": "thumbnail",
                "method": "POST",
                "url": "/api/v1/thumbnail",
                "payload": {"image": image_data_url, "width": 150, "height": 150}
            },
            {
                "name": "providers",
                "method": "GET",
                "url": "/api/v1/providers",
                "payload": None
            }
        ]
        
        results = {}
        
        for endpoint in endpoints:
            times = []
            
            for _ in range(10):  # 10 iterations
                start_time = time.time()
                
                if endpoint["method"] == "GET":
                    response = await client.get(
                        endpoint["url"],
                        headers={"Authorization": "Bearer test-token"}
                    )
                else:
                    response = await client.post(
                        endpoint["url"],
                        json=endpoint["payload"],
                        headers={"Authorization": "Bearer test-token"}
                    )
                
                end_time = time.time()
                
                if response.status_code == 200:
                    times.append((end_time - start_time) * 1000)
                
            results[endpoint["name"]] = {
                "stats": self.calculate_statistics(times),
                "success_count": len(times)
            }
        
        # Print results
        print("\n=== API Endpoint Performance ===")
        for endpoint_name, result in results.items():
            stats = result["stats"]
            print(f"{endpoint_name}: "
                  f"mean={stats['mean']:.1f}ms, "
                  f"p95={stats['p95']:.1f}ms, "
                  f"success={result['success_count']}/10")
        
        # Performance assertions
        assert results["validate"]["stats"]["mean"] < 2000, "Validation should be under 2s"
        assert results["analyze"]["stats"]["mean"] < 3000, "Analysis should be under 3s"
        assert results["process"]["stats"]["mean"] < 5000, "Processing should be under 5s"
        assert results["thumbnail"]["stats"]["mean"] < 2000, "Thumbnail should be under 2s"
        assert results["providers"]["stats"]["mean"] < 500, "Provider info should be under 0.5s"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_health_endpoints_performance(self, client: AsyncClient):
        """Test health endpoint performance"""
        
        health_endpoints = [
            "/health",
            "/health/ready", 
            "/health/live",
            "/health/capabilities"
        ]
        
        results = {}
        
        for endpoint in health_endpoints:
            times = []
            
            for _ in range(20):  # More iterations for health endpoints
                start_time = time.time()
                response = await client.get(endpoint)
                end_time = time.time()
                
                if response.status_code == 200:
                    times.append((end_time - start_time) * 1000)
            
            results[endpoint] = self.calculate_statistics(times)
        
        # Print results
        print("\n=== Health Endpoint Performance ===")
        for endpoint, stats in results.items():
            print(f"{endpoint}: "
                  f"mean={stats['mean']:.1f}ms, "
                  f"p95={stats['p95']:.1f}ms, "
                  f"max={stats['max']:.1f}ms")
        
        # Health endpoints should be very fast
        for endpoint, stats in results.items():
            assert stats["mean"] < 100, f"Health endpoint {endpoint} should respond under 100ms"
            assert stats["p95"] < 200, f"Health endpoint {endpoint} P95 should be under 200ms"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_load_testing(self, client: AsyncClient, mock_auth):
        """Load testing with sustained traffic"""
        
        image_data_url = self.create_test_image(600, 400)
        
        # Configuration
        duration_seconds = 30
        target_rps = 5  # requests per second
        
        async def make_request():
            try:
                start_time = time.time()
                response = await client.post(
                    "/api/v1/process",
                    json={"image": image_data_url, "provider": "claude"},
                    headers={"Authorization": "Bearer test-token"}
                )
                end_time = time.time()
                
                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "response_time": (end_time - start_time) * 1000,
                    "timestamp": end_time
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "timestamp": time.time()
                }
        
        # Generate load
        print(f"\nStarting load test: {target_rps} RPS for {duration_seconds}s")
        start_time = time.time()
        results = []
        
        while time.time() - start_time < duration_seconds:
            # Schedule requests for this second
            tasks = []
            for _ in range(target_rps):
                tasks.append(make_request())
            
            # Execute requests
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend([r for r in responses if isinstance(r, dict)])
            
            # Wait for next second
            next_second = start_time + len(results) // target_rps + 1
            sleep_time = max(0, next_second - time.time())
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        # Analyze results
        successful_requests = [r for r in results if r.get("success")]
        failed_requests = [r for r in results if not r.get("success")]
        
        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            stats = self.calculate_statistics(response_times)
            
            print(f"\n=== Load Test Results ===")
            print(f"Total requests: {len(results)}")
            print(f"Successful: {len(successful_requests)} ({len(successful_requests)/len(results):.1%})")
            print(f"Failed: {len(failed_requests)} ({len(failed_requests)/len(results):.1%})")
            print(f"Average response time: {stats['mean']:.1f}ms")
            print(f"P95 response time: {stats['p95']:.1f}ms")
            print(f"Actual RPS: {len(results)/duration_seconds:.1f}")
            
            # Performance assertions
            success_rate = len(successful_requests) / len(results)
            assert success_rate >= 0.95, f"Success rate should be >= 95%, got {success_rate:.1%}"
            assert stats["p95"] < 10000, f"P95 response time should be under 10s, got {stats['p95']:.1f}ms"
        else:
            pytest.fail("No successful requests during load test")
    
    @pytest.mark.performance
    @pytest.mark.asyncio 
    async def test_stress_testing(self, client: AsyncClient, mock_auth):
        """Stress testing with high concurrency"""
        
        image_data_url = self.create_test_image(400, 300)
        
        # Gradually increase load
        concurrency_levels = [5, 10, 20, 30]
        results = {}
        
        for concurrency in concurrency_levels:
            print(f"\nStress testing with {concurrency} concurrent requests")
            
            async def stress_request():
                try:
                    start_time = time.time()
                    response = await client.post(
                        "/api/v1/process",
                        json={"image": image_data_url, "provider": "claude"},
                        headers={"Authorization": "Bearer test-token"}
                    )
                    end_time = time.time()
                    
                    return {
                        "success": response.status_code == 200,
                        "response_time": (end_time - start_time) * 1000,
                        "status_code": response.status_code
                    }
                except Exception as e:
                    return {"success": False, "error": str(e)}
            
            # Execute stress test
            tasks = [stress_request() for _ in range(concurrency)]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            valid_responses = [r for r in responses if isinstance(r, dict)]
            successful = [r for r in valid_responses if r.get("success")]
            
            if successful:
                response_times = [r["response_time"] for r in successful]
                stats = self.calculate_statistics(response_times)
                
                results[concurrency] = {
                    "success_rate": len(successful) / len(valid_responses),
                    "response_time_stats": stats,
                    "total_requests": len(valid_responses)
                }
            else:
                results[concurrency] = {
                    "success_rate": 0,
                    "total_requests": len(valid_responses),
                    "error": "No successful requests"
                }
        
        # Print stress test results
        print("\n=== Stress Test Results ===")
        for concurrency, result in results.items():
            if "response_time_stats" in result:
                stats = result["response_time_stats"]
                print(f"Concurrency {concurrency}: "
                      f"success_rate={result['success_rate']:.1%}, "
                      f"mean_time={stats['mean']:.1f}ms, "
                      f"p95_time={stats['p95']:.1f}ms")
            else:
                print(f"Concurrency {concurrency}: {result.get('error', 'Failed')}")
        
        # Find breaking point
        successful_levels = [c for c, r in results.items() if r["success_rate"] >= 0.8]
        if successful_levels:
            max_successful_concurrency = max(successful_levels)
            print(f"Maximum stable concurrency: {max_successful_concurrency}")
            assert max_successful_concurrency >= 5, "Should handle at least 5 concurrent requests"
        else:
            pytest.fail("Service failed at all concurrency levels")
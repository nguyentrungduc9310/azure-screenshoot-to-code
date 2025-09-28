# Makefile for Image Processor service testing and development

.PHONY: help install test test-unit test-integration test-e2e test-performance test-security test-compatibility test-all test-smoke clean coverage lint format docker-test

# Default target
help:
	@echo "Image Processor Service - Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install all dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-e2e         Run end-to-end tests only"
	@echo "  test-performance Run performance tests only"
	@echo "  test-security    Run security tests only"
	@echo "  test-compatibility Run provider compatibility tests only"
	@echo "  test-smoke       Run quick smoke tests"
	@echo "  coverage         Generate coverage report"
	@echo ""
	@echo "Quality:"
	@echo "  lint             Run linting checks"
	@echo "  format           Format code with black"
	@echo "  type-check       Run type checking with mypy"
	@echo "  security-scan    Run security scanning"
	@echo ""
	@echo "Development:"
	@echo "  dev              Start development server"
	@echo "  clean            Clean temporary files"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build     Build Docker image"
	@echo "  docker-test      Run tests in Docker container"
	@echo "  docker-dev       Start development environment with Docker"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r tests/requirements.txt

# Testing commands using test runner
test:
	python tests/test_runner.py all --verbose

test-unit:
	python tests/test_runner.py run unit --verbose

test-integration:
	python tests/test_runner.py run integration --verbose

test-e2e:
	python tests/test_runner.py run e2e --verbose

test-performance:
	python tests/test_runner.py run performance --verbose

test-security:
	python tests/test_runner.py run security --verbose

test-compatibility:
	python tests/test_runner.py run compatibility --verbose

test-smoke:
	python tests/test_runner.py smoke

# Testing with direct pytest
test-direct:
	pytest tests/ -v --tb=short

test-unit-direct:
	pytest tests/unit/ -v --tb=short

test-integration-direct:
	pytest tests/integration/ -v --tb=short

test-fast:
	pytest tests/ -v --tb=short -m "not slow and not performance"

test-parallel:
	pytest tests/ -v --tb=short -n auto

# Coverage
coverage:
	python tests/test_runner.py all --coverage
	@echo "Coverage report generated in htmlcov/index.html"

coverage-xml:
	pytest tests/ --cov=app --cov-report=xml --cov-report=term-missing

coverage-html:
	pytest tests/ --cov=app --cov-report=html:htmlcov --cov-report=term-missing
	@echo "HTML coverage report: htmlcov/index.html"

# Code quality
lint:
	@echo "Running flake8..."
	flake8 app/ tests/ --max-line-length=100 --ignore=E203,W503
	@echo "Running black check..."
	black --check app/ tests/
	@echo "Running isort check..."
	isort --check-only app/ tests/

format:
	@echo "Formatting with black..."
	black app/ tests/
	@echo "Sorting imports with isort..."
	isort app/ tests/

type-check:
	@echo "Running mypy type checking..."
	mypy app/ --ignore-missing-imports

security-scan:
	@echo "Running bandit security scan..."
	bandit -r app/ -f json -o security-report.json
	bandit -r app/ -f txt
	@echo "Running safety check..."
	safety check --json --output safety-report.json
	safety check

# Development
dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

dev-debug:
	uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --log-level debug

# Docker commands
docker-build:
	docker build -t image-processor:latest .

docker-test:
	docker-compose -f docker-compose.yml run --rm image-processor-test

docker-dev:
	docker-compose -f docker-compose.yml up image-processor

docker-clean:
	docker-compose -f docker-compose.yml down -v
	docker system prune -f

# Performance testing
performance-test:
	python tests/test_runner.py run performance --verbose
	@echo "Performance test results available"

load-test:
	@echo "Running load tests with locust..."
	locust -f tests/load_tests.py --host=http://localhost:8001

# Comprehensive testing
test-all-comprehensive:
	@echo "Running comprehensive test suite..."
	python tests/test_runner.py all --verbose --coverage
	make lint
	make type-check
	make security-scan
	@echo "All tests and checks completed!"

# CI/CD pipeline simulation
ci-test:
	@echo "Running CI test pipeline..."
	make install-dev
	make lint
	make type-check
	make test-smoke
	make test-unit
	make test-integration
	make security-scan
	@echo "CI pipeline completed successfully!"

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf dist/
	rm -rf build/
	rm -f security-report.json
	rm -f safety-report.json
	rm -f test_report.html

# Test data generation
generate-test-data:
	python -c "
import base64
from PIL import Image
import io

# Generate test images
sizes = [(100, 100), (800, 600), (1920, 1080), (4000, 3000)]
formats = ['PNG', 'JPEG']

for width, height in sizes:
    for fmt in formats:
        img = Image.new('RGB', (width, height), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format=fmt)
        data = base64.b64encode(buffer.getvalue()).decode()
        
        filename = f'test_data/{width}x{height}_{fmt.lower()}.txt'
        with open(filename, 'w') as f:
            f.write(f'data:image/{fmt.lower()};base64,{data}')
        
        print(f'Generated: {filename}')
"

# Documentation
docs-serve:
	@echo "API documentation available at:"
	@echo "  OpenAPI spec: docs/api/openapi.yaml"
	@echo "  API reference: docs/api/image-processor-api.md"
	@echo "  Integration guide: docs/integration/image-processor-integration.md"

# Health checks
health-check:
	@echo "Checking service health..."
	curl -f http://localhost:8001/health || echo "Service not running"
	curl -f http://localhost:8001/health/ready || echo "Service not ready"

# Monitoring
monitor:
	@echo "Monitoring endpoints:"
	@echo "Health: http://localhost:8001/health"
	@echo "Metrics: http://localhost:8001/health/metrics (requires auth)"
	@echo "Capabilities: http://localhost:8001/health/capabilities"

# Environment setup
setup-env:
	@echo "Setting up development environment..."
	python -m venv venv
	@echo "Activate virtual environment with: source venv/bin/activate"
	@echo "Then run: make install-dev"

# Quick development cycle
dev-cycle: clean lint test-smoke
	@echo "Development cycle completed!"

# Production readiness check
prod-check:
	@echo "Running production readiness checks..."
	make test-all-comprehensive
	make security-scan
	@echo "Production readiness check completed!"
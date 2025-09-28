"""
Mock Logger for Security Scanning
Simple logger implementation for standalone security scanning
"""
import logging
from datetime import datetime
from typing import Any


class MockStructuredLogger:
    """Mock structured logger for security scanning when shared logger is not available"""
    
    def __init__(self, service_name: str = "security-scanner", environment: str = "development", log_level: str = "INFO"):
        self.service_name = service_name
        self.environment = environment
        
        # Set up basic logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(service_name)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        if kwargs:
            extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            self.logger.info(f"{message} | {extra_info}")
        else:
            self.logger.info(message)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        if kwargs:
            extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            self.logger.warning(f"{message} | {extra_info}")
        else:
            self.logger.warning(message)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        if kwargs:
            extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            self.logger.error(f"{message} | {extra_info}")
        else:
            self.logger.error(message)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        if kwargs:
            extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            self.logger.debug(f"{message} | {extra_info}")
        else:
            self.logger.debug(message)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        return datetime.utcnow().isoformat()


def get_logger(service_name: str = "security-scanner", environment: str = "development", log_level: str = "INFO"):
    """Get a logger instance"""
    try:
        from shared.monitoring.structured_logger import StructuredLogger
        return StructuredLogger(service_name, environment, log_level)
    except ImportError:
        return MockStructuredLogger(service_name, environment, log_level)
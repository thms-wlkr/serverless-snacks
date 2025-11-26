"""Shared pytest fixtures and utilities."""
from dataclasses import dataclass


@dataclass
class LambdaContext:
    """Mock Lambda context for testing."""
    function_name: str = "test-function"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:test"
    aws_request_id: str = "test-request-id"

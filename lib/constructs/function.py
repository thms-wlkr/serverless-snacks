"""
Reusable Python Lambda function construct.
Provides consistent configuration for all Lambda functions in the application.
"""
from typing import Optional, Dict

from aws_cdk import (
    Duration,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_logs as logs,
)
from constructs import Construct


class PythonFunction(lambda_.Function):
    """
    Custom Lambda function construct with defaults.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        handler_path: str,
        environment: Optional[Dict[str, str]] = None,
        timeout: Optional[Duration] = None,
        memory_size: Optional[int] = None,
        **kwargs
    ) -> None:
        # Create log group with retention policy
        log_group = logs.LogGroup(
            scope,
            f"{construct_id}LogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # CDK auto-generates based on stack and construct_id
        # Production: could add explicit function name for identification
        super().__init__(
            scope,
            construct_id,
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(handler_path),
            timeout=timeout or Duration.seconds(30),
            memory_size=memory_size or 256,
            environment=environment or {},
            log_group=log_group,
            retry_attempts=2,
            **kwargs
        )

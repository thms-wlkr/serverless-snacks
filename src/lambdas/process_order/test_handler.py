"""Unit tests for process_order Lambda handler."""
import json
import os
from datetime import datetime, UTC
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

from tests.conftest import LambdaContext


# Pytest fixtures run before each test that uses them (similar to beforeEach in TypeScript)
@pytest.fixture
def aws_environment():
    """Fixture to set up mocked AWS environment"""
    with mock_aws():
        # Create DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
        table = dynamodb.create_table(
            TableName="test-orders-table",
            KeySchema=[{"AttributeName": "orderId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "orderId", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Set environment variables
        os.environ["TABLE_NAME"] = "test-orders-table"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
        os.environ["POWERTOOLS_SERVICE_NAME"] = "serverless-snacks"
        os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "ServerlessSnacks"

        yield {
            "table": table,
            "dynamodb": dynamodb,
        }


def test_process_order_success(aws_environment):
    """Test processing an order successfully"""
    from .handler import lambda_handler

    # First, create an order in DynamoDB
    table = aws_environment["table"]
    order_id = "test-order-123"
    table.put_item(
        Item={
            "orderId": order_id,
            "customerName": "Thomas Walker",
            "status": "NEW",
            "total": Decimal("10.0"),
            "createdAt": datetime.now(UTC).isoformat(),
        }
    )

    # Now process the order via SQS event (which wraps EventBridge event)
    event = {
        "Records": [
            {
                "messageId": "test-message-1",
                "body": json.dumps({
                    "detail-type": "OrderCreated",
                    "source": "serverless.snacks.orders",
                    "detail": {
                        "orderId": order_id,
                        "customerName": "Thomas Walker",
                        "total": 10.0,
                    },
                })
            }
        ]
    }

    response = lambda_handler(event, LambdaContext())

    # Powertools batch processor returns partial failure response
    assert "batchItemFailures" in response
    assert len(response["batchItemFailures"]) == 0  # No failures

    # Verify order status was updated in DynamoDB
    db_response = table.get_item(Key={"orderId": order_id})
    assert db_response["Item"]["status"] == "PROCESSED"
    assert "processedAt" in db_response["Item"]


def test_process_order_idempotent(aws_environment):
    """Test that processing an already processed order is idempotent"""
    from .handler import lambda_handler

    # Create an order that's already processed
    table = aws_environment["table"]
    order_id = "test-order-456"
    table.put_item(
        Item={
            "orderId": order_id,
            "customerName": "Ollie McCaffery",
            "status": "PROCESSED",  # Already processed
            "total": Decimal("15.0"),
            "createdAt": datetime.now(UTC).isoformat(),
            "processedAt": datetime.now(UTC).isoformat(),
        }
    )

    event = {
        "Records": [
            {
                "messageId": "test-message-2",
                "body": json.dumps({
                    "detail-type": "OrderCreated",
                    "source": "serverless.snacks.orders",
                    "detail": {
                        "orderId": order_id,
                        "customerName": "Ollie McCaffery",
                        "total": 15.0,
                    },
                })
            }
        ]
    }

    response = lambda_handler(event, LambdaContext())

    # Powertools batch processor returns partial failure response
    assert "batchItemFailures" in response
    assert len(response["batchItemFailures"]) == 0  # No failures


def test_process_order_not_found(aws_environment):
    """Test processing an order that doesn't exist"""
    from .handler import lambda_handler
    from aws_lambda_powertools.utilities.batch.exceptions import BatchProcessingError

    event = {
        "Records": [
            {
                "messageId": "test-message-3",
                "body": json.dumps({
                    "detail-type": "OrderCreated",
                    "source": "serverless.snacks.orders",
                    "detail": {
                        "orderId": "non-existent-order",
                        "customerName": "Ghost Customer",
                        "total": 99.99,
                    },
                })
            }
        ]
    }

    # When entire batch fails, Powertools batch processor raises BatchProcessingError
    with pytest.raises(BatchProcessingError) as exc_info:
        lambda_handler(event, LambdaContext())

    # Verify the exception contains the error about the order not found
    assert "Order non-existent-order not found" in str(exc_info.value)


def test_process_order_updates_status_only(aws_environment):
    """Test that processing only updates status and processedAt, not other fields"""
    from .handler import lambda_handler

    table = aws_environment["table"]
    order_id = "test-order-789"
    original_customer = "Original Customer"
    original_total = Decimal("25.50")

    table.put_item(
        Item={
            "orderId": order_id,
            "customerName": original_customer,
            "status": "NEW",
            "total": original_total,
            "createdAt": datetime.now(UTC).isoformat(),
        }
    )

    event = {
        "Records": [
            {
                "messageId": "test-message-4",
                "body": json.dumps({
                    "detail-type": "OrderCreated",
                    "source": "serverless.snacks.orders",
                    "detail": {
                        "orderId": order_id,
                        "customerName": "Different Customer",  # Different from stored value
                        "total": 99.99,  # Different from stored value
                    },
                })
            }
        ]
    }

    lambda_handler(event, LambdaContext())

    # Verify original data is preserved
    db_response = table.get_item(Key={"orderId": order_id})
    assert db_response["Item"]["customerName"] == original_customer
    assert db_response["Item"]["total"] == original_total
    assert db_response["Item"]["status"] == "PROCESSED"

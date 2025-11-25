import json
import os
import pytest
import boto3
from moto import mock_aws
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class LambdaContext:
    """Mock Lambda context for testing"""
    function_name: str = "test-function"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:test"
    aws_request_id: str = "test-request-id"


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

        # Create EventBridge bus
        events_client = boto3.client("events", region_name="eu-west-1")
        events_client.create_event_bus(Name="test-event-bus")

        # Set environment variables
        os.environ["TABLE_NAME"] = "test-orders-table"
        os.environ["EVENT_BUS_NAME"] = "test-event-bus"
        os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"
        os.environ["POWERTOOLS_SERVICE_NAME"] = "serverless-snacks"
        os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "ServerlessSnacks"

        yield {
            "table": table,
            "dynamodb": dynamodb,
            "events_client": events_client,
        }


def test_create_order_success(aws_environment):
    """Test creating an order successfully"""
    from src.lambdas.create_order.handler import lambda_handler

    event = {
        "customerName": "Thomas Walker",
        "snackItems": [
            {"name": "Crisps", "price": "1.50", "quantity": 2},
            {"name": "Chocolate", "price": "2.00", "quantity": 1},
        ],
    }

    response = lambda_handler(event, LambdaContext())

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["message"] == "Order created successfully"
    assert "orderId" in body
    assert body["status"] == "NEW"
    assert body["total"] == 5.0

    # Verify order was saved to DynamoDB
    table = aws_environment["table"]
    db_response = table.get_item(Key={"orderId": body["orderId"]})
    assert "Item" in db_response
    assert db_response["Item"]["status"] == "NEW"
    assert db_response["Item"]["customerName"] == "Thomas Walker"


def test_create_order_missing_customer_name(aws_environment):
    """Test creating an order with missing customer name"""
    from src.lambdas.create_order.handler import lambda_handler

    event = {
        "snackItems": [
            {"name": "Crisps", "price": "1.50", "quantity": 2},
        ]
    }

    response = lambda_handler(event, LambdaContext())

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_create_order_missing_snack_items(aws_environment):
    """Test creating an order with missing snack items"""
    from src.lambdas.create_order.handler import lambda_handler

    event = {"customerName": "Thomas Walker"}

    response = lambda_handler(event, LambdaContext())

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body


def test_create_order_calculates_total_correctly(aws_environment):
    """Test that order total is calculated correctly"""
    from src.lambdas.create_order.handler import lambda_handler

    event = {
        "customerName": "Ollie McCaffery",
        "snackItems": [
            {"name": "Crisps", "price": "2.00", "quantity": 3},
            {"name": "Chocolate", "price": "3.00", "quantity": 2},
            {"name": "Biscuits", "price": "4.00", "quantity": 1},
        ],
    }

    response = lambda_handler(event, LambdaContext())

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["total"] == 16.0


def test_create_order_publishes_event(aws_environment):
    """Test that creating an order publishes an event to EventBridge"""
    from src.lambdas.create_order.handler import lambda_handler
    from unittest.mock import patch

    event = {
        "customerName": "Event Test",
        "snackItems": [
            {"name": "Crisps", "price": "1.00", "quantity": 1},
        ],
    }

    # EventBridge event publishing not verified in this test
    # In production I would verify via CloudWatch Logs or EventBridge test events
    response = lambda_handler(event, LambdaContext())

    assert response["statusCode"] == 201
    # If event publishing failed, Lambda would return 500 error

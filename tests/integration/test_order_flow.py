"""
Integration tests for deployed Serverless Snacks infrastructure.
Tests the full order processing flow using real AWS resources.

Prerequisites:
- Infrastructure must be deployed: cdk deploy --all
- AWS credentials configured with access to deployed resources
"""
import json
import time
import uuid
import boto3
import pytest


# AWS clients
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")
cloudformation = boto3.client("cloudformation")


@pytest.fixture(scope="module")
def deployed_resources():
    """Get deployed resource names from CloudFormation outputs."""
    # Get DataStack outputs
    data_stack = cloudformation.describe_stacks(
        StackName="ServerlessSnacks-DataStack"
    )
    data_outputs = {
        output["OutputKey"]: output["OutputValue"]
        for output in data_stack["Stacks"][0]["Outputs"]
    }

    # Get AppStack outputs
    app_stack = cloudformation.describe_stacks(
        StackName="ServerlessSnacks-AppStack"
    )
    app_outputs = {
        output["OutputKey"]: output["OutputValue"]
        for output in app_stack["Stacks"][0]["Outputs"]
    }

    return {
        "table_name": data_outputs["OrdersTableName"],
        "create_order_function": app_outputs["CreateOrderFunction"],
    }


def test_create_order_end_to_end(deployed_resources):
    """Test complete order flow from creation to processing."""
    # Create order via Lambda
    order_payload = {
        "customerName": f"Integration Test {uuid.uuid4().hex[:8]}",
        "snackItems": [
            {"name": "Crisps", "price": "2.50", "quantity": 2},
            {"name": "Chocolate", "price": "1.50", "quantity": 1},
        ],
    }

    response = lambda_client.invoke(
        FunctionName=deployed_resources["create_order_function"],
        InvocationType="RequestResponse",
        Payload=json.dumps(order_payload),
    )

    # Parse response
    response_payload = json.loads(response["Payload"].read())
    assert response_payload["statusCode"] == 201

    body = json.loads(response_payload["body"])
    order_id = body["orderId"]
    assert body["status"] == "NEW"
    assert body["total"] == 6.5

    # Verify order in DynamoDB
    table = dynamodb.Table(deployed_resources["table_name"])
    db_response = table.get_item(Key={"orderId": order_id})

    assert "Item" in db_response
    order = db_response["Item"]
    assert order["customerName"] == order_payload["customerName"]
    assert order["status"] == "NEW"
    assert float(order["total"]) == 6.5

    # Wait for EventBridge -> SQS -> Lambda processing
    # Processing typically takes 5-15 seconds
    max_wait = 30
    processed = False

    for _ in range(max_wait):
        time.sleep(1)
        db_response = table.get_item(Key={"orderId": order_id})
        order = db_response["Item"]

        if order["status"] == "PROCESSED":
            processed = True
            assert "processedAt" in order
            break

    assert processed, f"Order not processed after {max_wait} seconds"


def test_create_order_with_multiple_items(deployed_resources):
    """Test order creation with multiple different items."""
    order_payload = {
        "customerName": f"Multi-Item Test {uuid.uuid4().hex[:8]}",
        "snackItems": [
            {"name": "Crisps", "price": "1.00", "quantity": 3},
            {"name": "Chocolate", "price": "2.00", "quantity": 2},
            {"name": "Biscuits", "price": "1.50", "quantity": 1},
        ],
    }

    response = lambda_client.invoke(
        FunctionName=deployed_resources["create_order_function"],
        InvocationType="RequestResponse",
        Payload=json.dumps(order_payload),
    )

    response_payload = json.loads(response["Payload"].read())
    assert response_payload["statusCode"] == 201

    body = json.loads(response_payload["body"])
    # (1.00 * 3) + (2.00 * 2) + (1.50 * 1) = 8.5
    assert body["total"] == 8.5



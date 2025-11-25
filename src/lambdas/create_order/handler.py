"""Lambda function for creating new orders."""
import json
import os
import uuid
from datetime import datetime, UTC
from decimal import Decimal

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit

# X-Ray Tracer could be added for distributed tracing in production
logger = Logger()
metrics = Metrics()

dynamodb = boto3.resource("dynamodb")
events_client = boto3.client("events")

TABLE_NAME = os.environ["TABLE_NAME"]
EVENT_BUS_NAME = os.environ["EVENT_BUS_NAME"]


@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event, context):
    """
    Handle new order creation requests.

    Validates the order, saves it to DynamoDB with NEW status,
    and publishes an OrderCreated event for downstream processing.
    """
    try:
        order_data = json.loads(event) if isinstance(event, str) else event

        logger.info(
            "Received order creation request",
            hasCustomerName="customerName" in order_data,
            hasSnackItems="snackItems" in order_data
        )

        # Validate request
        if "customerName" not in order_data or "snackItems" not in order_data:
            missing_fields = [
                f for f in ["customerName", "snackItems"]
                if f not in order_data
            ]
            logger.error("Missing required fields", missingFields=missing_fields)
            metrics.add_metric(name="ValidationErrors", unit=MetricUnit.Count, value=1)
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Missing required fields: customerName and snackItems"
                })
            }

        order_id = str(uuid.uuid4())
        total = sum(
            Decimal(str(item["price"])) * item["quantity"]
            for item in order_data["snackItems"]
        )

        logger.info(
            "Creating order",
            orderId=order_id,
            customerName=order_data["customerName"],
            itemCount=len(order_data["snackItems"]),
            total=float(total)
        )

        order = {
            "orderId": order_id,
            "customerName": order_data["customerName"],
            "snackItems": order_data["snackItems"],
            "total": total,  # Store as Decimal for DynamoDB
            "status": "NEW",
            "createdAt": datetime.now(UTC).isoformat(),
        }

        # Save to DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        table.put_item(Item=order)

        logger.info("Order saved to DynamoDB", orderId=order_id, tableName=TABLE_NAME)

        # Publish event to EventBridge
        events_client.put_events(
            Entries=[
                {
                    "Source": "serverless.snacks.orders",
                    "DetailType": "OrderCreated",
                    "Detail": json.dumps({
                        "orderId": order_id,
                        "customerName": order_data["customerName"],
                        "total": float(total),
                        "itemCount": len(order_data["snackItems"]),
                    }),
                    "EventBusName": EVENT_BUS_NAME,
                }
            ]
        )

        logger.info(
            "Event published to EventBridge",
            orderId=order_id,
            eventBusName=EVENT_BUS_NAME,
            eventType="OrderCreated"
        )

        # Add custom metrics
        metrics.add_metric(name="OrdersCreated", unit=MetricUnit.Count, value=1)
        metrics.add_metric(name="OrderTotal", unit=MetricUnit.Count, value=float(total))

        return {
            "statusCode": 201,
            "body": json.dumps({
                "message": "Order created successfully",
                "orderId": order_id,
                "status": "NEW",
                "total": float(total),
            })
        }

    except KeyError as e:
        logger.exception("Missing required field in snack item", error=str(e))
        metrics.add_metric(name="OrderCreationErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": f"Missing required field in snack item: {str(e)}"
            })
        }
    except Exception as e:
        logger.exception("Error creating order", error=str(e), errorType=type(e).__name__)
        metrics.add_metric(name="OrderCreationErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }

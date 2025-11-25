"""Lambda function for processing orders from SQS queue."""
import json
import os
from datetime import datetime, UTC

import boto3
from aws_lambda_powertools import Logger, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import (
    BatchProcessor,
    EventType,
    process_partial_response
)
from aws_lambda_powertools.utilities.batch.exceptions import BatchProcessingError

# Initialize Powertools
# Note: X-Ray Tracer could be added for distributed tracing in production
# (tracer = Tracer()) but omitted here to keep the test scope focused
logger = Logger()
metrics = Metrics()

dynamodb = boto3.resource("dynamodb")
processor = BatchProcessor(event_type=EventType.SQS)

TABLE_NAME = os.environ["TABLE_NAME"]


def process_record(record: dict) -> dict:
    """
    Process a single SQS record containing an EventBridge event.
    """
    # Parse the EventBridge event from SQS message body
    message_body = json.loads(record["body"])

    # Extract order details from EventBridge event
    order_id = message_body["detail"]["orderId"]

    logger.info(
        "Processing order",
        orderId=order_id,
        eventId=message_body.get("id"),
        source=message_body.get("source")
    )

    table = dynamodb.Table(TABLE_NAME)
    response = table.get_item(Key={"orderId": order_id})

    if "Item" not in response:
        logger.error("Order not found", orderId=order_id)
        metrics.add_metric(name="OrderNotFound", unit=MetricUnit.Count, value=1)
        raise ValueError(f"Order {order_id} not found")

    order = response["Item"]
    logger.info(
        "Order retrieved",
        orderId=order_id,
        currentStatus=order["status"]
    )

    # Idempotency check
    if order["status"] != "NEW":
        logger.info(
            "Order already processed",
            orderId=order_id,
            status=order["status"]
        )
        metrics.add_metric(name="OrdersAlreadyProcessed", unit=MetricUnit.Count, value=1)
        return {"orderId": order_id, "status": "skipped"}

    # Update order status
    table.update_item(
        Key={"orderId": order_id},
        UpdateExpression="SET #status = :status, processedAt = :processedAt",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "PROCESSED",
            ":processedAt": datetime.now(UTC).isoformat(),
        },
    )

    logger.info(
        "Order processed successfully",
        orderId=order_id,
        previousStatus="NEW",
        newStatus="PROCESSED"
    )

    metrics.add_metric(name="OrdersProcessed", unit=MetricUnit.Count, value=1)

    return {"orderId": order_id, "status": "processed"}


@logger.inject_lambda_context
@metrics.log_metrics
def lambda_handler(event, context):
    """
    Process order created events from SQS queue.

    Uses Lambda Powertools batch processing for partial failure handling.
    SQS receives events from EventBridge and batches them for processing.
    Updates the order status from NEW to PROCESSED.
    """
    try:
        # Use Powertools batch processor for automatic partial failure handling
        batch = process_partial_response(
            event=event,
            record_handler=process_record,
            processor=processor,
            context=context
        )

        # Log batch processing results
        logger.info(
            "Batch processing complete",
            totalRecords=len(event.get("Records", [])),
            successful=len(batch["batchItemFailures"]) if batch else 0,
        )

        return batch

    except BatchProcessingError as e:
        logger.error(
            "Batch processing error",
            error=str(e),
            failedRecords=len(e.child_exceptions)
        )
        metrics.add_metric(name="BatchProcessingErrors", unit=MetricUnit.Count, value=1)
        raise
    except Exception as e:
        logger.exception(
            "Unexpected error in batch processing",
            error=str(e),
            errorType=type(e).__name__
        )
        metrics.add_metric(name="UnexpectedErrors", unit=MetricUnit.Count, value=1)
        raise

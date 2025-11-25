from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_events as events,
    aws_events_targets as targets,
    aws_dynamodb as dynamodb,
    aws_sqs as sqs,
    aws_kms as kms,
    aws_lambda_event_sources as event_sources,
)
from constructs import Construct
from lib.constructs.function import PythonFunction


class AppStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        orders_table: dynamodb.ITable,
        encryption_key: kms.IKey,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Event bus for publishing order lifecycle events
        event_bus = events.EventBus(
            self,
            "OrderEventBus",
            event_bus_name="serverless-snacks-orders",
        )

        # DLQ for handling failed order processing attempts
        processing_dlq = sqs.Queue(
            self,
            "ProcessingDLQ",
            queue_name="serverless-snacks-processing-dlq",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=encryption_key,
        )

        # Order creation function
        create_order_fn = PythonFunction(
            self,
            "CreateOrder",
            handler_path="src/lambdas/create_order",
            environment={
                "TABLE_NAME": orders_table.table_name,
                "EVENT_BUS_NAME": event_bus.event_bus_name,
                "POWERTOOLS_SERVICE_NAME": "serverless-snacks",
                "POWERTOOLS_METRICS_NAMESPACE": "ServerlessSnacks",
            },
            timeout=Duration.seconds(15),
            memory_size=256,
        )

        orders_table.grant_write_data(create_order_fn)
        event_bus.grant_put_events_to(create_order_fn)

        # Order processing function
        # Example: Shows how to configure Lambda resources using construct
        # Production: Could add reserved_concurrent_executions for throttling control
        process_order_fn = PythonFunction(
            self,
            "ProcessOrder",
            handler_path="src/lambdas/process_order",
            environment={
                "TABLE_NAME": orders_table.table_name,
                "POWERTOOLS_SERVICE_NAME": "serverless-snacks",
                "POWERTOOLS_METRICS_NAMESPACE": "ServerlessSnacks",
            },
            timeout=Duration.seconds(60),
            memory_size=512,
            dead_letter_queue=processing_dlq,
        )
        orders_table.grant_read_write_data(process_order_fn)

        # Provides buffering and better control over Lambda invocation rate
        processing_queue = sqs.Queue(
            self,
            "ProcessingQueue",
            queue_name="serverless-snacks-processing-queue",
            visibility_timeout=Duration.seconds(process_order_fn.timeout.to_seconds() * 6),
            retention_period=Duration.days(4),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=processing_dlq,
            ),
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=encryption_key,
        )

        # Connect Lambda to SQS queue
        process_order_fn.add_event_source(
            event_sources.SqsEventSource(
                processing_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(5),
            )
        )

        # Route new order events to SQS queue
        events.Rule(
            self,
            "OnOrderCreated",
            event_bus=event_bus,
            event_pattern=events.EventPattern(
                source=["serverless.snacks.orders"],
                detail_type=["OrderCreated"],
            ),
            targets=[
                targets.SqsQueue(
                    processing_queue,
                    retry_attempts=3,
                    max_event_age=Duration.hours(2),
                    dead_letter_queue=processing_dlq,
                )
            ],
        )

        CfnOutput(
            self,
            "CreateOrderFunction",
            value=create_order_fn.function_name,
            description="Function for creating new orders",
        )

        CfnOutput(
            self,
            "ProcessOrderFunction",
            value=process_order_fn.function_name,
            description="Function for processing orders",
        )

        CfnOutput(
            self,
            "EventBus",
            value=event_bus.event_bus_name,
            description="Event bus for order events",
        )

        CfnOutput(
            self,
            "ProcessingDLQUrl",
            value=processing_dlq.queue_url,
            description="Dead letter queue for failed processing",
        )

        # In a production environment, would add CloudWatch Alarms for:
        # - DLQ message count
        # - Lambda error rates 
        # - Lambda throttles
        # - DynamoDB throttles

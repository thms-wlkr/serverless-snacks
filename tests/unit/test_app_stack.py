import pytest
import aws_cdk as cdk
from aws_cdk import assertions
from lib.app_stack import AppStack
from lib.data_stack import DataStack

# Pytest fixtures run before each test that uses them (similar to beforeEach in TypeScript)
@pytest.fixture
def app_stack():
    """Fixture to create AppStack with DataStack for testing"""
    app = cdk.App()
    data_stack = DataStack(app, "TestDataStack")
    stack = AppStack(
        app,
        "TestAppStack",
        orders_table=data_stack.orders_table,
        encryption_key=data_stack.encryption_key
    )
    return stack


def test_lambda_functions_created(app_stack):
    """Test that both Lambda functions are created"""
    template = assertions.Template.from_stack(app_stack)

    # Check both Lambda functions exist (may include log retention Lambdas, hence >= 2)
    resources = template.find_resources("AWS::Lambda::Function")
    assert len(resources) >= 2, "Should have at least 2 Lambda functions"


def test_lambda_runtime_configuration(app_stack):
    """Test Lambda functions use Python 3.12 runtime"""
    template = assertions.Template.from_stack(app_stack)

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "Handler": "handler.lambda_handler",
        }
    )


def test_eventbridge_bus_created(app_stack):
    """Test that EventBridge event bus is created"""
    template = assertions.Template.from_stack(app_stack)

    template.resource_count_is("AWS::Events::EventBus", 1)

    template.has_resource_properties(
        "AWS::Events::EventBus",
        {
            "Name": "serverless-snacks-orders"
        }
    )


def test_eventbridge_rule_configuration(app_stack):
    """Test EventBridge rule has correct event pattern"""
    template = assertions.Template.from_stack(app_stack)

    template.resource_count_is("AWS::Events::Rule", 1)

    template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "EventPattern": {
                "source": ["serverless.snacks.orders"],
                "detail-type": ["OrderCreated"],
            },
            "State": "ENABLED",
        }
    )


def test_dlq_created(app_stack):
    """Test that SQS queues are created (processing queue + DLQ)"""
    template = assertions.Template.from_stack(app_stack)

    # Should have 2 queues: processing queue and DLQ
    template.resource_count_is("AWS::SQS::Queue", 2)

    # Verify DLQ exists with correct configuration
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "serverless-snacks-processing-dlq",
            "MessageRetentionPeriod": 1209600
        }
    )

    # Verify processing queue exists
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "serverless-snacks-processing-queue",
        }
    )


def test_stack_outputs(app_stack):
    """Test that all required outputs are defined"""
    template = assertions.Template.from_stack(app_stack)

    template.has_output(
        "CreateOrderFunction",
        assertions.Match.object_like({
            "Description": "Function for creating new orders"
        })
    )

    template.has_output(
        "ProcessOrderFunction",
        assertions.Match.object_like({
            "Description": "Function for processing orders"
        })
    )


def test_sqs_queues_encrypted_with_kms(app_stack):
    """Test that SQS queues use customer-managed KMS encryption"""
    template = assertions.Template.from_stack(app_stack)

    # Both queues should use KMS encryption
    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "serverless-snacks-processing-queue",
            "KmsMasterKeyId": assertions.Match.any_value(),
        }
    )

    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "serverless-snacks-processing-dlq",
            "KmsMasterKeyId": assertions.Match.any_value(),
        }
    )

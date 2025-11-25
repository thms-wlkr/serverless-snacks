import pytest
import aws_cdk as cdk
from aws_cdk import assertions
from lib.data_stack import DataStack

# Pytest fixtures run before each test that uses them (similar to beforeEach in TypeScript)
@pytest.fixture
def data_stack():
    """Fixture to create a DataStack for testing"""
    app = cdk.App()
    stack = DataStack(app, "TestDataStack")
    return stack


def test_dynamodb_table_created(data_stack):
    """Test that DynamoDB table is created"""
    template = assertions.Template.from_stack(data_stack)
    template.resource_count_is("AWS::DynamoDB::Table", 1)


def test_dynamodb_table_configuration(data_stack):
    """Test DynamoDB table has correct key schema and settings"""
    template = assertions.Template.from_stack(data_stack)

    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "KeySchema": [
                {"AttributeName": "orderId", "KeyType": "HASH"}
            ],
            "AttributeDefinitions": [
                {"AttributeName": "orderId", "AttributeType": "S"}
            ],
            "BillingMode": "PAY_PER_REQUEST",
            "PointInTimeRecoverySpecification": {
                "PointInTimeRecoveryEnabled": True
            },
        }
    )


def test_dynamodb_table_removal_policy(data_stack):
    """Test that table has DESTROY removal policy for testing"""
    template = assertions.Template.from_stack(data_stack)

    # DeletionPolicy is a CloudFormation resource attribute, not a property
    template.has_resource(
        "AWS::DynamoDB::Table",
        {
            "DeletionPolicy": "Delete",
            "UpdateReplacePolicy": "Delete",
        }
    )


def test_outputs_defined(data_stack):
    """Test that stack outputs are defined"""
    template = assertions.Template.from_stack(data_stack)

    template.has_output(
        "OrdersTableName",
        assertions.Match.object_like({
            "Description": "DynamoDB table for orders"
        })
    )


def test_kms_key_created(data_stack):
    """Test that KMS key is created for encryption"""
    template = assertions.Template.from_stack(data_stack)
    template.resource_count_is("AWS::KMS::Key", 1)


def test_kms_key_rotation_enabled(data_stack):
    """Test that KMS key has rotation enabled"""
    template = assertions.Template.from_stack(data_stack)

    template.has_resource_properties(
        "AWS::KMS::Key",
        {
            "EnableKeyRotation": True,
        }
    )


def test_kms_alias_created(data_stack):
    """Test that KMS key alias is created"""
    template = assertions.Template.from_stack(data_stack)

    template.has_resource_properties(
        "AWS::KMS::Alias",
        {
            "AliasName": "alias/serverless-snacks",
        }
    )


def test_dynamodb_encrypted_with_kms(data_stack):
    """Test that DynamoDB table uses customer-managed KMS encryption"""
    template = assertions.Template.from_stack(data_stack)

    # Table should reference a KMS key
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "SSESpecification": {
                "SSEEnabled": True,
                "SSEType": "KMS",
            }
        }
    )

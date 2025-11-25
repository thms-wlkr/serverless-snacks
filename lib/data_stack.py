from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_kms as kms,
)
from constructs import Construct


class DataStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # KMS key for encryption at rest
        self.encryption_key = kms.Key(
            self,
            "EncryptionKey",
            description="Customer-managed key for Serverless Snacks application data encryption",
            enable_key_rotation=True,  # Automatic annual rotation
            removal_policy=RemovalPolicy.DESTROY,  # DESTROY for demo, would use RETAINin production
        )

        # Alias for easier key identification
        kms.Alias(
            self,
            "EncryptionKeyAlias",
            alias_name="alias/serverless-snacks",
            target_key=self.encryption_key,
        )

        # DynamoDB Table for Orders
        self.orders_table = dynamodb.Table(
            self,
            "OrdersTable",
            partition_key=dynamodb.Attribute(
                name="orderId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # DESTROY for demo purposes - use RETAIN for production to prevent data loss
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            # Customer-managed encryption key for data at rest
            encryption_key=self.encryption_key,
        )

        CfnOutput(
            self,
            "OrdersTableName",
            value=self.orders_table.table_name,
            description="DynamoDB table for orders",
        )

#!/usr/bin/env python3
import os
import aws_cdk as cdk
from lib.data_stack import DataStack
from lib.app_stack import AppStack

app = cdk.App()

# Environment configuration
env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", "eu-west-1")
)

# DataStack: Stateful resources (DynamoDB)
# This stack persists even when redeploying application code
data_stack = DataStack(
    app,
    "ServerlessSnacks-DataStack",
    env=env,
)

# AppStack: Stateless resources (Lambdas, EventBridge)
# Can be destroyed and redeployed without losing data
app_stack = AppStack(
    app,
    "ServerlessSnacks-AppStack",
    orders_table=data_stack.orders_table,
    encryption_key=data_stack.encryption_key,
    env=env,
)

app.synth()

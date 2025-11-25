# Serverless Snacks

Serverless order processing system built with AWS CDK (Python). Demonstrates event-driven architecture using Lambda, DynamoDB, EventBridge, and SQS.

## Architecture

Two CDK stacks:
- **DataStack**: DynamoDB table with KMS encryption
- **AppStack**: Lambda functions, EventBridge, SQS queues

### Flow

1. CreateOrder Lambda receives order → saves to DynamoDB → publishes event to EventBridge
2. EventBridge routes event to SQS queue
3. ProcessOrder Lambda polls SQS → processes orders in batches → updates DynamoDB

### Key Features

- SQS decoupling between EventBridge and Lambda for buffering
- Batch processing (up to 10 messages per batch)
- Dead Letter Queue for failed messages
- KMS encryption for DynamoDB and SQS
- Structured logging with Lambda Powertools
- Idempotent processing

## Prerequisites

- Python 3.12+
- Node.js 24+ (for CDK)
- AWS CLI configured
- CDK CLI: `npm install -g aws-cdk`

## Quick Start

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy
cdk deploy --all

# Destroy when done
cdk destroy --all
```

## Testing

```bash
# Run tests
make test          # All tests
make test-unit     # Unit tests only
make test-cov      # With coverage

# Or use pytest directly
pytest tests/ -v
pytest tests/unit/ -v
pytest tests/ --cov=lib --cov=src
```

## Deployment

```bash
make synth       # View CloudFormation
make deploy      # Deploy all stacks
make destroy     # Clean up
```

## Testing After Deployment

Invoke the CreateOrder Lambda via AWS Console or CLI:

```bash
aws lambda invoke \
  --function-name <function-name> \
  --payload '{"customerName":"Test","snackItems":[{"name":"Crisps","price":"1.50","quantity":2}]}' \
  response.json
```

Check DynamoDB to verify order was created with status `NEW`, then after a few seconds check again - status should be `PROCESSED`.

View logs in CloudWatch to see the event flow.

## Project Structure

```
├── bin/app.py              # CDK entry point
├── lib/
│   ├── data_stack.py       # DynamoDB + KMS
│   ├── app_stack.py        # Lambda + EventBridge + SQS
│   └── constructs/         # Reusable constructs
├── src/lambdas/            # Lambda handlers
├── tests/                  # Unit + integration tests
└── Makefile                # Helper commands
```

## Design Notes

- **Stacks separated** by lifecycle (stateful vs stateless)
- **KMS encryption** for DynamoDB and SQS
- **SQS between EventBridge and Lambda** for decoupling and buffering
- **Batch processing** with Lambda Powertools for efficiency
- **DLQ** for failed message handling
- `DESTROY` removal policy used for demo (production would use `RETAIN`)

## CI/CD

GitHub Actions workflow included:
- Linting (pylint)
- Unit + integration tests
- CDK synth validation

See `.github/workflows/ci.yml` for details.

.PHONY: install test test-unit test-integration synth deploy destroy clean

# Activate virtual environment for all commands
VENV = .venv/bin/activate

install:
	. $(VENV) && pip install -r requirements.txt
	. $(VENV) && pip install -r requirements-dev.txt

test:
	. $(VENV) && pytest tests/unit/ src/ tests/integration/ -v

test-unit:
	. $(VENV) && pytest tests/unit/ src/ -v

test-integration:
	. $(VENV) && pytest tests/integration/ -v

synth:
	. $(VENV) && cdk synth

deploy:
	. $(VENV) && cdk deploy --all

destroy:
	. $(VENV) && cdk destroy --all

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf cdk.out .coverage

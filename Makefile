#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = TC5061-Proyecto-Equipo30
PYTHON_VERSION = 3.12
PYTHON_INTERPRETER = python3

#################################################################################
# COMMANDS                                                                      #
#################################################################################

## Install Python dependencies and local package in editable mode
.PHONY: requirements
requirements:
	$(PYTHON_INTERPRETER) -m pip install -U pip wheel
	$(PYTHON_INTERPRETER) -m pip install setuptools==80.10.2
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt
	$(PYTHON_INTERPRETER) -m pip install -e .

## Delete all compiled Python files, caches and build artifacts
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache build dist *.egg-info

## Lint source code using ruff / flake8
.PHONY: lint
lint:
	$(PYTHON_INTERPRETER) -m ruff check src/ tests/
	$(PYTHON_INTERPRETER) -m ruff format --check src/ tests/

## Format source code using ruff / black
.PHONY: format
format:
	$(PYTHON_INTERPRETER) -m ruff check --fix src/ tests/
	$(PYTHON_INTERPRETER) -m ruff format src/ tests/

## Run unit tests with pytest
.PHONY: test
test:
	$(PYTHON_INTERPRETER) -m pytest tests

## Static code security scan with bandit
.PHONY: security_code
security_code:
	$(PYTHON_INTERPRETER) -m bandit -r src scripts

## Dependency vulnerability scan with pip-audit
.PHONY: security_deps
security_deps:
	$(PYTHON_INTERPRETER) -m pip_audit

#################################################################################
# PROJECT PIPELINES (CCDS v1)                                                   #
#################################################################################

## Download raw data from MiBici portal
.PHONY: download_data
download_data:
	$(PYTHON_INTERPRETER) -m src.data.p2_download_raw_data

## Build interim dataset and engineer features
.PHONY: data
data:
	$(PYTHON_INTERPRETER) -m src.data.p2_dataset
	$(PYTHON_INTERPRETER) -m src.features.p2_features

## Build interim dataset and engineer features (shared: Question 3)
.PHONY: data_p3
data_p3:
	$(PYTHON_INTERPRETER) -m src.data.dataset
	$(PYTHON_INTERPRETER) -m src.features.features

## Train all models and log experiments to MLflow (P1, P2 and P3)
.PHONY: train
train:
	$(PYTHON_INTERPRETER) -m src.models.run_all_experiments

## Train specifically Question 2 risk classifier
.PHONY: train_p2
train_p2:
	$(PYTHON_INTERPRETER) -m src.models.p2_train

## Train specifically Question 3 station-clustering model
.PHONY: train_p3
train_p3:
	$(PYTHON_INTERPRETER) -m src.models.p3_train

## Launch local MLflow Tracking server (DB-backed, required for the Model Registry) on port 5000
.PHONY: mlflow
mlflow:
	mlflow server --backend-store-uri sqlite:///mlflow.db --port 5000

## Run DeepChecks data integrity and train/test drift validation suites
.PHONY: deepchecks
deepchecks:
	$(PYTHON_INTERPRETER) -m scripts.run_deepchecks

#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)

## Prepare Question 1 hourly flows and features
.PHONY: data_p1
data_p1:
	$(PYTHON_INTERPRETER) -m src.data.p1_dataset
	$(PYTHON_INTERPRETER) -m src.features.p1_features

## Train Question 1 and log the four comparable MLflow runs
.PHONY: train_p1
train_p1:
	$(PYTHON_INTERPRETER) -m src.models.p1_train

#################################################################################
# CONTAINERIZATION & API (WEEK 8)                                               #
#################################################################################

CONTAINER_ENGINE ?= $(shell which docker 2>/dev/null || which podman 2>/dev/null || echo docker)
IMAGE_NAME = mibici-risk-api:latest
CONTAINER_NAME = mibici-risk-service

## Build API container image using Docker or Podman
.PHONY: build_container
build_container:
	$(CONTAINER_ENGINE) build -t $(IMAGE_NAME) -f Containerfile .

## Run API container locally connecting to MLflow tracking server
.PHONY: run_container
run_container:
	$(CONTAINER_ENGINE) run -d --name $(CONTAINER_NAME) -p 8000:8000 \
		-e MLFLOW_TRACKING_URI=http://host.docker.internal:5001 \
		$(IMAGE_NAME)

## Stop and remove running API container
.PHONY: stop_container
stop_container:
	-$(CONTAINER_ENGINE) stop $(CONTAINER_NAME)
	-$(CONTAINER_ENGINE) rm $(CONTAINER_NAME)

## Test API endpoints running on port 8000
.PHONY: test_api_live
test_api_live:
	curl -s http://127.0.0.1:8000/health
	@echo ""
	curl -s -X POST http://127.0.0.1:8000/predict -H "Content-Type: application/json" \
		-d '{"capacity":20,"latitude":20.67,"longitude":-103.35,"salidas_lag_1":1,"llegadas_lag_1":2,"salidas_lag_2":1,"llegadas_lag_2":2,"salidas_lag_24":3,"llegadas_lag_24":4,"salidas_lag_168":5,"llegadas_lag_168":6,"balance_rolling_3h":-1.5,"balance_rolling_12h":0.5,"sin_hour":0.5,"cos_hour":0.866,"sin_dow":-0.5,"cos_dow":0.866}'
	@echo ""


#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = TC5061-Proyecto-Equipo30
PYTHON_VERSION = 3.12
PYTHON_INTERPRETER = python3
MLFLOW_PORT ?= 5000
MLFLOW_BIND_HOST ?= 0.0.0.0
MLFLOW_ALLOWED_HOSTS ?= localhost:*,127.0.0.1:*,host.docker.internal:*,host.containers.internal:*

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

## Train and register Question 2 Challenger model v2 in MLflow Model Registry
.PHONY: train_challenger
train_challenger:
	$(PYTHON_INTERPRETER) scripts/train_and_register_challenger.py

## Run A/B testing suite between Champion v1 and Challenger v2 on production data
.PHONY: ab_test
ab_test:
	$(PYTHON_INTERPRETER) scripts/run_ab_testing.py

## Train specifically Question 3 station-clustering model
.PHONY: train_p3
train_p3:
	$(PYTHON_INTERPRETER) -m src.models.p3_train

## Launch MLflow Tracking for local containers (override MLFLOW_PORT if needed)
.PHONY: mlflow
mlflow:
	$(PYTHON_INTERPRETER) -m mlflow server --backend-store-uri sqlite:///mlflow.db \
		--host $(MLFLOW_BIND_HOST) --port $(MLFLOW_PORT) \
		--allowed-hosts '$(MLFLOW_ALLOWED_HOSTS)' --serve-artifacts

## Run DeepChecks data integrity and train/test drift validation suites
.PHONY: deepchecks
deepchecks:
	$(PYTHON_INTERPRETER) -m scripts.run_deepchecks

## Generate Evidently data drift and data quality reports for P2
.PHONY: evidently
evidently:
	$(PYTHON_INTERPRETER) -m scripts.run_evidently

## Generate visual ranking and distribution plots from Evidently drift audit
.PHONY: drift_figures
drift_figures:
	$(PYTHON_INTERPRETER) scripts/generate_drift_figures.py

## Generate official week 9 technical and executive report (DOCX, MD, PDF)
.PHONY: report_week9
report_week9:
	$(PYTHON_INTERPRETER) scripts/generate_week9_report.py

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
CONTAINER_HOST = $(if $(findstring podman,$(CONTAINER_ENGINE)),host.containers.internal,host.docker.internal)
CONTAINER_BUILD_FLAGS = $(if $(findstring podman,$(CONTAINER_ENGINE)),--format=docker,)
CONTAINER_TRACKING_URI ?= http://$(CONTAINER_HOST):$(MLFLOW_PORT)
CONTAINER_HOST_ARGS = $(if $(and $(filter Linux,$(shell uname -s)),$(findstring docker,$(CONTAINER_ENGINE))),--add-host=host.docker.internal:host-gateway,)
MODEL_URI ?= models:/mibici-equipo30-p2-riesgo@champion
API_BASE_URL ?= http://127.0.0.1:8000

## Build API container image using Docker or Podman
.PHONY: build_container
build_container:
	$(CONTAINER_ENGINE) build $(CONTAINER_BUILD_FLAGS) -t $(IMAGE_NAME) -f Containerfile .

## Run API container locally connecting to MLflow tracking server
.PHONY: run_container
run_container:
	$(CONTAINER_ENGINE) run -d --name $(CONTAINER_NAME) -p 8000:8000 \
		$(CONTAINER_HOST_ARGS) \
		-e MLFLOW_TRACKING_URI=$(CONTAINER_TRACKING_URI) \
		-e MODEL_URI=$(MODEL_URI) \
		$(IMAGE_NAME)

## Stop and remove running API container
.PHONY: stop_container
stop_container:
	-$(CONTAINER_ENGINE) stop $(CONTAINER_NAME)
	-$(CONTAINER_ENGINE) rm $(CONTAINER_NAME)

## Test API endpoints running on port 8000
.PHONY: test_api_live
test_api_live:
	$(PYTHON_INTERPRETER) -m scripts.verify_container_api --base-url $(API_BASE_URL) \
		--container-engine $(CONTAINER_ENGINE) --container-name $(CONTAINER_NAME)

#################################################################################
# ORCHESTRATION, LOAD TESTING & FINOPS (WEEK 10)                                #
#################################################################################

## Start MLflow and API stack with Docker Compose
.PHONY: compose_up
compose_up:
	docker compose up -d --build

## Stop Docker Compose services preserving MLflow volume
.PHONY: compose_down
compose_down:
	docker compose down

## Run stepped Locust load tests with live docker stats monitoring
.PHONY: load_test
load_test:
	$(PYTHON_INTERPRETER) scripts/run_load_and_monitor.py --host $(API_BASE_URL)

## Run FinOps cost-per-inference analysis and generate figures
.PHONY: finops
finops:
	$(PYTHON_INTERPRETER) scripts/finops_analysis.py

## Generate official week 10 Operations & FinOps report (DOCX, MD, PDF)
.PHONY: report_week10
report_week10:
	$(PYTHON_INTERPRETER) scripts/generate_week10_report.py

#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = MLOps_Equipo30
PYTHON_VERSION = 3.13
PYTHON_INTERPRETER = python

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies
.PHONY: requirements
requirements:
	$(PYTHON_INTERPRETER) -m pip install -U pip
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt
	



## Delete all compiled Python files
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


## Lint using ruff (use `make format` to do formatting)
.PHONY: lint
lint:
	ruff format --check
	ruff check

## Format source code with ruff
.PHONY: format
format:
	ruff check --fix
	ruff format



## Run tests
.PHONY: test
test:
	python -m pytest tests


## Set up Python interpreter environment
.PHONY: create_environment
ifeq ($(OS),Windows_NT)
create_environment:
	py -$(PYTHON_VERSION) -m venv .venv
	@echo ">>> New virtualenv created in .venv/. Activate with:"
	@echo "    .venv\\Scripts\\Activate.ps1   (PowerShell)"
	@echo "    .venv\\Scripts\\activate.bat   (cmd.exe)"
else
create_environment:
	$(PYTHON_INTERPRETER)$(PYTHON_VERSION) -m venv .venv
	@echo ">>> New virtualenv created in .venv/. Activate with:"
	@echo "    source .venv/bin/activate"
endif




#################################################################################
# PROJECT RULES                                                                 #
#################################################################################


## Make dataset
.PHONY: data
data: requirements
	$(PYTHON_INTERPRETER) MiBici/clasificacion_dataset.py

## Make station features
.PHONY: features
features: data
	$(PYTHON_INTERPRETER) MiBici/clasificacion_features.py

## Train clustering models with MLflow-tracked experiment sweep
.PHONY: train
train: features
	$(PYTHON_INTERPRETER) MiBici/modeling/clasificacion_train.py


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

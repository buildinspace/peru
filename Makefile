PYTHON ?= python3
FLAKE8 ?= flake8
PIP ?= pip3

VENV ?= .venv

##@ Code Quality

.PHONY: all
all: check test ## Run all checks and tests

.PHONY: test
test: ## Run all tests
	$(PYTHON) test.py -v

.PHONY: check
check: ## Run all checks
	$(FLAKE8) peru tests

##@ Dev Env Setup

.PHONY: venv
venv: ## Create a venv
	$(PYTHON) -m venv --clear $(VENV)
	@echo "Activate the venv with 'source $(VENV)/bin/activate'"

.PHONY: deps-dev
deps-dev: ## Install development dependencies
	$(PIP) install -r requirements-dev.txt

##@ Utility

.PHONY: install
install: ## Install peru
	$(PYTHON) setup.py install --user

.PHONY: uninstall
uninstall: ## Uninstall peru
	$(PIP) uninstall peru

.PHONY: help
help:  ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[\#a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

# Home Assistant Configuration Management Makefile

# Load environment variables from .env file
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# Configuration
HA_HOST ?= your_homeassistant_host
HA_REMOTE_PATH ?= /config/
LOCAL_CONFIG_PATH ?= config/
BACKUP_DIR ?= backups
VENV_PATH ?= venv
TOOLS_PATH ?= tools

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help pull push validate backup clean setup test status entities reload format-yaml

# Default target
help:
	@echo "$(GREEN)Home Assistant Configuration Management$(NC)"
	@echo ""
	@echo "Available commands:"
	@echo "  $(YELLOW)pull$(NC)     - Pull latest config from Home Assistant"
	@echo "  $(YELLOW)push$(NC)     - Push local config to Home Assistant (with validation)"
	@echo "  $(YELLOW)validate$(NC) - Run all validation tests"
	@echo "  $(YELLOW)backup$(NC)   - Create timestamped backup of current config"
	@echo "  $(YELLOW)setup$(NC)    - Set up Python environment and dependencies"
	@echo "  $(YELLOW)test$(NC)     - Run validation tests (alias for validate)"
	@echo "  $(YELLOW)status$(NC)   - Show configuration status and entity counts"
	@echo "  $(YELLOW)entities$(NC) - Explore available entities (usage: make entities [ARGS='options'])"
	@echo "  $(YELLOW)reload$(NC)   - Reload Home Assistant configuration (without pushing)"
	@echo "  $(YELLOW)format-yaml$(NC) - Format YAML files (usage: make format-yaml [FILES='file1.yaml file2.yaml'])"
	@echo "  $(YELLOW)clean$(NC)    - Clean up temporary files and caches"

# Pull configuration from Home Assistant
pull:
	@echo "$(GREEN)Pulling configuration from Home Assistant...$(NC)"
	@rsync -avz --delete --exclude-from=.rsync-excludes $(HA_HOST):$(HA_REMOTE_PATH) $(LOCAL_CONFIG_PATH)
	@echo "$(GREEN)Configuration pulled successfully!$(NC)"
	@echo "$(YELLOW)Running validation to ensure integrity...$(NC)"
	@$(MAKE) validate

# Push configuration to Home Assistant (with pre-validation)
push:
	@echo "$(GREEN)Validating configuration before push...$(NC)"
	@$(MAKE) validate
	@echo "$(GREEN)Validation passed! Pushing to Home Assistant...$(NC)"
	@rsync -avz --delete --exclude-from=.rsync-excludes $(LOCAL_CONFIG_PATH) $(HA_HOST):$(HA_REMOTE_PATH)
	@echo "$(GREEN)Configuration pushed successfully!$(NC)"
	@echo "$(GREEN)Reloading Home Assistant configuration...$(NC)"
	@. $(VENV_PATH)/bin/activate && python $(TOOLS_PATH)/reload_config.py
	@echo "$(GREEN)Configuration deployment complete!$(NC)"

# Run all validation tests
validate: check-setup
	@echo "$(GREEN)Running Home Assistant configuration validation...$(NC)"
	@. $(VENV_PATH)/bin/activate && python $(TOOLS_PATH)/run_tests.py

# Alias for validate
test: validate

# Create backup of current configuration
backup:
	@echo "$(GREEN)Creating backup of current configuration...$(NC)"
	@mkdir -p $(BACKUP_DIR)
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	backup_name="$(BACKUP_DIR)/ha_config_$$timestamp"; \
	tar -czf "$$backup_name.tar.gz" $(LOCAL_CONFIG_PATH); \
	echo "$(GREEN)Backup created: $$backup_name.tar.gz$(NC)"

# Set up Python environment and dependencies
setup:
	@echo "$(GREEN)Setting up Python environment...$(NC)"
	@python3 -m venv $(VENV_PATH)
	@. $(VENV_PATH)/bin/activate && pip install --upgrade pip
	@. $(VENV_PATH)/bin/activate && pip install homeassistant voluptuous pyyaml jsonschema requests
	@echo "$(GREEN)Setup complete!$(NC)"

# Show configuration status
status: check-setup
	@echo "$(GREEN)Home Assistant Configuration Status$(NC)"
	@echo "=================================="
	@echo "Config directory: $(LOCAL_CONFIG_PATH)"
	@echo "Remote host: $(HA_HOST)"
	@echo ""
	@if [ -f "$(LOCAL_CONFIG_PATH)configuration.yaml" ]; then \
		echo "$(GREEN)✓$(NC) Configuration file found"; \
	else \
		echo "$(RED)✗$(NC) Configuration file missing"; \
	fi
	@if [ -d "$(LOCAL_CONFIG_PATH).storage" ]; then \
		echo "$(GREEN)✓$(NC) Storage directory found"; \
	else \
		echo "$(RED)✗$(NC) Storage directory missing"; \
	fi
	@echo ""
	@echo "$(YELLOW)Entity Summary:$(NC)"
	@. $(VENV_PATH)/bin/activate && python $(TOOLS_PATH)/reference_validator.py 2>/dev/null | grep "Examples:" -A 1 -B 1 | head -20

# Explore available Home Assistant entities
entities: check-setup
	@echo "$(GREEN)Home Assistant Entity Explorer$(NC)"
	@echo "Usage examples:"
	@echo "  make entities                    - Show summary of all entities"
	@echo "  make entities ARGS='--domain climate'  - Show only climate entities"
	@echo "  make entities ARGS='--area kitchen'    - Show only kitchen entities"
	@echo "  make entities ARGS='--search temp'     - Search for temperature entities"
	@echo "  make entities ARGS='--full'            - Show complete detailed output"
	@echo ""
	@. $(VENV_PATH)/bin/activate && python $(TOOLS_PATH)/entity_explorer.py $(ARGS)

# Reload Home Assistant configuration via API
reload: check-setup
	@echo "$(GREEN)Reloading Home Assistant configuration...$(NC)"
	@. $(VENV_PATH)/bin/activate && python $(TOOLS_PATH)/reload_config.py

# Format YAML files (specific files or all in config directory)
format-yaml:
	@echo "$(GREEN)Formatting YAML files...$(NC)"
	@if [ -n "$(FILES)" ]; then \
		echo "Formatting specified files: $(FILES)"; \
		for file in $(FILES); do \
			if [ -f "$$file" ]; then \
				echo "Formatting: $$file"; \
				.claude-code/hooks/yaml-formatter.sh "$$file"; \
			else \
				echo "$(YELLOW)Warning: File not found: $$file$(NC)"; \
			fi; \
		done; \
	else \
		echo "Formatting all YAML files in $(LOCAL_CONFIG_PATH) directory..."; \
		for file in $$(find $(LOCAL_CONFIG_PATH) -name "*.yaml" -o -name "*.yml"); do \
			if [ -f "$$file" ]; then \
				echo "Formatting: $$file"; \
				.claude-code/hooks/yaml-formatter.sh "$$file"; \
			fi; \
		done; \
	fi
	@echo "$(GREEN)YAML formatting complete!$(NC)"

# Clean up temporary files
clean:
	@echo "$(GREEN)Cleaning up temporary files...$(NC)"
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.log" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(NC)"

# Check if setup is complete
check-setup:
	@if [ ! -d "$(VENV_PATH)" ]; then \
		echo "$(RED)Python environment not found. Run 'make setup' first.$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "$(TOOLS_PATH)/run_tests.py" ]; then \
		echo "$(RED)Validation tools not found.$(NC)"; \
		exit 1; \
	fi

# Development targets (not shown in help)
.PHONY: pull-storage push-storage validate-yaml validate-references validate-ha

# Pull only storage files (for development)
pull-storage:
	@rsync -avz $(HA_HOST):$(HA_REMOTE_PATH).storage/ $(LOCAL_CONFIG_PATH).storage/

# Individual validation targets
validate-yaml: check-setup
	@. $(VENV_PATH)/bin/activate && python $(TOOLS_PATH)/yaml_validator.py

validate-references: check-setup
	@. $(VENV_PATH)/bin/activate && python $(TOOLS_PATH)/reference_validator.py

validate-ha: check-setup
	@. $(VENV_PATH)/bin/activate && python $(TOOLS_PATH)/ha_official_validator.py

# SSH connectivity test
test-ssh:
	@echo "$(GREEN)Testing SSH connection to Home Assistant...$(NC)"
	@ssh -o ConnectTimeout=10 $(HA_HOST) "echo 'Connection successful'" && \
		echo "$(GREEN)✓ SSH connection working$(NC)" || \
		echo "$(RED)✗ SSH connection failed$(NC)"

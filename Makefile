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
MAX_BACKUPS ?= 5
SKIP_BACKUP ?= 0

# Colors for output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help pull push validate backup clean setup test status entities reload format-yaml check-env list-backups restore

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
	@echo "  $(YELLOW)check-env$(NC) - Validate environment configuration (.env file)"
	@echo "  $(YELLOW)list-backups$(NC) - List available configuration backups"
	@echo "  $(YELLOW)restore$(NC)  - Restore config from backup (BACKUP=path or most recent)"
	@echo "  $(YELLOW)clean$(NC)    - Clean up temporary files and caches"

# Pull configuration from Home Assistant
pull: check-env
	@$(MAKE) _auto-backup _BACKUP_LABEL=pre-pull
	@echo "$(GREEN)Pulling configuration from Home Assistant...$(NC)"
	@rsync -avz --delete --exclude-from=.rsync-excludes-pull $(HA_HOST):$(HA_REMOTE_PATH) $(LOCAL_CONFIG_PATH)
	@echo "$(GREEN)Configuration pulled successfully!$(NC)"
	@echo "$(YELLOW)Running validation to ensure integrity...$(NC)"
	@$(MAKE) validate

# Push configuration to Home Assistant (with pre-validation)
push: check-env
	@echo "$(GREEN)Validating configuration before push...$(NC)"
	@$(MAKE) validate
	@$(MAKE) _auto-backup _BACKUP_LABEL=pre-push
	@echo "$(GREEN)Validation passed! Pushing to Home Assistant...$(NC)"
	@rsync -avz --delete --exclude-from=.rsync-excludes-push $(LOCAL_CONFIG_PATH) $(HA_HOST):$(HA_REMOTE_PATH)
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
	@$(MAKE) _rotate-backups

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

# Check if required environment variables are configured
check-env:
	@if [ "$(HA_HOST)" = "your_homeassistant_host" ] || [ -z "$(HA_HOST)" ]; then \
		echo "$(RED)Error: HA_HOST not configured. Please set it in your .env file.$(NC)"; \
		echo "$(YELLOW)Example: HA_HOST=homeassistant.local$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f ".env" ]; then \
		echo "$(YELLOW)Warning: .env file not found. Copy .env.example to .env and configure your settings.$(NC)"; \
	fi
	@if ! command -v rsync >/dev/null 2>&1; then \
		echo "$(RED)Error: rsync not found in PATH.$(NC)"; \
		echo "$(YELLOW)Install via Homebrew: brew install rsync$(NC)"; \
		exit 1; \
	fi
	@if ! ssh -o ConnectTimeout=5 -o BatchMode=yes $(HA_HOST) "exit" >/dev/null 2>&1; then \
		echo "$(RED)Error: Unable to connect to Home Assistant via SSH ($(HA_HOST)).$(NC)"; \
		echo "$(YELLOW)Check SSH auth, host reachability, and DNS/hostname settings.$(NC)"; \
		exit 1; \
	fi
	@if ! ssh -o ConnectTimeout=5 -o BatchMode=yes $(HA_HOST) "command -v rsync >/dev/null 2>&1"; then \
		echo "$(RED)Error: rsync not found on Home Assistant ($(HA_HOST)).$(NC)"; \
		echo "$(YELLOW)For Home Assistant OS, install the 'Advanced SSH & Web Terminal' addon$(NC)"; \
		echo "$(YELLOW)and add rsync to the packages list in the addon configuration:$(NC)"; \
		echo "$(YELLOW)  packages:$(NC)"; \
		echo "$(YELLOW)    - rsync$(NC)"; \
		echo "$(YELLOW)Then restart the addon.$(NC)"; \
		exit 1; \
	fi

# List available backups
list-backups:
	@echo "$(GREEN)Available configuration backups:$(NC)"
	@echo ""
	@if [ -d "$(BACKUP_DIR)" ] && ls $(BACKUP_DIR)/ha_config_*.tar.gz 1>/dev/null 2>&1; then \
		ls -1t $(BACKUP_DIR)/ha_config_*.tar.gz | while read f; do \
			size=$$(du -h "$$f" | cut -f1); \
			echo "  $$size  $$f"; \
		done; \
		echo ""; \
		count=$$(ls -1 $(BACKUP_DIR)/ha_config_*.tar.gz 2>/dev/null | wc -l | tr -d ' '); \
		echo "$(YELLOW)Total: $$count backup(s) (max retained: $(MAX_BACKUPS))$(NC)"; \
	else \
		echo "  $(YELLOW)No backups found.$(NC)"; \
	fi

# Restore configuration from backup
restore:
	@if [ -d "$(BACKUP_DIR)" ] && ls $(BACKUP_DIR)/ha_config_*.tar.gz 1>/dev/null 2>&1; then \
		if [ -n "$(BACKUP)" ]; then \
			backup_file="$(BACKUP)"; \
		else \
			backup_file=$$(ls -1t $(BACKUP_DIR)/ha_config_*.tar.gz | head -1); \
		fi; \
		if [ ! -f "$$backup_file" ]; then \
			echo "$(RED)Error: Backup file not found: $$backup_file$(NC)"; \
			exit 1; \
		fi; \
		echo "$(YELLOW)Will restore from: $$backup_file$(NC)"; \
		echo "$(RED)WARNING: This will overwrite the current config/ directory!$(NC)"; \
		echo "$(YELLOW)Press Ctrl+C within 5 seconds to cancel...$(NC)"; \
		sleep 5; \
		echo "$(GREEN)Restoring configuration...$(NC)"; \
		rm -rf $(LOCAL_CONFIG_PATH); \
		tar -xzf "$$backup_file"; \
		echo "$(GREEN)Configuration restored from: $$backup_file$(NC)"; \
	else \
		echo "$(RED)No backups found in $(BACKUP_DIR)/$(NC)"; \
		exit 1; \
	fi

# Internal: auto-backup before destructive operations
_auto-backup:
	@if [ "$(SKIP_BACKUP)" = "1" ]; then \
		echo "$(YELLOW)Skipping auto-backup (SKIP_BACKUP=1)$(NC)"; \
	elif [ ! -d "$(LOCAL_CONFIG_PATH)" ]; then \
		echo "$(YELLOW)Skipping auto-backup ($(LOCAL_CONFIG_PATH) does not exist yet)$(NC)"; \
	else \
		echo "$(GREEN)Creating auto-backup ($(_BACKUP_LABEL))...$(NC)"; \
		mkdir -p $(BACKUP_DIR); \
		timestamp=$$(date +%Y%m%d_%H%M%S); \
		backup_name="$(BACKUP_DIR)/ha_config_$(_BACKUP_LABEL)_$$timestamp"; \
		tar -czf "$$backup_name.tar.gz" $(LOCAL_CONFIG_PATH); \
		echo "$(GREEN)Auto-backup created: $$backup_name.tar.gz$(NC)"; \
		$(MAKE) _rotate-backups; \
	fi

# Internal: rotate old backups beyond MAX_BACKUPS
_rotate-backups:
	@if [ -d "$(BACKUP_DIR)" ] && ls $(BACKUP_DIR)/ha_config_*.tar.gz 1>/dev/null 2>&1; then \
		count=$$(ls -1 $(BACKUP_DIR)/ha_config_*.tar.gz | wc -l | tr -d ' '); \
		if [ "$$count" -gt "$(MAX_BACKUPS)" ]; then \
			excess=$$((count - $(MAX_BACKUPS))); \
			echo "$(YELLOW)Rotating backups: removing $$excess old backup(s) (keeping $(MAX_BACKUPS))$(NC)"; \
			ls -1t $(BACKUP_DIR)/ha_config_*.tar.gz | tail -n "$$excess" | while read f; do \
				rm -f "$$f"; \
				echo "  Removed: $$f"; \
			done; \
		fi; \
	fi

# Development targets (not shown in help)
.PHONY: pull-storage push-storage validate-yaml validate-references validate-ha _auto-backup _rotate-backups

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

# Rsync exclude integration tests
test-rsync:
	@echo "$(GREEN)Running rsync exclude integration tests...$(NC)"
	@python3 -m pytest tests/test_rsync_excludes.py

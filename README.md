# Home Assistant Configuration Management with Claude Code

A comprehensive system for managing Home Assistant configurations with automated validation, testing, and deployment - all enhanced by Claude Code for natural language automation creation.

[![](https://github.com/user-attachments/assets/e4bb0179-a649-42d6-98f1-d8c29d5e84a3)](https://youtu.be/70VUzSw15-4)
Click to play

## 🌟 Features

- **🤖 AI-Powered Automation Creation**: Use Claude Code to write automations in plain English
- **🛡️ Multi-Layer Validation**: Comprehensive validation prevents broken configurations
- **🔄 Safe Deployments**: Pre-push validation blocks invalid configs from reaching HA
- **🔍 Entity Discovery**: Advanced tools to explore and search available entities
- **⚡ Automated Hooks**: Validation runs automatically on file changes
- **📊 Entity Registry Integration**: Real-time validation against your actual HA setup

## 📦 Easy Installation (For Beginners)

**New to command line tools? No problem!** We've made it super easy to get started.

### One-Click Setup Scripts

Download the project and run the setup script for your operating system:

#### **For Mac Users:**
1. Download or clone this repository ([quick tutorial](https://youtu.be/q9wc7hUrW8U?si=_eT7nL8R8xXec7hL))
2. Open Terminal and navigate to the project folder ([how to use Terminal on Mac](https://youtu.be/aj9QWELAv9o?si=jx5HexpF60q3ZxO4))
3. Run the setup script:
```bash
./setup-mac.sh
```

#### **For Windows Users:**
1. Download or clone this repository ([quick tutorial](https://youtu.be/q9wc7hUrW8U?si=_eT7nL8R8xXec7hL))
2. Open Command Prompt and navigate to the project folder ([how to use terminal on Win](https://youtu.be/8gUvxU7EoNE?si=BCgFIU8ng_ebhWaR))
3. Run the setup script:
```cmd
setup-windows.bat
```

### What the Scripts Do
- ✅ Check that you have all required software (Python, Git, etc.)
- ✅ Download and install Claude Code automatically if missing
- ✅ Install any missing dependencies automatically
- ✅ Set up the Python environment with all needed packages
- ✅ Guide you through the next steps

### After Setup
1. **Configure your Home Assistant connection** (the script will show you how)
2. **Open Claude Code** ([download here](https://claude.com/solutions/coding) if not installed) and navigate to your project folder
3. **Pull your configuration** by typing `make pull` in Claude Code
4. **Start creating automations** with Claude Code!

**That's it!** The scripts handle all the technical setup for you. Claude Code makes running commands super easy - just type them directly!

---

## 🚀 Quick Start (Advanced Users)

This repository provides a complete framework for managing Home Assistant configurations with Claude Code. Here's how it works:

### Repository Structure
- **Template Configs**: The `config/` folder contains sanitized example configurations (no secrets)
- **Validation Tools**: The `tools/` folder has all validation scripts
- **Management Commands**: The `Makefile` contains pull/push commands
- **Development Setup**: `pyproject.toml` and other dev files for tooling

### User Workflow

#### 1. Clone Repository
```bash
git clone git@github.com:philippb/claude-homeassistant.git
cd claude-homeassistant
make setup  # Creates Python venv and installs dependencies
```

#### 2. Configure Connection
Copy the example environment file and configure your settings:
```bash
cp .env.example .env
# Edit .env with your actual Home Assistant details
```

The `.env` file should contain:
```bash
# Home Assistant Configuration
HA_TOKEN=your_home_assistant_token
HA_URL=http://your_homeassistant_host:8123

# SSH Configuration for rsync operations
HA_HOST=your_homeassistant_host
HA_REMOTE_PATH=/config/

# Local Configuration (optional - defaults provided)
LOCAL_CONFIG_PATH=config/
BACKUP_DIR=backups
VENV_PATH=venv
TOOLS_PATH=tools
```

#### 2b. Set Up SSH Access to Home Assistant

**Required**: Install the [Advanced SSH & Web Terminal](https://github.com/hassio-addons/addon-ssh) add-on for Home Assistant, which provides SSH/SFTP access needed for the rsync operations in this project.

<details>
<summary><strong>Click to expand SSH setup instructions</strong></summary>

##### Generate SSH Key Pair (if you don't have one)

```bash
# Generate a new SSH key pair for Home Assistant
ssh-keygen -t ed25519 -f ~/.ssh/homeassistant -C "your-email@example.com"

# Verify the key files were created
ls -l ~/.ssh/homeassistant*
```

This creates:
- `~/.ssh/homeassistant` (private key - keep this secure)
- `~/.ssh/homeassistant.pub` (public key - this goes into HA)

##### Configure Advanced SSH & Web Terminal Add-on

1. Install the **Advanced SSH & Web Terminal** add-on in Home Assistant
2. Configure the add-on with this YAML configuration:

```yaml
username: root
password: ""
authorized_keys:
  - >-
    ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... your-email@example.com
sftp: true
compatibility_mode: false
allow_agent_forwarding: false
allow_remote_port_forwarding: false
allow_tcp_forwarding: false
```

**Important**: Replace the `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA...` line with the contents of your `~/.ssh/homeassistant.pub` file.

3. Start the add-on and ensure it's running

##### Configure SSH Client on Your Computer

Create or edit your SSH config file (`~/.ssh/config`):

```
# Home Assistant SSH Configuration
Host homeassistant
  HostName homeassistant.local  # or your HA IP address
  User root
  IdentityFile ~/.ssh/homeassistant
  StrictHostKeyChecking no
```

**Note**: Replace `homeassistant.local` with your Home Assistant's IP address if hostname resolution doesn't work.

##### Test SSH Connection

```bash
# Test the SSH connection
ssh homeassistant

# You should see:
# Welcome to the Home Assistant command line.
```

If successful, you can exit with `exit` or `Ctrl+D`.

</details>

#### 2c. Get Your Home Assistant Token

To get your `HA_TOKEN`:
1. Go to Home Assistant → Settings → People → Your Profile
2. Scroll to "Long-lived access tokens"
3. Click "Create Token"
4. Give it a name like "Claude Home Assistant"
5. Copy the token and paste it as `HA_TOKEN` value in your `.env` file

#### 3. Pull Your Real Configuration
```bash
make pull  # Downloads YOUR actual HA config, overwriting template files
```

**Important**: This step replaces the template `config/` folder with your real Home Assistant configuration files.

#### 4. Work with Your Configuration
- Edit your real configs locally with full validation
- Use Claude Code to create automations in natural language
- Validation hooks automatically check syntax and entity references

#### 5. Push Changes Back
```bash
make push  # Uploads changes back to your HA instance (with validation)
```

### How It Works

1. **Template Start**: You begin with example configs showing proper structure
2. **Real Data**: First `make pull` overwrites templates with your actual HA setup
3. **Local Development**: Edit real configs locally with validation safety
4. **Safe Deployment**: `make push` validates before uploading to prevent broken configs

This gives you a complete development environment while only modifying your HA instance when completed.

## ⚙️ Prerequisites

### Make Command

This project uses `make` commands for configuration management. If you don't have `make` installed:

**macOS:**
```bash
xcode-select --install  # Installs Command Line Tools including make
```

**Windows:**
- **Option 1**: Use WSL (Windows Subsystem for Linux) - recommended
- **Option 2**: Install via Chocolatey: `choco install make`
- **Option 3**: Use Git Bash (includes make)
- **Option 4**: Install MinGW-w64

**Alternative**: If you can't install `make`, you can run the underlying commands directly by checking the `Makefile` for the actual command syntax.

## 📁 Project Structure

```
├── config/                 # Home Assistant configuration files, downloaded from HA via script
│   ├── configuration.yaml
│   ├── automations.yaml
│   ├── scripts.yaml
│   └── .storage/          # Entity registry (pulled from HA)
├── tools/                 # Validation scripts for Claude
│   ├── run_tests.py       # Main test suite runner
│   ├── yaml_validator.py  # YAML syntax validation
│   ├── reference_validator.py # Entity reference validation
│   ├── ha_official_validator.py # Official HA validation
│   └── entity_explorer.py # Entity discovery tool
├── .claude-code/          # Claude Code project settings
│   ├── hooks/            # Automated validation hooks
│   └── settings.json     # Project configuration
├── .env.example          # Environment configuration template
├── venv/                 # Python virtual environment
├── Makefile              # Management commands
└── CLAUDE.md             # Claude Code instructions
```

## 🛠️ Available Commands

### Configuration Management
```bash
make pull      # Pull latest config from Home Assistant (auto-backup first)
make push      # Push local config to HA (with validation, auto-backup first)
make backup    # Create timestamped backup
make validate  # Run all validation tests
```

### Backup & Restore
```bash
make list-backups                    # List available backups with sizes
make restore                         # Restore most recent backup
make restore BACKUP=backups/file.tar.gz  # Restore specific backup
make pull SKIP_BACKUP=1              # Skip auto-backup (e.g., first run)
```

### Entity Discovery
```bash
make entities                           # Show entity summary
make entities ARGS='--domain climate'   # Climate entities only
make entities ARGS='--search motion'    # Search for motion sensors
make entities ARGS='--area kitchen'     # Kitchen entities only
make entities ARGS='--full'            # Complete detailed output
```

### Individual Validators
```bash
. venv/bin/activate
python tools/yaml_validator.py         # YAML syntax only
python tools/reference_validator.py    # Entity references only
python tools/ha_official_validator.py  # Official HA validation
```

## 🔧 Validation System

The system provides three layers of validation:

### 1. YAML Syntax Validation
- Validates YAML syntax with HA-specific tags (`!include`, `!secret`, `!input`)
- Checks file encoding (UTF-8 required)
- Validates basic HA file structures

### 2. Entity Reference Validation
- Verifies all entity references exist in your HA instance
- Checks device and area references
- Warns about disabled entities
- Extracts entities from Jinja2 templates

### 3. Official HA Validation
- Uses Home Assistant's own validation tools
- Most comprehensive check available
- Catches integration-specific issues

## 🤖 Claude Code Integration

### Automated Validation Hooks

Two hooks ensure configuration safety:

1. **Post-Edit Hook**: Runs validation after editing YAML files
2. **Pre-Push Hook**: Validates before syncing to HA (blocks if invalid)

### Entity Naming Convention

This system supports standardized entity naming:

**Format: `location_room_device_sensor`**

Examples:
```
binary_sensor.home_basement_motion_battery
media_player.office_kitchen_sonos
climate.home_living_room_heatpump
```

### Natural Language Automation Creation

With Claude Code, you can:

1. **Describe automations in English**:
   ```
   "Turn off all lights at midnight on weekdays"
   ```

2. **Claude writes the YAML**:
   ```yaml
   - id: weekday_midnight_lights_off
     alias: "Weekday Midnight Lights Off"
     trigger:
       - platform: time
         at: "00:00:00"
     condition:
       - condition: time
         weekday: [mon, tue, wed, thu, fri]
     action:
       - service: light.turn_off
         target:
           entity_id: all
   ```

3. **Automatic validation ensures correctness**
4. **Deploy safely with `make push`**

## 📊 Entity Discovery

The entity explorer helps you understand what's available:

```bash
# Find all motion sensors
. venv/bin/activate && python tools/entity_explorer.py --search motion

# Show all climate controls
. venv/bin/activate && python tools/entity_explorer.py --domain climate

# Kitchen devices only
. venv/bin/activate && python tools/entity_explorer.py --area kitchen
```

## 🔒 Security & Best Practices

- **Secrets Management**: `secrets.yaml` is excluded from validation
- **SSH Authentication**: Uses SSH keys for secure HA access
- **No Credentials Stored**: Repository contains no sensitive data
- **Pre-Push Validation**: Prevents broken configs from reaching HA
- **Backup System**: Automatic timestamped backups before changes

## 🐛 Troubleshooting

### Build Error: lru-dict or Other C Extensions (macOS)
If you see errors like `Building wheel for lru-dict... error` during `make setup`, you likely have an old Python version from Xcode Command Line Tools.

**Solution**: Install Python 3.12+ via Homebrew:
```bash
brew install python@3.12
export PATH="/opt/homebrew/bin:$PATH"
```
Then run `make setup` again. Home Assistant 2024.x requires Python 3.12+.

### Validation Errors
1. Check YAML syntax first: `. venv/bin/activate && python tools/yaml_validator.py`
2. Verify entity references: `. venv/bin/activate && python tools/reference_validator.py`
3. Check HA logs if official validation fails

### SSH Connection Issues

<details>
<summary><strong>Click to expand SSH troubleshooting</strong></summary>

#### Common SSH Problems and Solutions

1. **Connection refused or timeout**:
   ```bash
   # Test if the SSH add-on is running
   ssh homeassistant
   # If this fails, check if the Advanced SSH & Web Terminal add-on is started in HA
   ```

2. **Permission denied (publickey)**:
   ```bash
   # Check SSH key permissions
   chmod 600 ~/.ssh/homeassistant
   chmod 644 ~/.ssh/homeassistant.pub

   # Verify your public key is correctly added to the HA SSH add-on config
   cat ~/.ssh/homeassistant.pub
   ```

3. **Host key verification failed**:
   ```bash
   # Remove old host key and try again
   ssh-keygen -R homeassistant.local
   # Or if using IP address:
   ssh-keygen -R 192.168.1.100
   ```

4. **SSH config issues**:
   ```bash
   # Test connection with verbose output
   ssh -v homeassistant

   # Check your SSH config
   cat ~/.ssh/config
   ```

5. **Advanced SSH & Web Terminal not responding**:
   - Restart the add-on in Home Assistant
   - Check Home Assistant logs for SSH add-on errors
   - Verify the add-on configuration YAML is valid

#### Verifying Your Setup

Run these commands to verify everything is configured correctly:

```bash
# 1. Check SSH key files exist and have correct permissions
ls -la ~/.ssh/homeassistant*

# 2. Check SSH config
grep -A 5 "Host homeassistant" ~/.ssh/config

# 3. Test SSH connection
ssh homeassistant "ls /config"

# 4. Test rsync (what make pull/push uses)
rsync -avz --dry-run homeassistant:/config/ ./test/
```

</details>

### Missing Dependencies
```bash
. venv/bin/activate
pip install homeassistant voluptuous pyyaml jsonschema requests
```

## 🔧 Configuration

### Environment Variables
Configure via `.env` file in project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Available variables:
```bash
# Home Assistant Configuration
HA_TOKEN=your_home_assistant_token       # HA API token
HA_URL=http://your_homeassistant_host:8123  # HA instance URL

# SSH Configuration for rsync operations
HA_HOST=your_homeassistant_host          # SSH hostname for HA
HA_REMOTE_PATH=/config/                  # Remote config path

# Local Configuration (optional - defaults provided)
LOCAL_CONFIG_PATH=config/                # Local config directory
BACKUP_DIR=backups                       # Backup directory
VENV_PATH=venv                          # Python virtual environment path
TOOLS_PATH=tools                        # Tools directory

# Backup Configuration (optional)
MAX_BACKUPS=5                           # Max backups to retain (oldest auto-deleted)
```

### Claude Code Settings
Located in `.claude-code/settings.json`:
```json
{
  "hooks": {
    "enabled": true,
    "posttooluse": [".claude-code/hooks/posttooluse-ha-validation.sh"],
    "pretooluse": [".claude-code/hooks/pretooluse-ha-push-validation.sh"]
  },
  "validation": {
    "enabled": true,
    "auto_run": true,
    "block_invalid_push": true
  }
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all validations pass
5. Submit a pull request

## 📄 License

Apache 2.0

## 🙏 Acknowledgments

- [Home Assistant](https://home-assistant.io) for the amazing platform
- [Claude Code](https://claude.ai) for AI-powered development
- The HA community for validation best practices

---

**Ready to revolutionize your Home Assistant automation workflow?** Start by describing what you want in plain English and let Claude Code handle the rest! 🚀

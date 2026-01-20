@echo off
setlocal enabledelayedexpansion

REM Home Assistant Configuration Management - Windows Setup Script
REM This script checks prerequisites and sets up your environment

echo.
echo ========================================================
echo   Home Assistant Configuration Management - Windows Setup
echo ========================================================
echo.

REM ===============================
REM Phase 1: Check All Prerequisites
REM ===============================
echo Checking prerequisites...
echo.

set MISSING_REQUIRED=0
set MISSING_OPTIONAL=0
set MISSING_LIST=

REM --- Check Git ---
set GIT_OK=0
where git >nul 2>&1
if errorlevel 1 (
    REM Try common Git installation paths
    if exist "C:\Program Files\Git\cmd\git.exe" (
        set "PATH=%PATH%;C:\Program Files\Git\cmd"
        echo [OK] Git (found in Program Files)
        set GIT_OK=1
    ) else if exist "C:\Program Files (x86)\Git\cmd\git.exe" (
        set "PATH=%PATH%;C:\Program Files (x86)\Git\cmd"
        echo [OK] Git (found in Program Files x86)
        set GIT_OK=1
    ) else (
        echo [MISSING] Git - REQUIRED
        set MISSING_REQUIRED=1
        set "MISSING_LIST=!MISSING_LIST!  - Git: https://git-scm.com/download/win\n"
    )
) else (
    echo [OK] Git
    set GIT_OK=1
)

REM --- Check Make ---
set MAKE_OK=0
make --version >nul 2>&1
if errorlevel 1 (
    REM Try Git Bash location
    if exist "C:\Program Files\Git\usr\bin\make.exe" (
        set "PATH=%PATH%;C:\Program Files\Git\usr\bin"
        echo [OK] Make (found in Git Bash)
        set MAKE_OK=1
    ) else if exist "C:\Program Files (x86)\Git\usr\bin\make.exe" (
        set "PATH=%PATH%;C:\Program Files (x86)\Git\usr\bin"
        echo [OK] Make (found in Git Bash x86)
        set MAKE_OK=1
    ) else (
        echo [MISSING] Make - REQUIRED
        set MISSING_REQUIRED=1
        set "MISSING_LIST=!MISSING_LIST!  - Make: Use Git Bash, or install via: choco install make\n"
    )
) else (
    echo [OK] Make
    set MAKE_OK=1
)

REM --- Check Node.js (needed for Claude Code CLI) ---
set NODE_OK=0
node --version >nul 2>&1
if errorlevel 1 (
    echo [MISSING] Node.js - REQUIRED for Claude Code CLI
    set MISSING_REQUIRED=1
    set "MISSING_LIST=!MISSING_LIST!  - Node.js: https://nodejs.org/en/download/\n"
) else (
    for /f "tokens=1 delims= " %%i in ('node --version 2^>nul') do set NODE_VERSION=%%i
    echo [OK] Node.js !NODE_VERSION!
    set NODE_OK=1
)

REM --- Check Claude Code CLI ---
set CLAUDE_OK=0
where claude >nul 2>&1
if errorlevel 1 (
    echo [MISSING] Claude Code CLI - REQUIRED
    set MISSING_OPTIONAL=1
) else (
    echo [OK] Claude Code CLI
    set CLAUDE_OK=1
)

echo.

REM ===============================
REM Phase 2: Report Missing Dependencies
REM ===============================
if %MISSING_REQUIRED%==1 (
    echo ========================================================
    echo   MISSING REQUIRED DEPENDENCIES
    echo ========================================================
    echo.
    echo The following tools must be installed before continuing:
    echo.
    if %PYTHON_OK%==0 (
        echo   [X] Python
        echo       Download: https://www.python.org/downloads/
        echo       IMPORTANT: Check "Add Python to PATH" during installation
        echo.
    )
    if %GIT_OK%==0 (
        echo   [X] Git
        echo       Download: https://git-scm.com/download/win
        echo       Includes Git Bash which provides Unix-like tools
        echo.
    )
    if %MAKE_OK%==0 (
        echo   [X] Make
        echo       Option 1: Use Git Bash instead of CMD (recommended)
        echo       Option 2: Install Chocolatey, then: choco install make
        echo       Option 3: Install WSL: wsl --install
        echo.
    )
    if %NODE_OK%==0 (
        echo   [X] Node.js
        echo       Download: https://nodejs.org/en/download/
        echo       Required to install Claude Code CLI
        echo.
    )
    echo ========================================================
    echo.
    echo Please install the missing dependencies and re-run this script.
    echo.
    echo TIP: For the best experience on Windows, use Git Bash instead
    echo      of Command Prompt. Git Bash includes make and other tools.
    echo.
    pause
    exit /b 1
)

REM ===============================
REM Phase 3: Check Claude Code CLI
REM ===============================
if %CLAUDE_OK%==0 (
    echo ========================================================
    echo   CLAUDE CODE CLI NOT FOUND
    echo ========================================================
    echo.
    echo Claude Code CLI is required but not installed.
    echo.
    echo To install Claude Code CLI, run this command:
    echo.
    echo     npm install -g @anthropic-ai/claude-code
    echo.
    echo After installation:
    echo   1. Close and reopen your terminal
    echo   2. Run: claude --version
    echo   3. Re-run this setup script
    echo.
    echo Note: You need a Claude Pro/Max subscription or API access.
    echo Visit https://claude.com/solutions/coding for details.
    echo.
    pause
    exit /b 0
)

echo All prerequisites found!
echo.

REM ===============================
REM Phase 4: Project Setup
REM ===============================
echo Verifying Python environment...

REM Verify critical dependencies are importable
set VERIFY_FAILED=0

uv run python -c "import yaml" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyYAML not installed correctly
    set VERIFY_FAILED=1
)

uv run python -c "import voluptuous" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Voluptuous not installed correctly
    set VERIFY_FAILED=1
)

uv run python -c "import jsonschema" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] jsonschema not installed correctly
    set VERIFY_FAILED=1
)

uv run python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] requests not installed correctly
    set VERIFY_FAILED=1
)

if %VERIFY_FAILED%==1 (
    echo.
    echo [WARNING] Some dependencies failed to install. Try running:
    echo    uv sync
    echo.
) else (
    echo [OK] All Python dependencies verified
)

echo.
echo ========================================================
echo   Home Assistant Configuration
echo ========================================================
echo.
echo Let's configure your Home Assistant connection!
echo.

REM Get Home Assistant host
:get_host
set /p HA_HOST="Enter your Home Assistant hostname or IP address (e.g., homeassistant.local or 192.168.1.100): "
if "%HA_HOST%"=="" (
    echo [ERROR] Hostname/IP cannot be empty
    goto get_host
)

REM Get SSH username
:get_user
set /p HA_USER="Enter the SSH username for Home Assistant (default: root): "
if "%HA_USER%"=="" (
    set HA_USER=root
)
echo Using SSH user: %HA_USER%

echo.
echo Testing connection to %HA_HOST%...
ping -n 1 %HA_HOST% >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Cannot reach %HA_HOST% - please verify the address
    set /p continue_setup="Continue anyway? (y/N): "
    if /i not "!continue_setup!"=="y" (
        echo Setup cancelled. Please check your Home Assistant address and try again.
        pause
        exit /b 1
    )
) else (
    echo [OK] Host %HA_HOST% is reachable
)

echo.
echo SSH Configuration
echo ===================
echo.
echo For secure access, this tool uses SSH keys. Do you have SSH access configured?
echo.
echo Options:
echo 1. I already have SSH key access configured
echo 2. I need help setting up SSH keys
echo 3. Skip SSH setup for now (manual configuration later)
echo.
set /p ssh_option="Choose option (1-3): "

if "%ssh_option%"=="1" (
    echo.
    echo Testing SSH connection to %HA_USER%@%HA_HOST%...
    REM Test SSH connection
    ssh -o ConnectTimeout=5 -o BatchMode=yes %HA_USER%@%HA_HOST% exit >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] SSH connection failed
        echo.
        echo Please check your SSH configuration and try again.
        echo Common issues:
        echo   - SSH keys not added to Home Assistant
        echo   - Incorrect hostname/IP or username
        echo   - SSH addon not enabled in Home Assistant
        echo   - Firewall blocking port 22
        set SSH_CONFIGURED=false
    ) else (
        echo [OK] SSH connection successful!
        set SSH_CONFIGURED=true
    )
) else if "%ssh_option%"=="2" (
    echo.
    echo SSH Setup Help
    echo =================
    echo.
    echo To set up SSH access to Home Assistant:
    echo.
    echo 1. Install the 'SSH ^& Web Terminal' add-on in Home Assistant
    echo    Settings -^> Add-ons -^> Add-on Store -^> Search "SSH"
    echo.
    echo 2. Generate an SSH key pair if you don't have one:
    echo    ssh-keygen -t ed25519 -C "your-email@example.com"
    echo.
    echo 3. Copy your public key to Home Assistant:
    echo    - View your key: type %USERPROFILE%\.ssh\id_ed25519.pub
    echo    - Add it to the SSH addon's "authorized_keys" setting
    echo.
    echo 4. Test the connection:
    echo    ssh %HA_USER%@%HA_HOST%
    echo.
    echo For detailed instructions, visit:
    echo https://github.com/home-assistant/addons/blob/master/ssh/DOCS.md
    echo.
    echo TIP: On Windows, Git Bash or WSL provide better SSH support.
    echo.
    set SSH_CONFIGURED=false
) else if "%ssh_option%"=="3" (
    echo.
    echo [INFO] Skipping SSH setup - you can configure this later
    set SSH_CONFIGURED=false
) else (
    echo Invalid option. Skipping SSH setup.
    set SSH_CONFIGURED=false
)

echo.
echo ========================================================
echo   Setup Complete!
echo ========================================================
echo.
echo Configuration Summary:
echo   - Home Assistant Host: %HA_HOST%
echo   - SSH User: %HA_USER%
if "%SSH_CONFIGURED%"=="true" (
    echo   - SSH Access: [OK] Configured and tested
) else (
    echo   - SSH Access: [!] Needs configuration
)
echo.
echo Next steps:
if "%SSH_CONFIGURED%"=="true" (
    echo   1. Pull your configuration:  task pull
    echo   2. Start Claude Code:        claude
    echo   3. Ask Claude to help with your Home Assistant!
) else (
    echo   1. Complete SSH setup (see instructions above)
    echo   2. Pull your configuration:  task pull
    echo   3. Start Claude Code:        claude
)
echo.
echo --------------------------------------------------------
echo TIP: Use Git Bash instead of CMD for best compatibility
echo --------------------------------------------------------
echo.
echo Documentation: README.md
echo Issues: https://github.com/philippb/claude-homeassistant/issues
echo.
pause

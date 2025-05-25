# QBittorrent智能下载助手启动脚本 (PowerShell版本)
# 设置编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 设置颜色函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Write-Step {
    param(
        [int]$StepNum,
        [int]$TotalSteps,
        [string]$Message
    )
    Write-ColorOutput "[$StepNum/$TotalSteps] $Message" "Cyan"
}

function Write-Success {
    param([string]$Message)
    Write-ColorOutput "✅ $Message" "Green"
}

function Write-Error {
    param([string]$Message)
    Write-ColorOutput "❌ $Message" "Red"
}

function Write-Warning {
    param([string]$Message)
    Write-ColorOutput "⚠️ $Message" "Yellow"
}

function Write-Info {
    param([string]$Message)
    Write-ColorOutput "💡 $Message" "Blue"
}

# 主程序
try {
    Write-Host ""
    Write-ColorOutput "==========================================" "Magenta"
    Write-ColorOutput "🚀 QBittorrent智能下载助手启动脚本" "Magenta"
    Write-ColorOutput "==========================================" "Magenta"
    Write-Host ""

    $VenvDir = "venv"
    $TotalSteps = 8

    # 步骤1: 检查Python
    Write-Step 1 $TotalSteps "检查Python环境..."
    $PythonCmd = $null
    
    # 尝试不同的Python命令
    $PythonCommands = @("python", "python3", "py")
    foreach ($cmd in $PythonCommands) {
        try {
            $version = & $cmd --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                $PythonCmd = $cmd
                Write-Success "找到Python: $version (命令: $cmd)"
                break
            }
        } catch {
            continue
        }
    }

    if (-not $PythonCmd) {
        Write-Error "未找到Python，请先安装Python 3.8+"
        Write-Info "下载地址: https://www.python.org/downloads/"
        Read-Host "按任意键退出"
        exit 1
    }

    # 步骤2: 检查虚拟环境
    Write-Step 2 $TotalSteps "检查虚拟环境..."
    if (-not (Test-Path $VenvDir)) {
        Write-Info "创建虚拟环境..."
        & $PythonCmd -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) {
            Write-Error "创建虚拟环境失败"
            Read-Host "按任意键退出"
            exit 1
        }
        Write-Success "虚拟环境创建完成"
    } else {
        Write-Success "虚拟环境已存在"
    }

    # 步骤3: 激活虚拟环境
    Write-Step 3 $TotalSteps "激活虚拟环境..."
    $ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
    if (Test-Path $ActivateScript) {
        & $ActivateScript
        Write-Success "虚拟环境已激活"
    } else {
        Write-Error "找不到虚拟环境激活脚本"
        Read-Host "按任意键退出"
        exit 1
    }

    # 步骤4: 升级pip
    Write-Step 4 $TotalSteps "升级pip..."
    python -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Success "pip已升级"
    } else {
        Write-Warning "pip升级失败，继续..."
    }

    # 步骤5: 安装依赖
    Write-Step 5 $TotalSteps "检查和安装依赖..."
    if (Test-Path "requirements.txt") {
        Write-Info "安装依赖包..."
        python -m pip install -r requirements.txt --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "静默安装失败，尝试详细安装..."
            python -m pip install -r requirements.txt
            if ($LASTEXITCODE -ne 0) {
                Write-Error "依赖安装失败"
                Read-Host "按任意键退出"
                exit 1
            }
        }
        Write-Success "依赖安装完成"
    } else {
        Write-Warning "未找到requirements.txt，安装基础依赖..."
        python -m pip install aiohttp pyperclip watchdog tenacity --quiet
    }

    # 步骤6: 检查配置文件
    Write-Step 6 $TotalSteps "检查配置文件..."
    $ConfigFile = "qbittorrent_monitor\config.json"
    if (-not (Test-Path $ConfigFile)) {
        Write-Error "配置文件不存在: $ConfigFile"
        Write-Info "请确保配置文件存在并配置正确"
        Read-Host "按任意键退出"
        exit 1
    }
    Write-Success "配置文件检查完成"

    # 步骤7: 显示启动信息
    Write-Step 7 $TotalSteps "准备启动..."
    Write-Host ""
    Write-ColorOutput "==========================================" "Yellow"
    Write-ColorOutput "📋 启动信息:" "Yellow"
    Write-ColorOutput "   🐍 Python命令: $PythonCmd" "White"
    Write-ColorOutput "   📁 虚拟环境: $VenvDir" "White"
    Write-ColorOutput "   📄 配置文件: $ConfigFile" "White"
    Write-ColorOutput "   🚀 启动方式: python start.py" "White"
    Write-ColorOutput "==========================================" "Yellow"
    Write-Host ""

    # 步骤8: 启动程序
    Write-Step 8 $TotalSteps "启动程序..."
    Write-Host ""
    Write-ColorOutput "🎯 正在启动QBittorrent智能下载助手..." "Green"
    Write-ColorOutput "💡 使用 Ctrl+C 安全退出程序" "Blue"
    Write-Host ""
    
    # 启动程序
    python start.py

} catch {
    Write-Error "脚本执行出错: $($_.Exception.Message)"
    Write-Host $_.ScriptStackTrace
} finally {
    Write-Host ""
    Write-Info "程序已退出，按任意键关闭窗口..."
    Read-Host
} 
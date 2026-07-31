# OAIW 7 Agent 多CLI窗口团队启动器
# 为每个角色启动一个独立的 Claude Code CLI 窗口

$RootDir = "D:\OAIW"
$AgentsFile = "$RootDir\.team\agents.json"
$Roles = @('pm', 'fe', 'be', 'rpa', 'biz', 'ai', 'qa')
$Icons = @('👔', '🎨', '⚙️', '🤖', '📊', '🧠', '🧪')

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " OAIW 7 Agent 多CLI窗口团队 启动器" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 读取 agents.json
$AgentsJson = Get-Content $AgentsFile -Raw -Encoding UTF8
if (-not $AgentsJson) {
    Write-Host "❌ 无法读取 agents.json" -ForegroundColor Red
    exit 1
}

$agents = $AgentsJson | ConvertFrom-Json

# 为每个角色生成 agent JSON 并启动独立窗口
for ($i = 0; $i -lt $Roles.Length; $i++) {
    $role = $Roles[$i]
    $icon = $Icons[$i]
    $agent = $agents.$role

    if (-not $agent) {
        Write-Host "  ⚠️ 找不到 $role 的配置" -ForegroundColor Yellow
        continue
    }

    # 构建单个角色的 agents JSON
    $singleAgentJson = @{
        $role = @{
            description = $agent.description
            prompt = $agent.prompt
        }
    } | ConvertTo-Json -Compress -Depth 10

    # 转义 JSON 中的引号以便作为命令行参数传递
    # 注意：PowerShell 的 Start-Process 传参需要小心
    # 用 -ArgumentList 传数组更可靠
    $agentArg = $singleAgentJson -replace '"', '\"'

    $title = "OAIW $icon $role"

    # 构建启动脚本（写入临时文件以避免命令行长度和转义问题）
    $launcherScript = @"
`$env:CLAUDE_CODE_SIMPLE = "1"
Set-Location '$RootDir'
Write-Host '╔══════════════════════════════════════════╗' -ForegroundColor Cyan
Write-Host '║  OAIW $icon $role' -ForegroundColor Cyan
Write-Host '╚══════════════════════════════════════════╝' -ForegroundColor Cyan
Write-Host ''
Write-Host '等待PM分配任务中...' -ForegroundColor Yellow
Write-Host '任务文件目录: .team\tasks\' -ForegroundColor DarkGray
Write-Host '提示: 用 Get-ChildItem .team\tasks\ 查看新任务' -ForegroundColor DarkGray
Write-Host ''
claude --agent '$role' --agents '$singleAgentJson'
"@

    $launcherPath = "$RootDir\.team\launch_$role.ps1"
    $launcherScript | Set-Content $launcherPath -Encoding UTF8

    Start-Process powershell -ArgumentList @(
        '-NoExit',
        '-ExecutionPolicy', 'Bypass',
        '-File', $launcherPath
    ) -WindowStyle Normal

    Start-Sleep -Milliseconds 800
    Write-Host "  ✅ $icon $role ($role) 窗口已启动" -ForegroundColor Green
}

Write-Host ""
Write-Host "所有 Agent 窗口已启动！" -ForegroundColor Green
Write-Host "你现在在本窗口以 👔 PM 身份与团队协作。" -ForegroundColor Cyan
Write-Host ""
Write-Host "提示：每个Agent窗口都有独立标题栏显示角色图标，一目了然" -ForegroundColor DarkGray

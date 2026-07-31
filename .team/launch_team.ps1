# OAIW 7 Agent 多CLI窗口团队启动器
# 用 Start-Process 数组传参避免引号转义问题

$RootDir = "D:\OAIW"
$AgentsFile = "$RootDir\.team\agents.json"

# 读取 agents.json
$AgentsJson = Get-Content $AgentsFile -Raw -Encoding UTF8
$agents = $AgentsJson | ConvertFrom-Json

$Roles = @('pm', 'fe', 'be', 'rpa', 'biz', 'ai', 'qa')
$Icons = @('PM', 'FE', 'BE', 'RPA', 'Biz', 'AI', 'QA')

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " OAIW 7 Agent Team Launcher" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

for ($i = 0; $i -lt $Roles.Length; $i++) {
    $role = $Roles[$i]
    $icon = $Icons[$i]
    $agent = $agents.$role

    # 构建单个角色的 agents JSON
    $single = @{
        $role = @{
            description = $agent.description
            prompt = $agent.prompt
        }
    }
    $jsonStr = $single | ConvertTo-Json -Compress -Depth 10 -EscapeHandling EscapeNonAscii

    # 用 -ArgumentList 数组传参，避免引号转义
    $claudeArgs = @(
        '--agent', $role,
        '--agents', $jsonStr,
        '--bare'
    )

    Start-Process -WindowStyle Normal -FilePath claude -ArgumentList $claudeArgs -WorkingDirectory $RootDir
    Start-Sleep -Seconds 2
    Write-Host "  [OK] $icon window launched" -ForegroundColor Green
}

Write-Host ""
Write-Host "All 7 Agent windows launched!" -ForegroundColor Green
Write-Host "You (PM) are in this window. Tell me the requirements!" -ForegroundColor Yellow

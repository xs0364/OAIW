$env:CLAUDE_CODE_SIMPLE = "1"
Set-Location "D:\OAIW"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OAIW Agent - RPA" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Waiting for PM tasks..." -ForegroundColor Yellow
Write-Host "Tasks: .team\tasks\" -ForegroundColor DarkGray
Write-Host ""
$b64 = "eyJycGEiOiB7ImRlc2NyaXB0aW9uIjogIlJQQeiHquWKqOWMluW3peeoi+W4iCDigJQgUGxheXdyaWdodCArIE9wZW5DViArIOa4r+WPo+mpseWKqCIsICJwcm9tcHQiOiAi5L2g5piv44CQT0FJVyBSUEHoh6rliqjljJblt6XnqIvluIggUlBBIPCfpJbjgJHjgIJcblxuIyMg6IGM6LSjXG4tIFBsYXl3cmlnaHQg5rWP6KeI5Zmo6Ieq5Yqo5YyWICsg5riv5Y+j5p+l6K+i6amx5YqoXG4tIOi0n+i0oyBiYWNrZW5kL3JwYS9wb3J0cy/vvIjom4flj6Mv55uQ55SwL+mdkuWymy/lroHms6LmuK/vvIlcblxuIyMg5b2T5YmN5pSv5oyB55qE5riv5Y+jXG58IOa4r+WPoyB8IOaWueazlSB8IOmqjOivgeeggSB8XG58LS0tLS0tfC0tLS0tLXwtLS0tLS0tLXxcbnwg6JuH5Y+jIHwgUGxheXdyaWdodCB8IOaWh+Wtl+eCuemAiShOSU0gVmlzaW9uKSB8XG58IOebkOeUsCB8IFBsYXl3cmlnaHQgfCBwYXNzcG9ydOeZu+W9lSB8XG58IOmdkuWymyB8IFBsYXl3cmlnaHQgfCBkZGRkb2Ny5Zu+5b2i6aqM6K+B56CBIHxcbnwg5a6B5rOiIHwgSFRUUCBBUEkgfCDpooTphY10b2tlbiB8XG5cbiMjIOaKgOacr+agiFxuLSBQbGF5d3JpZ2h0IChzeW5jICsgYXN5bmNpby50b190aHJlYWQpIC8gT3BlbkNWIC8gTklNIFZpc2lvbiAvIGRkZGRvY3Jcbi0gSEVBRExFU1M9RmFsc2XvvIjmnInlpLTmqKHlvI/vvIlcbi0g55m75b2V5oCB5a2YICpfYXV0aF9zdGF0ZS5qc29uXG5cbiMjIOWNj+S9nOaooeW8j1xuLSDwn5OlIOivuyAudGVhbVxcdGFza3NcXCDojrflj5bku7vliqFcbi0g8J+TpCDlhpkgLnRlYW1cXHJlc3VsdHNcXDxJRD5fcnBhX2RvbmUuanNvblxuLSDwn5OLIOivuyAudGVhbVxcY29udGV4dC5qc29uXG4tIPCfp6og6ZyA6KaB5rWL6K+V5pe26YCa55+lIFFB77ya5YaZIC50ZWFtXFx0YXNrc1xcPElEPl9xYS5qc29uIn19"
$json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64))
claude --agent "rpa" --agents $json

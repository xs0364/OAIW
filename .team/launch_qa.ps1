$env:CLAUDE_CODE_SIMPLE = "1"
Set-Location "D:\OAIW"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OAIW Agent - QA" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Waiting for PM tasks..." -ForegroundColor Yellow
Write-Host "Tasks: .team\tasks\" -ForegroundColor DarkGray
Write-Host ""
$b64 = "eyJxYSI6IHsiZGVzY3JpcHRpb24iOiAiUUHmtYvor5Xlt6XnqIvluIgg4oCUIEFQSea1i+ivlSArIOWbnuW9kua1i+ivlSArIOi+ueeVjOa1i+ivlSIsICJwcm9tcHQiOiAi5L2g5piv44CQT0FJVyBRQea1i+ivleW3peeoi+W4iCBRQSDwn6eq44CR44CCXG5cbiMjIOiBjOi0o1xuLSDlhajpk77ot6/mtYvor5XjgIHlm57lvZLmtYvor5XjgIHovrnnlYzmtYvor5VcblxuIyMg5rWL6K+V6IyD5Zu0XG4jIyMgQVBJ5rWL6K+VXG4tIGJhY2tlbmQvY29yZS9yb3V0ZXJzLyDkuIvmiYDmnInnq6/ngrlcbi0g5q2j5bi45rWB56iLICsg6ZSZ6K+v5Y+C5pWwICsg6L6555WM5YC8ICsgQXV0aOmqjOivgVxuXG4jIyMg5riv5Y+j5Zue5b2S5rWL6K+VXG4tIOibh+WPozog55m75b2V4oaS6aqM6K+B56CB4oaS5p+l5p+c4oaS57uT5p6c6Kej5p6QXG4tIOebkOeUsDogcGFzc3BvcnTnmbvlvZXihpLmn6Xmn5xcbi0g6Z2S5bKbOiBkZGRkb2Ny4oaS5p+l5p+cXG4tIOWugeazojogQVBJ6LCD55SoXG5cbiMjIyBSUEHlvJXmk47mtYvor5Vcbi0gL3JwYS9ydW4gKyAvcnBhL3J1bi9zdHJlYW1cbi0g55m75b2V5oCB6L+H5pyf4oaS6YeN5paw55m75b2VXG5cbiMjIyDliY3lj7Dlip/og73mtYvor5XvvIhQbGF5d3JpZ2h077yJXG4tIFJQQemhtemdolNTReaXpeW/lyAvIEFJ5aSa5rig6YGT5YiH5o2iIC8g6L+Q5Lu36aG16Z2iXG5cbiMjIOWNj+S9nOaooeW8j1xuLSDwn5OlIOivuyAudGVhbVxcdGFza3NcXCDojrflj5bmtYvor5Xku7vliqFcbi0g8J+TpCDlhpkgLnRlYW1cXHJlc3VsdHNcXDxJRD5fcWFfZG9uZS5qc29u77yI5ZCr5rWL6K+V5oql5ZGK77yJXG4tIPCfk4sg6K+7IC50ZWFtXFxjb250ZXh0Lmpzb25cbi0gUE3liIbphY3mtYvor5Xku7vliqHlkI7miY3ku4vlhaVcbi0g5Y+R546wYnVn5YaZIC50ZWFtXFx0YXNrc1xcIOe7meWvueW6lOinkuiJsuS/ruWkjSJ9fQ=="
$json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64))
claude --agent "qa" --agents $json

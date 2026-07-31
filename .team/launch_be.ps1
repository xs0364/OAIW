$env:CLAUDE_CODE_SIMPLE = "1"
Set-Location "D:\OAIW"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OAIW Agent - BE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Waiting for PM tasks..." -ForegroundColor Yellow
Write-Host "Tasks: .team\tasks\" -ForegroundColor DarkGray
Write-Host ""
$b64 = "eyJiZSI6IHsiZGVzY3JpcHRpb24iOiAi5ZCO56uv5bel56iL5biIIOKAlCBGYXN0QVBJICsgU1FMQWxjaGVteSArIFB5dGhvbiIsICJwcm9tcHQiOiAi5L2g5piv44CQT0FJVyDlkI7nq6/lt6XnqIvluIggQkUg4pqZ77iP44CR44CCXG5cbiMjIOiBjOi0o1xuLSDmiYDmnIkgRmFzdEFQSSDlkI7nq6/lvIDlj5Hlkoznu7TmiqRcbi0gYmFja2VuZC9jb3JlL3JvdXRlcnMvKi5weeOAgWNvbmZpZy5weeOAgWRhdGFiYXNlLnB544CBbWFpbi5weVxuLSBSUEEg5byV5pOO5bGCIGJhY2tlbmQvcnBhL19faW5pdF9fLnB5XG5cbiMjIOW3suefpei3r+eUsVxufCDot6/lvoQgfCDlip/og70gfFxufC0tLS0tLXwtLS0tLS18XG58IC9hcGkvYXV0aC8qIHwg55So5oi36K6k6K+BIHxcbnwgL2FwaS91c2VycyB8IOeUqOaIt+euoeeQhiB8XG58IC9hcGkvcnBhL3J1blsvc3RyZWFtXSB8IFJQQeS7u+WKoSB8XG58IC9hcGkvc2V0dGluZ3MvKiB8IOezu+e7n+iuvue9riB8XG58IC9hcGkvY2hhdC8qIHwgQUnogYrlpKkgfFxuXG4jIyDlhbPplK7nuqbmnZ9cbi0gUHl0aG9uIDMuMTQ6IFJQQeeUqCBhc3luY2lvLnRvX3RocmVhZCgpICsgc3luY19wbGF5d3JpZ2h0XG4tIFNTReerr+eCueWFvOWuuemXrumimOazqOaEj+WJjeerr1Byb3h55Luj55CGXG4tIOS/ruaUuSBycGEvX19pbml0X18ucHkg5ZCO6ZyA5riFIF9fcHljYWNoZV9fIOmHjeWQr1xuXG4jIyDljY/kvZzmqKHlvI9cbi0g8J+TpSDor7sgLnRlYW1cXHRhc2tzXFwg6I635Y+W5Lu75YqhXG4tIPCfk6Qg5YaZIC50ZWFtXFxyZXN1bHRzXFw8SUQ+X2JlX2RvbmUuanNvbiDlm57miqVcbi0g8J+TiyDor7sgLnRlYW1cXGNvbnRleHQuanNvblxuLSDwn5SEIOmcgOmFjeWQiOaXtuWGmSAudGVhbVxcdGFza3NcXCDnu5nlhbbku5bop5LoibJcbi0g6YeN5ZCv5ZCO56uv5ZG95LukOiBjZCBEOi9PQUlXICYmIHB5dGhvbiAtbSB1dmljb3JuIGJhY2tlbmQubWFpbjphcHAgLS1ob3N0IDAuMC4wLjAgLS1wb3J0IDc5OTkgLS1yZWxvYWQifX0="
$json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64))
claude --agent "be" --agents $json

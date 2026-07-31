$env:CLAUDE_CODE_SIMPLE = "1"
Set-Location "D:\OAIW"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OAIW Agent - BIZ" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Waiting for PM tasks..." -ForegroundColor Yellow
Write-Host "Tasks: .team\tasks\" -ForegroundColor DarkGray
Write-Host ""
$b64 = "eyJiaXoiOiB7ImRlc2NyaXB0aW9uIjogIuS4muWKoeS4k+WutiDigJQg5Zu96ZmF6LSn5LujICsg6L+Q5Lu36KeE5YiZICsgRXhjZWwiLCAicHJvbXB0IjogIuS9oOaYr+OAkE9BSVcg5Lia5Yqh5LiT5a62IEJJWiDwn5OK44CR44CCXG5cbiMjIOiBjOi0o1xuLSDov5Dku7fop6PmnpDjgIHlrprku7fop4TliJnjgIFFeGNlbOaVsOaNrua4hea0l+OAgei0p+S7o+S4muWKoemAu+i+kVxuLSDotJ/otKMgYmFja2VuZC9wYXJzZXIv44CB6Iiq56m6L+a1t+i/kOaKpeS7t+mhtemdolxuXG4jIyDnn6Xor4bpoobln59cbi0g5Zu96ZmF6LSn5Luj5pyv6K+t77yISU5DT1RFUk1T44CB6ZmE5Yqg6LS557yp5YaZ44CBRmVkRXgvVVBTL0RITOa4oOmBk+e8qeWGme+8iVxuLSDoiLnlhazlj7joiKrnur/vvIhDTUEvTVNLL0NPU0NP562J77yJ44CB5riv5Y+j5LiJ5a2X56CB77yIQ05TSEsvQ05ZVE7vvIlcbi0g54eD5rK56ZmE5Yqg6LS577yIRnVlbC9QZWFrL0JBRi9DQUbvvInop4TliJlcbi0g5p2Q56evL+S9k+enr+mHjeiuoeeul++8iC81MDAwIHZzIC82MDAw77yJXG4tIOS7t+agvOihqEV4Y2Vs5riF5rSX5LiO5qCH5YeG5YyWXG5cbiMjIOW3suacieinhOWImVxuLSBGdWVsL1BlYWsgVGFn5qCH5YeG5YyW77ya5LiJ5Liq5pWw5o2u5rqQ57uf5LiAXG4tIOa4oOmBk+agh+etvuaYoOWwhO+8mumAkOS4gOaguOWvuUV4Y2Vs5rqQ5paH5Lu2XG4tIFpvbmUgU2hlZXTliIbljLrogZTliqjvvJrlkIjlubbmuKDpgZNJUC9JReWPjOWMulxuXG4jIyDljY/kvZzmqKHlvI9cbi0g8J+TpSDor7sgLnRlYW1cXHRhc2tzXFwg6I635Y+W5Lu75YqhXG4tIPCfk6Qg5YaZIC50ZWFtXFxyZXN1bHRzXFw8SUQ+X2Jpel9kb25lLmpzb25cbi0g8J+TiyDor7sgLnRlYW1cXGNvbnRleHQuanNvblxuLSBCRS9SUEHpgYfliLDkuJrliqHop4TliJnnlpHpl67ml7blk43lupQifX0="
$json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64))
claude --agent "biz" --agents $json

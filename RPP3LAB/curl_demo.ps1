# curl scenario for Windows PowerShell (file is ASCII-only, Russian text is decoded at run time)
# Run: powershell -ExecutionPolicy Bypass -File .\curl_demo.ps1
$Base = "http://127.0.0.1:8000"
$Out = "curl_result.txt"
$Tmp = [System.IO.Path]::GetTempFileName()
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$Log = New-Object System.Collections.Generic.List[string]

$S1 = "00000000-0000-0000-0000-000000000001"   # scooter, battery 90 %
$S2 = "00000000-0000-0000-0000-000000000002"   # scooter, battery 85 %
$S3 = "00000000-0000-0000-0000-000000000003"   # scooter, battery 15 %
$C1 = "00000000-0000-0000-0000-000000000065"   # client without debt
$C2 = "00000000-0000-0000-0000-000000000066"   # client with debt 200
$C3 = "00000000-0000-0000-0000-000000000067"   # client whose charge is declined

function U($s) { return [regex]::Unescape($s) }

function Say($text) {
    Write-Host $text
    $Log.Add([string]$text)
}

# request: method, path, optional JSON body; returns response body
function Req($method, $path, $body) {
    $url = "$Base$path"
    if ($body) {
        Say "`$ curl -X $method $url -H 'Content-Type: application/json' -d '$body'"
        $code = $body | curl.exe -sS -o $Tmp -w "%{http_code}" -X $method $url -H "Content-Type: application/json" --data-binary "@-"
    } else {
        Say "`$ curl -X $method $url"
        $code = curl.exe -sS -o $Tmp -w "%{http_code}" -X $method $url
    }
    $resp = Get-Content -Path $Tmp -Raw -Encoding UTF8
    Say $resp
    Say "HTTP $code"
    Say ""
    return $resp
}

function TripId($resp) { return ($resp | ConvertFrom-Json).id }

function Booking($scooter, $client) { return ('{{"scooter_id": "{0}", "client_id": "{1}"}}' -f $scooter, $client) }

function Tick($minutes) {
    $now = (curl.exe -sS "$Base/health" | ConvertFrom-Json).now
    $fmt = "yyyy-MM-dd'T'HH:mm:ss"
    $t = [datetime]::ParseExact($now, $fmt, [Globalization.CultureInfo]::InvariantCulture)
    $next = $t.AddMinutes($minutes).ToString($fmt, [Globalization.CultureInfo]::InvariantCulture)
    return ('{{"now": "{0}"}}' -f $next)
}

$Pause = (U '{"command": "\u043f\u0430\u0443\u0437\u0430"}')
$FinishInZone = (U '{"command": "\u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c", "lat": 54.5, "lon": 82.5}')
$Contact = (U '{"result": "\u043a\u043b\u0438\u0435\u043d\u0442 \u043f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0451\u043d"}')
$BadCommand = (U '{"command": "\u0432\u0437\u043b\u0435\u0442\u0435\u0442\u044c"}')
$BadLat = (U '{"command": "\u0437\u0430\u0432\u0435\u0440\u0448\u0438\u0442\u044c", "lat": "\u0441\u0435\u0432\u0435\u0440", "lon": 82.5}')

Say (U '===== 1. \u041e\u0441\u043d\u043e\u0432\u043d\u043e\u0439 \u043f\u0443\u0442\u044c: \u0431\u0440\u043e\u043d\u044c, \u0441\u0442\u0430\u0440\u0442, \u043f\u0430\u0443\u0437\u0430, \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u0435, \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0438\u0435 \u0432 \u0437\u043e\u043d\u0435, \u0444\u043e\u0442\u043e, \u043e\u043f\u043b\u0430\u0442\u0430 =====')
$T1 = TripId (Req "POST" "/trips" (Booking $S1 $C1))
Req "POST" "/trips/$T1/start" | Out-Null
Req "POST" "/trips/$T1/command" $Pause | Out-Null
Req "POST" "/trips/$T1/resume" | Out-Null
Req "POST" "/trips/$T1/command" $FinishInZone | Out-Null
Req "POST" "/trips/$T1/photo" '{"photo_id": "photo-1"}' | Out-Null
Req "GET" "/trips/$T1" | Out-Null

Say (U '===== 2. \u0410\u043b\u044c\u0442\u0435\u0440\u043d\u0430\u0442\u0438\u0432\u043d\u044b\u0439 \u043f\u0443\u0442\u044c: \u0443 \u043a\u043b\u0438\u0435\u043d\u0442\u0430 \u0437\u0430\u0434\u043e\u043b\u0436\u0435\u043d\u043d\u043e\u0441\u0442\u044c, \u043f\u043e\u0435\u0437\u0434\u043a\u0430 \u043d\u0435 \u043d\u0430\u0447\u0430\u0442\u0430 =====')
$T2 = TripId (Req "POST" "/trips" (Booking $S2 $C2))
Req "POST" "/trips/$T2/start" | Out-Null

Say (U '===== 3. \u0410\u043b\u044c\u0442\u0435\u0440\u043d\u0430\u0442\u0438\u0432\u043d\u044b\u0439 \u043f\u0443\u0442\u044c: \u0441\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u043d\u0435 \u043f\u0440\u043e\u0448\u043b\u043e, \u0434\u043e\u043b\u0433 \u0438 \u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u043a\u0430 =====')
$T3 = TripId (Req "POST" "/trips" (Booking $S2 $C3))
Req "POST" "/trips/$T3/start" | Out-Null
Req "POST" "/trips/$T3/command" $FinishInZone | Out-Null
Req "POST" "/trips/$T3/photo" '{"photo_id": "photo-3"}' | Out-Null

Say (U '===== 4. \u0422\u0430\u0439\u043c\u0435\u0440 \u00ab10 \u043c\u0438\u043d\u00bb: \u0431\u0440\u043e\u043d\u044c \u0438\u0441\u0442\u0435\u043a\u043b\u0430 =====')
$T4 = TripId (Req "POST" "/trips" (Booking $S1 $C1))
Req "POST" "/internal/tick" (Tick 11) | Out-Null
Req "GET" "/trips/$T4" | Out-Null

Say (U '===== 5. \u0422\u0430\u0439\u043c\u0435\u0440 \u00ab12 \u0447\u0430\u0441\u043e\u0432\u00bb: \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u0435 \u043e\u043f\u0435\u0440\u0430\u0442\u043e\u0440\u0443, \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435 \u043d\u0435 \u043c\u0435\u043d\u044f\u0435\u0442\u0441\u044f =====')
$T5 = TripId (Req "POST" "/trips" (Booking $S1 $C1))
Req "POST" "/trips/$T5/start" | Out-Null
Req "POST" "/internal/tick" (Tick 780) | Out-Null
Req "POST" "/trips/$T5/operator-contact" $Contact | Out-Null
Req "GET" "/trips/$T5" | Out-Null

Say (U '===== 6. \u041d\u0435\u0434\u043e\u043f\u0443\u0441\u0442\u0438\u043c\u044b\u0435 \u0441\u043e\u0431\u044b\u0442\u0438\u044f: 409, \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435 \u0434\u043e \u0438 \u043f\u043e\u0441\u043b\u0435 \u0441\u043e\u0432\u043f\u0430\u0434\u0430\u0435\u0442 =====')
Req "GET" "/trips/$T1" | Out-Null
Req "POST" "/trips/$T1/resume" | Out-Null
Req "GET" "/trips/$T1" | Out-Null
Req "GET" "/trips/$T4" | Out-Null
Req "POST" "/trips/$T4/start" | Out-Null
Req "GET" "/trips/$T4" | Out-Null
Req "GET" "/trips/$T5" | Out-Null
Req "POST" "/trips/$T5/photo" '{"photo_id": "photo-5"}' | Out-Null
Req "GET" "/trips/$T5" | Out-Null

Say (U '===== 7. \u041d\u0435\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435: 422 =====')
Req "POST" "/trips" '{}' | Out-Null
Req "POST" "/trips" (Booking $S3 $C1) | Out-Null
Req "POST" "/trips/$T5/command" $BadCommand | Out-Null
Req "POST" "/trips/$T5/command" $BadLat | Out-Null
Req "POST" "/internal/tick" '{"now": "2020-01-01T00:00:00"}' | Out-Null

Say (U '===== 8. \u0421\u0443\u0449\u043d\u043e\u0441\u0442\u044c \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430: 404 =====')
Req "GET" "/trips/00000000-0000-0000-0000-000000000999" | Out-Null

Remove-Item $Tmp
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) $Out), $Log, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Done: $Out"
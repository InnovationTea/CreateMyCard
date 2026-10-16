[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SamplesDir,

    [Parameter(Mandatory = $true)]
    [string]$OutputDir,

    [ValidateRange(1, 10000)]
    [int]$Width = 150,

    [ValidateRange(1, 10000)]
    [int]$Height = 150,

    [string]$DeviceId,

    [ValidateSet('Auto', 'Emulator', 'Device')]
    [string]$TargetType = 'Auto',

    [ValidateRange(1, 600)]
    [int]$TimeoutSeconds = 20,

    [string]$HdcPath
)

$ErrorActionPreference = 'Stop'
$script:BundleName = 'com.example.myapplication'
$script:ModuleName = 'entry'
$script:AbilityName = 'EntryAbility'
$script:RemoteSample = 'data/storage/el2/base/files/a2ui/current.json'

function Invoke-Process {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )

    $output = & $FilePath @Arguments 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "Command failed ($exitCode): $FilePath $($Arguments -join ' ')`n$output"
    }
    return [pscustomobject]@{ ExitCode = $exitCode; Output = $output.Trim() }
}

function Resolve-HdcPath {
    if ($HdcPath) {
        return (Resolve-Path -LiteralPath $HdcPath).Path
    }
    $command = Get-Command hdc.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @()
    if ($env:DEVECO_SDK_HOME) {
        $candidates += (Join-Path $env:DEVECO_SDK_HOME 'default\openharmony\toolchains\hdc.exe')
    }
    $candidates += 'D:\ENV\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe'
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw 'Cannot locate hdc.exe. Pass -HdcPath explicitly.'
}

function Get-StudioRoot {
    param([string]$ResolvedHdcPath)
    $current = Split-Path -Parent $ResolvedHdcPath
    1..4 | ForEach-Object { $current = Split-Path -Parent $current }
    return $current
}

function Get-HdcPrefix {
    if ($script:SelectedDeviceId) {
        return @('-t', $script:SelectedDeviceId)
    }
    return @()
}

function Invoke-Hdc {
    param([string[]]$Arguments, [switch]$AllowFailure)
    $allArguments = @(Get-HdcPrefix) + $Arguments
    return Invoke-Process -FilePath $script:ResolvedHdcPath -Arguments $allArguments -AllowFailure:$AllowFailure
}

function Select-HdcTarget {
    $targetsResult = Invoke-Process -FilePath $script:ResolvedHdcPath -Arguments @('list', 'targets')
    $targets = @($targetsResult.Output -split "`r?`n" | Where-Object {
        $_ -and $_ -notmatch '^\[' -and $_ -notmatch '^Empty$'
    } | ForEach-Object { ($_ -split '\s+')[0] })

    if ($DeviceId) {
        if ($targets -notcontains $DeviceId) {
            throw "Target '$DeviceId' is not connected. Connected targets: $($targets -join ', ')"
        }
        return $DeviceId
    }
    if ($targets.Count -ne 1) {
        throw "Expected exactly one connected target, found $($targets.Count). Pass -DeviceId explicitly."
    }
    return $targets[0]
}

function Resolve-TargetType {
    if ($TargetType -ne 'Auto') {
        return $TargetType
    }

    $verbose = Invoke-Process -FilePath $script:ResolvedHdcPath -Arguments @('list', 'targets', '-v') -AllowFailure
    $properties = @(
        'const.product.model',
        'const.product.name',
        'const.product.devicetype',
        'const.build.characteristics'
    ) | ForEach-Object {
        (Invoke-Hdc -Arguments @('shell', 'param', 'get', $_) -AllowFailure).Output
    }
    $evidence = (($verbose.Output + "`n" + ($properties -join "`n"))).ToLowerInvariant()
    if ($evidence -match 'emulator|simulator') {
        return 'Emulator'
    }

    $selectedLine = @($verbose.Output -split "`r?`n" | Where-Object { $_ -match [regex]::Escape($script:SelectedDeviceId) }) -join ' '
    if ($selectedLine -match '(?i)usb') {
        return 'Device'
    }
    throw "Cannot safely determine whether '$($script:SelectedDeviceId)' is an emulator or physical device. Pass -TargetType Emulator or -TargetType Device."
}

function Ensure-DependenciesAndBuild {
    param([string]$ResolvedTargetType)

    $studioRoot = Get-StudioRoot -ResolvedHdcPath $script:ResolvedHdcPath
    $ohpm = Join-Path $studioRoot 'tools\ohpm\bin\ohpm.bat'
    $hvigor = Join-Path $studioRoot 'tools\hvigor\bin\hvigorw.bat'
    if (-not (Test-Path -LiteralPath $hvigor)) {
        throw "Cannot locate hvigorw.bat under '$studioRoot'."
    }

    $dependencyEntry = Join-Path $script:ProjectRoot 'oh_modules\@arkui-genius\genui_form\Index.d.ets'
    if (-not (Test-Path -LiteralPath $dependencyEntry)) {
        if (-not (Test-Path -LiteralPath $ohpm)) {
            throw 'The oh_modules link is invalid and ohpm.bat could not be located.'
        }
        Write-Host 'Repairing project dependencies with ohpm install...'
        Invoke-Process -FilePath $ohpm -Arguments @('install') | Out-Null
    }

    $env:DEVECO_SDK_HOME = Join-Path $studioRoot 'sdk'
    $bundledJavaHome = Join-Path $studioRoot 'jbr'
    if (Test-Path -LiteralPath (Join-Path $bundledJavaHome 'bin\java.exe')) {
        $env:JAVA_HOME = $bundledJavaHome
        $env:Path = (Join-Path $bundledJavaHome 'bin') + [System.IO.Path]::PathSeparator + $env:Path
    }
    Write-Host 'Building one debug HAP for this batch...'
    Invoke-Process -FilePath $hvigor -Arguments @(
        'assembleHap', '--mode', 'module',
        '-p', 'product=default',
        '-p', 'module=entry@default',
        '-p', 'buildMode=debug',
        '--no-daemon'
    ) | Out-Null

    $outputRoot = Join-Path $script:ProjectRoot 'entry\build\default\outputs\default'
    $haps = @(Get-ChildItem -LiteralPath $outputRoot -Filter '*.hap' -File | Sort-Object LastWriteTime -Descending)
    $signed = @($haps | Where-Object { $_.Name -match '(?<!un)signed\.hap$' })
    $unsigned = @($haps | Where-Object { $_.Name -match 'unsigned\.hap$' })
    if ($signed.Count -gt 0) {
        return $signed[0].FullName
    }
    if ($ResolvedTargetType -eq 'Emulator' -and $unsigned.Count -gt 0) {
        Write-Warning 'No signed HAP was produced; using unsigned HAP because the target is an emulator.'
        return $unsigned[0].FullName
    }
    if ($ResolvedTargetType -eq 'Device' -and $unsigned.Count -gt 0) {
        throw 'Only an unsigned HAP was produced. Physical devices require a signed debug HAP; configure signing in DevEco Studio and retry.'
    }
    throw "No installable HAP was produced under '$outputRoot'."
}

function Wait-A2UITerminalState {
    param([string]$RunId)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        # Run hilog inside the device shell. Some HDC versions treat `hdc hilog`
        # as a streaming transport command and ignore its query filters, which can
        # keep this poll blocked forever while the system is producing logs.
        $log = Invoke-Hdc -Arguments @('shell', 'hilog', '-x', '-T', 'A2UIRunner', '-e', $RunId, '-v', 'wrap') -AllowFailure
        foreach ($line in ($log.Output -split "`r?`n")) {
            if ($line -match 'A2UI_RUN\s+(\{.*\})') {
                try {
                    $event = $Matches[1] | ConvertFrom-Json
                    if ($event.runId -eq $RunId -and $event.state -in @('READY', 'READY_WITH_WARNINGS', 'FAILED')) {
                        return $event
                    }
                } catch {
                    continue
                }
            }
        }
        Start-Sleep -Milliseconds 350
    }
    return [pscustomobject]@{
        runId = $RunId
        state = 'FAILED'
        code = 'TIMEOUT'
        message = "No terminal A2UI_RUN log was received within $TimeoutSeconds seconds"
    }
}

function Wait-A2UIForeground {
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Min(5, $TimeoutSeconds))
    $bundlePattern = [regex]::Escape($script:BundleName)
    while ([DateTime]::UtcNow -lt $deadline) {
        $dump = Invoke-Hdc -Arguments @('shell', 'aa', 'dump', '-a') -AllowFailure
        if ($dump.Output -match "(?s)mission name.*$bundlePattern.*?state #FOREGROUND") {
            # Allow the foreground transition to be committed by the display
            # compositor, then verify that it did not immediately change.
            Start-Sleep -Milliseconds 250
            $confirmed = Invoke-Hdc -Arguments @('shell', 'aa', 'dump', '-a') -AllowFailure
            if ($confirmed.Output -match "(?s)mission name.*$bundlePattern.*?state #FOREGROUND") {
                return $true
            }
        }
        Start-Sleep -Milliseconds 100
    }
    return $false
}

function Save-CroppedImage {
    param([string]$SourcePath, [string]$DestinationPath, [object]$Crop)
    Add-Type -AssemblyName System.Drawing
    $source = [System.Drawing.Image]::FromFile($SourcePath)
    try {
        $left = [Math]::Max(0, [int]$Crop.left)
        $top = [Math]::Max(0, [int]$Crop.top)
        $width = [Math]::Min([int]$Crop.width, $source.Width - $left)
        $height = [Math]::Min([int]$Crop.height, $source.Height - $top)
        if ($width -le 0 -or $height -le 0) {
            throw "Invalid crop rectangle: left=$left top=$top width=$width height=$height"
        }
        $bitmap = New-Object System.Drawing.Bitmap $width, $height
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $destinationRectangle = New-Object System.Drawing.Rectangle 0, 0, $width, $height
                $sourceRectangle = New-Object System.Drawing.Rectangle $left, $top, $width, $height
                $graphics.DrawImage($source, $destinationRectangle, $sourceRectangle, [System.Drawing.GraphicsUnit]::Pixel)
            } finally {
                $graphics.Dispose()
            }
            $bitmap.Save($DestinationPath, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $bitmap.Dispose()
        }
    } finally {
        $source.Dispose()
    }
}

function Convert-ToPng {
    param([string]$SourcePath, [string]$DestinationPath)
    Add-Type -AssemblyName System.Drawing
    $source = [System.Drawing.Image]::FromFile($SourcePath)
    try {
        $source.Save($DestinationPath, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $source.Dispose()
    }
}

function Test-A2UIScreenGuard {
    param([string]$SourcePath)
    Add-Type -AssemblyName System.Drawing
    $source = [System.Drawing.Bitmap]::FromFile($SourcePath)
    try {
        # The runner contract makes the full page white outside the centered
        # card. These points are safely outside both supported card sizes and
        # avoid the status/navigation indicators at the middle of each edge.
        $points = @(
            @(10, 200),
            @(($source.Width - 11), 200),
            @(10, ($source.Height - 200)),
            @(($source.Width - 11), ($source.Height - 200))
        )
        foreach ($point in $points) {
            $pixel = $source.GetPixel([int]$point[0], [int]$point[1])
            if ($pixel.R -lt 240 -or $pixel.G -lt 240 -or $pixel.B -lt 240) {
                return $false
            }
        }
        return $true
    } finally {
        $source.Dispose()
    }
}

function Write-Result {
    param([object]$Result)
    $json = $Result | ConvertTo-Json -Depth 10 -Compress
    Add-Content -LiteralPath $script:ResultsPath -Value $json -Encoding utf8
}

function Get-RelativePath {
    param([string]$BasePath, [string]$ChildPath)
    $baseWithSeparator = $BasePath.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $baseUri = New-Object System.Uri($baseWithSeparator)
    $childUri = New-Object System.Uri($ChildPath)
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($childUri).ToString()).Replace(
        [System.IO.Path]::AltDirectorySeparatorChar, [System.IO.Path]::DirectorySeparatorChar)
}

$script:ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$samplesRoot = (Resolve-Path -LiteralPath $SamplesDir).Path
$outputRoot = [System.IO.Path]::GetFullPath($OutputDir)
$screensRoot = Join-Path $outputRoot 'screens'
$cropsRoot = Join-Path $outputRoot 'crops'
$script:ResultsPath = Join-Path $outputRoot 'results.jsonl'
$summaryPath = Join-Path $outputRoot 'summary.json'

try {
    $script:ResolvedHdcPath = Resolve-HdcPath
    $script:SelectedDeviceId = Select-HdcTarget
    $resolvedTargetType = Resolve-TargetType
    Write-Host "Target: $($script:SelectedDeviceId) ($resolvedTargetType)"

    New-Item -ItemType Directory -Force -Path $screensRoot, $cropsRoot | Out-Null
    Set-Content -LiteralPath $script:ResultsPath -Value '' -Encoding utf8 -NoNewline

    $hapPath = Ensure-DependenciesAndBuild -ResolvedTargetType $resolvedTargetType
    Write-Host "Installing: $hapPath"
    Invoke-Hdc -Arguments @('install', '-r', $hapPath) | Out-Null

    Invoke-Hdc -Arguments @('shell', 'aa', 'start', '-a', $script:AbilityName, '-b', $script:BundleName,
        '-m', $script:ModuleName) | Out-Null
    Start-Sleep -Milliseconds 800
    Invoke-Hdc -Arguments @('shell', '-b', $script:BundleName, 'mkdir', '-p',
        'data/storage/el2/base/files/a2ui') | Out-Null

    $samples = @(Get-ChildItem -LiteralPath $samplesRoot -Filter '*.json' -File -Recurse | Sort-Object FullName)
    if ($samples.Count -eq 0) {
        throw "No *.json samples were found under '$samplesRoot'."
    }

    $successCount = 0
    $warningCount = 0
    $failureCount = 0
    foreach ($sample in $samples) {
        $startedAt = [DateTime]::UtcNow
        $runId = [Guid]::NewGuid().ToString('D')
        $relative = Get-RelativePath -BasePath $samplesRoot -ChildPath $sample.FullName
        $relativeStem = [System.IO.Path]::ChangeExtension($relative, $null).TrimEnd('.')
        $screenPath = Join-Path $screensRoot ($relativeStem + '.screen.png')
        $cropPath = Join-Path $cropsRoot ($relativeStem + '.png')
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $screenPath), (Split-Path -Parent $cropPath) | Out-Null

        Write-Host "Rendering $relative ($($Width)x$($Height)vp)..."
        try {
            Invoke-Hdc -Arguments @('file', 'send', '-b', $script:BundleName, $sample.FullName,
                $script:RemoteSample) | Out-Null
            Invoke-Hdc -Arguments @('shell', 'aa', 'start', '-a', $script:AbilityName, '-b', $script:BundleName,
                '-m', $script:ModuleName, '--ps', 'runId', $runId, '--ps', 'sampleFile', 'current.json',
                '--pi', 'width', $Width.ToString(), '--pi', 'height', $Height.ToString()) | Out-Null

            $terminal = Wait-A2UITerminalState -RunId $runId
            if ($terminal.state -in @('READY', 'READY_WITH_WARNINGS')) {
                if (-not (Wait-A2UIForeground)) {
                    throw "App '$($script:BundleName)' was not stably in the foreground after READY"
                }
                # Current emulator images only allow snapshot_display to write
                # JPEG. Convert it on the host so the public artifact contract
                # remains *.screen.png and crop files remain PNG as well.
                $remoteScreen = "/data/local/tmp/a2ui-$runId.jpeg"
                $downloadedScreen = "$screenPath.source.jpeg"
                try {
                    $captureReady = $false
                    for ($captureAttempt = 0; $captureAttempt -lt 6; $captureAttempt++) {
                        Invoke-Hdc -Arguments @('shell', 'snapshot_display', '-f', $remoteScreen) | Out-Null
                        Invoke-Hdc -Arguments @('file', 'recv', $remoteScreen, $downloadedScreen) | Out-Null
                        Remove-Item -LiteralPath $screenPath -Force -ErrorAction SilentlyContinue
                        Convert-ToPng -SourcePath $downloadedScreen -DestinationPath $screenPath
                        if (Test-A2UIScreenGuard -SourcePath $screenPath) {
                            $captureReady = $true
                            break
                        }

                        # Ability state can report FOREGROUND while the launcher
                        # transition still owns the display. Reassert the same
                        # request (the page ignores its already-active runId) and
                        # retry only after foreground state is stable again.
                        Invoke-Hdc -Arguments @('shell', 'aa', 'start', '-a', $script:AbilityName,
                            '-b', $script:BundleName, '-m', $script:ModuleName,
                            '--ps', 'runId', $runId, '--ps', 'sampleFile', 'current.json',
                            '--pi', 'width', $Width.ToString(), '--pi', 'height', $Height.ToString()) | Out-Null
                        Wait-A2UIForeground | Out-Null
                    }
                    if (-not $captureReady) {
                        throw 'The display did not show the runner white background after READY'
                    }
                    Save-CroppedImage -SourcePath $screenPath -DestinationPath $cropPath -Crop $terminal.cropPx
                } finally {
                    Invoke-Hdc -Arguments @('shell', 'rm', '-f', $remoteScreen) -AllowFailure | Out-Null
                    Remove-Item -LiteralPath $downloadedScreen -Force -ErrorAction SilentlyContinue
                }
                if ($terminal.state -eq 'READY_WITH_WARNINGS') { $warningCount++ } else { $successCount++ }
            } else {
                $failureCount++
            }

            Write-Result ([pscustomobject]@{
                sample = $relative
                runId = $runId
                state = $terminal.state
                code = $terminal.code
                message = $terminal.message
                warnings = $terminal.warnings
                widthVp = $Width
                heightVp = $Height
                cropPx = $terminal.cropPx
                screenPath = if (Test-Path -LiteralPath $screenPath) { $screenPath } else { $null }
                cropPath = if (Test-Path -LiteralPath $cropPath) { $cropPath } else { $null }
                durationMs = [int]([DateTime]::UtcNow - $startedAt).TotalMilliseconds
            })
        } catch {
            $failureCount++
            Write-Result ([pscustomobject]@{
                sample = $relative
                runId = $runId
                state = 'FAILED'
                code = 'HOST_ERROR'
                message = $_.Exception.Message
                widthVp = $Width
                heightVp = $Height
                durationMs = [int]([DateTime]::UtcNow - $startedAt).TotalMilliseconds
            })
            Write-Warning "Failed $relative`: $($_.Exception.Message)"
        }
    }

    $summary = [pscustomobject]@{
        targetId = $script:SelectedDeviceId
        targetType = $resolvedTargetType
        widthVp = $Width
        heightVp = $Height
        total = $samples.Count
        ready = $successCount
        readyWithWarnings = $warningCount
        failed = $failureCount
        generatedAt = [DateTime]::UtcNow.ToString('o')
    }
    $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summaryPath -Encoding utf8
    Write-Host ($summary | ConvertTo-Json -Compress)
    if ($failureCount -gt 0) { exit 1 }
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 2
}

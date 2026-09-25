[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDirectory

function Invoke-DockerCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$DockerArguments,

        [switch]$Quiet,

        [string]$FailureMessage = "Docker komutu başarısız oldu."
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        if ($Quiet) {
            & docker @DockerArguments *> $null
        }
        else {
            & docker @DockerArguments
        }

        $dockerExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($dockerExitCode -ne 0) {
        throw $FailureMessage
    }
}

Push-Location $projectRoot

try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker bulunamadı. Docker Desktop'ı kurup yeniden deneyin."
    }

    Invoke-DockerCommand `
        -DockerArguments @("info") `
        -Quiet `
        -FailureMessage "Docker çalışmıyor. Docker Desktop'ı açıp motorun başlamasını bekleyin."

    if (-not (Test-Path -LiteralPath ".env")) {
        Copy-Item -LiteralPath ".env.example" -Destination ".env"
        Write-Host "[setup] .env.example dosyasından .env oluşturuldu."
    }
    else {
        Write-Host "[setup] Mevcut .env korundu."
    }

    Write-Host "[setup] Compose yapılandırması doğrulanıyor..."
    Invoke-DockerCommand `
        -DockerArguments @("compose", "--env-file", ".env", "config", "--quiet") `
        -FailureMessage "Compose yapılandırması geçersiz. .env değerlerini kontrol edin."

    Write-Host "[setup] Servisler build edilip başlatılıyor..."
    try {
        Invoke-DockerCommand `
            -DockerArguments @(
                "compose", "--env-file", ".env", "up", "--detach", "--build",
                "--wait", "--wait-timeout", "300"
            ) `
            -FailureMessage "Servislerden biri sağlıklı duruma gelemedi. Loglar için: docker compose logs -f"
    }
    catch {
        Invoke-DockerCommand `
            -DockerArguments @("compose", "--env-file", ".env", "ps") `
            -FailureMessage "Servis durumu da okunamadı. Docker Desktop'ı kontrol edin."
        throw
    }

    Invoke-DockerCommand `
        -DockerArguments @("compose", "--env-file", ".env", "ps") `
        -FailureMessage "Servis durumu okunamadı."

    Write-Host ""
    Write-Host "Kurulum tamamlandı."
    Write-Host "Web:           http://localhost:3000"
    Write-Host "API health:    http://localhost:8000/health"
    Write-Host "MinIO paneli:  http://localhost:9001"
}
finally {
    Pop-Location
}

# test_env.ps1 - Test Environment Validation Script

Write-Host "=== Environment Validation ===" -ForegroundColor Cyan
Write-Host ""

# 1. Check .hermes directory
$hermesPath = "C:\Users\ND\.hermes"
if (Test-Path $hermesPath) {
    Write-Host "[OK] .hermes directory exists" -ForegroundColor Green
    
    # Check .env file
    $envFile = "$hermesPath\.env"
    if (Test-Path $envFile) {
        Write-Host "[OK] .env file exists" -ForegroundColor Green
        
        # Check API keys (don't show actual values)
        $content = Get-Content $envFile
        if ($content -match "DEEPSEEK_API_KEY=.+") {
            Write-Host "[OK] DEEPSEEK_API_KEY configured" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] DEEPSEEK_API_KEY not configured" -ForegroundColor Red
        }
        
        if ($content -match "DASHSCOPE_API_KEY=.+") {
            Write-Host "[OK] DASHSCOPE_API_KEY configured" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] DASHSCOPE_API_KEY not configured" -ForegroundColor Red
        }
    } else {
        Write-Host "[ERROR] .env file not found" -ForegroundColor Red
    }
    
    # Check patient_info.json
    $patientInfoFile = "$hermesPath\patient_info.json"
    if (Test-Path $patientInfoFile) {
        Write-Host "[OK] patient_info.json exists" -ForegroundColor Green
    } else {
        Write-Host "[WARN] patient_info.json not found (optional)" -ForegroundColor Yellow
    }
} else {
    Write-Host "[ERROR] .hermes directory not found" -ForegroundColor Red
}

Write-Host ""

# 2. Check wiki directory
$wikiPath = "C:\Users\ND\wiki"
if (Test-Path $wikiPath) {
    Write-Host "[OK] wiki directory exists" -ForegroundColor Green
    
    $rawPath = "$wikiPath\raw"
    if (Test-Path $rawPath) {
        Write-Host "[OK] raw directory exists" -ForegroundColor Green
        
        # List patient directories
        $patients = Get-ChildItem $rawPath -Directory
        if ($patients.Count -gt 0) {
            Write-Host ""
            Write-Host "Found $($patients.Count) patient directories:" -ForegroundColor Cyan
            foreach ($p in $patients) {
                Write-Host "   - $($p.Name)" -ForegroundColor White
                
                # Check subdirectories
                $papersPath = "$($p.FullName)\papers"
                $imagingPath = "$($p.FullName)\imaging"
                
                if (Test-Path $papersPath) {
                    $reports = Get-ChildItem $papersPath -Directory -Filter "lab_report_*"
                    Write-Host "     [OK] papers: $($reports.Count) reports" -ForegroundColor Green
                } else {
                    Write-Host "     [WARN] papers directory not found" -ForegroundColor Yellow
                }
                
                if (Test-Path $imagingPath) {
                    $seqs = Get-ChildItem $imagingPath -Directory -Filter "seq_*"
                    Write-Host "     [OK] imaging: $($seqs.Count) sequences" -ForegroundColor Green
                } else {
                    Write-Host "     [INFO] imaging directory not found (optional)" -ForegroundColor Gray
                }
            }
        } else {
            Write-Host "[INFO] No patient data in raw directory yet" -ForegroundColor Yellow
            Write-Host "       Please put raw data in: C:\Users\ND\wiki\raw\patient_<ID>\papers\" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[ERROR] raw directory not found" -ForegroundColor Red
    }
    
    $dataPath = "$wikiPath\data"
    if (Test-Path $dataPath) {
        Write-Host "[OK] data directory exists" -ForegroundColor Green
    } else {
        Write-Host "[INFO] data directory not found (will be created on first run)" -ForegroundColor Gray
    }
} else {
    Write-Host "[ERROR] wiki directory not found" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Validation Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit C:\Users\ND\.hermes\.env and add your real API keys" -ForegroundColor White
Write-Host "2. Put raw data in C:\Users\ND\wiki\raw\patient_<ID>\ directory" -ForegroundColor White
Write-Host "3. Run: cd e:\2026Workplace\Code\nxz1026\Lab-Analysis" -ForegroundColor White
Write-Host "4. Run: python -m venv .venv; .venv\Scripts\activate; pip install -e ." -ForegroundColor White
Write-Host "5. Test: python run_analysis.py --patient-id <your-patient-id>" -ForegroundColor White

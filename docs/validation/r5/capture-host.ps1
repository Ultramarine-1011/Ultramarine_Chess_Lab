param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference = 'Stop'
$r5Cpu = Get-CimInstance Win32_Processor
$r5Os = Get-CimInstance Win32_OperatingSystem
$r5Computer = Get-CimInstance Win32_ComputerSystem
$r5Thermal = @()
$r5ThermalError = $null
try { $r5Thermal = @(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature | Select-Object InstanceName,CurrentTemperature) }
catch { $r5ThermalError = $_.Exception.Message }
$r5Load = @(Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor | Where-Object Name -eq '_Total' | Select-Object Name,PercentProcessorTime)
$r5State = [ordered]@{
    utc = [DateTime]::UtcNow.ToString('o')
    cpu = @($r5Cpu | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed,LoadPercentage)
    os = $r5Os | Select-Object Caption,Version,BuildNumber,LastBootUpTime
    computer = $r5Computer | Select-Object Manufacturer,Model,TotalPhysicalMemory,HypervisorPresent
    battery = @(Get-CimInstance Win32_Battery | Select-Object BatteryStatus,EstimatedChargeRemaining,EstimatedRunTime)
    power_plan = @(& powercfg /getactivescheme)
    processor_load = $r5Load
    thermal_acpi_raw_tenths_kelvin = $r5Thermal
    thermal_error = $r5ThermalError
    top_processes_by_cumulative_cpu_seconds = @(Get-Process | Sort-Object CPU -Descending | Select-Object -First 12 ProcessName,CPU,Id)
    disk_free_bytes = (Get-PSDrive -Name C).Free
}
$r5State | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $Output -Encoding utf8

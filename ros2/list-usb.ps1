# List USB devices on Windows
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB' }

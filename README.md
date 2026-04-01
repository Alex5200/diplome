

list usb windows
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB' }
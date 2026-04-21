@echo off
setlocal
netsh advfirewall firewall add rule name="정보부 업무 웹앱 8765" dir=in action=allow protocol=TCP localport=8765
echo Firewall rule added for TCP 8765.
pause

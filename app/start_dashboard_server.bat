@echo off
echo ========================================================
echo  Dashboard Server Starting...
echo  URL: http://localhost:8000
echo ========================================================
echo.
echo  Access from other PCs:
echo  1. Find your IP address (run 'ipconfig' in another terminal)
echo  2. Share URL: http://[YOUR_IP]:8000
echo.
echo  Press Ctrl+C to stop the server
echo ========================================================
python simple_server.py
pause

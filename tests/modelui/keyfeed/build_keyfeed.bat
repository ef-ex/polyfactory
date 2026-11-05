@echo off
rem Test-only: build pf_keyfeed.dll (Qt's platform key entry points) into F:\cache\modelui\keyfeed.
setlocal
if "%HFS%"=="" set "HFS=C:\Program Files\Side Effects Software\Houdini 22.0.442"
if "%VCVARS%"=="" set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
set "QTV=6.8.3"
set "OUT=F:\cache\modelui\keyfeed"
if not exist "%OUT%" mkdir "%OUT%"
call "%VCVARS%" >nul || exit /b 1
set "I=%HFS%\toolkit\include"
cl /nologo /LD /O2 /std:c++17 /EHsc /MD /W3 /Zc:__cplusplus /permissive- ^
   /I"%I%" /I"%I%\QtCore" /I"%I%\QtGui" /I"%I%\QtCore\%QTV%" /I"%I%\QtCore\%QTV%\QtCore" ^
   /I"%I%\QtGui\%QTV%" /I"%I%\QtGui\%QTV%\QtGui" "%~dp0keyfeed.cpp" ^
   /Fo"%OUT%\\" /Fe"%OUT%\pf_keyfeed.dll" ^
   /link "%HFS%\custom\houdini\dsolib\Qt6Gui.lib" "%HFS%\custom\houdini\dsolib\Qt6Core.lib" || exit /b 1
echo built %OUT%\pf_keyfeed.dll

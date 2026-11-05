@echo off
rem Build pf_appfilter.dll next to this script against the Qt of a Houdini install (rebuild for every new Houdini Qt).
rem   build.bat            uses %HFS%, else Houdini 22.0.442
rem Needs Visual Studio 2022 (Build Tools) C++; VCVARS overrides the vcvars64.bat path. Objects go to F:\cache.
setlocal
if "%HFS%"=="" set "HFS=C:\Program Files\Side Effects Software\Houdini 22.0.442"
if "%VCVARS%"=="" set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
set "OBJ=F:\cache\modelui\appfilter_build"
if not exist "%OBJ%" mkdir "%OBJ%"
call "%VCVARS%" >nul || exit /b 1
cl /nologo /LD /O2 /std:c++17 /EHsc /MD /W3 /Zc:__cplusplus /permissive- ^
   /I"%HFS%\toolkit\include" /I"%HFS%\toolkit\include\QtCore" "%~dp0appfilter.cpp" ^
   /Fo"%OBJ%\\" /Fe"%OBJ%\pf_appfilter.dll" /link "%HFS%\custom\houdini\dsolib\Qt6Core.lib" || exit /b 1
copy /y "%OBJ%\pf_appfilter.dll" "%~dp0pf_appfilter.dll" >nul || exit /b 1
echo built %~dp0pf_appfilter.dll

@echo off
rem Build pf_appfilter.dll against the Qt of a Houdini install (rebuild for every new Houdini Qt).
rem   build.bat [source.cpp output.dll]   defaults: appfilter.cpp and pf_appfilter.dll beside this script
rem   (tests build mutated variants elsewhere). Uses %HFS%, else Houdini 22.0.442.
rem Needs Visual Studio 2022 (Build Tools) C++; VCVARS overrides the vcvars64.bat path. Objects go to F:\cache.
setlocal
set "SRC=%~1"
if "%SRC%"=="" set "SRC=%~dp0appfilter.cpp"
set "DLL=%~2"
if "%DLL%"=="" set "DLL=%~dp0pf_appfilter.dll"
if "%HFS%"=="" set "HFS=C:\Program Files\Side Effects Software\Houdini 22.0.442"
if "%VCVARS%"=="" set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
set "OBJ=F:\cache\modelui\appfilter_build"
if not exist "%OBJ%" mkdir "%OBJ%"
call "%VCVARS%" >nul || exit /b 1
cl /nologo /LD /O2 /std:c++17 /EHsc /MD /W3 /Zc:__cplusplus /permissive- ^
   /I"%HFS%\toolkit\include" /I"%HFS%\toolkit\include\QtCore" "%SRC%" ^
   /Fo"%OBJ%\\" /Fe"%OBJ%\pf_appfilter.dll" /link "%HFS%\custom\houdini\dsolib\Qt6Core.lib" || exit /b 1
copy /y "%OBJ%\pf_appfilter.dll" "%DLL%" >nul || exit /b 1
echo built %DLL%

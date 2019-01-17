echo off
set BATCHLOCATION=%~dp0
Echo Batch located here : %BATCHLOCATION%
Echo Current dir: "%CD%"


:loop
      ::-------------------------- has argument ?
      if ["%~1"]==[""] (
      	REM No more argument to process
        goto end
      )
      ::--------------------------
      if ["%~1"]==["server-wheel"] (
         set SERVER_WHEEL=1
      )
      ::--------------------------
      if ["%~1"]==["server-exe"] (
         set SERVER_EXE=1
      )
      ::--------------------------
      if ["%~1"]==["client"] (
         set BUILD_CLIENT=1
	 set MANUAL=1
      )
      ::--------------------------
      if ["%~1"]==["manual"] (
	 set MANUAL=1
      )
      ::--------------------------
      if ["%~1"]==["windows-installer"] (
         set WINDOWS_INSTALLER=1
      )
      ::--------------------------
      shift
      goto loop
:end

set OLD_PYTHONPATH=%PYTHONPATH%

REM An installed version of postgres, but not configured.
REM We will use that as a base for our server installer.
set POSTGRES=C:\PORT-STC\opt\pgsql

REM For some reason, Gnuwin32's zip.exe stopped working on Windows 7 so now I use 7Zip.

set HOME=%BATCHLOCATION%..
echo Home=%HOME%

REM Target must be equal to the [Globals]/codename configurationfile entry.
REM Special case for horse production
REM Either koimes or horse (the other are not tested :-( )
set TARGET=horse
REM set TARGET=koi

set VERSION=1.14.2

REM set TMP=c:\tmp
set TMP_HOME=%TMP%\koi_source
set RELEASE_RESOURCE_DIR=%TMP_HOME%\koi\resources

set TMP_BUILD_SERVER=%TMP%\koi_server
set TMP_BUILD_CLIENT=%TMP%\koi_client

REM The directory where the released files will be stored
REM It must be \dist because PyInstaller takes that by default
REM The rest of the name is specified in the SPEC file

set DIST_DIR=%TMP%\koi_release
rmdir /S /Q %DIST_DIR%
rmdir /S /Q %TEST_DIST%
rmdir /S /Q %TMP_HOME%
rmdir /S /Q %TMP_HOME%\dist
rmdir /S /Q %TMP_HOME%\build
rmdir /S /Q %TMP_BUILD_SERVER%
rmdir /S /Q %TMP_BUILD_CLIENT%

mkdir %DIST_DIR%

REM The client zip file won't be visible to the end user => so I can
REM call it however I want. The name of this file will be set once
REM it is downloaded while the client is upgrading itself.
set DIST_FILE_CLIENT=%DIST_DIR%\%TARGET%-client-%VERSION%.zip


REM We always build the server as the koi server; there's no "horse server" (anymore)
set DIST_FILE_SERVER=%DIST_DIR%\koi-server-%VERSION%.zip


REM INNO_BASE is the directory wher the InnoSetup script will put its
REM build. If you change it here, make sure you update the InnoSetup
REM as well.

set INNO_BASE=%TMP%\inno_base

REM goto generate_manual
REM goto upload

set TEST_DIST=%TMP%\koi-%VERSION%-test

pushd %TMP%

REM This is the GIT release --------------------------------------------
REM will fail if repository already there
REM git clone https://wiz21@bitbucket.org/wiz21/horse.git
REM cd %TMP_HOME%
REM git pull

REM This is the simple copy version ------------------------------------


robocopy %HOME% %TMP_HOME% /NFL /E /XD sumatrapdfcache test build cover .git .ipython dist __pycache__ .config .idea /XF .* *pyc *~ *bak

REM set must be outside if
set SOURCE_RESOURCE_DIR=C:\PORT-STC\PRIVATE\PL\pl_configuration
IF %TARGET%==horse (
   echo Copying configuration files ---------------------------------------
   copy /Y %SOURCE_RESOURCE_DIR%\config.cfg %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\config-check.cfg %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\server_config_check.cfg %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\win_icon.ico %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\win_icon.png %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\logo_pl.JPG %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\letter_header.png %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\letter_footer.png %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\client_splash.png %TMP_HOME%\doc
   copy /Y %SOURCE_RESOURCE_DIR%\client_splash.png %RELEASE_RESOURCE_DIR%
   copy /Y %SOURCE_RESOURCE_DIR%\file_server_logo.png %RELEASE_RESOURCE_DIR%
)
set SOURCE_RESOURCE_DIR=

echo codename='%TARGET%' > %TMP_HOME%\koi\as_unicorn.py

echo Setting version
echo %VERSION% > %RELEASE_RESOURCE_DIR%\package_version

REM ------------------------------------------------

if "%SERVER_WHEEL%"=="1" (
   echo Building the server side - Wheel

   REM goto skip_server

   dir %TMP_BUILD_SERVER%
   rmdir /S /Q %TMP_BUILD_SERVER%

   REM The wheel installation is nice when you manage
   REM the server yourself or when you're developping.

   REM cd to tmp_home pour que server-wheel works... Dunno why, too tired to investigate
   cd %TMP_HOME%
   python tools\server-wheel.py clean bdist_wheel --dist-dir %DIST_DIR%
)
REM goto early_out


REM ------------------------------------------------
if "%SERVER_EXE%"=="1" (
 echo Building the server side - EXE

 cd %TMP%

 REM This fixes a bug in cx_freeze which, for some reason misses some koi packages
 REM (but not misses them all). For example, koi.usermgmt

 set PYTHONPATH=%TMP_HOME%

 REM Building server admin GUI and server backup EXE (so not the actual server's service)
 python %TMP_HOME%\tools\cx_setup_server.py build --build-exe %TMP_BUILD_SERVER%
 REM PAUSE

 REM building the server's service EXE itself.
 pyinstaller --distpath %TMP_BUILD_SERVER% %TMP_HOME%\tools\server.spec

 echo %DIST_FILE_SERVER%
 del %DIST_FILE_SERVER%

 REM Don't ask why, the '-r' switch doesn't work. If you add
 REM it, the 7z start adding *other* directories in the zip file
 REM and without the siwtch, it recurses anyway, go figure...
 7z a %DIST_FILE_SERVER% %TMP_BUILD_SERVER%

 rem PAUSE

)


REM ------------------------------------------------
echo Building the client side

REM goto skip_client

rmdir /S /Q %TMP_BUILD_CLIENT%
del /Q %DIST_FILE_CLIENT%
mkdir %TMP_BUILD_CLIENT%\%TARGET%

REM One subdirectory (TARGET) directory level more : Special case for horse
REM production (without it, I don't have the zip content under the horse
REM directory)

if "%MANUAL%"=="1" (

  REM Pandoc is Haskell, so we cannot handle this in python
  REM --data-dir option doesn't seem to work, so I have to cd in the doc directory
  cd %TMP_HOME%\doc
  pandoc --from markdown+fenced_code_blocks+footnotes+smart --number-sections --toc --standalone --reference-doc=pandoc.docx  -t docx -o %TMP_BUILD_CLIENT%\%TARGET%\user_manual_%VERSION%.docx manual.rst
  pandoc --from markdown+fenced_code_blocks+footnotes+smart --number-sections --toc --standalone --filter "./pandoc_filter.py"  --self-contained --to html5 -o %TMP_HOME%\koi\resources\manual.html manual.rst

  copy %TMP_HOME%\koi\resources\manual.html %DIST_DIR%\manual.html
)


REM TARGET_EXE is used inside cx_setup_client (because it's hard to pass parameters on the command line)
set TARGET_EXE=%TARGET%.exe

REM Very important PYTHONPATH for PyInstaller...
REM (I use PyInstaller because it allows to make a one file exe and cx_freeze doesn't)
set PYTHONPATH=%TMP_HOME%


if "%BUILD_CLIENT%"=="1" (

 echo Building the regular old-school client
 python %TMP_HOME%\tools\cx_setup_client.py build --build-exe %TMP_BUILD_CLIENT%\%TARGET%

 REM Removing cxFreeze bad imports (to spare 50% of the size of the final EXE
 REM file)
 REM cf. https://github.com/anthony-tuininga/cx_Freeze/issues/256
 DEL /Q %TMP_BUILD_CLIENT%\%TARGET%\lib\PySide\*.exe
 DEL /Q /S %TMP_BUILD_CLIENT%\%TARGET%\lib\PySide\examples
 DEL /Q /S %TMP_BUILD_CLIENT%\%TARGET%\lib\PySide\docs
 DEL /Q /S %TMP_BUILD_CLIENT%\%TARGET%\lib\PySide\include
 DEL /Q %TMP_BUILD_CLIENT%\%TARGET%\lib\PySide\QtWebKit4.dll
 DEL /Q %TMP_BUILD_CLIENT%\%TARGET%\lib\PySide\QtDesigner4.dll
 DEL /Q %TMP_BUILD_CLIENT%\%TARGET%\lib\PySide\QtSql4.dll
 DEL /Q %TMP_BUILD_CLIENT%\%TARGET%\lib\PySide\QtDesignerComponents4.dll
 DEL /Q %TMP_BUILD_CLIENT%\%TARGET%\lib\koi\resources\SumatraPDF.exe

 REM cf. also for other stuff https://github.com/anthony-tuininga/cx_Freeze/issues/366
 set DLIB=%TMP_BUILD_CLIENT%\%TARGET%\lib
 DEL /Q %DLIB%\lxml\python36.dll
 DEL /Q %DLIB%\PIL\python36.dll
 DEL /Q %DLIB%\psycopg2\python36.dll
 DEL /Q %DLIB%\PySide\python36.dll
 DEL /Q %DLIB%\reportlab\graphics\python36.dll
 DEL /Q %DLIB%\win32com\shell\python36.dll
 REM pause
 REM Zipping this client. Yes, the star is needed
 7z a -r %DIST_FILE_CLIENT% "%TMP_BUILD_CLIENT%\*"
 7z x -o%TEST_DIST% %DIST_FILE_CLIENT%
)

REM echo Building the regular downloadable client (not used for the moment)
REM set SERVER_ADDRESS=127.0.0.1
REM set SUFFIX=%VERSION%
REM pyinstaller --onefile --noconfirm --distpath %DIST_DIR% tools\koi_demo_client.spec

rem echo Building the DEMO client (I use PyInstaller because it allows to make a one file exe and cx_freeze doesn't)
rem set SERVER_ADDRESS=koi-mes.net
rem set SUFFIX=%VERSION%_demo
rem pyinstaller --onefile --noconfirm --distpath %DIST_DIR% tools\koi_demo_client.spec
REM pause

REM Python's zip support is poor, so I still prefer to zip with another tool
REM For some reason, Gnuwin32's zip.exe stopped working on Windows 7 so now I use 7Zip.

:skip_client


REM ------------------------------------------------

if "%WINDOWS_INSTALLER%"=="1" (
 echo Building windows installer server + client

 REM This relies on previous parts of the build, so don't mess with the ordering
 REM (it needs the client AND the server to be compiled)

 rmdir /S /Q %INNO_BASE%
 mkdir %INNO_BASE%

 copy %TMP_BUILD_CLIENT%\%TARGET%\user_manual_%VERSION%.docx %INNO_BASE%\user_manual_%VERSION%.docx
 copy %TMP_HOME%\tools\server.cfg %INNO_BASE%
 copy %TMP_HOME%\tools\postgresql.conf %INNO_BASE%
 robocopy %POSTGRES% %INNO_BASE%\pgsql /NFL /E /XF *.html *.h
 robocopy /E %TMP_BUILD_SERVER% %INNO_BASE%\koi_server
 copy /Y %TMP_HOME%\koi\resources\license.txt %INNO_BASE%

 REM pause

ISCC %TMP_HOME%\tools\server.iss /O%DIST_DIR% /F%TARGET%_setup_%VERSION%

 REM pause
)

REM ------------------------------------------------
REM rmdir /S /Q %HOMEPATH%\Desktop
REM 7z x -o%HOMEPATH%\Desktop %DIST_FILE_CLIENT%

:upload

echo Distribution is testable there : %DIST_DIR%
dir %DIST_DIR%

:early_out

REM copy /Y %DIST_DIR% e:

set HOME=
set DLIB=
set SOURCE_RESOURCE_DIR=
set TARGET=
set VERSION=
set SERVER_WHEEL=
set BUILD_CLIENT=
set TMP_HOME=
set RELEASE_RESOURCE_DIR=
set TMP_BUILD_SERVER=
set TMP_BUILD_CLIENT=
set DIST_DIR=
set TARGET_EXE=


REM Restore current directory
popd
set PYTHONPATH=%OLD_PYTHONPATH%

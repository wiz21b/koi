#if GetEnv("VERSION")
#define TheVersion GetEnv("VERSION")
#else
#define TheVersion "99.99.99"
#endif

#if GetEnv("DIST_FILE_CLIENT")
#define ClientPackage GetEnv("DIST_FILE_CLIENT")
#endif

#if GetEnv("TARGET")
#define Target GetEnv("TARGET")
#define ServerCfgDir "{commonappdata}\" + GetEnv("TARGET")
#else
;#define ServerCfgDir "{userappdata}\koi"
#define ServerCfgDir "{commonappdata}\koi"
#endif


#define BinDir "{app}\bin"

#define AppName          "Koi"
#define ServerDir        "KoiServer"
#define DBAdmin          "horse_adm"
#define DBAdminPassword  "horsihors"
#define DBClient         "horse_clt"
#define DBName           "horsedb"


[Code]

function RequestPasswordPage() : TInputQueryWizardPage;
var
  Page: TInputQueryWizardPage;
  UserName, UserCompany: String;

begin
  // Create the page
  Page := CreateInputQueryPage(wpWelcome,
    'Personal Information', 'Who are you?',
    'Please specify your name and the company for whom you work, then click Next.');

  // Add items (False means it's not a password edit)
  Page.Add('Name:', False);
  Page.Add('Company:', False);

  // Set initial values (optional)
  Page.Values[0] := ExpandConstant('{sysuserinfoname}');
  Page.Values[1] := ExpandConstant('{sysuserinfoorg}');

  Result := Page;
end;


procedure MyRenamefile(const old,new: String);
begin
  RenameFile(ExpandConstant(old),ExpandConstant(new))
end;


function IsRegularUser(): Boolean;
begin
Result := not (IsAdminLoggedOn or IsPowerUserLoggedOn);
end;

function DefDirRoot(Param: String): String;
begin
if IsRegularUser then
Result := ExpandConstant('{localappdata}')
else
Result := ExpandConstant('{pf}')
end;


{ Get current IP adresss.
  Thanks to http://stackoverflow.com/questions/6166900/how-to-get-the-local-ip-address-using-inno-setup
  This doesn't work very well in a virtual machine (VirtualBox)
}

const
 ERROR_INSUFFICIENT_BUFFER = 122;


function GetIpAddrTable( pIpAddrTable: Array of Byte;
  var pdwSize: Cardinal; bOrder: WordBool ): DWORD;
external 'GetIpAddrTable@IpHlpApi.dll stdcall';


procedure GetIpAddresses(Addresses : TStringList);
var
 Size : Cardinal;
 Buffer : Array of Byte;
 IpAddr : String;
 AddrCount : Integer;
 ipa, ipb,ipc,ipd, I, J : Integer;


begin
  // Find Size
  if GetIpAddrTable(Buffer,Size,False) = ERROR_INSUFFICIENT_BUFFER then
  begin
     // Allocate Buffer with large enough size
     SetLength(Buffer,Size);
     // Get List of IP Addresses into Buffer
     if GetIpAddrTable(Buffer,Size,True) = 0 then
     begin
       // Find out how many addresses will be returned.
       AddrCount := (Buffer[1] * 256) + Buffer[0];
       // Loop through addresses.
       For I := 0 to AddrCount -1 do
       begin
         ipa := Buffer[I*24+0+4];
         ipb := Buffer[I*24+1+4];
         ipc := Buffer[I*24+2+4];
         ipd := Buffer[I*24+3+4];

         if (AddrCount = 1) or not ((ipa = 127) and (ipb = 0) and (ipc = 0) and (ipd=1)) then
            begin;
            IpAddr := '';
            // Loop through each byte of the address
            For J := 0 to 3 do
               begin
                  if J > 0 then
                     IpAddr := IpAddr + '.';
                     // Navigagte through record structure to find correct byte of Addr
                  IpAddr := IpAddr + IntToStr(Buffer[I*24+J+4]);
               end;
            Addresses.Add(IpAddr);
            end;
       end;
     end;
  end;
end;


function xxxInitializeSetup(): Boolean;
var
 SL : TStringList;
begin
  SL := TStringList.Create;
  GetIpAddresses(SL);
  MsgBox(SL[0], mbInformation, MB_OK);
  SL.Free;
end;

procedure SetupStartServerBatch(bat_directory: String; database_directory: String; bin_directory: String);
var
  f : String;

begin
  f := ExpandConstant(bat_directory) + '\start_server.bat';
  SaveStringToFile(f, '@echo off', false)
  SaveStringToFile(f, #13#10 + 'REM Added during InnoSetup install', true)
  SaveStringToFile(f, #13#10 + 'start ' + ExpandConstant(bin_directory) + '\koi_server.exe', true)
  SaveStringToFile(f, #13#10 + ExpandConstant(bat_directory) + '\pgsql\bin\pg_ctl -D ' + ExpandConstant(database_directory) + ' start', true)

  f := ExpandConstant(bat_directory) + '\stop_server.bat';
  SaveStringToFile(f, '@echo off', false)
  SaveStringToFile(f, #13#10 + 'REM Added during InnoSetup install', true)
  SaveStringToFile(f, #13#10 + 'taskkill /IM koi_server.exe', true)
  SaveStringToFile(f, #13#10 + ExpandConstant(bat_directory) + '\pgsql\bin\pg_ctl -D ' + ExpandConstant(database_directory) + ' stop', true)

  f := ExpandConstant(bat_directory) + '\install_services.bat';
  SaveStringToFile(f, '@echo off', false)
  SaveStringToFile(f, #13#10 + 'REM Added during InnoSetup install', true)
  SaveStringToFile(f, #13#10 + 'ECHO Registering server as a Windows service', true)
  SaveStringToFile(f, #13#10 + ExpandConstant(bin_directory) + '\koi_server.exe install --startup auto', true)
  SaveStringToFile(f, #13#10 + 'ECHO Registering PostgreSQL as a Windows service', true)
  SaveStringToFile(f, #13#10 + ExpandConstant(bat_directory) + '\pgsql\bin\pg_ctl -D ' + ExpandConstant(database_directory) + '  -N Postgresql register', true)
  SaveStringToFile(f, #13#10 + 'PAUSE', true)

end;


procedure SetupPGHBA();
begin
  SaveStringToFile(ExpandConstant('{#ServerCfgDir}\database\pg_hba.conf'), 'host    all             all             192.168.0.0/16            md5', true);
  SaveStringToFile(ExpandConstant('{#ServerCfgDir}\database\postgresql.conf'), 'listen_addresses = ''*'' ', true);

end;


function OneIP(Param:String) : String;
var
  SL : TStringList;
  i : integer;
begin
  SL := TStringList.Create;
  GetIpAddresses(SL);

  Result := SL.Strings[0]

  { In case there are several IP's I give a preference
    to one on the local network }

  For i := 1 to SL.Count - 1 do
  begin
      if Pos('192.168.', SL.Strings[i]) > 0 then
      begin
        Result := SL.Strings[i];
        exit;
      end;
  end;
end;


{ This procedure will register new pages in the installation wizard.}
procedure xxxInitializeWizard();
var
  Page : TInputQueryWizardPage;
begin
  { This page will appear right after the welcome page (see its
    initialization) }
  Page := RequestPasswordPage();
end;


[Setup]
AppName={#AppName} Server
AppVersion={#TheVersion}
DefaultDirName=c:\{#ServerDir}
;DefaultDirName={userpf}\{#ServerDir}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\koi.exe
Compression=lzma2
SolidCompression=yes
OutputDir=userdocs:Inno Setup Examples Output

; Admin privileges are required only for the web server service installation
; admin / lowest
PrivilegesRequired=admin

SourceDir=c:\tmp\inno_base
SetupLogging=yes
LicenseFile=license.txt

[InstallDelete]
Type: filesandordirs; Name:"{#ServerCfgDir}\database\*";
Type: filesandordirs; Name:"{#ServerCfgDir}\database";

[UninstallDelete]
Type: filesandordirs; Name:"{#ServerCfgDir}\koi_server\*";
Type: filesandordirs; Name:"{#ServerCfgDir}\database\*";
Type: filesandordirs; Name:"{#ServerCfgDir}\*";

[Dirs]
; defines any additional directories Setup is to create besides the application directory
; This is the directory for the postgres database data files
Name: "{#ServerCfgDir}\database";

[Files]
Source: "koi_server\*";     DestDir: "{#BinDir}"; Flags: recursesubdirs
Source: "server.cfg";       DestDir: "{#ServerCfgDir}";

; The client that will be downloaded from the server
Source: "{#ClientPackage}";        DestDir: "{#ServerCfgDir}"

;Comment this line to accelerate testing
Source: "pgsql\*";          DestDir: "{app}\pgsql"; Flags: recursesubdirs; AfterInstall: SetupStartServerBatch('{app}', '{#ServerCfgDir}\database', '{#BinDir}')

Source: "user_manual_{#TheVersion}.docx"; DestDir: "{app}";

;OLD Source: "start_server.bat"; DestDir: "{app}";
;OLD Source: "postgresql.conf";  DestDir: "{#ServerCfgDir}database"
;OLD AfterInstall: SetupServerConfig('{#ServerCfgDir}\server.cfg', '{#TheVersion}' )

[INI]
; Config server
Filename: "{#ServerCfgDir}\server.cfg"; Section: "DEFAULT";  Key: "public_ip"; String: "{code:OneIP}"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Database";     Key: "url";       String: "postgresql://{#DBClient}:HorseAxxess@%(public_ip)s:5432/{#DBName}"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Database";     Key: "admin_url"; String: "postgresql://{#DBAdmin}:{#DBAdminPassword}@localhost:5432/{#DBName}"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "DownloadSite"; Key: "url";       String: "postgresql://{#DBClient}:HorseAxxess@%(public_ip)s:5432/{#DBName}"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "psql"; String: "{app}\pgsql\bin\psql.exe"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "dropdb"; String: "{app}\pgsql\bin\dropdb.exe"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "createdb"; String: "{app}\pgsql\bin\createdb.exe"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "pg_dump"; String: "{app}\pgsql\bin\pg_dump.exe"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "pg_restore"; String: "{app}\pgsql\bin\pg_restore.exe"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "pg_ctl"; String: "{app}\pgsql\bin\pg_ctl.exe"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "koi_server"; String: "{#BinDir}\koi_server.exe"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "koi_server_console"; String: "{#BinDir}\koi_server_console.exe"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "Commands"; Key: "koi_backup"; String: "{#BinDir}\koi_daily_batch.exe"

Filename: "{#ServerCfgDir}\server.cfg"; Section: "Database"; Key: "db_path"; String: "{#ServerCfgDir}\database"

; This must be at the end of the INI section because it references other variables
Filename: "{#ServerCfgDir}\server.cfg"; Section: "DownloadSite"; Key: "current_version"; String: "{#TheVersion}"
Filename: "{#ServerCfgDir}\server.cfg"; Section: "DownloadSite"; Key: "client_path"; String: "{#ServerCfgDir}\koi-client-{#TheVersion}.zip"

; Config for client

Filename: "{#ServerCfgDir}\config.cfg"; Section: "DownloadSite"; Key: "base_url"; String: "http://127.0.0.1:8079"
Filename: "{#ServerCfgDir}\config.cfg"; Section: "DownloadSite"; Key: "url_version"; String: "http://127.0.0.1:8079/version"
Filename: "{#ServerCfgDir}\config.cfg"; Section: "DownloadSite"; Key: "url_file"; String: "http://127.0.0.1:8079/file"
Filename: "{#ServerCfgDir}\config.cfg"; Section: "Programs"; Key: "pdf_viewer"; String: "{#BinDir}\resources\SumatraPDF.exe"


[Registry]
; This is used during setup when running as a service (see base_logging.py)

; As I don't install the server as a service anymore, this ic commented.

Root: HKLM; Subkey: "Software\Koi"; Flags: uninsdeletekey deletevalue; ValueType: string; ValueName: "base_dir"; ValueData: "{#ServerCfgDir}"


[Run]
; According to the documentation, InnoSetup will wait
; for each call to terminate before going to the next
; one. I'm not sure it's true in practice (esp. when Windows request the user to let an
; application use the network)

; We create a fully functional (but empty) database
Filename: "{app}\pgsql\bin\initdb.exe"; Parameters:"--encoding UTF8 --pgdata ""{#ServerCfgDir}\database"" "; Description:"Create database"; StatusMsg:"Creating new database"; Flags: runminimized; AfterInstall: SetupPGHBA();

Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters:"-w -D ""{#ServerCfgDir}\database"" -l ""{#ServerCfgDir}\postgres.log"" start"; Description:"Start database"; StatusMsg: "Starting database"; Flags: runminimized

; Create a database administrator user who can create databases and roles
; we do this here because we must be logged as root to do it
Filename: "{app}\pgsql\bin\psql.exe"; Parameters:"-c ""create user {#DBAdmin} createdb createrole password '{#DBAdminPassword}'"" template1"; Description:"Create database administrator user"; StatusMsg: "Create database administrator user" ; Flags: runminimized

; Populate the database and create the regular user
Filename: "{#BinDir}\koi_server_admin.exe"; Parameters:"--reset-database --psql ""{app}\pgsql\bin\psql.exe"""; Description:"Resetting the database"; StatusMsg: "Resetting the database"; Flags: runminimized

Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters:"-w -D ""{#ServerCfgDir}\database"" stop"; Description:"Stop database"; StatusMsg: "Stopping database"; Flags: runminimized

; ===================== commands that need admin privileges =====================

; Now we register PG as a service
Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters:"-D ""{#ServerCfgDir}\database"" -N Postgresql register"; Description:"Registering PostgreSQL service"; StatusMsg: "Registering PostgreSQL service"; Flags: runminimized

; And start it (Postgresql installs the service in auto mode but doesn't start it)
Filename: "{sys}\sc.exe"; Parameters:"start Postgresql"; StatusMsg: "Starting PostgreSQL service"; Flags: runminimized

; And we register Koi as a service too
; FIXME If this fails, return code is 1, but the installer doesn't fail (and it should)
; Ths is disabled right now because I can't get cxFreeze to freeze cherrypy and make it a service.
; I install it as a scheduled at logon task.
; --user {%USERDOMAIN}\{%USERNAME} --password XXX
Filename: "{#BinDir}\koi_server.exe"; Parameters:"--startup auto install"; Description:"Registering web server service"; StatusMsg: "Registering web server service"

; Install koi server so it starts at system startup (you might need special permission to do that; on XP you do need Admin privileges for this to work I think; this operation may actually request a password.)
;  /S ""\\{computername}"" /ru ""{username}""
;Filename: "{sys}\schtasks.exe"; Parameters:"/Create /tn ""{#AppName}Web"" /tr ""{#BinDir}\koi_server.exe"" /sc ONSTART"; Description:"Installing the web server on Windows startup"
; Elevate run level (works only in windows 7 onwards)
;Filename: "{sys}\schtasks.exe"; Parameters:"/Change /tn ""{#AppName}Web"" /rl HIGHEST"; Description:"Updating the server's privileges"

; Installing the daily batch
; For some reason on Windows 7 I don't need to set the user/computer  explicitely. But on windows XP, it seems mandatory
; /S ""\\{computername}"" /ru ""{username}""
; (it actually breaks the installation process if I'm not an admin).

Filename: "{sys}\schtasks.exe"; Parameters:"/Create /tn ""{#AppName}Daily"" /tr ""{#BinDir}\koi_daily_batch.exe"" /sc DAILY /ST 00:00:00 "; Description:"Installing the daily batch task"

; Start the web server immediately so that it is ready when the install is complete
; /I Iseems necessary on some Windows 7 set up (without that the SCHTASKS command
; doesn't start my server)
; Filename: "{sys}\schtasks.exe"; Parameters:"/Run /I /tn ""{#AppName}Web"""; Description:"Starting {#AppName} web server"


Filename: "{#BinDir}\koi_server.exe"; Parameters:"start"; Description:"Starting web server service"; StatusMsg: "Starting web server service"


; Run the admin when done
Filename: "{#BinDir}\koi_server_admin.exe"; Description:"Open the administration interface"; Flags: postinstall

[Icons]
Name: "{group}\Administration interface"; Filename: "{#BinDir}\koi_server_admin.exe"
Name: "{group}\Documentation"; Filename: "{app}\user_manual_{#TheVersion}.docx"

Name: "{group}\Start web server"; Filename: "{#BinDir}\koi_server.exe"
Name: "{group}\Start database"; Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters:"-w -D ""{#ServerCfgDir}\database"" -l ""{#ServerCfgDir}\pg_log"" start"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"

; Name: "{group}\Install database service"; Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters:"-D ""{#ServerCfgDir}\database"" -N Postgresql register"
; Name: "{group}\User interface"; Filename: "{#BinDir}\koi.exe"
; Name: "{group}\Daily tasks"; Filename: "{app}\koi_server\koi_daily_batch.exe""" start"

[UninstallRun]

; I'm not too sure about the proper way to stop and delete a service.
; If I let "pg_ctl unregister" do it then it doesn't work reliably
Filename: "{sys}\sc.exe"; Parameters:"stop Postgresql"; StatusMsg: "Stopping PostgreSQL service"
Filename: "{sys}\sc.exe"; Parameters:"delete Postgresql"; StatusMsg: "Removing PostgreSQL service"


; Kill manually started programs

Filename: "{sys}\taskkill.exe"; Parameters:"/F /IM koi_server.exe"; StatusMsg: "Stopping manually started server"
Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters:"-w -D ""{#ServerCfgDir}\database"" stop"; StatusMsg: "Stopping manually started postrgresql"

Filename: "{#BinDir}\koi_server.exe"; Parameters:"stop"; StatusMsg: "Registering web server service"
Filename: "{#BinDir}\koi_server.exe"; Parameters:"remove"; StatusMsg: "Registering web server service"

; Kill services

; Not active right now (see notes in installation phase)
; Filename: "{cmd}"; Parameters:"/C net stop KoiServiceProduction"; StatusMsg: "Stopping Koi server service"
; Filename: "{cmd}"; Parameters:"/C sc delete KoiServiceProduction"; StatusMsg: "Deleting Koi server service"


; Using pg_ctl as to make a pause between stop and delete of  server
Filename: "{app}\pgsql\bin\pg_ctl.exe"; Parameters:"-D {#ServerCfgDir}\database -N Postgresql unregister"; StatusMsg: "Unregistering PostgreSQL service"

Filename: "{sys}\schtasks.exe"; Parameters:"/Delete /tn ""{#AppName}Web"" /F"
Filename: "{sys}\schtasks.exe"; Parameters:"/Delete /tn ""{#AppName}Daily"" /F"

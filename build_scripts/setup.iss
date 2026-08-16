[Setup]
AppName=Twinclers Guard
AppVersion=1.0
DefaultDirName={autopf}\Twinclers Guard
DefaultGroupName=Twinclers Guard
OutputDir=.\Output
OutputBaseFilename=TwinclersGuardSetup
Compression=lzma
SolidCompression=yes
LicenseFile=License.txt
SetupIconFile=..\app.ico

[Files]
Source: "..\dist\main.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\libs\*"; DestDir: "{app}\libs"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Twinclers Guard"; Filename: "{app}\TwinclersGuard.exe"
Name: "{commondesktop}\Twinclers Guard"; Filename: "{app}\TwinclersGuard.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[UninstallRun]
Filename: "{app}\TwinclersGuard.exe"; Parameters: "--uninstall-cleanup"; Flags: runhidden

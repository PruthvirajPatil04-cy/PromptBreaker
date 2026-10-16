; PromptBreaker Desktop - Windows installer.
; Built with makensis (native on Linux) - output is a standard Windows PE.
Name "PromptBreaker Desktop"
OutFile "dist/PromptBreaker-Setup.exe"
InstallDir $PROGRAMFILES64\PromptBreaker
InstallDirRegKey HKLM "Software\PromptBreaker" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
Unicode true

!include "MUI2.nsh"
!define MUI_ICON "winres/icon.ico"
!define MUI_UNICON "winres/icon.ico"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "PromptBreaker Desktop" SecMain
  SetOutPath $INSTDIR
  File "dist/PromptBreaker.exe"
  File "config.json"
  File "README.txt"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\PromptBreaker" "InstallDir" $INSTDIR
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreaker" "DisplayName" "PromptBreaker Desktop"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreaker" "DisplayVersion" "1.1.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreaker" "Publisher" "PromptBreaker"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreaker" "DisplayIcon" "$INSTDIR\PromptBreaker.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreaker" "UninstallString" "$INSTDIR\Uninstall.exe"
  CreateShortCut "$DESKTOP\PromptBreaker.lnk" "$INSTDIR\PromptBreaker.exe"
  CreateShortCut "$SMPROGRAMS\PromptBreaker.lnk" "$INSTDIR\PromptBreaker.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\PromptBreaker.lnk"
  Delete "$SMPROGRAMS\PromptBreaker.lnk"
  Delete "$INSTDIR\PromptBreaker.exe"
  Delete "$INSTDIR\config.json"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "Software\PromptBreaker"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreaker"
SectionEnd

; PromptBreaker OFFLINE — per-user Windows installer (no admin required).
; Installs the self-contained bundle (embeddable Python + node.exe + Next
; standalone dashboard + demo chatbots) under %LOCALAPPDATA%\PromptBreaker.
; Built with makensis (native on Linux).
Name "PromptBreaker Offline"
OutFile "dist-offline/PromptBreaker-Offline-Setup.exe"
InstallDir "$LOCALAPPDATA\PromptBreaker"
RequestExecutionLevel user
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

Section "PromptBreaker Offline" SecMain
  SetOutPath $INSTDIR
  File "offline/PromptBreaker.exe"
  File "offline/config.json"
  File "offline/README.txt"
  File /r "offline/runtime"
  File /r "offline/app"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\PromptBreakerOffline" "InstallDir" $INSTDIR
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreakerOffline" "DisplayName" "PromptBreaker Offline"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreakerOffline" "DisplayVersion" "1.2.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreakerOffline" "Publisher" "PromptBreaker"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreakerOffline" "DisplayIcon" "$INSTDIR\PromptBreaker.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreakerOffline" "UninstallString" "$INSTDIR\Uninstall.exe"
  CreateShortCut "$DESKTOP\PromptBreaker Offline.lnk" "$INSTDIR\PromptBreaker.exe"
  CreateShortCut "$SMPROGRAMS\PromptBreaker Offline.lnk" "$INSTDIR\PromptBreaker.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\PromptBreaker Offline.lnk"
  Delete "$SMPROGRAMS\PromptBreaker Offline.lnk"
  Delete "$INSTDIR\PromptBreaker.exe"
  Delete "$INSTDIR\config.json"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\selftest.log"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\app"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\PromptBreakerOffline"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptBreakerOffline"
SectionEnd

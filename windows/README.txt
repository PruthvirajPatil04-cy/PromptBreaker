PromptBreaker Desktop - Windows app
===================================

A native window around the PromptBreaker LLM red-teaming dashboard.

INSTALL
  Run PromptBreaker-Setup.exe (installs to Program Files, adds Desktop and
  Start-menu shortcuts), or just unzip and double-click PromptBreaker.exe.

HOW IT CONNECTS (config.json sits next to PromptBreaker.exe)
  dashboardUrl   local dashboard at http://localhost:3000 - used when the
                 services are running in WSL on this PC (the on-stage path)
  publicUrl      the hosted demo site - used automatically when local is
                 offline; opens in your default browser because the hosted
                 site asks for a password
  publicUser /
  publicPass     login for the hosted site (default: cyberex / prithvi1999@)

  Hosted demo: https://queen-walked-informal-boots.trycloudflare.com
  The URL changes if the host PC restarts the tunnel - edit config.json
  with the fresh URL (it is printed by: journalctl -u promptbreaker-tunnel).

IF BOTH ARE OFFLINE
  You get a help page. Start the services in WSL on the host PC:
    sudo systemctl start promptbreaker-api promptbreaker-dashboard promptbreaker-chatbots
  Then double-click PromptBreaker again.

WEBVIEW2 RUNTIME
  Preinstalled on Windows 10/11. If a machine is missing it:
  https://developer.microsoft.com/microsoft-edge/webview2/

ETHICAL USE
  PromptBreaker is an authorized-testing tool. Only scan systems you own or
  have written permission to test.

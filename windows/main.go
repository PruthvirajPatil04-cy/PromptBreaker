// PromptBreaker Desktop — native Windows shell for the PromptBreaker
// dashboard. Local services first (on-stage demo path), hosted site second
// (opens in the default browser because its password gate needs one),
// offline help page last. Pure Go + WebView2, no cgo — cross-compiles from
// Linux with GOOS=windows.
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/jchv/go-webview2"
)

// Config lives in config.json next to the executable.
type Config struct {
	DashboardURL string `json:"dashboardUrl"` // local dashboard (WSL services)
	PublicURL    string `json:"publicUrl"`    // hosted demo site
	PublicUser   string `json:"publicUser"`   // basic-auth for the hosted site
	PublicPass   string `json:"publicPass"`
}

func loadConfig() Config {
	cfg := Config{DashboardURL: "http://localhost:3000"}
	if exe, err := os.Executable(); err == nil {
		if b, err := os.ReadFile(filepath.Join(filepath.Dir(exe), "config.json")); err == nil {
			_ = json.Unmarshal(b, &cfg)
		}
	}
	return cfg
}

func reachable(raw string, timeout time.Duration) bool {
	client := &http.Client{Timeout: timeout}
	resp, err := client.Get(raw)
	if err != nil {
		return false
	}
	_ = resp.Body.Close()
	return resp.StatusCode < 500
}

func openBrowser(raw string) {
	_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", raw).Start()
}

// window shows raw in a native WebView2 window. Returns false when the
// WebView2 runtime is unavailable (rare — it ships with Windows 10/11).
func window(raw, title string, width, height int) (ok bool) {
	defer func() {
		if r := recover(); r != nil {
			fmt.Println("webview unavailable:", r)
			ok = false
		}
	}()
	w := webview2.New(false)
	defer w.Destroy()
	w.SetTitle(title)
	w.SetSize(width, height, webview2.HintNone)
	w.Navigate(raw)
	w.Run()
	return true
}

func dataURL(html string) string {
	return "data:text/html;charset=utf-8," + url.PathEscape(html)
}

func helpPage(cfg Config) string {
	return dataURL(`<!doctype html><meta charset="utf-8"><style>
body{margin:0;background:#0A0A0B;color:#EDEDEF;font:15px/1.6 system-ui,sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh}
main{max-width:580px;padding:32px}
h1{color:#14B8A6;font-size:20px;margin:0 0 12px}
code{background:#121214;border:1px solid #1F1F23;border-radius:6px;padding:2px 6px;color:#14B8A6}
li{margin:8px 0}</style><main>
<h1>PromptBreaker is offline</h1>
<p>Neither the local dashboard nor the hosted site answered.</p>
<ol>
<li>Start the services (WSL on this PC):<br>
<code>sudo systemctl start promptbreaker-api promptbreaker-dashboard promptbreaker-chatbots</code></li>
<li>Then double-click <b>PromptBreaker</b> again.</li>
</ol>
<p>Hosted demo (used automatically when local is offline):<br><code>` + cfg.PublicURL + `</code></p>
<p style="color:#8B8B93;font-size:13px">Endpoints and credentials live in
<b>config.json</b> next to PromptBreaker.exe.</p></main>`)
}

func main() {
	cfg := loadConfig()

	// 1) local dashboard — the on-stage path (services running in WSL)
	if reachable(cfg.DashboardURL, 2*time.Second) {
		if window(cfg.DashboardURL, "PromptBreaker", 1320, 860) {
			return
		}
		openBrowser(cfg.DashboardURL)
		return
	}

	// 2) hosted demo — its basic-auth gate needs a real browser
	if cfg.PublicURL != "" && reachable(cfg.PublicURL, 6*time.Second) {
		openBrowser(cfg.PublicURL)
		return
	}

	// 3) both offline: help page
	if window(helpPage(cfg), "PromptBreaker - offline", 760, 520) {
		return
	}
	openBrowser(helpPage(cfg))
}

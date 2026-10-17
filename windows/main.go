// PromptBreaker Desktop — native Windows shell for the PromptBreaker
// dashboard. Two modes:
//
//   - OFFLINE bundle (runtime\ next to the exe): boots the bundled engine
//     (embeddable Python + uvicorn), the bundled demo chatbots and the
//     bundled Next standalone dashboard on 127.0.0.1, then opens a native
//     WebView2 window. No WSL, no tunnel, no internet required. The LLM
//     judge auto-detects a local Ollama and degrades to the deterministic
//     prefilter when it is absent (honest "no judge" verdicts, never a guess).
//   - THIN (no runtime\): local WSL services first (on-stage demo path),
//     hosted site second (opens in the default browser because its password
//     gate needs one), offline help page last.
//
// Pure Go + WebView2, no cgo — cross-compiles from Linux with GOOS=windows.
package main

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
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

// ---------------------------------------------------------------------------
// Offline bundle support
// ---------------------------------------------------------------------------

const (
	engineURL   = "http://127.0.0.1:8000"
	dashURL     = "http://127.0.0.1:3000"
	ollamaURL   = "http://127.0.0.1:11434"
	apiKeyFile  = "api.key"
	serviceTOut = 45 * time.Second
)

// demoTargets mirrors demo/chatbots.py — seeded into the fresh offline DB so
// the app is instantly demo-able (scan SecureBot out of the box).
var demoTargets = []struct {
	Name, Slug, Key string
	Port            int
}{
	{"SecureBot", "securebot", "securebot-demo-2026", 18081},
	{"RecordsClerk", "recordsclerk", "records-clerk-demo-2026", 18082},
	{"LeakyAssist", "leakyassist", "leakyassist-demo-2026", 18083},
	{"YesMan", "yesman", "yesman-demo-2026", 18084},
	{"AutoAgent", "autoagent", "autoagent-demo-2026", 18085},
	{"InfiniteWriter", "infinitewriter", "infinite-writer-demo-2026", 18086},
	{"CreativeAI", "creativeai", "creative-ai-demo-2026", 18087},
	{"EvasiveBot", "evasive", "evasive-demo-2026", 18088},
}

// offlinePaths describes the bundled runtime layout next to the exe.
type offlinePaths struct {
	ExeDir   string
	Python   string // runtime\python\python.exe
	Node     string // runtime\node.exe
	DashDir  string // runtime\dashboard (Next standalone output)
	Chatbots string // app\chatbots.py
	APIKey   string // runtime\api.key (plaintext; engine gets its sha256)
	DataDir  string // %LOCALAPPDATA%\PromptBreaker (db + hmac key)
}

func detectOffline() (offlinePaths, bool) {
	var p offlinePaths
	exe, err := os.Executable()
	if err != nil {
		return p, false
	}
	p.ExeDir = filepath.Dir(exe)
	rt := filepath.Join(p.ExeDir, "runtime")
	p.Python = filepath.Join(rt, "python", "python.exe")
	p.Node = filepath.Join(rt, "node.exe")
	p.DashDir = filepath.Join(rt, "dashboard")
	p.Chatbots = filepath.Join(p.ExeDir, "app", "chatbots.py")
	p.APIKey = filepath.Join(rt, apiKeyFile)
	for _, f := range []string{p.Python, p.Node, filepath.Join(p.DashDir, "server.js")} {
		if _, err := os.Stat(f); err != nil {
			return p, false
		}
	}
	if base, err := os.UserCacheDir(); err == nil {
		p.DataDir = filepath.Join(base, "PromptBreaker")
	} else {
		p.DataDir = filepath.Join(p.ExeDir, "data")
	}
	return p, true
}

// spawn starts a child process with a hidden console window.
func spawn(name string, args []string, dir string, env []string) *exec.Cmd {
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), env...)
	hideConsole(cmd)
	_ = cmd.Start()
	return cmd
}

// killTree force-terminates a child and everything it spawned.
func killTree(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	_ = exec.Command("taskkill", "/T", "/F", "/PID",
		strconv.Itoa(cmd.Process.Pid)).Run()
}

// ollamaUp probes a local Ollama. Returns the first installed model name
// (so the bundled engine judges with whatever model this machine actually
// has) or "" when no model endpoint exists.
func ollamaModel() string {
	client := &http.Client{Timeout: 1500 * time.Millisecond}
	resp, err := client.Get(ollamaURL + "/api/tags")
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return ""
	}
	var body struct {
		Models []struct {
			Name string `json:"name"`
		} `json:"models"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&body); err == nil && len(body.Models) > 0 {
		return body.Models[0].Name
	}
	return ""
}

// readFileOrGen returns the trimmed content of path, or generates a random
// hex secret and persists it there (0600) on first run.
func readFileOrGen(path string, bytesN int) string {
	if b, err := os.ReadFile(path); err == nil {
		if s := strings.TrimSpace(string(b)); s != "" {
			return s
		}
	}
	buf := make([]byte, bytesN)
	_, _ = rand.Read(buf)
	s := hex.EncodeToString(buf)
	_ = os.MkdirAll(filepath.Dir(path), 0o755)
	_ = os.WriteFile(path, []byte(s+"\n"), 0o600)
	return s
}

func sha256Hex(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}

func apiGet(base, path, key string) ([]byte, int) {
	req, _ := http.NewRequest("GET", base+path, nil)
	req.Header.Set("x-api-key", key)
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, 0
	}
	defer resp.Body.Close()
	var buf bytes.Buffer
	_, _ = buf.ReadFrom(resp.Body)
	return buf.Bytes(), resp.StatusCode
}

func apiPost(base, path, key string, body []byte) int {
	req, _ := http.NewRequest("POST", base+path, bytes.NewReader(body))
	req.Header.Set("x-api-key", key)
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return 0
	}
	_ = resp.Body.Close()
	return resp.StatusCode
}

// seedTargets registers the 8 demo bots as scan targets on first run so a
// fresh offline install is instantly usable. Idempotent: only seeds when the
// target list is still empty.
func seedTargets(key string) int {
	raw, code := apiGet(engineURL, "/v1/targets", key)
	if code != 200 {
		return -1
	}
	var list []map[string]any
	if err := json.Unmarshal(raw, &list); err != nil {
		return -1 // shape mismatch — leave the DB alone
	}
	if len(list) > 0 {
		return -2 // already seeded (re-launch / repeat selftest)
	}
	created := 0
	for _, t := range demoTargets {
		body, _ := json.Marshal(map[string]any{
			"name":         t.Name,
			"adapter":      "openai",
			"endpoint":     fmt.Sprintf("http://127.0.0.1:%d/v1", t.Port),
			"secretRef":    t.Key,
			"allowPrivate": true,
		})
		if apiPost(engineURL, "/v1/targets", key, body) == 201 {
			created++
		}
	}
	return created
}

// waitStatus polls url until it answers with want (0 = any <500) or timeout.
func waitStatus(url string, want int, timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	client := &http.Client{Timeout: 3 * time.Second}
	for time.Now().Before(deadline) {
		if resp, err := client.Get(url); err == nil {
			_ = resp.Body.Close()
			if want == 0 && resp.StatusCode < 500 {
				return true
			}
			if resp.StatusCode == want {
				return true
			}
		}
		time.Sleep(500 * time.Millisecond)
	}
	return false
}

// runOffline boots the bundled stack. Returns after opening the window (the
// services keep running until the window closes). selftest=true runs the
// full startup + health + seeding checks, writes a log and exits.
func runOffline(p offlinePaths, selftest bool) bool {
	apiKey := ""
	if b, err := os.ReadFile(p.APIKey); err == nil {
		apiKey = strings.TrimSpace(string(b))
	}
	secretOK := apiKey != ""

	judgeModel := ollamaModel()
	judge := judgeModel != ""
	hmac := readFileOrGen(filepath.Join(p.DataDir, "hmac.key"), 32)

	_ = os.MkdirAll(p.DataDir, 0o755)
	engineEnv := []string{
		"PB_API_HOST=127.0.0.1",
		"PB_API_PORT=8000",
		"PB_DATABASE_URL=sqlite+aiosqlite:///./promptbreaker.db",
		"PB_ALLOW_PRIVATE_TARGETS=true",
		"PB_EVIDENCE_HMAC_KEY=" + hmac,
		"PB_LLM_JUDGE_ENABLED=" + strconv.FormatBool(judge),
		"PB_JUDGE_BASE_URL=" + ollamaURL + "/v1",
	}
	if judge {
		engineEnv = append(engineEnv, "PB_JUDGE_MODEL="+judgeModel)
	}
	if secretOK {
		engineEnv = append(engineEnv, "PB_API_KEYS="+sha256Hex(apiKey))
	}

	// Fail fast when another service already owns our ports (a dev box with
	// the WSL services running forwards them onto Windows localhost). Starting
	// the bundle anyway would leave the bundled children dead while health
	// checks silently grade the foreign stack.
	for _, addr := range []string{"127.0.0.1:8000", "127.0.0.1:3000", "127.0.0.1:18081"} {
		ln, err := net.Listen("tcp", addr)
		if err != nil {
			fmt.Println("[offline] port", addr, "owned by another service:", err)
			if selftest {
				writeSelftestLog("FAIL port " + addr + " owned by another service (stop the WSL services first)")
				os.Exit(1)
			}
			return false
		}
		_ = ln.Close()
	}

	var children []*exec.Cmd
	if secretOK {
		children = append(children, spawn(p.Python,
			[]string{"-m", "uvicorn", "promptbreaker.api.app:app",
				"--host", "127.0.0.1", "--port", "8000"},
			p.DataDir, engineEnv))
	}
	if _, err := os.Stat(p.Chatbots); err == nil {
		children = append(children, spawn(p.Python,
			[]string{p.Chatbots, "--loopback"}, p.ExeDir, engineEnv))
	}
	children = append(children, spawn(p.Node,
		[]string{filepath.Join(p.DashDir, "server.js")}, p.DashDir,
		[]string{"PORT=3000", "HOSTNAME=127.0.0.1", "NODE_ENV=production",
			"NEXT_TELEMETRY_DISABLED=1"}))

	stop := func() {
		for _, c := range children {
			killTree(c)
		}
	}
	defer func() {
		if selftest {
			stop()
		}
	}()

	// tee launcher logs into %LOCALAPPDATA%\PromptBreaker\offline.log so a
	// failed boot on a judge's machine can be diagnosed from the file alone.
	lf, _ := os.OpenFile(filepath.Join(p.DataDir, "offline.log"),
		os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	if lf != nil {
		defer lf.Close()
	}
	logf := func(format string, a ...any) {
		line := "[offline] " + fmt.Sprintf(format, a...)
		fmt.Println(line)
		if lf != nil {
			_, _ = lf.WriteString(line + "\n")
		}
	}

	engineOK := !secretOK || waitStatus(engineURL+"/healthz", 200, serviceTOut)
	dashOK := waitStatus(dashURL+"/healthz", 200, serviceTOut)
	// Even with ports free, prove the dashboard we are about to open and the
	// engine behind it answer OUR per-bundle key along the browser's exact
	// path — a foreign stack squatting a port must never be graded as ours.
	oursOK := true
	if secretOK && engineOK && dashOK {
		if _, code := apiGet(dashURL, "/v1/targets", apiKey); code != 200 {
			oursOK = false
			logf("dashboard rejected our key (targets code=%d) — not our stack", code)
		}
	}
	logf("engine=%v dashboard=%v ours=%v judge(prefilter-only)=%v key=%v",
		engineOK, dashOK, oursOK, !judge, secretOK)
	if !engineOK || !dashOK || !oursOK {
		logf("startup FAILED — see errors above")
		if selftest {
			writeSelftestLog(fmt.Sprintf("FAIL engine=%v dashboard=%v ours=%v", engineOK, dashOK, oursOK))
			stop()
			os.Exit(1)
		}
		stop()
		return false
	}

	seeded := -1
	if secretOK {
		seeded = seedTargets(apiKey)
		switch {
		case seeded >= 0:
			logf("demo targets seeded: %d created", seeded)
		case seeded == -2:
			logf("demo targets already present (repeat launch)")
		default:
			logf("demo target seeding skipped (engine said %d)", seeded)
		}
	}

	if selftest {
		// one chatbot probe: the OpenAI-compatible models endpoint answers 200
		chatOK := false
		client := &http.Client{Timeout: 3 * time.Second}
		req, _ := http.NewRequest("GET", "http://127.0.0.1:18081/v1/models", nil)
		req.Header.Set("Authorization", "Bearer securebot-demo-2026")
		if resp, err := client.Do(req); err == nil {
			_ = resp.Body.Close()
			chatOK = resp.StatusCode == 200
		}
		logf("chatbots=%v seeded=%d", chatOK, seeded)
		seedOK := seeded == 8 || seeded == -2
		status := map[bool]string{true: "OK", false: "FAIL"}[chatOK && seedOK]
		writeSelftestLog(fmt.Sprintf(
			"%s engine=200 dashboard=200 chatbots=%v seeded=%d judge=%v",
			status, chatOK, seeded,
			map[bool]string{true: "llm+prefilter:" + judgeModel, false: "prefilter-only"}[judge]))
		stop()
		if status == "OK" {
			os.Exit(0)
		}
		os.Exit(1)
	}

	if window(dashURL, "PromptBreaker", 1320, 860) {
		return true
	}
	openBrowser(dashURL)
	return true
}

func writeSelftestLog(content string) {
	line := "PB_OFFLINE_SELFTEST " + time.Now().UTC().Format(time.RFC3339) + " " + content + "\n"
	if exe, err := os.Executable(); err == nil {
		if err := os.WriteFile(filepath.Join(filepath.Dir(exe), "selftest.log"),
			[]byte(line), 0o644); err == nil {
			return
		}
	}
	if base, err := os.UserCacheDir(); err == nil {
		_ = os.WriteFile(filepath.Join(base, "pb-selftest.log"), []byte(line), 0o644)
	}
}

func main() {
	selftest := false
	for _, a := range os.Args[1:] {
		if a == "--selftest" {
			selftest = true
		}
	}

	// 0) offline bundle next to the exe — fully local, no WSL/internet needed
	if p, ok := detectOffline(); ok {
		if runOffline(p, selftest) {
			return
		}
		// bundle failed to boot and no window opened: fall through to thin
		// chain so the user still has a path (hosted site / help page).
	}

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

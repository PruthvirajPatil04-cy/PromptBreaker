//go:build windows

package main

import (
	"os/exec"
	"syscall"
)

// hideConsole keeps the bundled python/node children from flashing console
// windows on the user's desktop.
func hideConsole(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
}

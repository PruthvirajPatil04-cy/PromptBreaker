//go:build !windows

package main

import "os/exec"

// hideConsole is a no-op off Windows; the file exists so the package still
// type-checks (go vet) on the Linux build host.
func hideConsole(cmd *exec.Cmd) {}

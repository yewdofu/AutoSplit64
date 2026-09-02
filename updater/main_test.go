package main

import (
	"archive/zip"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// selfReplaceProbeEnv turns a copy of this test binary into a stand-in for a
// running updater: it replaces its own image with the file the variable names,
// then exits. Windows refuses to open a running executable for writing, which
// is what broke the update in the first place, so nothing short of a real
// running image proves the rename swap actually works.
const selfReplaceProbeEnv = "AS64_SELF_REPLACE_PROBE"

// extractProbeEnv runs the whole installation step from inside the install
// directory, as a running executable that the update is about to overwrite.
const extractProbeEnv = "AS64_EXTRACT_PROBE"

func TestMain(m *testing.M) {
	if staged := os.Getenv(selfReplaceProbeEnv); staged != "" {
		self, err := os.Executable()
		if err != nil {
			os.Stderr.WriteString(err.Error())
			os.Exit(2)
		}
		if err := replaceSelf(staged, filepath.Clean(self)); err != nil {
			os.Stderr.WriteString(err.Error())
			os.Exit(3)
		}
		os.Exit(0)
	}
	if os.Getenv(extractProbeEnv) != "" {
		u := &UpdaterWindow{}
		if err := u.resolvePaths(); err != nil {
			os.Stderr.WriteString(err.Error())
			os.Exit(4)
		}
		if err := u.extract(); err != nil {
			os.Stderr.WriteString(err.Error())
			os.Exit(5)
		}
		os.Exit(0)
	}
	os.Exit(m.Run())
}

func TestRunningExecutableCannotBeOverwrittenInPlace(t *testing.T) {
	self, err := os.Executable()
	if err != nil {
		t.Fatalf("os.Executable: %v", err)
	}

	f, err := os.Create(self)
	if err == nil {
		f.Close()
		t.Fatal("opened a running executable for writing; the extraction no longer " +
			"needs to stage files and swap the running image aside")
	}
}

func TestReplaceSelfSwapsARunningExecutable(t *testing.T) {
	dir := t.TempDir()

	testBin, err := os.Executable()
	if err != nil {
		t.Fatalf("os.Executable: %v", err)
	}
	running := filepath.Join(dir, "AS64Updater.exe")
	copyFile(t, testBin, running)

	staged := filepath.Join(dir, "staged.exe")
	const payload = "new updater image"
	writeFile(t, staged, payload)

	cmd := exec.Command(running)
	cmd.Env = append(os.Environ(), selfReplaceProbeEnv+"="+staged)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("self-replacement failed: %v: %s", err, out)
	}

	if got := readFile(t, running); got != payload {
		t.Errorf("running executable was not replaced: got %q, want %q", got, payload)
	}
	// The image is still mapped as the process exits, so the ".old" removal
	// fails and the residue is left for the next run to clear. If this ever
	// stops holding, the cleanup at the top of run() is what keeps working.
	if _, err := os.Stat(running + ".old"); err != nil {
		t.Logf("no .old residue left behind (%v); cleanup in run() covers both cases", err)
	}
}

func TestExtractInstallsEveryEntryIncludingTheUpdaterItself(t *testing.T) {
	install := t.TempDir()
	u := newTestUpdater(t, install)

	writeFile(t, filepath.Join(install, "AutoSplit64.exe"), "old app")
	writeFile(t, u.selfExe, "old updater")

	writeZip(t, u.patchPath, map[string]string{
		"_internal/model.onnx": "new model",
		"AutoSplit64.exe":      "new app",
		"AS64Updater.exe":      "new updater",
	})

	if err := u.extract(); err != nil {
		t.Fatalf("extract: %v", err)
	}

	for name, want := range map[string]string{
		"_internal/model.onnx": "new model",
		"AutoSplit64.exe":      "new app",
		"AS64Updater.exe":      "new updater",
	} {
		got := readFile(t, filepath.Join(install, filepath.FromSlash(name)))
		if got != want {
			t.Errorf("%s: got %q, want %q", name, got, want)
		}
	}
}

// The one that reproduces the shipped bug end to end: a real running updater
// installs an update whose zip contains the updater itself, started from a
// working directory that is not the install directory.
func TestRunningUpdaterInstallsAnUpdateThatContainsItself(t *testing.T) {
	install := t.TempDir()
	elsewhere := t.TempDir()

	testBin, err := os.Executable()
	if err != nil {
		t.Fatalf("os.Executable: %v", err)
	}
	running := filepath.Join(install, "AS64Updater.exe")
	copyFile(t, testBin, running)
	writeFile(t, filepath.Join(install, "AutoSplit64.exe"), "old app")

	writeZip(t, filepath.Join(install, patchFileName), map[string]string{
		"_internal/model.onnx": "new model",
		"AutoSplit64.exe":      "new app",
		"AS64Updater.exe":      "new updater",
	})

	cmd := exec.Command(running)
	cmd.Env = append(os.Environ(), extractProbeEnv+"=1")
	// Deliberately not the install directory: the updater inherits its working
	// directory from whatever started AutoSplit64.exe and must not rely on it.
	cmd.Dir = elsewhere
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("install failed: %v: %s", err, out)
	}

	for name, want := range map[string]string{
		"_internal/model.onnx": "new model",
		"AutoSplit64.exe":      "new app",
		"AS64Updater.exe":      "new updater",
	} {
		got := readFile(t, filepath.Join(install, filepath.FromSlash(name)))
		if got != want {
			t.Errorf("%s: got %q, want %q", name, got, want)
		}
	}

	if entries, err := os.ReadDir(elsewhere); err != nil {
		t.Fatalf("ReadDir: %v", err)
	} else if len(entries) != 0 {
		t.Errorf("the update wrote into the working directory: %v", entries)
	}
}

func TestExtractLeavesNoStagingDirectoryBehind(t *testing.T) {
	install := t.TempDir()
	u := newTestUpdater(t, install)

	writeZip(t, u.patchPath, map[string]string{"AutoSplit64.exe": "new app"})

	if err := u.extract(); err != nil {
		t.Fatalf("extract: %v", err)
	}

	entries, err := os.ReadDir(install)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}
	for _, entry := range entries {
		if strings.HasPrefix(entry.Name(), ".as64update-tmp") {
			t.Errorf("staging directory %s was left behind", entry.Name())
		}
	}
}

func TestExtractRejectsEntriesOutsideTheInstallDirectory(t *testing.T) {
	for _, name := range []string{"../escaped.txt", `..\escaped.txt`, "sub/../../escaped.txt"} {
		t.Run(name, func(t *testing.T) {
			install := t.TempDir()
			outside := filepath.Join(filepath.Dir(install), "escaped.txt")
			u := newTestUpdater(t, install)

			writeZip(t, u.patchPath, map[string]string{name: "owned"})

			if err := u.extract(); err == nil {
				t.Fatal("extract accepted an entry pointing outside the install directory")
			}
			if _, err := os.Stat(outside); err == nil {
				t.Errorf("%s was written outside the install directory", outside)
			}
		})
	}
}

func TestExtractLeavesTheInstallUntouchedWhenAnEntryIsRejected(t *testing.T) {
	install := t.TempDir()
	u := newTestUpdater(t, install)

	app := filepath.Join(install, "AutoSplit64.exe")
	writeFile(t, app, "old app")

	// The good entry is staged first; the rejected one must stop the update
	// before anything is moved into place.
	writeZip(t, u.patchPath, map[string]string{
		"AutoSplit64.exe": "new app",
		"../escaped.txt":  "owned",
	})

	if err := u.extract(); err == nil {
		t.Fatal("extract accepted an entry pointing outside the install directory")
	}
	if got := readFile(t, app); got != "old app" {
		t.Errorf("install was modified by a failed update: AutoSplit64.exe is %q", got)
	}
}

// newTestUpdater builds an updater whose paths point at a throwaway install
// directory, the way resolvePaths would set them up from a real executable.
func newTestUpdater(t *testing.T, install string) *UpdaterWindow {
	t.Helper()
	return &UpdaterWindow{
		selfExe:   filepath.Join(install, "AS64Updater.exe"),
		baseDir:   install,
		patchPath: filepath.Join(install, patchFileName),
	}
}

func writeZip(t *testing.T, path string, entries map[string]string) {
	t.Helper()
	f, err := os.Create(path)
	if err != nil {
		t.Fatalf("create zip: %v", err)
	}
	defer f.Close()

	w := zip.NewWriter(f)
	for name, content := range entries {
		entry, err := w.Create(name)
		if err != nil {
			t.Fatalf("create zip entry %s: %v", name, err)
		}
		if _, err := entry.Write([]byte(content)); err != nil {
			t.Fatalf("write zip entry %s: %v", name, err)
		}
	}
	if err := w.Close(); err != nil {
		t.Fatalf("close zip: %v", err)
	}
}

func copyFile(t *testing.T, src, dst string) {
	t.Helper()
	data, err := os.ReadFile(src)
	if err != nil {
		t.Fatalf("read %s: %v", src, err)
	}
	if err := os.WriteFile(dst, data, 0755); err != nil {
		t.Fatalf("write %s: %v", dst, err)
	}
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

func readFile(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return string(data)
}

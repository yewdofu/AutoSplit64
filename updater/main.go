package main

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/lxn/walk"
	. "github.com/lxn/walk/declarative"
	"github.com/lxn/win"
	"golang.org/x/sys/windows"
)

const (
	apiURL    = "https://api.github.com/repos/yewdofu/AutoSplit64/releases/latest"
	patchFile = "patch.zip"
)

type Release struct {
	TagName string  `json:"tag_name"`
	Assets  []Asset `json:"assets"`
}

type Asset struct {
	Name               string `json:"name"`
	BrowserDownloadURL string `json:"browser_download_url"`
	Size               int64  `json:"size"`
}

type UpdaterWindow struct {
	*walk.MainWindow
	statusLabel *walk.Label
	progressBar *walk.ProgressBar
	abortBtn    *walk.PushButton
	aborted     bool
}

func main() {
	u := &UpdaterWindow{}

	if err := (MainWindow{
		AssignTo: &u.MainWindow,
		Title:    "AutoSplit64 Updater",
		MinSize:  Size{Width: 280, Height: 90},
		MaxSize:  Size{Width: 280, Height: 90},
		Layout:   VBox{Margins: Margins{Left: 6, Top: 6, Right: 6, Bottom: 6}, Spacing: 3},
		Children: []Widget{
			Label{AssignTo: &u.statusLabel, Text: "Connecting..."},
			ProgressBar{AssignTo: &u.progressBar, MinValue: 0, MaxValue: 100},
			Composite{
				Layout: HBox{MarginsZero: true},
				Children: []Widget{
					HSpacer{},
					PushButton{
						AssignTo: &u.abortBtn,
						Text:     "Abort",
						MaxSize:  Size{Width: 80},
						OnClicked: func() {
							u.aborted = true
							u.MainWindow.Close()
						},
					},
				},
			},
		},
	}.Create()); err != nil {
		panic(err)
	}

	u.MainWindow.SetBounds(walk.Rectangle{X: 100, Y: 100, Width: 280, Height: 90})
	hwnd := u.MainWindow.Handle()
	style := win.GetWindowLong(hwnd, win.GWL_STYLE)
	win.SetWindowLong(hwnd, win.GWL_STYLE, style&^win.WS_THICKFRAME)
	go u.run()
	u.Run()
}

func (u *UpdaterWindow) setStatus(text string) {
	u.Synchronize(func() { u.statusLabel.SetText(text) })
}

func (u *UpdaterWindow) setProgress(pct int) {
	u.Synchronize(func() { u.progressBar.SetValue(pct) })
}

func (u *UpdaterWindow) run() {
	release, err := fetchRelease()
	if err != nil {
		u.setStatus(fmt.Sprintf("Error: %v", err))
		return
	}

	var asset *Asset
	for i := range release.Assets {
		if strings.HasSuffix(release.Assets[i].Name, ".zip") {
			asset = &release.Assets[i]
			break
		}
	}
	if asset == nil {
		u.setStatus("Error: release asset not found")
		return
	}

	version := strings.TrimPrefix(release.TagName, "v")

	u.setStatus(fmt.Sprintf("Downloading Version %s", version))
	if err := u.download(asset.BrowserDownloadURL, asset.Size); err != nil {
		if !u.aborted {
			u.setStatus(fmt.Sprintf("Download error: %v", err))
		}
		os.Remove(patchFile)
		return
	}
	if u.aborted {
		os.Remove(patchFile)
		return
	}

	u.setStatus(fmt.Sprintf("Installing Version %s", version))
	u.setProgress(0)
	if err := u.extract(); err != nil {
		u.setStatus(fmt.Sprintf("Install error: %v", err))
		os.Remove(patchFile)
		return
	}
	os.Remove(patchFile)

	exePath, _ := filepath.Abs("AutoSplit64.exe")
	exec.Command(exePath).Start()

	u.Synchronize(func() { u.MainWindow.Close() })
}

func fetchRelease() (*Release, error) {
	req, _ := http.NewRequest("GET", apiURL, nil)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var r Release
	return &r, json.NewDecoder(resp.Body).Decode(&r)
}

func (u *UpdaterWindow) download(url string, totalSize int64) error {
	resp, err := http.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if totalSize == 0 {
		totalSize = resp.ContentLength
	}

	f, err := os.Create(patchFile)
	if err != nil {
		return err
	}
	defer f.Close()

	buf := make([]byte, 64*1024)
	var downloaded int64
	for {
		if u.aborted {
			return nil
		}
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			if _, writeErr := f.Write(buf[:n]); writeErr != nil {
				return writeErr
			}
			downloaded += int64(n)
			if totalSize > 0 {
				u.setProgress(int(downloaded * 100 / totalSize))
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			return readErr
		}
	}
	return nil
}

func (u *UpdaterWindow) extract() error {
	r, err := zip.OpenReader(patchFile)
	if err != nil {
		return err
	}
	defer r.Close()

	basePath, err := filepath.Abs(".")
	if err != nil {
		return err
	}

	selfExe, err := selfExecutablePath()
	if err != nil {
		return err
	}

	tmpDir, err := os.MkdirTemp(basePath, ".as64update-tmp")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmpDir)

	var totalSize int64
	for _, f := range r.File {
		totalSize += int64(f.UncompressedSize64)
	}
	if totalSize == 0 {
		totalSize = 1
	}

	var done int64
	for _, f := range r.File {
		if err := extractFile(f, basePath, tmpDir); err != nil {
			return err
		}
		done += int64(f.UncompressedSize64)
		u.setProgress(int(done * 100 / totalSize))
	}

	return replaceFiles(tmpDir, basePath, selfExe)
}

// extractFile validates that the entry resolves inside basePath, then writes
// it to the same relative location under tmpDir so replaceFiles can move it
// into place with a path that has already been checked.
func extractFile(f *zip.File, basePath, tmpDir string) error {
	name := filepath.FromSlash(f.Name)
	if filepath.IsAbs(name) {
		return fmt.Errorf("illegal file path in zip: %s", f.Name)
	}

	dst := filepath.Clean(filepath.Join(basePath, name))
	if dst != basePath && !strings.HasPrefix(dst, basePath+string(os.PathSeparator)) {
		return fmt.Errorf("illegal file path in zip: %s", f.Name)
	}

	rel, err := filepath.Rel(basePath, dst)
	if err != nil {
		return err
	}
	extractPath := filepath.Join(tmpDir, rel)

	if f.FileInfo().IsDir() {
		return os.MkdirAll(extractPath, 0755)
	}
	if err := os.MkdirAll(filepath.Dir(extractPath), 0755); err != nil {
		return err
	}

	out, err := os.Create(extractPath)
	if err != nil {
		return err
	}
	defer out.Close()

	src, err := f.Open()
	if err != nil {
		return err
	}
	defer src.Close()

	_, err = io.Copy(out, src)
	return err
}

func replaceFiles(tmpDir, basePath, selfExe string) error {
	var selfFound bool
	err := filepath.Walk(tmpDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(tmpDir, path)
		if err != nil {
			return err
		}
		if rel == "." {
			return nil
		}
		dest := filepath.Join(basePath, rel)
		if info.IsDir() {
			return os.MkdirAll(dest, 0755)
		}
		if err := os.MkdirAll(filepath.Dir(dest), 0755); err != nil {
			return err
		}
		if selfExe != "" && samePath(dest, selfExe) {
			selfFound = true
			return os.Rename(path, filepath.Join(basePath, "Updater.exe.new"))
		}
		return os.Rename(path, dest)
	})
	if err != nil {
		return err
	}
	if selfFound {
		launchSelfReplacement(filepath.Join(basePath, "Updater.exe.new"), selfExe)
	}
	return nil
}

// selfExecutablePath returns the normalized absolute path of the currently
// running executable (this Updater.exe).
func selfExecutablePath() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	abs, err := filepath.Abs(exe)
	if err != nil {
		return "", err
	}
	return filepath.Clean(abs), nil
}

// samePath compares two file paths ignoring case, which is required on
// Windows where paths are case-insensitive.
func samePath(a, b string) bool {
	return strings.EqualFold(filepath.Clean(a), filepath.Clean(b))
}

// launchSelfReplacement spawns a detached process that, after a short delay,
// overwrites the running Updater.exe with the staged Updater.exe.new. It must
// outlive the parent process, hence no Wait and DETACHED_PROCESS is used.
func launchSelfReplacement(newPath, selfExe string) {
	cmdStr := fmt.Sprintf(`ping 127.0.0.1 -n 2 > nul & move /Y "%s" "%s"`, newPath, selfExe)
	cmd := exec.Command("cmd.exe", "/c", cmdStr)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		CreationFlags: windows.CREATE_NEW_PROCESS_GROUP | windows.DETACHED_PROCESS,
	}
	cmd.Start()
}

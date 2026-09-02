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

	"github.com/lxn/walk"
	. "github.com/lxn/walk/declarative"
	"github.com/lxn/win"
)

const (
	apiURL        = "https://api.github.com/repos/yewdofu/AutoSplit64/releases/latest"
	patchFileName = "patch.zip"
	appExeName    = "AutoSplit64.exe"
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

	selfExe   string // absolute path of this running executable
	baseDir   string // install directory (the directory holding this executable)
	patchPath string // downloaded release zip, inside baseDir
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

// setStatus and setProgress are no-ops when there is no window, so the update
// logic can be driven directly from tests.

func (u *UpdaterWindow) setStatus(text string) {
	if u.MainWindow == nil {
		return
	}
	u.Synchronize(func() { u.statusLabel.SetText(text) })
}

func (u *UpdaterWindow) setProgress(pct int) {
	if u.MainWindow == nil {
		return
	}
	u.Synchronize(func() { u.progressBar.SetValue(pct) })
}

func (u *UpdaterWindow) run() {
	if err := u.resolvePaths(); err != nil {
		u.setStatus(fmt.Sprintf("Error: %v", err))
		return
	}

	// Clean up the ".old" residue left by a previous self-replacement. It is
	// usually gone by now, but removal can fail while the old image is still
	// mapped into memory; that error is ignored.
	_ = os.Remove(u.selfExe + ".old")

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
		os.Remove(u.patchPath)
		return
	}
	if u.aborted {
		os.Remove(u.patchPath)
		return
	}

	u.setStatus(fmt.Sprintf("Installing Version %s", version))
	u.setProgress(0)
	if err := u.extract(); err != nil {
		u.setStatus(fmt.Sprintf("Install error: %v", err))
		os.Remove(u.patchPath)
		return
	}
	os.Remove(u.patchPath)

	cmd := exec.Command(filepath.Join(u.baseDir, appExeName))
	cmd.Dir = u.baseDir
	cmd.Start()

	u.Synchronize(func() { u.MainWindow.Close() })
}

// resolvePaths anchors every path this updater touches to the directory of the
// running executable. The working directory is inherited from whatever started
// AutoSplit64.exe and is not necessarily the install directory, so it cannot be
// used to locate the installation.
func (u *UpdaterWindow) resolvePaths() error {
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	abs, err := filepath.Abs(exe)
	if err != nil {
		return err
	}
	u.selfExe = filepath.Clean(abs)
	u.baseDir = filepath.Dir(u.selfExe)
	u.patchPath = filepath.Join(u.baseDir, patchFileName)
	return nil
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

	f, err := os.Create(u.patchPath)
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
	r, err := zip.OpenReader(u.patchPath)
	if err != nil {
		return err
	}
	defer r.Close()

	basePath := u.baseDir

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

	return replaceFiles(tmpDir, basePath, u.selfExe)
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
	return filepath.Walk(tmpDir, func(path string, info os.FileInfo, err error) error {
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
			return replaceSelf(path, selfExe)
		}
		return os.Rename(path, dest)
	})
}

// samePath compares two file paths ignoring case, which is required on
// Windows where paths are case-insensitive.
func samePath(a, b string) bool {
	return strings.EqualFold(filepath.Clean(a), filepath.Clean(b))
}

// replaceSelf swaps the running updater executable for the staged replacement.
// Windows permits renaming an executable image that is currently in use, so the
// running file is first moved aside to ".old". The new file then takes its
// place via an ordinary rename, and removal of the old file is attempted
// best-effort (it may still be mapped into memory, in which case deletion fails
// with "Access is denied"; that is fine and the file is cleaned up on a later
// run).
func replaceSelf(newPath, selfExe string) error {
	oldExe := selfExe + ".old"
	if err := os.Rename(selfExe, oldExe); err != nil {
		return err
	}
	if err := os.Rename(newPath, selfExe); err != nil {
		return err
	}
	_ = os.Remove(oldExe)
	return nil
}

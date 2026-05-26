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

	var totalSize int64
	for _, f := range r.File {
		totalSize += int64(f.UncompressedSize64)
	}
	if totalSize == 0 {
		totalSize = 1
	}

	var done int64
	for _, f := range r.File {
		if err := extractFile(f); err != nil {
			return err
		}
		done += int64(f.UncompressedSize64)
		u.setProgress(int(done * 100 / totalSize))
	}
	return nil
}

func extractFile(f *zip.File) error {
	name := filepath.FromSlash(f.Name)

	if f.FileInfo().IsDir() {
		return os.MkdirAll(name, 0755)
	}
	if err := os.MkdirAll(filepath.Dir(name), 0755); err != nil {
		return err
	}

	dst, err := os.Create(name)
	if err != nil {
		return err
	}
	defer dst.Close()

	src, err := f.Open()
	if err != nil {
		return err
	}
	defer src.Close()

	_, err = io.Copy(dst, src)
	return err
}

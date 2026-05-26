import os
import json
import logging
import requests
import zipfile

from PyQt5 import QtCore

logging.basicConfig(
    filename="updater.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    filemode="w",
)


from as64core import resource_utils
from as64core import config


class UpdaterCore(QtCore.QThread):
    """
    Listener Callbacks:
        update_complete
        update_error
        download_complete
        download_report
        install_report

    """

    PATCH_FILE = "patch.zip"
    DEFAULT_VERSION_KEY = "version"
    DEFAULT_PATCH_URL_KEY = "patch_url"
    CONFIG_UPDATE_FILE = "config.update"

    def __init__(self,
                 master_version_url,
                 local_version_path,
                 master_version_key=DEFAULT_VERSION_KEY,
                 local_version_key=DEFAULT_VERSION_KEY,
                 patch_url_key=DEFAULT_PATCH_URL_KEY):
        super().__init__()

        # Version Data Locations
        self.master_version_url = master_version_url
        self.local_version_path = local_version_path

        # Version Data
        self.master_version = None
        self.local_version = None

        # Version Number Keys
        self.master_version_key = master_version_key
        self.local_version_key = local_version_key

        self.patch_url_key = patch_url_key

        # Listeners
        self._listener = None

        # Download Flags
        self._abort_download = False

    def run(self):
        logging.info("Updater started")
        self.acquire_master()

        if not self.master_version or not self.master_version.get(self.patch_url_key):
            logging.warning("No master version or patch_url found")
            self._listener.update_complete()
            return False

        logging.info(f"patch_url: {self.master_version.get(self.patch_url_key)}")
        self._listener.update_found(self.master_version[self.master_version_key])

        try:
            self._listener.download_begin()
        except AttributeError:
            pass

        try:
            self.download_patch()
        except Exception as e:
            logging.exception("Download failed")
            try:
                self._listener.update_error(f"Download failed: {e}")
            except AttributeError:
                pass
            return False

        if self._abort_download:
            self.cleanup()
            try:
                self._listener.update_complete()
            except AttributeError:
                pass
            return False

        if not self.apply_patch():
            self.cleanup()
            return False

        self.update_config()

        self.cleanup()

        logging.info("Update complete")
        self._listener.update_complete()

        return True

    def get_master(self):
        if not self.master_version:
            self.acquire_master()

        return self.master_version

    def get_local(self):
        if not self.local_version:
            self.load_local()

        return self.local_version

    def acquire_master(self):
        try:
            response = requests.get(
                self.master_version_url,
                headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                timeout=10,
            )
            release = response.json()
            asset = next((a for a in release.get("assets", []) if a["name"].endswith(".zip")), None)
            features = [
                line.strip().lstrip("-* ").strip()
                for line in release.get("body", "").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            self.master_version = {
                "version": release["tag_name"].lstrip("v"),
                "patch_url": asset["browser_download_url"] if asset else None,
                "patch_size": round(asset["size"] / (1024 * 1024), 1) if asset else 0,
                "version_features": features,
                "version_post": release.get("html_url", ""),
            }
        except (requests.exceptions.ConnectionError, json.decoder.JSONDecodeError, KeyError):
            pass

    def load_local(self):
        try:
            with open(resource_utils.resource_path(self.local_version_path)) as local:
                self.local_version = json.load(local)
        except FileNotFoundError:
            pass

    def update_available(self):
        if not self.master_version:
            self.acquire_master()

        if not self.local_version:
            self.load_local()

        if self.master_version is None or self.local_version is None:
            return False

        def parse(v):
            return tuple(int(x) for x in v.lstrip("v").split("."))

        return parse(self.local_version[self.local_version_key]) < parse(self.master_version[self.master_version_key])

    def download_patch(self):
        logging.info("Starting download")
        response = requests.get(
            self.master_version[self.patch_url_key],
            stream=True,
            timeout=60,
        )
        logging.info(f"Response status: {response.status_code}, Content-Length: {response.headers.get('Content-Length')}")
        response.raise_for_status()

        total_size = int(response.headers.get("Content-Length", 0))
        current_bytes = 0

        with open(UpdaterCore.PATCH_FILE, 'wb') as file:
            for chunk in response.iter_content(chunk_size=65536):
                if self._abort_download:
                    logging.info("Download aborted")
                    break
                if chunk:
                    file.write(chunk)
                    current_bytes += len(chunk)
                    logging.debug(f"Downloaded {current_bytes} / {total_size} bytes")
                    if total_size:
                        self._chunk_report(current_bytes, total_size)

        logging.info(f"Download finished: {current_bytes} bytes written")

        if not self._abort_download:
            try:
                self._listener.download_complete()
            except AttributeError:
                pass

    def apply_patch(self):
        logging.info("Applying patch")
        try:
            with zipfile.ZipFile(UpdaterCore.PATCH_FILE, 'r') as zip_file:
                entries = [info for info in zip_file.infolist() if not info.is_dir()]
                total_size = sum(info.file_size for info in entries) or 1
                current_bytes = 0

                for info in entries:
                    logging.debug(f"Extracting: {info.filename}")
                    zip_file.extract(info, '.')
                    current_bytes += info.file_size
                    try:
                        self._listener.install_report(current_bytes / total_size * 100.0)
                    except AttributeError:
                        pass
            logging.info("Patch applied successfully")
            return True
        except Exception as e:
            logging.exception("apply_patch failed")
            try:
                self._listener.update_error(str(e))
            except AttributeError:
                pass
            return False

    def update_config(self):
        try:
            with open(resource_utils.resource_path(self.CONFIG_UPDATE_FILE)) as file:
                config_update = json.load(file)
        except (FileNotFoundError, PermissionError):
            return

        try:
            for update in config_update["Update"]:
                config.set_key(update[0], update[1], config.get_default(update[0], update[1]))

            config.save_config()
        except:
            pass

    def cleanup(self):
        try:
            os.remove(UpdaterCore.PATCH_FILE)
        except (FileNotFoundError, PermissionError):
            pass

        try:
            os.remove(self.CONFIG_UPDATE_FILE)
        except (FileNotFoundError, PermissionError):
            pass

    def set_ignore_update(self, ignore):
        self.load_local()

        self.local_version["ignore_updates"] = ignore

        with open(self.local_version_path, "w") as file:
            json.dump(self.local_version, file, indent=4)

    def _chunk_report(self, current_bytes, total_size):
        percent = float(current_bytes) / total_size
        percent = round(percent * 100, 2)

        try:
            self._listener.download_report(percent)
        except AttributeError:
            pass

    def _chunk_read(self, response, chunk_size=8192, report_hook=None):
        total_size = int(response.info().get("Content-Length").strip())
        current_bytes = 0
        data = b""

        while not self._abort_download:
            chunk = response.read(chunk_size)
            current_bytes += len(chunk)

            if not chunk:
                break

            if report_hook:
                report_hook(current_bytes, total_size)

            data += chunk

        return data

    def abort_download(self):
        self._abort_download = True
        self.cleanup()


    def set_listener(self, listener):
        self._listener = listener

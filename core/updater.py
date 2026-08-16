import json
import os
import tempfile
import urllib.request
import urllib.error
import subprocess
import sys
import threading
from typing import Optional, Dict

from core.constants import APP_VERSION, UPDATE_URL

class AutoUpdater:
    @staticmethod
    def check_for_updates() -> Optional[Dict[str, str]]:
        """
        Checks the remote URL for an update.json file.
        Returns the metadata dict if a newer version is available, else None.
        """
        try:
            req = urllib.request.Request(UPDATE_URL, headers={'User-Agent': 'TwinclersGuard-Updater'})
            with urllib.request.urlopen(req, timeout=5) as response:
                metadata = json.loads(response.read().decode('utf-8'))
                
            latest = metadata.get("version", "0.0.0")
            
            # Simple version comparison
            current_tuple = tuple(map(int, APP_VERSION.split('.')))
            latest_tuple = tuple(map(int, latest.split('.')))
            
            if latest_tuple > current_tuple:
                return metadata
            return None
        except (urllib.error.URLError, json.JSONDecodeError, ValueError, OSError):
            return None

    @staticmethod
    def download_and_install(download_url: str, signature_hex: str, progress_callback=None) -> bool:
        """
        Downloads the installer, verifies its Ed25519 cryptographic signature,
        and executes it silently if authentic.
        """
        try:
            temp_dir = tempfile.gettempdir()
            installer_path = os.path.join(temp_dir, "TwinclersGuard_Update.exe")
            
            req = urllib.request.Request(download_url, headers={'User-Agent': 'TwinclersGuard-Updater'})
            with urllib.request.urlopen(req, timeout=10) as response:
                total_size = int(response.getheader('Content-Length', 0) or 0)
                bytes_so_far = 0
                
                with open(installer_path, 'wb') as f:
                    while True:
                        chunk = response.read(16384)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_so_far += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(bytes_so_far, total_size)
                            
            # Verify Cryptographic Signature to prevent MitM / Supply Chain Attacks
            from cryptography.hazmat.primitives.asymmetric import ed25519
            from cryptography.exceptions import InvalidSignature
            from core.constants import UPDATE_PUBLIC_KEY_HEX
            
            with open(installer_path, 'rb') as f:
                file_data = f.read()
                
            try:
                public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(UPDATE_PUBLIC_KEY_HEX))
                public_key.verify(bytes.fromhex(signature_hex), file_data)
            except (InvalidSignature, ValueError, TypeError):
                # Signature mismatch - malicious or corrupted file!
                os.remove(installer_path)
                return False
                            
            # Execute Inno Setup installer silently
            subprocess.Popen([installer_path, '/SILENT'])
            sys.exit(0)
            
        except (urllib.error.URLError, OSError, Exception):
            return False

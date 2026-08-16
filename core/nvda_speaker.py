"""
NVDA Speaker & Screen Reader Integration Module for Twinclers Guard.
Uses nvdaControllerClient.dll directly via ctypes with fallback to SAPI / Audio Cues.
"""

import os
import sys
import ctypes
import winsound

class NVDASpeaker:
    def __init__(self):
        self._nvda_dll = None
        self._sapi = None
        self._is_64bit = sys.maxsize > 2**32
        self._init_nvda()

    def _init_nvda(self):
        """Loads the nvdaControllerClient DLL matching the architecture (32/64 bit)."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        libs_dir = os.path.join(base_dir, "libs")
        
        dll_name = "nvdaControllerClient64.dll" if self._is_64bit else "nvdaControllerClient32.dll"
        dll_path = os.path.join(libs_dir, dll_name)

        if not os.path.exists(dll_path):
            # Fallback path jika ada di site-packages
            try:
                import accessible_output2
                pkg_lib = os.path.join(os.path.dirname(accessible_output2.__file__), "lib", dll_name)
                if os.path.exists(pkg_lib):
                    dll_path = pkg_lib
            except Exception:
                pass

        if os.path.exists(dll_path):
            try:
                self._nvda_dll = ctypes.windll.LoadLibrary(dll_path)
                # Definisikan signature fungsi DLL
                self._nvda_dll.nvdaController_testIfRunning.restype = ctypes.c_long
                
                self._nvda_dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
                self._nvda_dll.nvdaController_speakText.restype = ctypes.c_long

                self._nvda_dll.nvdaController_brailleMessage.argtypes = [ctypes.c_wchar_p]
                self._nvda_dll.nvdaController_brailleMessage.restype = ctypes.c_long

                self._nvda_dll.nvdaController_cancelSpeech.restype = ctypes.c_long
            except Exception as e:
                print(f"[NVDA] Gagal memuat DLL ({dll_path}): {e}")
                self._nvda_dll = None

    def is_nvda_running(self) -> bool:
        """Checks whether the NVDA process is currently running and responding to RPC."""
        if not self._nvda_dll:
            return False
        try:
            res = self._nvda_dll.nvdaController_testIfRunning()
            return res == 0
        except Exception:
            return False

    def _get_sapi(self):
        """Lazy loads Windows SAPI TTS if NVDA is inactive."""
        if self._sapi is None:
            try:
                import win32com.client
                self._sapi = win32com.client.Dispatch("SAPI.SpVoice")
            except Exception:
                self._sapi = False
        return self._sapi if self._sapi is not False else None

    def speak(self, text: str, interrupt: bool = False, sound_cue: bool = True):
        """
        Speaks text to NVDA or Fallback TTS.
        
        :param text: Text to be spoken
        :param interrupt: Stop previous speech if True
        :param sound_cue: Play a subtle notification beep
        """
        if not text:
            return

        # Play subtle audio cue jika diminta
        if sound_cue:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

        # 1. Coba lewat NVDA Controller Client DLL
        if self._nvda_dll:
            try:
                if interrupt:
                    self._nvda_dll.nvdaController_cancelSpeech()
                res = self._nvda_dll.nvdaController_speakText(text)
                if res == 0:
                    # Sukses terucap di NVDA
                    self.braille(text)
                    return
            except Exception:
                pass

        # 2. Fallback: Coba lewat accessible_output2 jika ada
        try:
            import accessible_output2.outputs.auto
            ao = accessible_output2.outputs.auto.Auto()
            if ao.is_active():
                ao.speak(text, interrupt=interrupt)
                return
        except Exception:
            pass

        # 3. Fallback: Windows SAPI Voice
        sapi = self._get_sapi()
        if sapi:
            try:
                # 1 = SVSFlagsAsync
                flags = 1 if not interrupt else 3 # 3 = SVSFlagsAsync | SVSFPurgeBeforeSpeak
                sapi.Speak(text, flags)
            except Exception:
                pass

    def braille(self, text: str):
        """Sends a message to the NVDA Braille display."""
        if self._nvda_dll:
            try:
                self._nvda_dll.nvdaController_brailleMessage(text)
            except Exception:
                pass

    def cancel_speech(self):
        """Stops the currently playing speech."""
        if self._nvda_dll:
            try:
                self._nvda_dll.nvdaController_cancelSpeech()
            except Exception:
                pass


# Global singleton
speaker = NVDASpeaker()

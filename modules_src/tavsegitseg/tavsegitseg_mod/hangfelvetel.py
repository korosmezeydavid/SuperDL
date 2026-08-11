# -*- coding: utf-8 -*-
"""Távsegítség – a RENDSZERHANG felvétele (WASAPI loopback, comtypes-szal).

A segített gép KIMENŐ hangját veszi fel (loopback) – EBBEN benne van a
képernyőolvasó beszéde is –, hogy a segítő hallja, mi történik. NINCS új
függőség: a comtypes már a Core-ban van (a SAPI is használja), így a fagyasztott
exében is megy. A felvett float32/48kHz/sztereó anyagot kompakt int16/16kHz/mono
PCM-mé alakítja (numpy) a hálózati küldéshez; a néma darabokat kihagyja
(sávszél-kímélés). ÉLŐBEN IGAZOLT: egy lejátszott tónust a loopback elkap.

A COM-interfészeket kézzel definiáljuk (RFC nélkül, a Windows Core Audio API
vtable-jei szerint) – lépésenként, élőben ellenőrizve épült.
"""
import ctypes
import threading
import time
from ctypes import (HRESULT, POINTER, Structure, byref, c_longlong, c_ulonglong,
                    c_void_p)
from ctypes import wintypes

_COM_OK = True
try:
    import comtypes
    from comtypes import GUID, IUnknown, COMMETHOD, CoCreateInstance, CLSCTX_ALL
except Exception:                       # nem-Windows / nincs comtypes (CI)
    _COM_OK = False


_AUDIO_SR = 16000                       # a küldött hang mintavétele (mono)
_SHARED = 0
_LOOPBACK = 0x00020000
_SILENT = 0x2


if _COM_OK:
    _CLSID_ENUM = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    _IID_AUDIOCLIENT = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
    _IID_CAPTURE = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")

    class WAVEFORMATEX(Structure):
        _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
                    ("nSamplesPerSec", wintypes.DWORD),
                    ("nAvgBytesPerSec", wintypes.DWORD),
                    ("nBlockAlign", wintypes.WORD),
                    ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD)]

    _RT = c_longlong

    class IAudioCaptureClient(IUnknown):
        _iid_ = _IID_CAPTURE
        _methods_ = [
            COMMETHOD([], HRESULT, "GetBuffer",
                      (['out'], POINTER(c_void_p), "ppData"),
                      (['out'], POINTER(wintypes.UINT), "pNumFrames"),
                      (['out'], POINTER(wintypes.DWORD), "pdwFlags"),
                      (['out'], POINTER(c_ulonglong), "pDevPos"),
                      (['out'], POINTER(c_ulonglong), "pQPCPos")),
            COMMETHOD([], HRESULT, "ReleaseBuffer",
                      (['in'], wintypes.UINT, "NumFramesRead")),
            COMMETHOD([], HRESULT, "GetNextPacketSize",
                      (['out'], POINTER(wintypes.UINT), "pNum")),
        ]

    class IAudioClient(IUnknown):
        _iid_ = _IID_AUDIOCLIENT
        _methods_ = [
            COMMETHOD([], HRESULT, "Initialize",
                      (['in'], wintypes.DWORD, "ShareMode"),
                      (['in'], wintypes.DWORD, "StreamFlags"),
                      (['in'], _RT, "hnsBufferDuration"),
                      (['in'], _RT, "hnsPeriodicity"),
                      (['in'], POINTER(WAVEFORMATEX), "pFormat"),
                      (['in'], POINTER(GUID), "AudioSessionGuid")),
            COMMETHOD([], HRESULT, "GetBufferSize"),
            COMMETHOD([], HRESULT, "GetStreamLatency"),
            COMMETHOD([], HRESULT, "GetCurrentPadding"),
            COMMETHOD([], HRESULT, "IsFormatSupported"),
            COMMETHOD([], HRESULT, "GetMixFormat",
                      (['out'], POINTER(POINTER(WAVEFORMATEX)), "ppFormat")),
            COMMETHOD([], HRESULT, "GetDevicePeriod"),
            COMMETHOD([], HRESULT, "Start"),
            COMMETHOD([], HRESULT, "Stop"),
            COMMETHOD([], HRESULT, "Reset"),
            COMMETHOD([], HRESULT, "SetEventHandle"),
            COMMETHOD([], HRESULT, "GetService",
                      (['in'], POINTER(GUID), "riid"),
                      (['out'], POINTER(POINTER(IAudioCaptureClient)), "ppv")),
        ]

    class IMMDevice(IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Activate",
                      (['in'], POINTER(GUID), "iid"),
                      (['in'], wintypes.DWORD, "clsctx"),
                      (['in'], c_void_p, "params"),
                      (['out'], POINTER(POINTER(IAudioClient)), "ppi"))]

    class IMMDeviceEnumerator(IUnknown):
        _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
        _methods_ = [
            COMMETHOD([], HRESULT, "EnumAudioEndpoints"),
            COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
                      (['in'], wintypes.DWORD, "flow"),
                      (['in'], wintypes.DWORD, "role"),
                      (['out'], POINTER(POINTER(IMMDevice)), "ppd"))]


class HangFelvevo:
    """A rendszer kimenő hangját (loopback) veszi fel, és int16/16kHz/mono PCM
    darabokat ad az `on_pcm(bytes)` visszahívónak. A néma részeket kihagyja."""

    def __init__(self, on_pcm=None):
        self.on_pcm = on_pcm
        self.elerheto = _COM_OK
        self._fut = False

    def indit(self):
        if not self.elerheto:
            return False
        self._fut = True
        threading.Thread(target=self._felvesz, daemon=True).start()
        return True

    def leallit(self):
        self._fut = False

    # ------------------------------------------------------------ belső
    def _felvesz(self):
        try:
            import numpy as np
        except Exception:
            return
        try:
            comtypes.CoInitialize()
        except Exception:
            pass
        client = capture = None
        try:
            enum = CoCreateInstance(_CLSID_ENUM, IMMDeviceEnumerator, CLSCTX_ALL)
            dev = enum.GetDefaultAudioEndpoint(0, 0)         # eRender, eConsole
            client = dev.Activate(byref(_IID_AUDIOCLIENT), CLSCTX_ALL, None)
            fmt = client.GetMixFormat()
            f = fmt[0]
            block = f.nBlockAlign
            ch = f.nChannels or 2
            sr = f.nSamplesPerSec or 48000
            is_float = (f.wBitsPerSample == 32)
            faktor = max(1, int(round(sr / _AUDIO_SR)))
            client.Initialize(_SHARED, _LOOPBACK, 2000000, 0, fmt, None)
            capture = client.GetService(byref(_IID_CAPTURE))
            client.Start()
            while self._fut:
                try:
                    npkt = capture.GetNextPacketSize()
                except Exception:
                    break
                if not npkt:
                    time.sleep(0.005)
                    continue
                data_ptr, nframes, flags, _dp, _qp = capture.GetBuffer()
                try:
                    if nframes and not (flags & _SILENT) and data_ptr:
                        raw = ctypes.string_at(data_ptr, nframes * block)
                        pcm = self._konvertal(np, raw, ch, faktor, is_float)
                        if pcm and self.on_pcm:
                            self.on_pcm(pcm)
                finally:
                    capture.ReleaseBuffer(nframes)
        except Exception:
            pass
        finally:
            try:
                if client:
                    client.Stop()
            except Exception:
                pass
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

    @staticmethod
    def _konvertal(np, raw, ch, faktor, is_float):
        if is_float:
            a = np.frombuffer(raw, dtype=np.float32)
        else:
            a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if a.size == 0:
            return b""
        if ch > 1:
            n = (a.size // ch) * ch
            a = a[:n].reshape(-1, ch).mean(axis=1)      # mono
        if faktor > 1:                                   # 48k → 16k (átlagolva)
            n = (a.size // faktor) * faktor
            if n == 0:
                return b""
            a = a[:n].reshape(-1, faktor).mean(axis=1)
        i16 = np.clip(a * 32767.0, -32768, 32767).astype(np.int16)
        return i16.tobytes()

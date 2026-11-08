import array
import math
import subprocess

import pytest

from modules_src.mediatools.mediatools_mod import videoedit as VE


@pytest.fixture
def media(tmp_path):
    ff = VE.ffmpeg_mod.find_ffmpeg()
    if not ff or not VE._ffprobe():
        pytest.skip("FFmpeg and ffprobe are required")

    def ffmpeg(*args):
        result = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                                capture_output=True, check=True, timeout=30)
        return result.stdout

    source = tmp_path / "beszéd.mp4"
    picture = tmp_path / "téli lufi.png"
    effect = tmp_path / "effekt.wav"
    ffmpeg("-f", "lavfi", "-i", "color=blue:s=320x240:r=25:d=4",
           "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", source)
    ffmpeg("-f", "lavfi", "-i", "color=red:s=80x40", "-frames:v", "1", picture)
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=1.5", effect)
    return ffmpeg, source, picture, effect


def _pixel(ffmpeg, path, time, x=270, y=25):
    frame = ffmpeg("-ss", time, "-i", path, "-frames:v", "1",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-")
    offset = (y * 320 + x) * 3
    return tuple(frame[offset:offset + 3])


def _tones(ffmpeg, path, time):
    raw = ffmpeg("-ss", time, "-i", path, "-t", "0.2",
                 "-vn", "-f", "s16le", "-ar", "48000", "-ac", "1", "-")
    samples = array.array("h", raw)
    def magnitude(frequency):
        phase = 2 * math.pi * frequency / 48000
        real = sum(sample * math.cos(phase * i) for i, sample in enumerate(samples))
        imag = sum(sample * math.sin(phase * i) for i, sample in enumerate(samples))
        return math.hypot(real, imag) / len(samples)

    return tuple(magnitude(frequency) for frequency in (440, 880))


def test_images_and_effects_export_at_project_times(media, tmp_path):
    ffmpeg, source, picture, effect = media
    editor = VE.VideoEditor()
    assert editor.add_clip(str(source))
    editor.add_layer("image", str(picture), 1.0, 1.5)
    editor.add_layer("audio", str(effect), 1.0)
    editor.add_note(0.5, "Megjegyzés")
    whole = tmp_path / "whole.mp4"
    section = tmp_path / "section.mp4"
    cut = tmp_path / "cut.mp4"
    preview = tmp_path / "preview.wav"
    assert editor.export(0, 4, str(whole)), editor.error
    assert editor.export(1.4, 3.4, str(section)), editor.error
    assert editor.export_cut(1.4, 1.8, str(cut)), editor.error
    assert editor.preview_audio(1.4, str(preview)), editor.error

    assert _pixel(ffmpeg, whole, 0.4)[2] > 200
    assert _pixel(ffmpeg, whole, 1.4)[0] > 200
    assert _pixel(ffmpeg, whole, 2.8)[2] > 200
    assert _pixel(ffmpeg, whole, 1.4, x=20)[2] > 200
    assert _pixel(ffmpeg, section, 0.1)[0] > 200
    assert _pixel(ffmpeg, section, 1.4)[2] > 200
    assert _pixel(ffmpeg, cut, 1.5)[0] > 200
    assert _pixel(ffmpeg, cut, 2.3)[2] > 200
    assert _tones(ffmpeg, whole, 0.4)[1] < 20
    for path, time in ((whole, 1.4), (section, 0.1), (cut, 1.5), (preview, 0.1)):
        speech, added = _tones(ffmpeg, path, time)
        assert speech > 500 and added > 150


def test_sound_can_be_added_to_silent_video(media, tmp_path):
    ffmpeg, source, picture, effect = media
    silent = tmp_path / "silent.mp4"
    ffmpeg("-i", source, "-c:v", "copy", "-an", silent)
    editor = VE.VideoEditor()
    assert editor.add_clip(str(silent))
    editor.add_layer("audio", str(effect), 0.75)
    out = tmp_path / "out.mp4"
    assert editor.export(0, 4, str(out)), editor.error
    speech, added = _tones(ffmpeg, out, 1.0)
    assert speech < 20 and added > 150


def test_layers_keep_global_time_after_appending_a_silent_clip(media, tmp_path):
    ffmpeg, source, picture, effect = media
    silent = tmp_path / "silent.mp4"
    ffmpeg("-i", source, "-c:v", "copy", "-an", silent)
    editor = VE.VideoEditor()
    assert editor.add_clip(str(source))
    assert editor.add_clip(str(silent))
    editor.add_layer("image", str(picture), 4.5, 1.25)
    editor.add_layer("audio", str(effect), 4.5)
    out = tmp_path / "joined.mp4"
    try:
        assert editor.export(0, 8, str(out)), editor.error
        assert _pixel(ffmpeg, out, 4.2)[2] > 200
        assert _pixel(ffmpeg, out, 4.9)[0] > 200
        assert _tones(ffmpeg, out, 4.9)[1] > 150
    finally:
        editor.cleanup()


def test_video_editor_layer_controls_and_accessible_summary():
    wx = pytest.importorskip("wx")
    from modules_src.mediatools.mediatools_mod import videoeditwin as window

    app = wx.App.Get() or wx.App(False)
    frame = window.VideoEditFrame(None)
    try:
        labels = [child.GetLabel().replace("&", "") for child in frame.GetChildren()[0].GetChildren()
                  if isinstance(child, wx.Button)]
        assert "Kép hozzáadása itt…" in labels
        assert "Hang hozzáadása itt…" in labels
        assert "Hangkeverés meghallgatása" in labels
        assert frame.layer_list.GetName() == "Beszúrt képek és hangok"
        frame.editor.clips.append(VE.Clip("teszt.mp4", duration=4))
        layer = VE.TimelineLayer("image", "téli lufi.png", 2, 5)
        frame.editor.layers.append(layer)
        frame._refresh_layers(layer)
        assert "téli lufi.png" in frame.layer_list.GetString(0)
        assert "vége 4.00" in frame.layer_list.GetString(0)
    finally:
        frame.Close()

// MIT-licensed Signalsmith Stretch adapter for the Super Media voice changer.
// This C ABI keeps the audio callback independent of C++ template types.
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <new>
#include <vector>
#include "signalsmith-stretch.h"

#ifdef _WIN32
#define VOICE_API extern "C" __declspec(dllexport)
#else
#define VOICE_API extern "C"
#endif

// Analysis-envelope / harmonic-carrier filter-bank vocoder. This is a real
// modulator/carrier vocoder, not a renamed pitch or EQ preset. All filters and
// buffers are initialized before the audio callback; processing allocates none.
struct Bandpass {
    float b0 = 0, b2 = 0, a1 = 0, a2 = 0;
    float z1 = 0, z2 = 0;

    void configure(float frequency, float rate) {
        constexpr float pi = 3.14159265358979323846f;
        const float omega = 2 * pi * frequency / rate;
        const float alpha = std::sin(omega) / 4.0f; // Q = 2
        const float norm = 1.0f / (1.0f + alpha);
        b0 = alpha * norm;
        b2 = -b0;
        a1 = -2 * std::cos(omega) * norm;
        a2 = (1 - alpha) * norm;
    }

    float process(float sample) {
        const float output = b0 * sample + z1;
        z1 = -a1 * output + z2;
        z2 = b2 * sample - a2 * output;
        return output;
    }
};

struct VocoderBand {
    Bandpass analysis;
    Bandpass carrier;
    float envelope = 0;
};

struct Vocoder {
    std::array<VocoderBand, 16> bands;
    float phase = 0;
    float rate;
    float attack;
    float release;

    explicit Vocoder(float sampleRate) : rate(sampleRate) {
        attack = std::exp(-1.0f / (0.005f * rate));
        release = std::exp(-1.0f / (0.070f * rate));
        for (size_t i = 0; i < bands.size(); ++i) {
            const float fraction = float(i) / float(bands.size() - 1);
            const float center = 140.0f * std::pow(5200.0f / 140.0f, fraction);
            bands[i].analysis.configure(center, rate);
            bands[i].carrier.configure(center, rate);
        }
    }

    float process(float modulator, float carrierHz) {
        phase += carrierHz / rate;
        if (phase >= 1.0f) phase -= 1.0f;
        const float saw = 2.0f * phase - 1.0f;
        float result = 0;
        for (auto &band : bands) {
            const float detected = std::abs(band.analysis.process(modulator));
            const float coefficient = detected > band.envelope ? attack : release;
            band.envelope = coefficient * band.envelope +
                            (1.0f - coefficient) * detected;
            result += band.envelope * band.carrier.process(saw);
        }
        // Moderate makeup gain, with a soft ceiling for overlapping bands.
        return std::tanh(result * 5.0f);
    }
};

struct VoiceStretch {
    signalsmith::stretch::SignalsmithStretch<float> engine;
    std::atomic<float> semitones{0};
    float appliedSemitones = 0;
    std::vector<float> input;
    std::vector<float> output;
    Vocoder vocoder;
    std::atomic<int> vocoderEnabled{0};
    std::atomic<float> vocoderHz{120};
    std::atomic<float> vocoderMix{1};
    int sampleRate;

    VoiceStretch(int rate, int window, int interval, int maxFrames)
        : input(maxFrames), output(maxFrames), vocoder(float(rate)), sampleRate(rate) {
        engine.configure(1, window, interval);
        engine.setFormantBase(180.0f / rate);
        engine.setFormantFactor(1.0f, true);
    }
};

VOICE_API VoiceStretch *voice_stretch_create(int sampleRate, int window,
                                              int interval, int maxFrames) {
    if (sampleRate < 8000 || sampleRate > 192000 || window < 256 ||
        interval < 64 || interval >= window || maxFrames < 64 ||
        maxFrames > 8192) return nullptr;
    try { return new VoiceStretch(sampleRate, window, interval, maxFrames); }
    catch (...) { return nullptr; }
}

VOICE_API void voice_stretch_destroy(VoiceStretch *state) { delete state; }

VOICE_API int voice_stretch_latency(const VoiceStretch *state) {
    if (!state) return -1;
    return state->engine.inputLatency() + state->engine.outputLatency();
}

VOICE_API int voice_stretch_set_pitch(VoiceStretch *state, float semitones) {
    if (!state || !(semitones >= -12 && semitones <= 12)) return 0;
    state->semitones.store(semitones, std::memory_order_relaxed);
    return 1;
}

VOICE_API int voice_stretch_set_vocoder(VoiceStretch *state, int enabled,
                                       float carrierHz, float mix) {
    if (!state || !(carrierHz >= 70 && carrierHz <= 400) ||
        !(mix >= 0 && mix <= 1)) return 0;
    state->vocoderHz.store(carrierHz, std::memory_order_relaxed);
    state->vocoderMix.store(mix, std::memory_order_relaxed);
    state->vocoderEnabled.store(enabled ? 1 : 0, std::memory_order_relaxed);
    return 1;
}

// In-place or separate mono PCM16 buffers. No allocation is done during process.
VOICE_API int voice_stretch_process(VoiceStretch *state, const int16_t *input,
                                    int16_t *output, int frames) {
    if (!state || !input || !output || frames < 0 ||
        frames > static_cast<int>(state->input.size())) return 0;
    try {
        const float pitch = state->semitones.load(std::memory_order_relaxed);
        if (pitch != state->appliedSemitones) {
            state->engine.setTransposeSemitones(pitch);
            state->appliedSemitones = pitch;
        }
        for (int i = 0; i < frames; ++i) state->input[i] = input[i] / 32768.0f;
        float *in[] = {state->input.data()};
        float *out[] = {state->output.data()};
        state->engine.process(in, frames, out, frames);
        const bool vocoderOn = state->vocoderEnabled.load(std::memory_order_relaxed);
        const float carrierHz = state->vocoderHz.load(std::memory_order_relaxed);
        const float wet = state->vocoderMix.load(std::memory_order_relaxed);
        for (int i = 0; i < frames; ++i) {
            float sample = state->output[i];
            if (vocoderOn) {
                const float transformed = state->vocoder.process(sample, carrierHz);
                sample = (1.0f - wet) * sample + wet * transformed;
            }
            float scaled = std::max(-1.0f, std::min(1.0f, sample));
            output[i] = static_cast<int16_t>(scaled * 32767.0f);
        }
        return 1;
    } catch (...) { return 0; }
}

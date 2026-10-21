// Isolated measurement probe for the MIT-licensed Signalsmith Stretch engine.
// Build against pinned signalsmith-stretch and signalsmith-linear headers.
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <vector>
#include "signalsmith-stretch.h"

int main(int argc, char **argv) {
    const int sampleRate = 44100;
    const int blockSamples = argc > 1 ? std::atoi(argv[1]) : 2048;
    const int intervalSamples = argc > 2 ? std::atoi(argv[2]) : 512;
    if (blockSamples < 256 || intervalSamples < 64 || intervalSamples >= blockSamples) return 2;
    signalsmith::stretch::SignalsmithStretch<float> engine;
    engine.configure(1, blockSamples, intervalSamples);
    engine.setTransposeSemitones(4);
    engine.setFormantBase(180.0f / sampleRate);
    engine.setFormantFactor(1.0f, true);

    constexpr int chunk = 256;
    std::vector<float> input(chunk), output(chunk);
    float *in[] = {input.data()};
    float *out[] = {output.data()};
    double maxProcessMs = 0;
    double sumProcessMs = 0;
    double energy = 0;
    const int count = sampleRate * 5 / chunk;
    for (int block = 0; block < count; ++block) {
        for (int i = 0; i < chunk; ++i) {
            const double t = (block * chunk + i) / double(sampleRate);
            input[i] = float(0.15 * std::sin(2 * 3.141592653589793 * 180 * t));
        }
        auto start = std::chrono::steady_clock::now();
        engine.process(in, chunk, out, chunk);
        auto finish = std::chrono::steady_clock::now();
        const double ms = std::chrono::duration<double, std::milli>(finish-start).count();
        sumProcessMs += ms;
        if (ms > maxProcessMs) maxProcessMs = ms;
        for (float sample : output) energy += sample * sample;
    }
    std::cout << "block=" << blockSamples << " interval=" << intervalSamples
              << " input_latency=" << engine.inputLatency()
              << " output_latency=" << engine.outputLatency()
              << " mean_process_ms=" << sumProcessMs / count
              << " max_process_ms=" << maxProcessMs
              << " output_rms=" << std::sqrt(energy / (count * chunk)) << '\n';
}

// Exercises the REAL ffmpeg-static/ffprobe-static binaries (bundled, fast,
// deterministic - unlike the OpenAI-backed transcription/translation calls,
// there's no reason to mock this). A tiny synthetic tone is generated once
// and converted through the real pipeline every test run.
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");
const ffmpegPath = require("ffmpeg-static");

const audioStorage = require("../lib/audioStorage");

let workDir;
let sourceWavPath;

beforeAll(() => {
    workDir = fs.mkdtempSync(path.join(os.tmpdir(), "audio-storage-test-"));
    sourceWavPath = path.join(workDir, "tone.wav");
    execFileSync(ffmpegPath, [
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-ac", "1", "-ar", "16000", sourceWavPath, "-y",
    ]);
});

afterAll(() => {
    fs.rmSync(workDir, { recursive: true, force: true });
});

test("converts a real audio file to a real MP3 in the recordings directory", async () => {
    const result = await audioStorage.convertToMp3(sourceWavPath);

    expect(result.storedFilename).toMatch(/\.mp3$/);
    expect(fs.existsSync(result.storedPath)).toBe(true);
    expect(result.fileSizeBytes).toBeGreaterThan(0);
    expect(result.storedPath).toBe(audioStorage.storedFilePath(result.storedFilename));

    await audioStorage.deleteStoredFile(result.storedFilename);
    expect(fs.existsSync(result.storedPath)).toBe(false);
});

test("reports a plausible duration for the converted file", async () => {
    const result = await audioStorage.convertToMp3(sourceWavPath);
    const duration = await audioStorage.probeDurationSeconds(result.storedPath);

    expect(duration).toBeGreaterThan(0.9);
    expect(duration).toBeLessThan(1.5);

    audioStorage.deleteStoredFile(result.storedFilename);
});

test("probeDurationSeconds resolves null (not throw) for a missing file", async () => {
    const duration = await audioStorage.probeDurationSeconds(path.join(workDir, "does-not-exist.mp3"));
    expect(duration).toBeNull();
});

test("deleteStoredFile is a safe no-op for a filename that was never stored", () => {
    expect(() => audioStorage.deleteStoredFile("never-existed.mp3")).not.toThrow();
});

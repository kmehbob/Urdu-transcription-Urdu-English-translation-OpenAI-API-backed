// Integration test against the REAL transcription service + REAL OpenAI
// audio API. Skipped by default; requires RUN_OPENAI_INTEGRATION_TESTS=1, a
// real running transcription service configured with a valid
// OPENAI_API_KEY, and a sample Urdu audio file at the path given by
// SAMPLE_URDU_AUDIO_PATH.
const path = require("path");
const fs = require("fs");

const runIntegration = process.env.RUN_OPENAI_INTEGRATION_TESTS === "1";
const describeIfEnabled = runIntegration ? describe : describe.skip;

describeIfEnabled("transcription service integration (real OpenAI API)", () => {
    const request = require("supertest");
    const app = require("../../serve.js");

    const samplePath = process.env.SAMPLE_URDU_AUDIO_PATH || path.join(__dirname, "fixtures", "sample-urdu.wav");

    test("transcribes a real Urdu audio sample into Urdu script", async () => {
        if (!fs.existsSync(samplePath)) {
            throw new Error(
                `No sample audio found at ${samplePath}. Set SAMPLE_URDU_AUDIO_PATH to a real Urdu .wav file.`
            );
        }

        const res = await request(app).post("/api/v1/transcribe").attach("file", samplePath);

        expect(res.status).toBe(200);
        expect(res.body.text.length).toBeGreaterThan(0);
        expect(res.body.language).toBe("ur");
    }, 60000);
});

if (!runIntegration) {
    test.skip("integration tests skipped (set RUN_OPENAI_INTEGRATION_TESTS=1 to run against real services)", () => {});
}

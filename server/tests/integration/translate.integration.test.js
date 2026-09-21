// Integration test against the REAL translation service + REAL OpenAI API.
// Skipped by default; requires RUN_OPENAI_INTEGRATION_TESTS=1 and both the
// gateway env (INTERNAL_SERVICE_TOKEN, TRANSLATION_SERVICE_URL) and an
// actual running translation service configured with a valid OPENAI_API_KEY.
const runIntegration = process.env.RUN_OPENAI_INTEGRATION_TESTS === "1";
const describeIfEnabled = runIntegration ? describe : describe.skip;

describeIfEnabled("translation service integration (real OpenAI API)", () => {
    const request = require("supertest");
    const app = require("../../serve.js");

    test("produces a plausible English translation for a simple Urdu sentence", async () => {
        const res = await request(app).post("/api/v1/translate").send({ text: "میرا نام علی ہے۔" });

        expect(res.status).toBe(200);
        expect(res.body.translation.toLowerCase()).toMatch(/ali/);
    }, 30000);

    test("preserves paragraph breaks across a multi-paragraph input", async () => {
        const text = "یہ پہلا پیراگراف ہے۔\n\nیہ دوسرا پیراگراف ہے۔";
        const res = await request(app).post("/api/v1/translate").send({ text });

        expect(res.status).toBe(200);
        expect(res.body.translation).toContain("\n\n");
    }, 30000);
});

if (!runIntegration) {
    test.skip("integration tests skipped (set RUN_OPENAI_INTEGRATION_TESTS=1 to run against real services)", () => {});
}

jest.mock("axios");
const axios = require("axios");
const request = require("supertest");

const mockRequest = jest.fn();
const mockGet = jest.fn();
axios.create.mockReturnValue({ request: mockRequest, get: mockGet });

const app = require("../serve.js");

beforeEach(() => {
    mockGet.mockReset();
});

test("GET /health reports liveness without contacting AI services", async () => {
    const res = await request(app).get("/health");
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: "ok" });
    expect(mockGet).not.toHaveBeenCalled();
});

test("GET /api/v1/health reports liveness without contacting AI services", async () => {
    const res = await request(app).get("/api/v1/health");
    expect(res.status).toBe(200);
    expect(mockGet).not.toHaveBeenCalled();
});

test("GET /api/v1/ready reports ready when both AI services respond", async () => {
    mockGet.mockResolvedValue({ status: 200 });
    const res = await request(app).get("/api/v1/ready");
    expect(res.status).toBe(200);
    expect(res.body.status).toBe("ready");
    expect(res.body.services).toEqual({ transcription: true, translation: true });
});

test("GET /api/v1/ready reports not_ready when an AI service is unreachable", async () => {
    mockGet.mockRejectedValue(new Error("connection refused"));
    const res = await request(app).get("/api/v1/ready");
    expect(res.status).toBe(503);
    expect(res.body.status).toBe("not_ready");
});

test("the old /speak (browser-TTS-replacement) route no longer exists", async () => {
    const res = await request(app).post("/speak").send({ text: "hello" });
    expect(res.status).toBe(404);
});

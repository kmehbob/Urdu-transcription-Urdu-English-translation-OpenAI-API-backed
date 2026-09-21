const fs = require("fs");
const https = require("https");
const axios = require("axios");
const config = require("./config");

// Thrown for any failure talking to an internal AI service. `status` is the
// HTTP status the gateway should return to the client; `publicMessage` is
// safe to show externally (never includes upstream URLs/stack traces).
class AiServiceError extends Error {
    constructor(publicMessage, status, cause) {
        super(publicMessage);
        this.name = "AiServiceError";
        this.publicMessage = publicMessage;
        this.status = status;
        this.cause = cause;
    }
}

let cachedInternalHttpsAgent = null;

// Builds the mutual-TLS agent used for every call to an internal AI service.
// Deliberately fails fast (at startup, when routes first require this
// module) rather than per-request if INTERNAL_TLS_ENABLED is on but
// misconfigured - a silently-plaintext fallback would defeat the point of
// requiring encryption in the first place.
function getInternalHttpsAgent() {
    if (!config.internalTlsEnabled) return undefined;
    if (cachedInternalHttpsAgent) return cachedInternalHttpsAgent;

    const { internalTlsClientCertFile, internalTlsClientKeyFile, internalTlsCaFile } = config;
    if (!internalTlsClientCertFile || !internalTlsClientKeyFile || !internalTlsCaFile) {
        throw new Error(
            "INTERNAL_TLS_ENABLED=true requires INTERNAL_TLS_CLIENT_CERT_FILE, " +
                "INTERNAL_TLS_CLIENT_KEY_FILE, and INTERNAL_TLS_CA_FILE to all be set"
        );
    }

    cachedInternalHttpsAgent = new https.Agent({
        cert: fs.readFileSync(internalTlsClientCertFile),
        key: fs.readFileSync(internalTlsClientKeyFile),
        ca: fs.readFileSync(internalTlsCaFile),
        rejectUnauthorized: true,
    });
    return cachedInternalHttpsAgent;
}

function createServiceClient(baseURL, timeoutMs) {
    return axios.create({
        baseURL,
        timeout: timeoutMs,
        maxContentLength: 200 * 1024 * 1024,
        maxBodyLength: 200 * 1024 * 1024,
        httpsAgent: getInternalHttpsAgent(),
        headers: config.internalServiceToken
            ? { Authorization: `Bearer ${config.internalServiceToken}` }
            : {},
        validateStatus: () => true, // we classify status ourselves below
    });
}

// Performs a request that is aborted if the originating client disconnects,
// and normalizes any failure into an AiServiceError with a safe message.
async function callService({ client, req, method, url, data, axiosOpts, serviceLabel }) {
    const controller = new AbortController();
    const onClose = () => controller.abort();
    // req.on("close") is NOT a reliable client-disconnect signal: the
    // IncomingMessage's own 'close' fires once its body has been fully
    // read/destroyed (e.g. right after multer/express.json() consumes it),
    // long before the response is sent, even though the connection is still
    // open. req.socket's 'close' only fires when the underlying TCP
    // connection actually terminates, which is what we actually want here.
    if (req?.socket) req.socket.on("close", onClose);

    try {
        const response = await client.request({
            method,
            url,
            data,
            signal: controller.signal,
            ...axiosOpts,
        });

        if (response.status >= 200 && response.status < 300) {
            return response.data;
        }

        if (response.status === 401 || response.status === 403) {
            throw new AiServiceError(`${serviceLabel} rejected the request`, 502);
        }
        if (response.status === 429 || response.status === 503) {
            throw new AiServiceError(`${serviceLabel} is busy, please try again shortly`, 503);
        }
        if (response.status >= 400 && response.status < 500) {
            // FastAPI's default HTTPException serializes as {"detail": "..."} -
            // our own error responses use {"error": "..."} - check both so a
            // specific message from either side actually reaches the client
            // instead of always falling back to the generic one.
            const data = response.data;
            const detail = (data && typeof data.error === "string" && data.error)
                || (data && typeof data.detail === "string" && data.detail)
                || null;
            throw new AiServiceError(detail || `Invalid request to ${serviceLabel}`, 400);
        }
        throw new AiServiceError(`${serviceLabel} failed to process the request`, 502);
    } catch (err) {
        if (err instanceof AiServiceError) throw err;
        if (axios.isCancel(err) || err.code === "ERR_CANCELED") {
            throw new AiServiceError("Request cancelled", 499);
        }
        if (err.code === "ECONNABORTED" || err.message?.includes("timeout")) {
            throw new AiServiceError(`${serviceLabel} timed out`, 504);
        }
        if (err.code === "ECONNREFUSED" || err.code === "ENOTFOUND" || err.code === "EHOSTUNREACH") {
            throw new AiServiceError(`${serviceLabel} is currently unavailable`, 503);
        }
        throw new AiServiceError(`${serviceLabel} failed to process the request`, 502, err);
    } finally {
        if (req?.socket) req.socket.removeListener("close", onClose);
    }
}

module.exports = { createServiceClient, callService, AiServiceError, getInternalHttpsAgent };

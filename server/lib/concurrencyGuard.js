// Simple counting semaphore used as Express middleware to cap how many
// expensive OpenAI-backed requests (transcribe/translate) the gateway will
// forward concurrently. This is defense-in-depth on top of the semaphores
// enforced inside each Python AI service, so a burst of requests fails fast
// with 503 at the gateway instead of queuing indefinitely.
function concurrencyGuard(limit, busyMessage) {
    let inFlight = 0;
    return function (req, res, next) {
        if (inFlight >= limit) {
            return res.status(503).json({ error: busyMessage || "Server is busy, please try again shortly", requestId: req.id });
        }
        inFlight += 1;
        // Node fires both 'finish' and 'close' for a normal completed
        // response (not just aborted ones), so the release must be
        // idempotent - otherwise every request decrements the counter twice
        // and the limit is never actually enforced under real concurrency.
        let released = false;
        const release = () => {
            if (released) return;
            released = true;
            inFlight = Math.max(0, inFlight - 1);
        };
        res.once("finish", release);
        res.once("close", release);
        next();
    };
}

module.exports = concurrencyGuard;

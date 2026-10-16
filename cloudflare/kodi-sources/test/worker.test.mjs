import assert from "node:assert/strict";
import test from "node:test";
import worker from "../src/index.mjs";

test("health endpoint", async () => {
  const response = await worker.fetch(new Request("https://example.workers.dev/health"));
  assert.equal(response.status, 200);
  assert.equal((await response.json()).ok, true);
});
test("source API contract is read-only and needs no Kodi token", async () => {
  const response = await worker.fetch(new Request(
    "https://example.workers.dev/v1/sources?title=Teste&imdb=tt1254207&year=2008"));
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.deepEqual(body.sources, []);
  assert.deepEqual(body.providers, []);
  assert.equal(body.imdb, "tt1254207");
});
test("invalid queries are rejected", async () => {
  const response = await worker.fetch(new Request(
    "https://example.workers.dev/v1/sources?title=Teste&imdb=broken"));
  assert.equal(response.status, 400);
});
test("no upstream provider is called from the scaffold", async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = () => { throw Error("Should not fetch upstream"); };
  try {
    const response = await worker.fetch(new Request(
      "https://example.workers.dev/v1/sources?title=Teste"));
    assert.equal(response.status, 200);
  } finally {
    globalThis.fetch = saved;
  }
});

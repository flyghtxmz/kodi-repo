import assert from "node:assert/strict";
import test from "node:test";
import worker from "../src/index.mjs";

const env = {};
const url = "https://example.workers.dev/v1/sources?imdb=tt1254207&title=Big%20Buck%20Bunny&year=2008";

test("health endpoint is public", async () => {
  const response = await worker.fetch(new Request("https://example.workers.dev/health"), env);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).ok, true);
});

test("sources are public read-only; a failing upstream yields 502", async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("offline test"); };
  try {
    const response = await worker.fetch(new Request(url), env);
    assert.equal(response.status, 502);
  } finally {
    globalThis.fetch = saved;
  }
});

test("invalid imdb is rejected", async () => {
  const response = await worker.fetch(new Request(url.replace("tt1254207", "../bad")), env);
  assert.equal(response.status, 400);
});

test("licensed Internet Archive entry is returned; no invented seeders or language", async () => {
  const saved = globalThis.fetch;
  const cc = "https://creativecommons.org/licenses/by/3.0/";
  globalThis.fetch = async (request) => {
    const target = String(request);
    if (target.includes("/advancedsearch.php")) {
      return new Response(JSON.stringify({ response: { docs: [{
        identifier: "BigBuckBunnyOpen", title: "Big Buck Bunny", year: "2008", licenseurl: cc,
      }] } }), { status: 200 });
    }
    if (target.includes("/metadata/")) {
      return new Response(JSON.stringify({
        metadata: { licenseurl: cc }, files: [
          { name: "BigBuckBunnyOpen_archive.torrent", source: "metadata" },
          { name: "bigbuckbunny_1080p.mp4", size: "650000000" },
        ],
      }), { status: 200 });
    }
    throw new Error("Unexpected upstream request: " + target);
  };
  try {
    const response = await worker.fetch(new Request(url), env);
    assert.equal(response.status, 200);
    const result = await response.json();
    assert.equal(result.sources.length, 1);
    assert.match(response.headers.get("cache-control"), /max-age=300/);
    assert.equal(result.sources[0].quality, "1080p");
    assert.equal(result.sources[0].seeders, null);
    assert.equal(result.sources[0].language, "unknown");
    assert.equal(result.sources[0].verified_license, true);
    assert.ok(result.sources[0].url.endsWith("BigBuckBunnyOpen_archive.torrent"));
  } finally {
    globalThis.fetch = saved;
  }
});

test("unlicensed results never appear", async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    response: { docs: [{
      identifier: "unlicensed", title: "Big Buck Bunny", licenseurl: "https://untrusted.invalid/cc",
    }] },
  }), { status: 200 });
  try {
    const response = await worker.fetch(new Request(url), env);
    assert.equal((await response.json()).sources.length, 0);
  } finally {
    globalThis.fetch = saved;
  }
});

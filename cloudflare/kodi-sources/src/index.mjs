// Felipe Vídeos / Cloudflare Worker: gateway de fontes com licença aberta.
// Nunca coloca indexadores privados, tokens ou chaves no código publicado.
const ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php";
const ARCHIVE_METADATA = "https://archive.org/metadata/";
const ARCHIVE_DOWNLOAD = "https://archive.org/download/";
const IMDB = /^tt[0-9]{5,12}$/;
const ARCHIVE_ID = /^[a-zA-Z0-9][a-zA-Z0-9._-]{0,119}$/;
const QUALITY_RANK = { SD: 0, "480p": 1, "720p": 2, "1080p": 3, "4K": 4 };

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}
function equalSecret(a, b) {
  if (!a || !b) return false;
  // Length is not a secret; compare equal-length strings without early exit.
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
function norm(value) {
  return String(value || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
}
function quality(filename) {
  // '_' também separa resolução em nomes de releases e vídeos do Archive.
  if (/(?:^|[^a-z0-9])(2160p?|4k|uhd)(?=$|[^a-z0-9])/i.test(filename)) return "4K";
  if (/(?:^|[^a-z0-9])1080p?(?=$|[^a-z0-9])/i.test(filename)) return "1080p";
  if (/(?:^|[^a-z0-9])720p?(?=$|[^a-z0-9])/i.test(filename)) return "720p";
  if (/(?:^|[^a-z0-9])480p?(?=$|[^a-z0-9])/i.test(filename)) return "480p";
  return "SD";
}
function licensed(value) {
  const v = Array.isArray(value) ? value[0] : value;
  if (typeof v !== "string") return false;
  try {
    const url = new URL(v);
    return (url.protocol === "https:" || url.protocol === "http:") &&
      ["creativecommons.org", "www.creativecommons.org"].includes(url.hostname) &&
      (/^\/licenses\/(by|by-sa|by-nd|by-nc|by-nc-sa|by-nc-nd)\/\d/i.test(url.pathname) ||
       /^\/publicdomain\/(zero|mark)\/\d/i.test(url.pathname));
  } catch { return false; }
}
async function fetchJson(url) {
  const response = await fetch(url, {
    headers: { accept: "application/json", "user-agent": "FelipeVideosCloudflare/0.1" },
    signal: AbortSignal.timeout(9000),
  });
  if (!response.ok) throw new Error("origin_" + response.status);
  const length = Number(response.headers.get("content-length") || 0);
  if (length > 1500000) throw new Error("response_too_large");
  const body = await response.text();
  if (body.length > 1500000) throw new Error("response_too_large");
  return JSON.parse(body);
}
function archiveQuery(title) {
  const parts = norm(title).split(" ").filter(Boolean).slice(0, 7);
  if (!parts.length) throw new Error("empty_title");
  // Keywords are strictly alphanumeric to avoid user-supplied Solr operators.
  return "mediatype:movies AND licenseurl:http*creativecommons.org* AND " +
    parts.map(x => "title:" + x).join(" AND ");
}
async function archiveSources(title, year) {
  const params = new URLSearchParams();
  params.set("q", archiveQuery(title));
  for (const f of ["identifier", "title", "licenseurl", "year"]) params.append("fl[]", f);
  params.set("rows", "15");
  params.set("output", "json");
  const search = await fetchJson(ARCHIVE_SEARCH + "?" + params.toString());
  const results = [];
  const documents = (search?.response?.docs || []).slice(0, 15);
  let checked = 0;
  for (const item of documents) {
    if (checked >= 5) break;
    if (!item || !ARCHIVE_ID.test(item.identifier || "") || !licensed(item.licenseurl)) continue;
    const candidate = norm(item.title);
    const expected = norm(title);
    if (!candidate.includes(expected) && !expected.includes(candidate)) continue;
    if (year && item.year && String(item.year).slice(0, 4) !== String(year)) continue;
    checked++;
    try {
      const data = await fetchJson(ARCHIVE_METADATA + encodeURIComponent(item.identifier));
      if (!licensed(data?.metadata?.licenseurl)) continue;
      const files = Array.isArray(data.files) ? data.files : [];
      const torrent = files.find(f => typeof f?.name === "string" &&
        /^[a-zA-Z0-9._-]+_archive\.torrent$/i.test(f.name) && f.source === "metadata");
      const videoFiles = files.filter(f => typeof f?.name === "string" &&
        /\.(mp4|mkv|webm|mov|m4v)$/i.test(f.name) &&
        !/(sample|trailer|thumb|preview)/i.test(f.name));
      if (!torrent || videoFiles.length === 0) continue;
      const best = [...videoFiles].sort((a,b) =>
        QUALITY_RANK[quality(b.name)] - QUALITY_RANK[quality(a.name)] ||
        Number(b.size || 0) - Number(a.size || 0))[0];
      const chosen = quality(best.name);
      const size = Math.max(0, Number(best.size || 0));
      results.push({
        id: item.identifier,
        title: String(item.title).slice(0, 160),
        source: "Internet Archive",
        quality: chosen,
        size: Number.isFinite(size) ? size : 0,
        seeders: null,   // O Archive não publica seeders via metadata.
        language: "unknown", // Não inferir PT-BR a partir do título.
        verified_license: true,
        type: "torrent",
        url: ARCHIVE_DOWNLOAD + encodeURIComponent(item.identifier) + "/" +
          encodeURIComponent(torrent.name),
      });
    } catch { /* Falha isolada de um upload não compromete os demais. */ }
  }
  return results;
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "GET") return json({ error: "method_not_allowed" }, 405);
    if (url.pathname === "/health") return json({ ok: true, version: "0.1", deployed: true });
    if (url.pathname !== "/v1/sources") return json({ error: "not_found" }, 404);
    if (!env.KODI_API_TOKEN) return json({ error: "service_not_configured" }, 503);
    const authorization = request.headers.get("authorization") || "";
    if (!equalSecret(authorization, "Bearer " + env.KODI_API_TOKEN))
      return json({ error: "unauthorized" }, 401);
    const title = (url.searchParams.get("title") || "").trim();
    const imdb = (url.searchParams.get("imdb") || "").trim();
    const year = (url.searchParams.get("year") || "").trim();
    if (!title || title.length > 120 || !/^[12]\d{3}$/.test(year || "2000") ||
        (imdb && !IMDB.test(imdb)))
      return json({ error: "invalid_query" }, 400);
    try {
      const sources = await archiveSources(title, year);
      return json({ imdb: imdb || null, title, year: year || null,
                    sources, providers: ["Internet Archive"] });
    } catch (error) {
      return json({ error: "upstream_unavailable" }, 502);
    }
  },
};

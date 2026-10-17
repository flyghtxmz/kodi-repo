// Adaptador opcional Torrentio/Stremio para fontes declaradas pelo provedor.
// Não consulta nem transfere arquivos BitTorrent, apenas metadados JSON.
const VALID_IMDB = /^tt[0-9]{5,12}$/;
const HASH = /^[0-9a-f]{40}$/i;
const MAX_JSON = 600_000;
const QUALITY_RANK = {SD:0,"480p":1,"720p":2,"1080p":3,"4K":4};
const REMOVED = new Set(["internet archive","archive.org","archive","internetarchive"]);
const DEFAULT_BASE =
  "https://torrentio.strem.fun/providers=comando,bludv,micoleaodublado|language=portuguese";

function clean(text, max=200) {
  return String(text || "").replace(/[\x00-\x1f\x7f]/g," ").replace(/\s+/g," ").trim().slice(0,max);
}

export function torrentioBaseUrl(configured=DEFAULT_BASE) {
  const parsed = new URL(configured);
  if (parsed.protocol !== "https:" || parsed.hostname !== "torrentio.strem.fun" ||
      parsed.username || parsed.password || parsed.port ||
      parsed.search || parsed.hash || parsed.pathname.length > 350 ||
      !/^\/(?:[a-z0-9_.,=%|+-]+)?\/?$/i.test(parsed.pathname))
    throw new Error("invalid_torrentio_base");
  // Um URL com credencial de debrid jamais deve aparecer na resposta pública.
  if (/realdebrid|premiumize|alldebrid|debridlink|torbox|apikey|token=/i.test(parsed.pathname))
    throw new Error("credentials_in_public_config");
  return parsed.origin + parsed.pathname.replace(/\/+$/,"");
}

function normalized(text) {
  return String(text || "").normalize("NFKD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
}

export function explicitLanguage(description) {
  const value = normalized(description);
  if (/(?:^|[^a-z])(pt[\s._-]?br|dublado|dual[\s._-]?audio|portugues|brazilian[\s._-]?portuguese)(?=$|[^a-z])/i.test(value))
    return "pt-br";
  if (/(?:^|[^a-z])(english|ingles|hindi|russian|francais|french|spanish|espanol)(?=$|[^a-z])/i.test(value))
    return "other";
  return "unknown";
}

function quality(text) {
  if (/(?:^|[^a-z0-9])(?:2160p?|4k|uhd)(?=$|[^a-z0-9])/i.test(text)) return "4K";
  if (/(?:^|[^a-z0-9])1080p?(?=$|[^a-z0-9])/i.test(text)) return "1080p";
  if (/(?:^|[^a-z0-9])720p?(?=$|[^a-z0-9])/i.test(text)) return "720p";
  if (/(?:^|[^a-z0-9])480p?(?=$|[^a-z0-9])/i.test(text)) return "480p";
  return "SD";
}
function sizeFromText(text) {
  const match = String(text || "").match(/(?:^|[^0-9])([0-9]{1,5}(?:[,.][0-9]{1,3})?)\s*(GiB|MiB|GB|MB)\b/i);
  if (!match) return 0;
  const bytes = Number(match[1].replace(",",".")) * (match[2].toLowerCase().startsWith("g") ? 1073741824 : 1048576);
  return Number.isFinite(bytes) && bytes >= 0 ? Math.floor(bytes) : 0;
}
function seedersFromText(text) {
  const match = String(text || "").match(/(?:👤|👥|seeders?\s*[:=]|peers?\s*[:=])\s*(\d{1,7})/i);
  return match ? Number(match[1]) : null;
}
function providerFromText(text) {
  const known = ["MicoLeaoDublado", "Comando", "BluDV", "ThePirateBay", "1337x", "EXT"];
  const candidate = known.find(x => normalized(text).includes(normalized(x)));
  return candidate ? "Torrentio / " + candidate : "Torrentio";
}
function torrentHash(item) {
  const hash = String(item.infoHash || item.infohash || "").toLowerCase();
  return HASH.test(hash) ? hash : null;
}
function hashFromUri(uri) {
  if (typeof uri !== "string") return null;
  const match = uri.match(/[?&]xt=urn%3Abtih%3A([0-9a-f]{40})|[?&]xt=urn:btih:([0-9a-f]{40})/i);
  return match ? (match[1] || match[2]).toLowerCase() : null;
}
function score(item) {
  return [
    item.language === "pt-br" ? 2 : item.language === "unknown" ? 1 : 0,
    QUALITY_RANK[item.quality] || 0,
    Number(item.seeders || 0),
    Number(item.size || 0)
  ];
}
function better(a,b) {
  const one=score(a), two=score(b);
  for(let i=0;i<one.length;i++) if(one[i]!==two[i]) return one[i]>two[i];
  return false;
}

export function fromTorrentioPayload(payload) {
  if (!payload || !Array.isArray(payload.streams)) throw new Error("invalid_streams");
  const unique = new Map();
  let valid=0, ptBr=0;
  for (const item of payload.streams.slice(0,100)) {
    if (!item || typeof item !== "object") continue;
    const hash = torrentHash(item);
    if (!hash) continue; // Debrid/direct URLs sem hash não são torrents Elementum.
    const rawTitle = String(item.title || item.description || item.name || "");
    const rawName = String(item.name || "");
    const language = explicitLanguage(rawTitle + " " + rawName);
    const q = quality(rawTitle + " " + rawName);
    const size = Number(item.behaviorHints?.videoSize) || sizeFromText(rawTitle);
    const fileIdx = Number.isSafeInteger(item.fileIdx) && item.fileIdx >= 0
      ? item.fileIdx : null;
    const src = {
      title: clean(rawTitle.split("\n")[0] || rawName, 160) || "Fonte Torrentio",
      source: providerFromText(rawTitle + " " + rawName),
      url: "magnet:?xt=urn:btih:" + hash,
      infoHash: hash,
      fileIdx,
      quality:q,
      size: Math.max(0,size),
      seeders:seedersFromText(rawTitle),
      language,
      audio_verified:false,
      type:"torrent"
    };
    valid++;
    if(language==="pt-br") ptBr++;
    const key = hash + ":" + (fileIdx ?? "");
    const prior=unique.get(key);
    if (!prior || better(src,prior)) unique.set(key,src);
  }
  const indexed = new Set([...unique.values()].filter(x => x.fileIdx !== null).map(x => x.infoHash));
  const sources=Array.from(unique.values()).filter(x => x.fileIdx !== null || !indexed.has(x.infoHash)).sort((a,b)=>{
    const x=score(a),y=score(b);
    for(let i=0;i<x.length;i++) if(x[i]!==y[i]) return y[i]-x[i];
    return a.title.localeCompare(b.title,"pt-BR");
  });
  return {
    sources,
    stats:{
      raw:payload.streams.length,
      hash_valid:valid,
      unique:sources.length,
      repeated_hashes:valid-sources.length,
      pt_br_marked:ptBr,
      pt_br_unique:sources.filter(x=>x.language==="pt-br").length
    }
  };
}

export function mergeSources(existing=[],additional=[]) {
  const map=new Map();
  for(const item of [...existing,...additional]) {
    if (!item || typeof item!=="object") continue;
    if(REMOVED.has(normalized(item.source))) continue;
    const uri=item.url || item.magnet;
    const hash=torrentHash(item) || hashFromUri(uri);
    const identity=hash || (typeof uri==="string" && uri.startsWith("https://") ? uri : "");
    if (!identity) continue;
    const key = identity + ":" + (item.fileIdx ?? item.file_index ?? "");
    const prior=map.get(key);
    if (!prior || better(item,prior)) map.set(key,item);
  }
  return [...map.values()].sort((a,b)=>{
    const x=score(a),y=score(b);
    for(let i=0;i<x.length;i++) if(x[i]!==y[i]) return y[i]-x[i];
    return String(a.title||"").localeCompare(String(b.title||""),"pt-BR");
  }).slice(0,80);
}

export async function queryTorrentio(imdb,options={}) {
  if (!VALID_IMDB.test(imdb||"")) return {sources:[],stats:{skipped:"missing_or_invalid_imdb"}};
  const base=torrentioBaseUrl(options.base);
  const fetcher=options.fetcher || fetch;
  const address=base+"/stream/movie/"+imdb+".json";
  const result=await fetcher(address,{
    headers:{accept:"application/json","user-agent":"FelipeVideosCloudflare/0.3"},
    signal:AbortSignal.timeout(8000)
  });
  if (!result.ok) throw new Error("torrentio_http_"+result.status);
  const reported=Number(result.headers?.get?.("content-length")||0);
  if(reported>MAX_JSON) throw new Error("torrentio_response_too_large");
  const body=await result.text();
  if(body.length>MAX_JSON) throw new Error("torrentio_response_too_large");
  return fromTorrentioPayload(JSON.parse(body));
}

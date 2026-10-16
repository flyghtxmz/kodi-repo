import {queryTorrentio,mergeSources} from "./torrentio.mjs";
// Felipe Vídeos: interface do Worker, sem fontes incluídas.
// Preserve os adaptadores que você criou no painel Cloudflare. Não faça
// redeploy deste template sobre sua versão customizada sem sincronizar o código.
const IMDB = /^tt[0-9]{5,12}$/;
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": status === 200 ? "public, max-age=120" : "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}
export default {
  async fetch(request, env={}) {
    const url = new URL(request.url);
    if (request.method !== "GET") return json({error:"method_not_allowed"},405);
    if (url.pathname === "/health") return json({ok:true,version:"0.2",deployed:true});
    if (url.pathname !== "/v1/sources") return json({error:"not_found"},404);
    const title = (url.searchParams.get("title") || "").trim();
    const imdb = (url.searchParams.get("imdb") || "").trim();
    const year = (url.searchParams.get("year") || "").trim();
    if (!title || title.length > 120 ||
        (year && !/^[12]\d{3}$/.test(year)) ||
        (imdb && !IMDB.test(imdb)))
      return json({error:"invalid_query"},400);
    // Integração opt-in: a produção editada na Cloudflare permanece intocada.
    // Ajustar/mesclar os adaptadores do ambiente publicado antes de fazer deploy.
    let sources=[],providers=[],providerStats={};
    if (env?.TORRENTIO_ENABLED === "true" && imdb) {
      providers.push("Torrentio");
      try {
        const result=await queryTorrentio(imdb,{base:env.TORRENTIO_BASE_URL});
        sources=mergeSources([],result.sources);
        providerStats.torrentio=result.stats;
      } catch(error) {
        providerStats.torrentio={error:String(error?.message||"unavailable").slice(0,80)};
      }
    }
    return json({imdb:imdb || null,title,year:year || null,sources,providers,providerStats});
  },
};

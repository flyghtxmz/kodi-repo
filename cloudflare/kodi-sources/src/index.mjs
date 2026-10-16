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
  async fetch(request) {
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
    // Template intencionalmente sem indexadores. O Worker já publicado
    // pode ter suas próprias implementações de fontes.
    return json({imdb:imdb || null,title,year:year || null,sources:[],providers:[]});
  },
};

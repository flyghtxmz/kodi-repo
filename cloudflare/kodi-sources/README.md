# Felipe Vídeos — Cloudflare Sources

O Worker neste diretório é um template com adaptador **opcional** do Torrentio
(desativado por padrão) e sem Internet Archive.
Ele aceita `GET /v1/sources?title=...&year=...&imdb=...` e responde JSON
com `{title,year,imdb,sources,providers}`. Não inclui Internet Archive.

**Atenção:** o Worker de produção já foi alterado diretamente na conta
Cloudflare do usuário e pode conter adaptadores customizados de indexadores.
**NÃO execute `wrangler deploy` com este template** sem antes sincronizar
esses adaptadores: isso sobrescreveria a versão publicada com um backend vazio.

O Kodi encontra o endereço publicado automaticamente pelo arquivo
[endpoint.json](endpoint.json), que não contém segredo nem token.

Uma fonte compatível para reprodução autorizada tem o formato:

```json
{
  "title": "Vídeo licenciado",
  "source": "Provedor autorizado",
  "url": "https://media.example.org/video.torrent",
  "quality": "1080p",
  "seeders": 8,
  "size": 1000000000,
  "language": "pt-br"
}
```

O campo `url` também pode ser um magnet válido (`magnet:?xt=urn:btih:...`).
O addon aceita esses formatos, ordena fontes com áudio PT-BR declarado e
bloqueia links inseguros e o provedor removido. Não verifica por si só os
direitos de distribuição de cada fonte; use conteúdo autorizado.

Teste do contrato: `node --test cloudflare/kodi-sources/test/worker.test.mjs`.

## Adaptador Torrentio (somente depois de sincronizar com o Worker publicado)

O módulo `src/torrentio.mjs` consulta **metadados JSON** do protocolo Stremio.
Só busca filmes com IMDb ID válido (`tt...`); a escolha de episódios de séries
está pendente. O módulo aceita apenas `https://torrentio.strem.fun` como origem.

- Habilitação no Worker template: variável `TORRENTIO_ENABLED=true`.
- Origem opcional: variável `TORRENTIO_BASE_URL`; padrão
  `https://torrentio.strem.fun/providers=comando,bludv,micoleaodublado|language=portuguese`.
- **Não guarde credenciais de serviços debrid em URL pública**.
- `queryTorrentio` considera somente `infoHash` válido e converte para magnet
  compatível com Elementum. URL de streaming/debrid não é aceita por esse adaptador.
- Duplicatas são agrupadas por hash e a fonte com rótulo PT-BR explícito tem prioridade.
- `providerStats.torrentio` mostra `raw`, `unique`, `repeated_hashes`,
  `pt_br_unique`; são métricas de retorno, não garantia de áudio/reprodução.
- `fileIdx` é mantido como metadado, mas o Elementum pode precisar de seleção
  manual do arquivo correto em torrents com múltiplos vídeos.
- Respostas externas têm timeout de 8 segundos e limite de 600 KB.

**Muito importante:** alterar ou publicar o Worker template **substitui** os
adaptadores personalizados existentes no painel Cloudflare. Integre apenas
`src/torrentio.mjs` e a chamada `queryTorrentio()` na versão real antes
 de publicar; não faça deploy direto do arquivo `src/index.mjs` deste repo.

Teste isolado: `node --test cloudflare/kodi-sources/test/torrentio.test.mjs`.

# Felipe Vídeos — Cloudflare Sources

O Worker definido neste diretório é um **template de contrato**, sem fontes inclusas.
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

# Felipe Vídeos — Cloudflare Sources API

Worker para busca dinâmica de torrents **distribuídos em acervos com licenças abertas**.
Executa no Cloudflare e devolve dados para uma tela de seleção no Kodi. Não executa
BitTorrent no Cloudflare, não exige Prowlarr e não configura provedores do Elementum.

## Publicar no seu Cloudflare

Os arquivos deste diretório são código-fonte. **Não há Worker publicado por este commit.**
Execute, a partir de `cloudflare/kodi-sources`:

```sh
npx wrangler login
npx wrangler secret put KODI_API_TOKEN
npx wrangler deploy
```

O comando de secret solicitará um valor **forte e exclusivo** e o salvará nas configurações
privadas do Worker; nunca o inclua no repositório, no arquivo `wrangler.toml`,
em screenshots nem em URLs. Guarde o token também nas configurações locais do Kodi.

Copie o endereço HTTPS exibido pelo Wrangler, normalmente
`https://felipe-videos-sources.<seu-subdominio>.workers.dev`.
Esse endereço é um exemplo de formato, **não** é um endpoint existente.

## API

- `GET /health`: `{"ok":true,"version":"0.1","deployed":true}`.
- `GET /v1/sources?imdb=tt1254207&title=Big%20Buck%20Bunny&year=2008`
  retorna `{imdb,title,year,sources:[...],providers:["Internet Archive"]}`.
- A rota de fontes exige `Authorization: Bearer <seu token>` no cabeçalho.
- Cada fonte inclui `title,source,quality,size,seeders,language,url,type`.
  Os torrents encontrados são do acervo Internet Archive com declaração Creative Commons
  validada pelo metadado antes de apresentar o arquivo.
- `seeders: null` significa **desconhecido**, não zero.
- `language: "unknown"` significa áudio **não verificado**.
- `sources: []` significa que nenhuma fonte com os critérios foi encontrada.

O Worker recebe o IMDb ID do catálogo, mas a origem atual não oferece consulta
por IMDb: a seleção é feita por **título e ano**. Filmes comerciais recentes que
não estão em acervos abertos normalmente retornarão lista vazia. Não é uma API
para localizar cópias comerciais sem autorização.

## Testes sem Cloudflare

```sh
node --test test/worker.test.mjs
```

## Conectar ao Felipe Vídeos

No Kodi, abra **Add-ons > Felipe Vídeos > Configure > Cloudflare** e informe
**URL HTTPS do Worker** e **Token da API**. Depois abra um filme e escolha
**Fontes via Cloudflare**. O addon apresenta as opções e envia a fonte
selecionada ao Elementum como reprodutor. Elementum não precisa ter
provedores de pesquisa instalados.

As URLs e tokens são settings locais no Kodi, nunca versionados no GitHub.
A integração Prowlarr existente permanece opcional e separada.

## Limites e operação

- Cloudflare Workers é um proxy leve de **metadados**, não um downloader, indexador
  BitTorrent ou cache de arquivos.
- Há limites de consultas, latência e quotas da sua conta Cloudflare.
- Não use este endpoint como proxy aberto nem inclua tokens em logs.
- O código de produção deve ser mantido atualizado conforme alterações nas APIs
  das fontes e no formato de resposta.

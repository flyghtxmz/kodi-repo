# Felipe Vídeos — Cloudflare Sources API

Endpoint público **somente de leitura** para fontes de vídeos abertos do Internet Archive.
A consulta retorna apenas arquivos com licença Creative Commons declarada nos
metadados, revalidada antes de exibir torrents. O próprio Elementum do Kodi
é usado apenas para reproduzir o torrent escolhido.

## Sem digitar URL ou token no Kodi

O addon descobre a URL do Worker automaticamente pelo arquivo versionado
`cloudflare/kodi-sources/endpoint.json` no GitHub. Esse arquivo armazena
**somente o endereço HTTPS público** do Worker (não é segredo).

Depois de publicar o Worker, informe o endereço resultante para incluí-lo
no arquivo `endpoint.json`, no formato:

```json
{"endpoint": "https://felipe-videos-sources.SEU-SUBDOMINIO.workers.dev"}
```

O endereço acima é apenas um exemplo e **não é uma implantação real**.
O valor inicial vazio significa que a ligação com a conta ainda não foi feita.
Quando o endereço estiver cadastrado, o Kodi passa a descobri-lo
automaticamente, sem alterar configurações da TV Box nem atualizar o ZIP.

## Publicação

O Wrangler já estando autenticado:

```powershell
npx wrangler deploy .\cloudflare\kodi-sources\src\index.mjs --name felipe-videos-sources --compatibility-date 2026-10-16
```

Se já existir um Worker com código anterior que exigia `KODI_API_TOKEN`,
é necessário **publicar a versão atualizada**; a versão antiga continuará
exigindo esse cabeçalho até receber o novo deploy. O segredo antigo pode
permanecer armazenado no Cloudflare; o código desta versão não o utiliza.

## Rotas

- `GET /health`: estado e versão.
- `GET /v1/sources?imdb=tt1254207&title=Big%20Buck%20Bunny&year=2008`:
  resposta com uma lista de torrents de acervos abertos.
- `sources: []`: nenhuma fonte encontrada.
- `seeders: null`, `language: unknown`: não informado pela fonte.

A rota de fontes é pública e **não requer token**. Isso é deliberado: um
token incluído no GitHub público ou distribuído no ZIP do Kodi pode ser
extraído por qualquer pessoa. Em caso de uso elevado, configure regras
de rate limiting/WAF na sua conta Cloudflare. O Worker valida parâmetros,
limita resultados e usa cache para reduzir requisições repetidas.

Este Worker não pesquisa indexadores de filmes comerciais e não
reproduz nem armazena torrents no Cloudflare.

## Testes

```sh
node --test cloudflare/kodi-sources/test/worker.test.mjs
```

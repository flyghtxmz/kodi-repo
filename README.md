# Felipe Addons — Kodi

Instalação: https://flyghtxmz.github.io/kodi-repo/

No Kodi, adicione esse endereço como fonte, instale
`repository.flyghtxmz-1.0.3.zip` e em **Install from repository**
selecione **Felipe Vídeos**.

## Felipe Vídeos 1.3.7

**Tela principal**

- Filmes
- Séries
- Buscar filmes e séries
- Ferramentas
- Sobre o Felipe Vídeos

Filmes contém *Filmes de 2026*, *Filmes de 2025* e *Filmes em alta*
(os anos são atualizados dinamicamente). Séries contém *Séries de 2026*
e *Séries em alta*. O catálogo e as capas vêm do Cinemeta.

Ao selecionar um filme ou série aparece um **popup nativo do Kodi** com
**Buscar fontes**, trailer (quando disponível), onde assistir no Brasil e sinopse,
sem abrir uma nova pasta. **Buscar fontes** abre um segundo popup com as
fontes disponíveis; ao escolher uma delas o Elementum é chamado diretamente.
Cancelar qualquer popup mantém o usuário no catálogo.
A lista de fontes é obtida do Worker publicado na conta
Cloudflare, cuja URL é lida automaticamente de
[endpoint.json](cloudflare/kodi-sources/endpoint.json). Não precisa inserir
endereço ou token na TV Box.

O addon bloqueia o provedor Internet Archive, mesmo que o Worker publicado
ainda o retorne. A interface aceita torrents HTTPS e magnet links válidos, remove duplicatas pelo infohash mesmo quando os provedores divergem;
reprodução é delegada ao Elementum, sem buscar provedores dentro dele.
Áudio PT-BR na lista é **declarado pela fonte**, não verificado.

As antigas categorias de filmes abertos, clipe de demonstração, URL de vídeo
pessoal, pesquisa duplicada pelo Elementum e menus Prowlarr/Debrid foram
removidos. Ferramentas reúne diagnóstico, configurações do Elementum e
entrada manual de magnet/.torrent.

**Importante:** o código do Worker no repositório é apenas um template vazio.
O Worker real pode conter modificações feitas diretamente na Cloudflare.
Não faça redeploy deste template sem sincronizar previamente os indexadores
customizados, pois ele substituiria a API atual.

## Desenvolvimento e testes

```bash
python tools/build_repo.py
python -m unittest discover -s tests -v
node --test cloudflare/kodi-sources/test/worker.test.mjs
```

O build e os testes são executados automaticamente nos GitHub Actions.
O repositório Kodi permanece na versão 1.0.3.

Para a reprodução de torrents, instale Elementum separadamente. BitTorrent
pode expor o seu IP aos peers e transmitir dados a outros usuários. Utilize
somente arquivos cuja distribuição e reprodução são autorizadas.

## Integração Torrentio — preparação

Adaptador opcional em `cloudflare/kodi-sources/src/torrentio.mjs`, com
validação de IMDb ID, timeout de 8 segundos, limite de resposta e deduplicação
por hash. Métricas brutas e únicas ficam em `providerStats.torrentio`.
O Worker publicado manualmente na Cloudflare **não foi modificado**.
Sincronize o código customizado antes de habilitar o adaptador; veja
[as instruções específicas](cloudflare/kodi-sources/README.md).

O Kodi 1.3.7 faz uma segunda deduplicação por hash e prioriza PT-BR declarado,
sem inferir áudio pelo nome do indexador. O Elementum pode exigir a escolha
manual do arquivo de vídeo no caso de torrents com múltiplos arquivos.

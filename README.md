# Felipe Addons — Kodi

Fonte Kodi no GitHub Pages: https://flyghtxmz.github.io/kodi-repo/

No Kodi: File manager > Add source > cole o URL; em Add-ons > Install from zip file, instale `repository.flyghtxmz-1.0.1.zip`. Em Install from repository, escolha `Felipe Addons - Repositório` e instale `Felipe Vídeos`.

## Felipe Vídeos 1.1.0 (Kodi 21.2 Omega)

- Reprodução de URL direta de vídeo, com clipe de teste CC0.
- Digitação/colagem de magnet link (`magnet:?xt=urn:btih:...`) ou URL HTTP(S) terminada em `.torrent`.
- Encaminhamento da reprodução ao **Elementum instalado separadamente** na TV Box (não é incluído no ZIP).
- Atalho para abrir as configurações do Elementum, que controla buffer, armazenamento e limpeza.

**Dependência opcional:** instale e configure o Elementum seguindo https://elementumorg.github.io/getting-started/installation/ e abra-o uma vez antes de usar torrents. A versão 1.1.0 não procura torrents, não oferece catálogos de filmes, não controla o buffer por conta própria e não contém motor BitTorrent.

**Privacidade:** BitTorrent pode compartilhar dados com outros peers e expor o endereço IP público. Utilize somente conteúdos cuja distribuição é autorizada.

## Manutenção

Rode `python tools/build_repo.py` para gerar ZIPs, `addons.xml` e `addons.xml.md5`, e `python -m unittest discover -s tests -v` para os testes. O workflow `Publish Kodi addon packages` recompila e publica os artefatos a cada alteração do código-fonte.

## Diagnóstico de conectividade (Kodi Omega)

O instalador do repositório 1.0.1 inclui a dependência `xbmc.addon` e declara `<hashes>false</hashes>`. Se o Kodi mostrar **Could not connect to repository**, reinstale o ZIP 1.0.1 e use o comando **Check for updates** no menu de contexto do repositório. Para investigar erros persistentes, verifique a conectividade do Kodi com `addons.xml` e envie o `kodi.log` com o erro de `CRepository`/TLS.

# Felipe Addons — Kodi

Fonte Kodi no GitHub Pages: https://flyghtxmz.github.io/kodi-repo/

No Kodi: File manager > Add source > cole o URL; em Add-ons > Install from zip file, instale `repository.flyghtxmz-1.0.3.zip`. Em Install from repository, escolha `Felipe Addons - Repositório` e instale `Felipe Vídeos`.

## Felipe Vídeos 1.3.0 (Kodi 21.2 Omega)

- Reprodução de URL direta de vídeo, com clipe de teste CC0.
- Digitação/colagem de magnet link (`magnet:?xt=urn:btih:...`) ou URL HTTP(S) terminada em `.torrent`.
- Encaminhamento da reprodução ao **Elementum instalado separadamente** na TV Box (não é incluído no ZIP).
- Atalho para abrir as configurações do Elementum, que controla buffer, armazenamento e limpeza.

**Dependência opcional:** instale e configure o Elementum seguindo https://elementumorg.github.io/getting-started/installation/ e abra-o uma vez antes de usar torrents. A versão 1.1.0 não procura torrents, não oferece catálogos de filmes, não controla o buffer por conta própria e não contém motor BitTorrent.

**Privacidade:** BitTorrent pode compartilhar dados com outros peers e expor o endereço IP público. Utilize somente conteúdos cuja distribuição é autorizada.

## Manutenção

Rode `python tools/build_repo.py` para gerar ZIPs, `addons.xml` e `addons.xml.md5`, e `python -m unittest discover -s tests -v` para os testes. O workflow `Publish Kodi addon packages` recompila e publica os artefatos a cada alteração do código-fonte.

## Diagnóstico de conectividade (Kodi Omega)

O instalador do repositório 1.0.3 inclui a dependência `xbmc.addon` e declara `<hashes>false</hashes>`. Se o Kodi mostrar **Could not connect to repository**, reinstale o ZIP 1.0.3 e use o comando **Check for updates** no menu de contexto do repositório. Para investigar erros persistentes, verifique a conectividade do Kodi com `addons.xml` e envie o `kodi.log` com o erro de `CRepository`/TLS.

## Diagnóstico (TV Box / Android TV)

Se **Install from repository** mostrar `Could not connect to repository`, é possível instalar o vídeo addon independentemente do repositório: **Install from zip file > Felipe Addons > Felipe Vídeos - instalador direto e diagnóstico** (link no índice da fonte). Depois abra **Video add-ons > Felipe Vídeos > Diagnosticar repositório**. O relatório usa Kodi VFS/cURL e Python HTTPS no mesmo aparelho, valida o checksum e procura mensagens do Kodi relacionadas ao repositório. Envie uma foto da tela de resultados; não publique logs completos sem revisar dados pessoais.

## Release do repositório 1.0.3

Numeração do instalador aumentada de 1.0.1 para 1.0.2 para o Kodi reconhecer a versão atual. Esta mudança, por si só, não comprova que o erro de conexão ao catálogo foi resolvido.

## Correção de conectividade 1.0.3

A fonte de instalação permanece em `https://flyghtxmz.github.io/kodi-repo/` (GitHub Pages), enquanto o manifesto do repositório instalado lê `addons.xml`, `addons.xml.md5` e os pacotes ZIP em `https://raw.githubusercontent.com/flyghtxmz/kodi-repo/main/`. Essa separação reproduz a estratégia observada no manifesto `repository.cineroom` v1.0.1. Instale o ZIP 1.0.3 para substituir as URLs antigas no Kodi; a alteração só pode ser validada completamente em um Kodi real.


## Felipe Vídeos 1.3.0 — Catálogo automático

- Menu de Mais populares, Filmes, Séries e programas, Documentários, Animações e Curtas-metragens.
- Busca por título, capas, sinopse, paginação e reprodução sem digitar links.
- O addon consulta sob demanda a API do Internet Archive e resolve automaticamente a URL do vídeo escolhido, sem API key.
- Itens filtrados pela licença Creative Commons ou domínio público declarada no catálogo; a licença é revalidada antes da reprodução. Não é o catálogo comercial do CineRoom.
- A disponibilidade do catálogo varia com o Internet Archive. Elementum continua opcional para magnet links fornecidos pelo usuário.
- O repositório Felipe Addons 1.0.3 permanece sem alteração, permitindo atualizar o addon pelo Kodi.


### Seleção de destaque

A primeira tela de destaques apresenta quatro filmes abertos da Blender Foundation (Big Buck Bunny, Sintel, Elephants Dream e Tears of Steel) usando vídeos de demonstração hospedados no Google Cloud Storage; o addon escolhe automaticamente as URLs, sem edição pelo usuário. Nas outras seções, a busca do Internet Archive ainda depende de metadados de licença informados pelos responsáveis de cada upload e pode conter classificações incorretas; o addon não garante a legitimidade de terceiros.


### Ajuste de fontes (1.2.2)

A seleção de destaques utiliza identificadores pré-curados de filmes abertos da Blender Foundation, mas consulta os metadados do Internet Archive para resolver automaticamente o MP4 atual, confirmar a licença informada e evitar URLs de demonstração inacessíveis no Google Storage. A lista é de cinco filmes, incluindo Cosmos Laundromat.


## Filmes atuais — Felipe Vídeos 1.3.0

Novos menus **Filmes de 2026**, **Filmes do ano anterior**, **Filmes em alta**, **Séries recentes**, **Séries em alta**, e **Buscar lançamentos e séries**. O addon consulta o serviço público Cinemeta no momento de abrir cada seção (atualização dinâmica sem API key), com capas, sinopses e trailers fornecidos pelo Cinemeta. As fichas incluem link para busca de serviços oficiais na JustWatch Brasil (abertura via Chrome no Android TV se instalado), e trailers podem ser vistos com o addon oficial YouTube do Kodi.

**A listagem de lançamentos é informativa**: não transmite obras comerciais nem oferece torrents ou fontes não autorizadas. A reprodução integral continua nas seções de licença aberta, resolvida automaticamente. Metadados podem incluir filmes anunciados ainda não lançados; o status deve ser verificado na plataforma distribuidora. O repositório continua 1.0.3.

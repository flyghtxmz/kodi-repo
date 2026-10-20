## Felipe Cinema 1.6.2 — modo padrão e navegação persistente

Cinema está ativado por padrão, inclusive após atualizar a versão anterior.
A configuração `cinema_default_v3` permite desativá-lo manualmente em
**Configurar → Interface**. Próxima/anterior página mantém a própria janela
Cinema e a fileira original. Erros não trocam automaticamente para o modo
nativo, e um problema de rede preserva a página anterior. O foco de um
pôster agora tem faixa **▶ SELECIONADO** e borda vermelha.

## Felipe Cinema 1.6.1 — início e navegação dentro da interface Cinema

A alteração 1.6.0 ampliou apenas o menu nativo. A 1.6.1 refaz a própria tela Cinema:

- Início com duas fileiras independentes de capas: filmes e séries em alta na semana.
- Faixa de atalhos para Netflix, Prime Video, Apple TV+, Disney+, HBO Max,
  Paramount+, Globoplay e Crunchyroll. Ao escolher uma plataforma, as duas
  fileiras mostram seus filmes e séries populares.
- Filmes e Séries com lançamentos, mais avaliados e atalhos por gênero.
- Em alta alterna entre hoje e semana; busca retorna filmes e séries separados.
- Próxima/anterior página dentro de cada fileira, sem limite de apenas 20 títulos.
- Fechar/cancelar a ficha volta à mesma página e posição, sem consultar tudo de novo.
  Após entregar reprodução ao Elementum ou YouTube, Cinema não reabre sobre o player.
- Consultas, teclado e ficha são executados somente depois de destruir a janela
  modal. Os callbacks da janela apenas leem controles e agendam ações.
- Falha ao buscar a próxima página preserva a anterior; falha inicial oferece tentar
  novamente. A tela identifica explicitamente a versão 1.6.1.

Acesse em Ferramentas → Experimentar interface Cinema ou habilite Cinema em
Configurar → Interface. Navegação nativa continua disponível pelo menu lateral.
A região de referência das plataformas continua explícita; não são rankings
oficiais nem confirmação de disponibilidade brasileira.

Validação: testes automatizados de navegação, paginação, restauração da seleção,
separação dos ciclos de vida modal/player e limites geométricos do XML. Não há
motor gráfico Kodi/TV Box neste ambiente: aparência e estabilidade no aparelho
não foram verificadas visualmente.

## Felipe Vídeos 1.6.0 — catálogo por plataforma e navegação nativa

- Início com busca, tendências do dia/semana, plataformas, filmes, séries e ferramentas.
- Netflix, Prime Video, Apple TV+, Disney+, HBO Max, Paramount+, Globoplay e Crunchyroll,
  com filmes/séries separados, paginação e nomes/sinopses PT-BR quando fornecidos.
- Listas de plataforma preservam a popularidade do TMDb; tendências usam o catálogo
  diário/semanal do TMDb. Não são rankings oficiais dos serviços.
- As plataformas usam as regiões do provedor público: Netflix/Apple/Disney GB,
  Prime/Paramount/Crunchyroll US, HBO Max NL e Globoplay BR. O menu informa essa
  referência; consulte “Onde assistir no Brasil” na ficha para disponibilidade local.
  Uma plataforma pode retornar uma lista vazia ou ficar indisponível.
- Navegação nativa como padrão também após atualizar da 1.5.7. A configuração antiga
  de Cinema não é reaproveitada. A interface experimental continua em Ferramentas
  ou Configurar → Interface, mediante nova escolha do usuário.
- Fichas rejeitam respostas/cache com outro IMDb ID ou tipo de mídia. A opção
  “Sinopse e detalhes” fica no popup do título.
- Ferramentas → Diagnosticar fechamento registra a última etapa da ficha, ID e horário,
  sem salvar links de reprodução. Ajuda a investigar um fechamento nativo;
  não substitui kodi.old.log nem identifica sozinho a causa.
- A reprodução continua a cargo do Elementum. Não é possível validar crashes de
  drivers, decodificação ou do binário Elementum nos testes Python fora do aparelho.

Atualize o repositório no Kodi e instale Felipe Vídeos **1.6.0**. O instalador
atual também está em https://flyghtxmz.github.io/kodi-repo/.

Referência do catálogo: https://github.com/mrcanelas/tmdb-addon

### Histórico

## Felipe Vídeos 1.5.7 — estabilidade no Kodi Android

- **Cinema:** ao selecionar um pôster, a janela fullscreen modal é encerrada
  antes de abrir o popup nativo do Kodi e antes de enviar a reprodução ao Elementum.
  Evita diálogos sobrepostos dentro de `WindowXMLDialog.onClick`, uma fonte
  potencial de instabilidade em builds Android.
- **Modo seguro:** em **Configurar → Interface**, desative **Usar a interface
  Felipe Cinema** para retornar ao menu clássico, sem remover o addon.
- **Diagnóstico:** o leitor de logs inclui `kodi.old.log` quando disponível
  para investigar o fechamento inesperado. Logs e testes não comprovam a causa
  nativa de todo crash; se persistir, será necessário analisar o log do aparelho.
- **Reprodução:** a mensagem "Solicitação enviada" significa apenas que o Kodi
  aceitou o comando. Não garante que o magnet foi resolvido ou que havia peers.

## Interface fullscreen Felipe Cinema — 1.5.6

Ao abrir Felipe Vídeos, a nova interface fullscreen **Felipe Cinema** cobre a
skin do Kodi, com navegação por controle remoto, capas, painel de destaque e
atalhos laterais para Início, Filmes, Séries, Em alta e Busca.

A interface é feita com `xbmcgui.WindowXMLDialog` e o arquivo
`resources/skins/Default/1080i/FelipeCinema.xml`; **não altera a skin
global do Kodi**. Títulos são selecionados pelo controle remoto e continuam
abrindo os popups de temporadas, fontes e trailers existentes, por cima da
interface. A busca usa IMDb ID, preservando o fluxo do Elementum.

O menu **Menu clássico** permite retornar à navegação antiga sem reinstalar.
Se o dispositivo ou a skin instalada não suportar a janela, o plugin volta
ao menu tradicional automaticamente. VOLTAR fecha o Felipe Cinema.
A primeira abertura de uma categoria consulta seu catálogo; ao selecionar um
título, o plugin abre a ficha completa. Traduções em cache aparecem de imediato;
as traduções faltantes são obtidas pela ficha ao abrir o título.

A versão 1.5.6 é uma **primeira interface funcional**: não implementa
navegação infinita nem telas inteiramente novas de reprodução, e precisa de
validação real no Kodi 21. Os serviços de fontes e a Cloudflare não foram
alterados nesta atualização.

## Novas opções de filmes — 1.5.5

A área **Filmes** agora oferece **Clássicos e nostalgia (por década)** (anos
1920–2010), **Cinema brasileiro**, **Filmes em português** e **Animes e longas
de animação japonesa**, além das categorias já existentes. A escolha da década
abre um popup para selecionar o ano, e então o catálogo de filmes daquele ano.
As capas, os títulos PT-BR, as sinopses no painel e o popup de fontes
continuam funcionando. A navegação de clássicos é uma organização por
**ano de lançamento**, não uma classificação crítica de obras-primas.

As opções de cinema brasileiro e idioma/país reutilizam a pesquisa e os
filtros existentes; a quantidade de títulos depende dos registros do
Cinemeta e TMDb. A ordem alfabética é mantida por página.

Essa atualização altera apenas **os menus do Kodi**, não o Worker Cloudflare
nem o motor de reprodução Elementum. Não é uma correção para torrents que
ficam carregando após a mensagem de solicitação enviada.

## Versão 1.5.4 — correção de magnet e áudio PT-BR

- Corrigida a passagem de magnet ao Elementum: o identificador `xt=urn:btih:HASH` usa **dois-pontos literais** dentro do magnet, e a URL externa do Kodi é codificada uma única vez. Corrige o caso de log `missing info-hash from URI` com `xt=urn%253Abtih%253A...`.
- A mesma normalização é feita no momento da reprodução para URLs antigas ainda armazenadas em cache, inclusive de outros provedores. O índice original `oindex` continua preservado.
- `Subs EN/PTBR` e outras marcas **somente de legenda** não serão consideradas como evidência de áudio dublado. Indicadores efetivos de dublagem, como `DUBLADO` e `Áudio BR`, continuam reconhecidos.
- A busca rápida ainda recorre aos demais provedores quando não encontra áudio PT-BR declarado. A classificação é textual, não confirmação da faixa de áudio.
- Os testes de código reproduzem o magnet do log e os falsos positivos de legenda; a reprodução real requer validação na TV Box com um torrent autorizado e peers disponíveis.

## Felipe Vídeos 1.5.5 — dublados e diagnóstico de reprodução

- **PT-BR**: a busca rápida do Torrentio não encerra a pesquisa se não houver áudio brasileiro indicado. Nesse caso também consulta Cloudflare, MediaFusion e Comet (filmes) ou os demais provedores compatíveis (episódios). Isso pode levar alguns segundos a mais em títulos sem PT-BR marcado.
- Idioma é identificado a partir dos campos explícitos do título, descrição, nome de arquivo e idiomas retornados pelo serviço. **Provedor brasileiro sozinho não prova dublagem.**
- Na janela de fontes, as entradas PT-BR identificadas recebem o marcador **🔊 PT-BR indicado** e há uma opção **Mostrar somente dublados/PT-BR indicados**. Fontes sem informação aparecem como **Áudio não confirmado**. A indicação depende dos metadados, não é validação real das trilhas do arquivo.
- **Reprodução**: uma resposta Player.Open: OK não prova que houve início de vídeo. A mensagem agora deixa isso explícito. O Kodi ganhou **Ferramentas > Diagnosticar última reprodução**, que mostra se um vídeo está tocando, nome do provedor, idioma declarado, seeders informados e registros locais, sem exibir magnet/URL do torrent e sem tentar reproduzir de novo.
- Caso o próprio Elementum não inicie, use **Ferramentas > Testar Elementum**. Problemas de peers, magnet, armazenamento e buffer precisam ser verificados na TV Box; o addon não consegue consertá-los apenas enviando outro comando.
- Nenhuma mudança foi enviada ao Worker de produção da Cloudflare.

## Envio ao Elementum (1.5.1)

O popup envia a fonte selecionada por `Player.Open`, verificando o aceite do
Kodi e preservando `uri` e `oindex`. O mesmo método vale para entrada manual.
O addon avisa se o Elementum está desativado ou se o Kodi recusa a solicitação;
não repete o envio automaticamente. Falhas no cache opcional de legendas não
interrompem a reprodução.

A notificação “Solicitação enviada” confirma somente que o Kodi aceitou o
pedido. O Elementum ainda precisa resolver metadata, encontrar peers e preparar
o buffer. Se não aparecer sua tela de carregamento, use **Ferramentas → Testar
Elementum (abrir addon)**. O **Diagnóstico de conexão** agora também inclui
as mensagens recentes do Elementum e o aceite/recusa do pedido, com URLs
ocultas. Não exige habilitar servidor HTTP, portas ou controle remoto no Kodi.

Referências: [Player.Open no Kodi](https://kodi.wiki/view/JSON-RPC_API/v13#Player.Open)
e [rota de reprodução do Elementum](https://github.com/elgatito/elementum/blob/master/api/play.go).

## Novas fontes, exploração e legendas (1.5.0)

Atualize **Felipe Vídeos para 1.5.0** pelo repositório do Kodi.

- Filmes combinam o Worker existente, Torrentio, **MediaFusion e Comet**;
  séries consultam os três provedores diretos pelo IMDb e episódio exatos.
  Cada provedor falha isoladamente. A seleção mantém até 100 fontes sem
  duplicatas de hash/arquivo, com prioridade para PT-BR, português e peers
  informados. Contagens de reprodução não são apresentadas como seeders.
- Em **Filmes/Séries → Explorar catálogo**, escolha ano, idioma original,
  país e idioma, ou animes. Filmes também oferecem clássicos por década/ano.
  O recorte de país combina seu idioma principal com o país confirmado nos
  metadados; não cobre todas as produções multilíngues de cada país. Animes
  combinam idioma japonês e animação. Há paginação de 20 entradas de origem;
  alguns filtros podem apresentar menos itens por página.
- Novos catálogos usam o TMDb localizado com o IMDb confirmado antes da busca
  de fontes. Detalhes e episódios têm alternativa ao Cinemeta, preservando
  IMDb e a numeração real. A nota IMDb não é substituída pela nota TMDb.
- Quando o Worker não encontra um filme pelo título original, tenta também
  o nome brasileiro já disponível no cache de tradução, sem alterar ano/IMDb.
- Durante a reprodução, abra **Ferramentas → Legendas PT-BR do título
  selecionado**, escolha o arquivo compatível com seu release e volte ao
  vídeo. A pesquisa no OpenSubtitles via Stremio prioriza PT-BR e inclui PT.
  Somente a legenda escolhida é baixada e aplicada; sincronização depende
  do release. A seleção corresponde ao último título iniciado pelo addon.

Os novos provedores e as legendas usam a conexão do Kodi, sem exigir token
ou conta e sem tráfego adicional no Worker/SQL. MediaFusion e Comet têm cache
local de cinco minutos; buscas vazias, um minuto. Os novos caches têm limite
de 2 MB por arquivo; catálogos ficam por uma hora, países por 24 horas,
e no máximo cinco SRTs são mantidos. A primeira consulta por país pode levar
alguns segundos para confirmar a origem dos títulos.

As instâncias comunitárias podem ficar indisponíveis. A presença de uma fonte
não comprova que existam peers acessíveis. A reprodução continua no Elementum,
preservando `fileIdx` como `oindex` e trackers explicitamente fornecidos.

Referências dos provedores: [MediaFusion](https://github.com/mhdzumair/MediaFusion),
[Comet](https://github.com/g0ldyy/comet) e
[OpenSubtitles para Stremio](https://github.com/Stremio/stremio-opensubtitles-v3).

Verificação manual das APIs (metadados; não baixa vídeos):
`python tools/check_expansion_live.py --download-subtitle`.
O parâmetro opcional baixa somente um SRT para validar o formato.

## Ajustes de apresentação da versão 1.4.3

- O título exibido é procurado em **português (Brasil)** pelo serviço TMDb localizado. O IMDb ID original continua no link da ficha e da busca de torrents.
- A sinopse é gravada no **painel de informações da capa** do Kodi em `plot`, `plotoutline` e no `VideoInfoTag` (Kodi Omega), sem criar a opção de sinopse no popup.
- Há mais categorias por ano (**2024, 2025, 2026**) para filmes e séries, além de História, Guerra e Faroeste, e Música nos filmes. Os anos mudam automaticamente.
- O cache de tradução evita repetir consultas; a primeira visita a uma página pode levar alguns segundos. Quando uma tradução não está disponível, o título original permanece e uma mensagem em PT-BR substitui a sinopse.
- A versão da TV Box **precisa ser atualizada para 1.4.3**; mudar somente o código do GitHub não altera o addon que já está instalado.
- A aparência exata do painel depende do skin do Kodi, mas todos os campos nativos de sinopse são preenchidos.

## Séries: temporadas e episódios exatos (1.4.3)

Ao selecionar uma série, o **popup mostra as temporadas cadastradas** e a
quantidade de episódios por temporada. A escolha de temporada abre outro
popup com o identificador original de cada episódio, como **S01E01**,
**S01E03** ou **S02E08** (números reais do Cinemeta, não posição da lista).
A **temporada 0 (S00)** aparece como *Especiais*, quando existe.

O próximo popup oferece as fontes do episódio selecionado. A busca
direta no Torrentio utiliza o identificador Stremio
`ttIMDb:temporada:episódio`, como `tt0944947:2:8`, com cache independente
por episódio. **O Worker antigo, restrito à busca de filmes, não é
consultado para episódios** para evitar confundir a série com filmes ou
fontes de episódios diferentes. Cancelar qualquer popup não reproduz nada.

Os títulos de episódios são os fornecidos pelo Cinemeta e podem não estar
traduzidos; a numeração é a original da fonte. A disponibilidade de torrent,
idioma e arquivo correto depende do indexador e do Elementum.

# Felipe Addons — Kodi

Instalação: https://flyghtxmz.github.io/kodi-repo/

No Kodi, adicione esse endereço como fonte, instale
`repository.flyghtxmz-1.0.3.zip` e em **Install from repository**
selecione **Felipe Vídeos**.

## Felipe Vídeos 1.4.5

**Torrentio direto no Kodi:** a busca de fontes de filmes consulta o Worker e o
Torrentio em paralelo, pela conexão da própria TV Box. Os resultados aparecem
no mesmo seletor, com deduplicação por hash e arquivo. Se uma origem falhar,
as fontes da outra continuam disponíveis. Não é necessário token.

O Torrentio tem cache local de cinco minutos, limitado a 32 títulos e 1 MB.
Áudio brasileiro explicitamente declarado tem prioridade; indicação genérica
de português permanece `pt`. Nos pacotes, `fileIdx` é repassado ao Elementum
como **`oindex`**, que corresponde à ordem original dos arquivos do torrent.
Pacotes sem índice específico são descartados. O acesso ainda depende da
disponibilidade do serviço e da conexão da TV Box; não há proxy ou resolução
automática de desafios de acesso.

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
**Buscar fontes**, trailer (quando disponível) e onde assistir no Brasil,
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

## Títulos em português e mais categorias (1.4.0)

- A listagem mantém identificadores IMDb do Cinemeta para não perder
  compatibilidade com Cloudflare, Torrentio e Elementum. Nome e sinopse
  são enriquecidos com o serviço TMDb configurado para `pt-BR`.
- No primeiro acesso aos títulos novos, as traduções são consultadas em paralelo
  e armazenadas no Kodi por sete dias. Quando não houver tradução, mantém-se
  o título de origem, sem inventar um nome em português.
- Filmes: lançamentos do ano, ano anterior, em alta e mais bem avaliados,
  além do submenu **Gêneros**: ação, aventura, animação, comédia, crime,
  documentários, drama, família, fantasia, terror, mistério, romance,
  ficção científica e suspense.
- Séries: recentes, em alta e mais bem avaliadas, além de **Gêneros**:
  ação, aventura, animação, comédia, crime, documentários, drama, fantasia,
  mistério, ficção científica, suspense e reality shows.
- Dentro do catálogo, a sinopse aparece na área de informações da capa,
  não no popup; o popup mantém a seleção de fontes, o trailer e onde assistir.
- A classificação alfabética A–Z considera o título exibido em PT-BR, a cada
  página (20 itens). O serviço externo continua definindo quais títulos entram
  em cada página e em cada gênero.
- A nota **IMDb** continua sendo obtida do Cinemeta e mantida em cache por
  24h por título, sem ser substituída pela nota do TMDb.

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

## Integração Torrentio no Worker — histórico

Adaptador opcional em `cloudflare/kodi-sources/src/torrentio.mjs`, com
validação de IMDb ID, timeout de 8 segundos, limite de resposta e deduplicação
por hash. Métricas brutas e únicas ficam em `providerStats.torrentio`.
O Worker publicado manualmente na Cloudflare **não foi modificado**.
Sincronize o código customizado antes de habilitar o adaptador; veja
[as instruções específicas](cloudflare/kodi-sources/README.md).

Na versão 1.4.1 a consulta é direta no Kodi, e a seleção de arquivos fornecida
pelo Torrentio é preservada até o Elementum. O Worker não precisa consultar o Torrentio.

## Sinopses PT-BR e notas IMDb (1.3.8)

- A ficha de filmes e séries consulta a descrição em **português do Brasil** do
  serviço público TMDb-Stremio (`tmdb.elfhosted.com`, configuração `pt-BR`).
- As sinopses são armazenadas **localmente na TV Box** por sete dias;
  se houver indisponibilidade, usa o último texto válido ou exibe uma mensagem
  em português, sem apresentar a sinopse original em inglês.
- A **nota IMDb** vem do campo `imdbRating` do **Cinemeta**, não da nota
  `vote_average` do TMDb. O cache local mantém o valor por **24 horas**.
  Depois desse período, ela é reconsultada quando o usuário abre a ficha;
  a atualização não executa em segundo plano quando o Kodi está fechado.
- As notas podem permanecer temporariamente iguais caso o Cinemeta ainda não
  tenha refletido uma mudança feita no IMDb. A origem externa é responsável
  por publicar o dado, e o addon não promete sincronização em tempo real.
- A sinopse PT-BR aparece diretamente no **painel de informações da capa**
  ao selecionar o filme ou série, substituindo a antiga mensagem
  "Abra o título para consultar a sinopse". A opção "Sinopse e detalhes"
  foi retirada do popup; o popup continua apenas com busca de fontes,
  trailer e onde assistir no Brasil.
- Para evitar longas esperas, as listagens agora exibem até **20 títulos por
  página**. Na primeira visita o addon busca as traduções desses títulos
  em paralelo (até oito requisições simultâneas, 3 s por consulta).
  Resultados permanecem em cache por sete dias; falhas mostram uma mensagem
  em português, e novas tentativas são feitas no máximo uma vez por dia.
- Nenhuma chave TMDb é exigida nas configurações do Kodi, e o Worker de
  produção da Cloudflare não foi modificado.

## Versão 1.4.5 — inicialização de fontes no Elementum

- **Torrentio:** trackers públicos informados na resposta são incluídos no magnet
  (`tr=`), evitando depender exclusivamente de DHT para descobrir peers.
  Não são adicionados trackers inventados e endereços locais são descartados.
- **Seleção:** mantém prioridade de áudio PT-BR, mas dentro do mesmo idioma
  mostra primeiro as fontes com seeders positivos e conhecidos, antes de usar
  a resolução como desempate. Seeders são apenas números declarados pelo
  provedor e não garantem que os peers estejam acessíveis.
- **Seleção de arquivo:** mantém o índice original `fileIdx` como `oindex`
  na chamada oficial `plugin://plugin.video.elementum/play` quando informado.
- **Fontes sem peers:** quando o provedor informa *zero* seeders, exibe um
  alerta com opção de cancelar; sem contagem disponível, não inventa zero.
- **Reprodução:** um único comando `PlayMedia` por escolha; não dispara
  repetição automática enquanto o Elementum ainda está iniciando.

As mudanças são no addon Kodi, não no Worker da Cloudflare. A rapidez real
continua dependente de peers, rede, espaço disponível, velocidade do disco e
configurações de buffer do Elementum. Se uma fonte continuar travando, teste
outra com seeders positivos e consulte **Ferramentas > Configurações do
Elementum**, ou o log do Kodi para identificar falhas de buffer e metadata.

## Diagnóstico Elementum (1.4.5)

**Ferramentas > Testar Elementum (abrir addon)** informa a versão instalada e
abre o menu nativo do Elementum, sem iniciar torrents aleatórios. Se o
Elementum não abrir, verifique instalação, inicialização do serviço nativo e
logs do Kodi. Se abrir mas o torrent escolhido não carregar, confira seeders
reais, disponibilidade de peers, armazenamento e configuração de buffer.

O addon não garante que um torrent listado seja reproduzível. A origem do
problema só pode ser comprovada no Kodi/TV Box, não pelos testes no GitHub.

## Velocidade de abertura — 1.5.2

- A busca inicial no seletor de fontes usa o Torrentio primeiro. Havendo resultados,
  o popup abre sem aguardar Cloudflare, MediaFusion ou Comet.
- A última opção do popup, **Pesquisar também Cloudflare, MediaFusion e Comet**,
  faz a pesquisa completa sob demanda. Quando o Torrentio falha ou não encontra
  fontes, os outros provedores são consultados automaticamente.
- Fichas Cinemeta validadas são guardadas por **15 minutos**, acelerando reaberturas
  do mesmo filme/série. O cache separado da nota IMDb continua com **24 horas**.
- O log do Kodi registra a duração da ficha, a duração da busca de fontes e a
  confirmação do `Player.Open`. Em **Ferramentas → Diagnóstico de conexão**,
  os últimos trechos relevantes são exibidos sem URLs dos torrents.
- Um `Player.Open` aceito significa que o Kodi recebeu o comando; **não** prova
  que o torrent encontrou peers, baixou metadados ou completou o buffer.
  Esses fatores dependem do Elementum, da fonte, do armazenamento e da rede.
- Para diagnosticar demora **depois de selecionar** a fonte, use
  **Ferramentas → Testar Elementum**, confira seeders reais e consulte o log
  do Kodi/Elementum. Não aumentamos automaticamente buffer, não repetimos
  tentativas e não alteramos configurações de rede da TV Box.

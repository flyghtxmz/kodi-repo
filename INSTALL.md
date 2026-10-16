# Configuração de serviços privados — Felipe Vídeos (Kodi)

O código do addon é publicado em um repositório **público**. Não inclua tokens,
endereços internos de servidor, listas privadas de fontes ou credenciais neste
repositório. Insira esses valores apenas nas configurações locais do Kodi.

## 1. Prowlarr

Instale o Prowlarr no equipamento que ficará ligado enquanto a TV Box utilizar
o Kodi. Veja a documentação oficial em https://prowlarr.com/ .

Exemplo Docker (ajuste o caminho de configuração):

```bash
docker run -d --name prowlarr --restart unless-stopped \
  -p 9696:9696 \
  -v /seu/caminho/prowlarr:/config \
  lscr.io/linuxserver/prowlarr:latest
```

Abra `http://IP_DO_SERVIDOR:9696` no navegador de um equipamento da mesma rede.
Na **TV Box**, `localhost` aponta para a própria TV Box, e não para o PC
que executa o Prowlarr. Use o IP ou hostname do servidor.

No Prowlarr, configure seus **indexadores previamente autorizados** na seção
**Indexers**. A relação pessoal de fontes não pertence ao GitHub público.

Em **Settings > General**, consulte sua API key. Guarde-a somente no Kodi.
Quando acesso remoto for necessário, use HTTPS, acesso restrito à rede
ou encaminhamento seguro. Não exponha a API diretamente à Internet aberta.

## 2. Tag de idioma

Crie uma tag chamada `portugues` na seção de tags do Prowlarr e aplique-a
aos indexadores escolhidos. O nome da tag não é um parâmetro diretamente
aceito por `GET /api/v1/search`: o cliente precisa ler os IDs de tags
através de `GET /api/v1/tag`, identificar os indexadores que carregam
aquele ID através de `GET /api/v1/indexer`, e fornecer seus
`indexerIds` numéricos na busca.

Essa filtragem seleciona indexadores, **não comprova que o áudio do
arquivo está em português**. Tags nos nomes dos lançamentos são apenas
indícios; a verificação final depende dos metadados e faixas de áudio.

## 3. Debrid

Os provedores debrid possuem contas e APIs independentes.

* Real-Debrid: https://api.real-debrid.com/
* TorBox: https://api-docs.torbox.app/

Obtenha seu token pela área de conta do provedor, configure-o no Kodi
e evite colá-lo em arquivos do projeto, relatórios de erro ou capturas
de tela. Os serviços podem exigir assinatura e limites de uso.

**Nota de implementação:** no TorBox, uma resposta de `mylist` não fornece
necessariamente uma URL direta de vídeo. O endpoint apropriado para obter
o link de um arquivo específico é `GET /v1/api/torrents/requestdl` com
`torrent_id` e `file_id`. O campo de status também não tem apenas a
opção `ready`; existem estados como `cached`, `completed` e
`downloading` e o arquivo pode não estar pronto. Consulte a documentação
antes de desenvolver o resolver.

## 4. Configurações no Kodi

Abra **Add-ons > My add-ons > Video add-ons > Felipe Vídeos > Configure**.

* Prowlarr URL: endereço acessível pela TV Box
* Prowlarr API Key: chave pessoal; não deve constar no GitHub
* Tag de idioma: `portugues`
* Qualidade mínima: `1080p` por padrão
* Seeders mínimos: `3` por padrão
* Provedor debrid e token: de acordo com sua conta

O campo de senha é mascarado na interface, **mas o Kodi não garante
armazenamento criptografado** do conteúdo da configuração.

## 5. Diagnóstico de rede

No PC ou servidor de sua rede, teste a API diretamente sem incluir a
chave na linha de comando compartilhada ou em arquivos públicos:

```bash
curl --get "http://IP_DO_SERVIDOR:9696/api/v1/search" \
  -H "X-Api-Key: SEU_TOKEN_LOCAL" \
  --data-urlencode "query=Big Buck Bunny" \
  --data-urlencode "type=movie" \
  --data-urlencode "limit=5"
```

Use o token real apenas na sua máquina. HTTP 401 indica autenticação
incorreta, erros de conexão podem indicar firewall, endereço IP errado,
protocolo HTTPS incorreto ou Prowlarr fora de serviço.

## 6. Fontes e proxies

A configuração de indexadores, inclusive tags e eventuais proxies,
é feita no Prowlarr. Para serviços com proteção anti-bot, verifique
as condições de acesso e orientações do provedor antes de usar qualquer
mecanismo de proxy. Não configure nem publique credenciais de proxies
ou de indexadores neste repositório.

## 7. Integração de catálogo (1.3.1)

Na ficha de um filme comercial do Cinemeta, depois de configurar Prowlarr e
seu token, aparece **Reproduzir automaticamente (PT-BR)**. Essa opção
executa a consulta, classifica os resultados, tenta até cinco candidatos
e envia ao Kodi uma URL HTTPS se um serviço debrid a resolver.

O código **não cadastra nem habilita indexadores automaticamente**: eles
precisam ser configurados no Prowlarr. O identificador IMDb identifica o
filme no catálogo, mas não confirma que alguma cópia esteja disponível.
O reconhecimento do idioma é heurístico pelo nome da release.

A integração foi verificada por análise estática e testes do repositório,
mas ainda depende de testes reais com contas configuradas. A etapa de
polling pode durar até 60 segundos se o serviço debrid não completar.

## 8. Exemplo de mapping.json

O arquivo real `src/plugin.video.flyghtxmz/resources/data/mapping.json`
começa como `{}`, que é JSON válido. Como **JSON não aceita comentários**,
o exemplo fica aqui, sem entrar automaticamente na distribuição:

```json
{
  "tt1254207": {
    "sources": [
      {
        "title": "Big Buck Bunny (exemplo) 1080p PT-BR",
        "quality": "1080p",
        "seeders": 3,
        "magnet": "magnet:?xt=urn:btih:SUBSTITUIR_POR_HASH_REAL"
      }
    ]
  }
}
```

O título, idioma e magnet são **ilustrativos**, não são uma release
verificada. Um magnet verdadeiro deve ser fornecido pelo responsável
pela distribuição autorizada. Deixe o campo de URL do Prowlarr vazio
para ativar o fallback pelo arquivo local.

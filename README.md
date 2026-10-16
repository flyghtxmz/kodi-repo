# Felipe Addons — Kodi

Repositório independente de addons Kodi 19+ (Python 3).

O instalador `repository.flyghtxmz-1.0.0.zip` permite instalar o repositório **Felipe Addons** pelo Kodi, após habilitar o GitHub Pages em **Settings > Pages**, publicação da branch `main` na pasta `/ (root)`.

**Endereço no Kodi (Add Source):** https://flyghtxmz.github.io/kodi-repo/

Depois em **Add-ons > Install from zip file**, instale o repositório e em **Install from repository** escolha o addon **Felipe Vídeos**.

O addon Felipe Vídeos fornece um vídeo demonstrativo e a opção de abrir uma URL própria. Use apenas conteúdos autorizados.

Para reconstruir os pacotes: `python tools/build_repo.py`. Testes: `python -m unittest discover -s tests -v`.

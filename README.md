# Tile Game

O cliente inicia e encerra um servidor local automaticamente. Para jogar, voce so
precisa executar o cliente e clicar em **Play**.

## Primeira execucao no Windows

Abra o PowerShell nesta pasta (`TCC`) e execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python Client\main.py
```

Nas proximas vezes, basta ativar o ambiente e abrir o cliente:

```powershell
.\.venv\Scripts\Activate.ps1
python Client\main.py
```

## Fluxo da partida

1. `Client/main.py` abre o menu.
2. Play chama `pedir_servidor_criar_partida()`.
3. O cliente executa `Server/main.py` em segundo plano.
4. O cliente se conecta a `ws://127.0.0.1:8765/ws`.
5. Ao receber o identificador do jogador e o mapa, a partida e aberta.
6. Fechar o cliente tambem encerra o servidor criado por ele.

Se o servidor nao iniciar, os detalhes ficam em `server.log`.

## Controles

- `W`, `A`, `S`, `D`: mover a camera.
- Roda do mouse: zoom.
- Clique em um tile: abrir o menu de construcao.
- `F11`: alternar tela cheia.

Para testar apenas o servidor, opcionalmente:

```powershell
python Server\main.py
```

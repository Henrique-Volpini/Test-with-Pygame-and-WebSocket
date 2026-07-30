# Tile Game

Jogo multiplayer em Python e Pygame. Um jogador hospeda a partida no próprio computador e os outros se conectam pela mesma rede local ou por uma rede virtual, como Hamachi ou Radmin VPN.

## Primeira execução no Windows

Abra o PowerShell na pasta do projeto e execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python Client\main.py
```

Nas próximas execuções:

```powershell
.\.venv\Scripts\Activate.ps1
python Client\main.py
```

## Hospedar uma partida

1. Clique em **Hostear**.
2. Digite no campo o tamanho do mundo, entre `1` e `200`. O valor é usado na largura e na altura; por exemplo, `50` gera um mundo `50 × 50`.
3. Clique em **Iniciar**.
4. O terminal mostrará o tamanho enviado e o código da partida.
5. Compartilhe o código com os outros jogadores e mantenha o cliente aberto.

O cliente inicia `Server/main.py` automaticamente. Mundos grandes demoram mais para serem gerados; um mundo `200 × 200` pode levar vários segundos antes de a partida abrir.

## Conectar a uma partida

1. Esteja na mesma rede local ou rede virtual do host.
2. Clique em **Conectar**.
3. Digite o código no campo dentro do jogo.
4. Pressione `Enter` para conectar ou `Esc` para voltar ao menu.

O código representa o endereço IPv4 do host. Ele funciona pela rede local e prioriza endereços do Hamachi (`25.x.x.x`) e Radmin VPN (`26.x.x.x`). Ele não permite conexão direta pela internet sem uma LAN virtual ou configuração de rede equivalente.


## Solução de problemas

- Os detalhes da inicialização do servidor ficam em `server.log`.
- Se aparecer que a porta `8765` já está sendo usada, feche qualquer cliente ou servidor antigo do jogo antes de tentar novamente.
- Se o código aparecer, mas o mundo não abrir imediatamente, aguarde a geração do mapa, especialmente para tamanhos próximos de `200`.
- Confirme que os dois computadores aparecem online na mesma rede Hamachi ou Radmin VPN.
- Confirme que o Firewall do Windows permitiu o Python na rede utilizada.


## Controles

- `W`, `A`, `S`, `D`: mover a câmera.
- Roda do mouse: controlar o zoom.
- Clique em um tile: selecionar o tile ou abrir o menu de construção.
- `F11`: alternar a tela cheia.

## Executar apenas o servidor

O servidor pode ser iniciado separadamente para testes:

```powershell
python Server\main.py
```

Sem um tamanho informado pelo cliente, o servidor utiliza o tamanho padrão `120 × 90`.

# Tile Game

Jogo multiplayer em Python com interface HTML, CSS e JavaScript exibida pelo pywebview. Um jogador hospeda a partida no próprio computador e os outros se conectam pela mesma rede local ou por uma rede virtual, como Hamachi ou Radmin VPN.

## Primeira execução no Windows

Abra o PowerShell na pasta do projeto e execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python Client\main.py
```

No Windows, a interface usa o Microsoft Edge WebView2 Runtime. Se a janela não abrir, instale ou repare o runtime antes de tentar novamente.

Nas próximas execuções:

```powershell
.\.venv\Scripts\Activate.ps1
python Client\main.py
```

## Estrutura do frontend

O `Client/index.html` é apenas o ponto de entrada da interface. Cada parte do jogo mantém seu próprio HTML, CSS e JavaScript:

- `Client/ui/web/menu/`: menu principal, host e conexão.
- `Client/ui/web/lobby/`: prévia do mundo, seed, configurações e jogadores da sala.
- `Client/ui/web/game/`: canvas, HUD, seleção e construção.
- `Client/ui/web/settings/`: painel de exibição, saída e controles futuros de áudio.
- `Client/ui/web/shared/`: ponte com o pywebview e utilitários compartilhados.
- `Client/ui/web/app.js`: carrega os fragmentos e coordena a transição entre menu, sala e partida.

## Hospedar uma partida

1. Clique em **Hostear**.
2. Aguarde a abertura da sala e a geração da prévia do mundo.
3. Compartilhe o código exibido no topo com os outros jogadores.
4. Se quiser, edite a seed, o tamanho (`1` a `200`) ou ajuste **Terra firme**, **Montanhas** e **Florestas**. A composição estimada mostra quanto haverá de água, planície, floresta e montanha.
5. Clique em **Aplicar alterações** para manter a seed ou em **Criar outro mapa** para sortear uma nova seed com as mesmas preferências.
6. Confira os jogadores online e clique em **Iniciar partida** quando todos estiverem
   prontos. O botão fica bloqueado enquanto houver alterações de mapa ainda não
   aplicadas.

Somente o anfitrião pode alterar o mapa ou iniciar a partida. A prévia exibida no lobby é o mesmo mundo usado no jogo. A mesma seed, tamanho e parâmetros reproduz o mesmo mapa.

O cliente inicia `Server/main.py` automaticamente. Mundos grandes demoram mais para serem gerados; um mundo `200 × 200` pode levar vários segundos antes de a partida abrir.

## Conectar a uma partida

1. Esteja na mesma rede local ou rede virtual do host.
2. Clique em **Conectar**.
3. Digite o código no campo dentro do jogo.
4. Pressione `Enter` ou clique em **Entrar na sala**.
5. Confira a prévia, a seed e os jogadores enquanto aguarda o anfitrião iniciar.

O código de nove caracteres muda sempre que uma nova sala é criada. Ele carrega o endereço IPv4 e uma identificação aleatória que o servidor valida, funcionando pela rede local e priorizando endereços do Hamachi (`25.x.x.x`) e Radmin VPN (`26.x.x.x`). Ele não permite conexão direta pela internet sem uma LAN virtual ou configuração de rede equivalente.


## Solução de problemas

- Os detalhes da inicialização do servidor ficam em `server.log`.
- Se a janela não abrir, confirme que o Microsoft Edge WebView2 Runtime está instalado.
- Se aparecer que a porta `8765` já está sendo usada, feche qualquer cliente ou servidor antigo do jogo antes de tentar novamente.
- Se o código aparecer, mas o mundo não abrir imediatamente, aguarde a geração do mapa, especialmente para tamanhos próximos de `200`.
- Confirme que os dois computadores aparecem online na mesma rede Hamachi ou Radmin VPN.
- Confirme que o Firewall do Windows permitiu o Python na rede utilizada.


## Controles

- `W`, `A`, `S`, `D`: mover a câmera.
- Roda do mouse: controlar o zoom.
- Clique em um tile: selecionar o tile ou abrir o menu de construção.
- `Esc`: abrir ou fechar as configurações no menu, na sala e durante a partida.
- `F11`: alternar a tela cheia.

As **Configurações** também podem ser abertas pelo botão do menu principal. O
painel permite escolher uma resolução predefinida, alternar entre janela e tela
cheia ou sair do jogo. A seção de áudio já está reservada para uma implementação
futura, mas permanece desativada enquanto o projeto não possui som.

## Executar apenas o servidor

O servidor pode ser iniciado separadamente para testes:

```powershell
python Server\main.py
```

Sem um tamanho informado pelo cliente, o servidor utiliza o tamanho padrão `120 × 90`.

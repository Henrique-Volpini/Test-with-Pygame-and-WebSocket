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

Somente o anfitrião pode alterar o mapa ou iniciar a partida. A prévia exibida no lobby é o mundo-base usado no jogo. Ao iniciar, o servidor procura regiões naturais de grama `5 × 5` próximas de lados opostos da borda e converte somente o centro `3 × 3` de cada região na cidade principal gratuita do jogador; o restante do terreno não é alterado. A câmera abre na cidade do próprio jogador. A mesma seed, tamanho e parâmetros reproduz o mesmo mundo-base.

O mapa precisa ter regiões naturais de grama suficientes para separar todas as cidades. Se não houver espaço para a quantidade de jogadores, a partida permanece no lobby e o servidor pede outro mapa ou menos jogadores.

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
- Clique em uma Guarda, Dock ou Centro da Cidade: abrir o menu próprio da
  construção sobre o painel inferior.
- Clique em outro tile: selecionar o tile ou abrir o menu de construção.
- Aba **Construções**: abrir ou recolher o painel pela borda inferior.
- `Esc`: abrir ou fechar as configurações no menu, na sala e durante a partida.
- `F11`: alternar a tela cheia.

Durante a partida, a barra superior mostra o tempo restante para o próximo
ciclo de `10` segundos. Produção, movimentação e demais sistemas de turno devem
usar esse mesmo tick autoritativo do servidor.

## Tropas e combate

- A **Guarda** custa `120 ouro / 180 madeira / 80 comida` e só pode substituir
  um tile de Cidade do próprio jogador.
- O **Dock** custa `100 ouro / 220 madeira / 40 comida` e só pode substituir
  água costeira livre, ortogonalmente ao lado de terra. Um Dock não prolonga a
  costa para permitir construções em cadeia no oceano.
- No menu próprio da **Guarda**, uma tropa terrestre pode ser encomendada por
  `75` de ouro. A ordem espera o ciclo global atual terminar e então leva `2`
  ciclos completos (`20` segundos) para ficar pronta, até o limite de `24`
  tropas terrestres por jogador.
- No menu próprio do **Dock**, um barco pode ser encomendado por `120` de ouro.
  Depois da mesma espera pelo próximo ciclo global, ele leva `3` ciclos
  completos (`30` segundos) para ficar pronto, até o limite de `12` barcos por
  jogador. O próprio Dock continua sendo uma posição aquática.
- Cada Guarda ou Dock mantém uma fila serial de até `5` ordens. O ouro é
  descontado ao confirmar a ordem; unidades prontas aguardam sem novo custo se
  não houver um tile livre para surgirem. O Centro da Cidade mostra o resumo e
  os limites do exército, mas não recruta.
- Clique em uma tropa própria para selecioná-la e use o botão direito em um
  destino. Tropas terrestres não atravessam água ou montanhas; barcos navegam
  somente por água e docks.
- Tropas sem ordem detectam inimigos próximos. Uma ordem explícita sempre tem
  prioridade, e movimento, ataque, dano e morte só são resolvidos no tick.
- Ao chegar um novo tick, o cliente interpola o caminho percorrido e desenha
  poeira para tropas terrestres ou esteira para barcos. Para isso, compara os
  IDs e as posições dos dois snapshots autoritativos consecutivos; a posição
  final continua sendo sempre a enviada pelo servidor.
- Não é possível construir no tile de uma tropa nem na faixa imediata ao redor
  de uma tropa inimiga. Criar água custa `40` de ouro, evitando que o terreno
  gratuito substitua o combate e aprisione exércitos instantaneamente.
- Tropas terrestres têm `12 HP`, movem `2` tiles, causam `4` de dano a alcance
  `1` e detectam alvos a `6` tiles. Barcos têm `22 HP`, movem `3` tiles, causam
  `6` de dano a alcance `2` e detectam alvos a `8` tiles. O dano é simultâneo,
  portanto duas unidades podem destruir uma à outra no mesmo ciclo.

O comando de rede de uma tropa usa este formato:

```json
{"tipo":"ordenar_tropa","unit_id":"troop-1","x":12,"y":8}
```

O recrutamento manual usa a coordenada da construção:

```json
{"tipo":"recrutar_tropa","x":8,"y":14}
```

Nos snapshots, cada item da fila informa `remaining_ticks`, `total_ticks` e
`waiting_for_start`. Enquanto `waiting_for_start` for `true`, a ordem está
aguardando o ciclo global atual terminar e ainda não consumiu nenhum tick de
produção.

Cada snapshot contém `player_id` e uma lista `troops`. Uma unidade é enviada
como `{id, owner, is_mine, kind, x, y, hp, max_hp, target, status}`; `kind` é
`land` ou `boat`, e `target` é uma coordenada `[x, y]` ou `null`.

As **Configurações** também podem ser abertas pelo botão do menu principal. O
painel permite escolher uma resolução predefinida, alternar entre janela e tela
cheia ou sair do jogo. Há formatos `4:3` e panorâmicos, incluindo
`1366 × 768`, `1536 × 864`, `1600 × 900` e `1920 × 1080`; a interface e o
canvas aproveitam a largura disponível sem distorcer o jogo. A seção de áudio já está reservada para uma implementação
futura, mas permanece desativada enquanto o projeto não possui som.

## Executar apenas o servidor

O servidor pode ser iniciado separadamente para testes:

```powershell
python Server\main.py
```

Sem um tamanho informado pelo cliente, o servidor utiliza o tamanho padrão `120 × 90`.

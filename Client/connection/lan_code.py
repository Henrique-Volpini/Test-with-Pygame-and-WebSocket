import ipaddress
import secrets
import socket


ALFABETO = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PORTA_SERVIDOR = 8765
MAX_CODE_LENGTH = 9
IPV4_SPACE = 1 << 32
CODE_SPACE = 36**MAX_CODE_LENGTH

_last_room_code = None


def _int_para_base36(value):
    codigo = ""
    while value:
        value, resto = divmod(value, 36)
        codigo = ALFABETO[resto] + codigo
    return codigo or "0"


def ip_para_codigo(ip):
    valor = int(ipaddress.IPv4Address(ip))
    return _int_para_base36(valor)


def criar_codigo_sala(ip):
    """Cria um alias variavel que ainda carrega o IPv4 para conexao direta."""
    global _last_room_code

    ip_value = int(ipaddress.IPv4Address(ip))
    max_salt = (CODE_SPACE - 1 - ip_value) // IPV4_SPACE
    if max_salt < 1:
        raise RuntimeError("Nao ha espaco para criar um codigo de sala.")

    codigo = None
    salt = 1
    for _ in range(4):
        salt = secrets.randbelow(max_salt) + 1
        packed = ip_value + salt * IPV4_SPACE
        codigo = _int_para_base36(packed).rjust(MAX_CODE_LENGTH, "0")
        if codigo != _last_room_code:
            break
    if codigo == _last_room_code:
        salt = salt % max_salt + 1
        packed = ip_value + salt * IPV4_SPACE
        codigo = _int_para_base36(packed).rjust(MAX_CODE_LENGTH, "0")

    _last_room_code = codigo
    return codigo


def codigo_para_ip(codigo):
    if not isinstance(codigo, str) or not codigo.isascii():
        raise ValueError("Codigo invalido.")
    codigo = codigo.strip().upper()
    if (
        not codigo
        or len(codigo) > MAX_CODE_LENGTH
        or any(character not in ALFABETO for character in codigo)
    ):
        raise ValueError("Codigo invalido.")
    try:
        packed = int(codigo, 36)
        return str(ipaddress.IPv4Address(packed % IPV4_SPACE))
    except (ipaddress.AddressValueError, ValueError):
        raise ValueError("Codigo invalido.")


def criar_url_websocket(ip):
    return f"ws://{ip}:{PORTA_SERVIDOR}/ws"


def obter_ip_preferido():
    try:
        enderecos = list({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
    except socket.gaierror:
        enderecos = []

    for prefixo in ("25.", "26."):
        for endereco in enderecos:
            if endereco.startswith(prefixo):
                return endereco

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        for endereco in enderecos:
            if not endereco.startswith(("127.", "169.254.")):
                return endereco
    finally:
        sock.close()

    raise RuntimeError("Nenhum IP de rede foi encontrado.")

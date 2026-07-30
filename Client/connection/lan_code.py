import ipaddress
import socket


ALFABETO = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PORTA_SERVIDOR = 8765


def ip_para_codigo(ip):
    valor = int(ipaddress.IPv4Address(ip))
    codigo = ""
    while valor:
        valor, resto = divmod(valor, 36)
        codigo = ALFABETO[resto] + codigo
    return codigo or "0"


def codigo_para_ip(codigo):
    codigo = codigo.strip().upper()
    if not codigo or len(codigo) > 7:
        raise ValueError("Codigo invalido.")
    try:
        return str(ipaddress.IPv4Address(int(codigo, 36)))
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

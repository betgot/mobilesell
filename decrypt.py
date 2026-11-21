import sys
import re
import base64
import hashlib
import argparse

HTML_PATH = "index.html"
OUT_PATH = "decrypt.html"
DEFAULT_HOST = "mobilesell.ru"
HOST_CANDIDATES = ("", DEFAULT_HOST, "www." + DEFAULT_HOST)

_WM_PARTS = ("by", " ", "t.", "me", "/", "rd", "def")


def _wm():
    return "".join(_WM_PARTS)


def print_banner():
    banner = r"""
    ██████╗ ███████╗ ██████╗██████╗ ██╗   ██╗██████╗ ████████╗
    ██╔══██╗██╔════╝██╔════╝██╔══██╗╚██╗ ██╔╝██╔══██╗╚══██╔══╝
    ██║  ██║█████╗  ██║     ██████╔╝ ╚████╔╝ ██████╔╝   ██║
    ██║  ██║██╔══╝  ██║     ██╔══██╗  ╚██╔╝  ██╔═══╝    ██║
    ██████╔╝███████╗╚██████╗██║  ██║   ██║   ██║        ██║
    ╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚═╝        ╚═╝
    """
    lines = banner.strip("\n").split("\n")
    start, end = (255, 165, 0), (200, 0, 0)
    n = len(lines)
    for i, line in enumerate(lines):
        t = i / max(n - 1, 1)
        r = int(start[0] + (end[0] - start[0]) * t)
        g = int(start[1] + (end[1] - start[1]) * t)
        b = int(start[2] + (end[2] - start[2]) * t)
        print(f"\033[38;2;{r};{g};{b}m{line}\033[0m")
    print()


#by @rddef
def parse_arr(html, name):
    m = re.search(rf"\b{name}\s*=\s*\[([^\]]*)\]", html)
    if not m:
        sys.exit(f"Ошибка: массив {name} не найден")
    return [int(x) for x in re.split(r"[,\s]+", m.group(1).strip()) if x]


def sha256(*parts):
    return hashlib.sha256(b"".join(parts)).digest()


def make_keys(S, host):
    D = host.lower().removeprefix("www.").encode()
    return sha256(bytes(S), D, b"\x01"), sha256(bytes(S), D, b"\x02")


def calc_mac(KM, n, ct):
    ip = bytes(x ^ 0x36 for x in KM + b"\x00" * 32)
    op = bytes(x ^ 0x5c for x in KM + b"\x00" * 32)
    return sha256(op, sha256(ip, n, ct))


def decrypt(KE, n, ct):
    out = bytearray(len(ct))
    for i in range(0, len(ct), 32):
        ks = sha256(KE, n, (i >> 5).to_bytes(4, "big"))
        block = ct[i:i + 32]
        out[i:i + len(block)] = bytes(a ^ b for a, b in zip(block, ks))
    return out


def zw_encode(text):
    bits = "".join(f"{b:08b}" for b in text.encode("utf-8"))
    return "".join("\u200c" if bit == "0" else "\u200d" for bit in bits)


def zw_span():
    return f'<span style="display:none;font-size:0">{zw_encode(_wm())}</span>'


def embed_watermarks(html):
    zw = zw_span()
    pre = "\u200b" * 3
    w = _wm()

    html = pre + html

    if "</head>" in html:
        html = html.replace("</head>", f"<!-- {w} -->\n</head>", 1)

    tag_comment = f"<!-- {w} -->"
    for tag in ("<div", "<section", "<script", "<style", "<main", "<header",
                "<footer", "<nav", "<article", "<aside", "<table", "<form"):
        html = html.replace(tag, f"{tag_comment}{tag}")

    for tag in ("</div>", "</section>", "</script>", "</style>", "</main>",
                "</header>", "</footer>", "</nav>", "</article>", "</aside>",
                "</table>", "</form>", "</body>", "</html>"):
        html = html.replace(tag, f"{zw}{tag}")

    html = re.sub(r"(<script\b[^>]*>)", rf"\1\n/* {w} */\n", html, flags=re.I)
    html = html + f"\n<!-- {w} -->\n"
    return html


def head_inner(html):
    m = re.search(r"<head\b[^>]*>(.*?)</head>", html, re.S | re.I)
    inner = m.group(1) if m else ""
    inner = re.sub(
        r'<script\b[^>]*id="pk-data"[^>]*>.*?</script>',
        "", inner, flags=re.S | re.I,
    )
    return inner


def body_attrs(html):
    m = re.search(r"<body\b([^>]*)>", html, re.I)
    return m.group(1) if m else ""


def title_of(html):
    m = re.search(r"<title\b[^>]*>(.*?)</title>", html, re.S | re.I)
    return m.group(1).strip() if m else "game"


def build_html(title, head, body, payload):
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
{head}
</head>
<body{body}>
<script>
{payload}
</script>
</body>
</html>
"""


def find_host(hosts, S, n, ct, mac):
    for host in hosts:
        KE, KM = make_keys(S, host)
        if calc_mac(KM, n, ct) == mac:
            return host, KE
    return None


def main():
    print_banner()

    ap = argparse.ArgumentParser(description="Расшифровка pk-data из index.html")
    ap.add_argument("--html", default=HTML_PATH, help="входной HTML")
    ap.add_argument("--out", default=OUT_PATH, help="выходной HTML")
    ap.add_argument("--host", default="auto", help="hostname для ключа")
    args = ap.parse_args()

    html = open(args.html, encoding="utf-8").read()

    m = re.search(r'id="pk-data"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        sys.exit('Ошибка: тег id="pk-data" не найден')
    blob = base64.b64decode(m.group(1).strip())

    P, Q = parse_arr(html, "P"), parse_arr(html, "Q")
    if len(P) != 16 or len(Q) != 16:
        sys.exit("Ошибка: P и Q должны быть по 16 элементов")

    S = bytearray(32)
    for i in range(16):
        S[i] = P[i]
        S[31 - i] = (Q[i] + 165) & 0xFF

    n = blob[:16]
    ct = blob[16:-32]
    mac = blob[-32:]

    candidates = list(HOST_CANDIDATES) if args.host == "auto" else [args.host]

    seen, hosts = set(), []
    for h in candidates:
        key = h.lower().removeprefix("www.")
        if key not in seen:
            seen.add(key)
            hosts.append(h)

    chosen = find_host(hosts, S, n, ct, mac)

    if chosen is None:
        out = decrypt(make_keys(S, hosts[0])[0], n, ct)
        open("game.bin", "wb").write(out)
        sys.exit("Ошибка: MAC не сошёлся (сырые байты в game.bin)")

    KE = chosen[1]
    out = decrypt(KE, n, ct)

    try:
        payload = out.decode("utf-8")
    except UnicodeDecodeError:
        open("game.bin", "wb").write(out)
        sys.exit("Ошибка: результат не UTF-8 (сырые байты в game.bin)")

    final_html = build_html(
        title_of(html),
        head_inner(html),
        body_attrs(html),
        payload,
    )
    final_html = embed_watermarks(final_html)

    open(args.out, "w", encoding="utf-8").write(final_html)
    print(f"Готово: {args.out}")


if __name__ == "__main__":
    main()
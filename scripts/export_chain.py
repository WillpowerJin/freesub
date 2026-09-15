#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成手机可直接订阅的前置链式配置。

Clash Meta (iOS / Android): clash-tw-chain.yaml
v2rayNG (Android 自定义配置): output/v2rayng-chain.json

链路: 本机 → 前置(可直连) → 家宽/台湾节点 → 目标
Hysteria2 / TUIC / AnyTLS 不入链 (UDP 过 TCP 前置不可用)。
"""

from __future__ import annotations

import copy
import json
import os
import time
from typing import Any

import requests
import yaml

WORKDIR = os.path.dirname(os.path.abspath(__file__))
BASEDIR = os.path.dirname(WORKDIR)
OUTPUT_DIR = os.path.join(BASEDIR, "output")

FRONT_SUB_URL = (
    "https://yx.jinjin909.ggff.net/"
    "633a113e-af18-4142-859b-e2ebae6d726e/sub?target=clash"
)

FRONT_FALLBACKS: list[dict[str, Any]] = [
    {
        "name": "兜底|cm优选1",
        "type": "vless",
        "server": "youxuan1.cf.090227.xyz",
        "port": 443,
        "uuid": "633a113e-af18-4142-859b-e2ebae6d726e",
        "udp": True,
        "tls": True,
        "alpn": ["h3"],
        "skip-cert-verify": False,
        "servername": "yx.jinjin909.ggff.net",
        "client-fingerprint": "chrome",
        "network": "ws",
        "ws-opts": {
            "path": "/?ed=2048",
            "headers": {"Host": "yx.jinjin909.ggff.net"},
        },
        "ip-version": "ipv4",
    },
    {
        "name": "兜底|visa中国",
        "type": "vless",
        "server": "www.visa.cn",
        "port": 443,
        "uuid": "633a113e-af18-4142-859b-e2ebae6d726e",
        "udp": True,
        "tls": True,
        "alpn": ["h3"],
        "skip-cert-verify": False,
        "servername": "yx.jinjin909.ggff.net",
        "client-fingerprint": "chrome",
        "network": "ws",
        "ws-opts": {
            "path": "/?ed=2048",
            "headers": {"Host": "yx.jinjin909.ggff.net"},
        },
        "ip-version": "ipv4",
    },
]

SKIP_TYPES = {"hysteria2", "hysteria", "tuic", "anytls", "wireguard", "snell"}
DIALER_GROUP = "前置选择"
MAX_V2RAYNG_CHAIN = 20
CHAIN_README_MARKER = "## 📱 手机链式订阅（前置代理，可直接用）"


def repo_name() -> str:
    return os.environ.get("GITHUB_REPOSITORY", "WillpowerJin/freesub").strip() or "WillpowerJin/freesub"


def load_clash_proxies(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    proxies = data.get("proxies") or []
    return [p for p in proxies if isinstance(p, dict) and p.get("name") and p.get("type")]


def is_chainable(proxy: dict[str, Any]) -> bool:
    return str(proxy.get("type", "")).lower() not in SKIP_TYPES


def uniquify(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_name: set[str] = set()
    seen_ep: set[str] = set()
    out: list[dict[str, Any]] = []
    for p in proxies:
        name = p["name"]
        ep = "|".join([
            str(p.get("type") or ""),
            str(p.get("server") or ""),
            str(p.get("port") or ""),
            str(p.get("uuid") or p.get("password") or ""),
        ])
        if name in seen_name or ep in seen_ep:
            continue
        seen_name.add(name)
        seen_ep.add(ep)
        out.append(p)
    return out


def with_dialer(proxy: dict[str, Any]) -> dict[str, Any]:
    p = copy.deepcopy(proxy)
    p["udp"] = True
    p["ip-version"] = "ipv4"
    p["dialer-proxy"] = DIALER_GROUP
    return p


def cdn_url(rel: str, cache_bust: int) -> str:
    return f"https://cdn.jsdelivr.net/gh/{repo_name()}@main/{rel}?v={cache_bust}"


def raw_url(rel: str) -> str:
    return f"https://raw.githubusercontent.com/{repo_name()}/main/{rel}"


def build_clash_chain(
    baked: list[dict[str, Any]],
    res_names: list[str],
    tw_names: list[str],
    cache_bust: int,
) -> dict[str, Any]:
    proxies = copy.deepcopy(FRONT_FALLBACKS) + baked
    groups: list[dict[str, Any]] = [
        {
            "name": DIALER_GROUP,
            "type": "select",
            "proxies": ["前置自动", "兜底|cm优选1", "兜底|visa中国", "DIRECT"],
            "use": ["前置订阅"],
            "exclude-filter": "Trojan",
        },
        {
            "name": "前置自动",
            "type": "url-test",
            "url": "https://www.gstatic.com/generate_204",
            "interval": 120,
            "tolerance": 50,
            "lazy": False,
            "proxies": ["兜底|cm优选1", "兜底|visa中国"],
            "use": ["前置订阅"],
            "exclude-filter": "Trojan",
        },
    ]

    select_proxies = ["家宽自动", "台湾自动", "全部自动", "前置自动"]
    if res_names:
        groups.append({
            "name": "家宽自动",
            "type": "url-test",
            "url": "https://www.gstatic.com/generate_204",
            "interval": 120,
            "tolerance": 50,
            "lazy": False,
            "proxies": res_names,
        })
        select_proxies.extend(res_names)
    else:
        select_proxies.remove("家宽自动")

    if tw_names:
        groups.append({
            "name": "台湾自动",
            "type": "url-test",
            "url": "https://www.gstatic.com/generate_204",
            "interval": 120,
            "tolerance": 50,
            "lazy": False,
            "proxies": tw_names,
        })
        select_proxies.extend(n for n in tw_names if n not in res_names)
    else:
        select_proxies.remove("台湾自动")

    groups.append({
        "name": "全部自动",
        "type": "url-test",
        "url": "https://www.gstatic.com/generate_204",
        "interval": 300,
        "tolerance": 80,
        "lazy": True,
        "proxies": ["前置自动"],
        "use": ["全部套链"],
        "exclude-filter": "(?i)hysteria|hy2|tuic|anytls",
    })
    groups.append({
        "name": "PROXIES",
        "type": "select",
        "proxies": select_proxies,
    })

    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "tcp-concurrent": True,
        "unified-delay": True,
        "find-process-mode": "off",
        "profile": {"store-selected": True, "store-fake-ip": True},
        "dns": {
            "enable": True,
            "ipv6": False,
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "fake-ip-filter": [
                "*.lan",
                "*.local",
                "+.qq.com",
                "+.weixin.qq.com",
                "+.wechat.com",
                "+.qpic.cn",
                "+.qlogo.cn",
                "+.tenpay.com",
                "localhost.ptlogin2.qq.com",
            ],
            "default-nameserver": ["223.5.5.5", "8.8.8.8"],
            "nameserver": [
                "https://dns.alidns.com/dns-query",
                "https://doh.pub/dns-query",
            ],
            "proxy-server-nameserver": [
                "https://dns.alidns.com/dns-query",
                "tls://223.5.5.5",
            ],
        },
        "tun": {
            "enable": True,
            "stack": "mixed",
            "auto-route": True,
            "auto-detect-interface": True,
            "dns-hijack": ["any:53"],
        },
        "sniffer": {
            "enable": True,
            "parse-pure-ip": True,
            "override-destination": True,
            "sniff": {
                "HTTP": {"ports": [80, "8080-8880"], "override-destination": True},
                "TLS": {"ports": [443, 8443]},
            },
        },
        "proxies": proxies,
        "proxy-providers": {
            "前置订阅": {
                "type": "http",
                "url": FRONT_SUB_URL,
                "interval": 3600,
                "proxy": "DIRECT",
                "header": {"User-Agent": ["clash.meta"]},
                "override": {
                    "additional-prefix": "前置|",
                    "udp": True,
                    "ip-version": "ipv4",
                },
                "health-check": {
                    "enable": True,
                    "url": "https://www.gstatic.com/generate_204",
                    "interval": 300,
                },
            },
            "全部套链": {
                "type": "http",
                "url": cdn_url("output/clash.yaml", cache_bust),
                "interval": 21600,
                "proxy": "DIRECT",
                "header": {"User-Agent": ["clash.meta"]},
                "override": {
                    "additional-prefix": "套链|",
                    "dialer-proxy": DIALER_GROUP,
                    "udp": True,
                    "ip-version": "ipv4",
                },
                "exclude-type": "hysteria2|hysteria|tuic|anytls|wireguard",
                "exclude-filter": "(?i)hysteria|hy2|tuic|anytls",
                "health-check": {
                    "enable": True,
                    "lazy": True,
                    "url": "https://www.gstatic.com/generate_204",
                    "interval": 600,
                },
            },
        },
        "proxy-groups": groups,
        "rules": [
            "DOMAIN-SUFFIX,ggff.net,DIRECT",
            "DOMAIN-SUFFIX,090227.xyz,DIRECT",
            "DOMAIN-SUFFIX,jsdelivr.net,DIRECT",
            "DOMAIN-SUFFIX,githubusercontent.com,DIRECT",
            "DOMAIN,www.visa.cn,DIRECT",
            "DOMAIN,saas.sin.fan,DIRECT",
            "DOMAIN,time.is,DIRECT",
            "DOMAIN,icook.hk,DIRECT",
            "DOMAIN,icook.tw,DIRECT",
            "PROCESS-NAME,WeChat,DIRECT",
            "PROCESS-NAME,微信,DIRECT",
            "PROCESS-NAME,com.tencent.xin,DIRECT",
            "DOMAIN-SUFFIX,weixin.qq.com,DIRECT",
            "DOMAIN-SUFFIX,wechat.com,DIRECT",
            "DOMAIN-SUFFIX,servicewechat.com,DIRECT",
            "DOMAIN-SUFFIX,qpic.cn,DIRECT",
            "DOMAIN-SUFFIX,qlogo.cn,DIRECT",
            "DOMAIN-SUFFIX,tenpay.com,DIRECT",
            "DOMAIN-KEYWORD,weixin,DIRECT",
            "GEOSITE,CN,DIRECT",
            "GEOIP,CN,DIRECT",
            "MATCH,PROXIES",
        ],
    }


def _stream_from_clash(p: dict[str, Any], dialer: str | None) -> dict[str, Any]:
    network = p.get("network") or "tcp"
    stream: dict[str, Any] = {"network": network}
    if p.get("reality-opts"):
        ro = p["reality-opts"] or {}
        stream["security"] = "reality"
        stream["realitySettings"] = {
            "serverName": p.get("servername") or p.get("sni") or p["server"],
            "fingerprint": p.get("client-fingerprint") or "chrome",
            "publicKey": ro.get("public-key") or "",
            "shortId": ro.get("short-id") or "",
            "spiderX": "",
        }
    elif p.get("tls") or p.get("type") == "trojan":
        stream["security"] = "tls"
        tls: dict[str, Any] = {
            "serverName": p.get("servername") or p.get("sni") or p["server"],
            "allowInsecure": bool(p.get("skip-cert-verify")),
        }
        if p.get("client-fingerprint"):
            tls["fingerprint"] = p["client-fingerprint"]
        alpn = p.get("alpn")
        if alpn:
            tls["alpn"] = alpn if isinstance(alpn, list) else [alpn]
        stream["tlsSettings"] = tls

    if network == "ws":
        wo = p.get("ws-opts") or {}
        stream["wsSettings"] = {
            "path": wo.get("path") or "/",
            "headers": wo.get("headers") or {},
        }
    elif network == "grpc":
        go = p.get("grpc-opts") or {}
        stream["grpcSettings"] = {"serviceName": go.get("grpc-service-name") or ""}
    elif network in ("h2", "http"):
        stream["network"] = "http"
        ho = p.get("h2-opts") or p.get("http-opts") or {}
        host = ho.get("host") or []
        if isinstance(host, str):
            host = [host]
        stream["httpSettings"] = {"path": ho.get("path") or "/", "host": host}
    elif network == "httpupgrade":
        ho = p.get("httpupgrade-opts") or {}
        host = (ho.get("headers") or {}).get("Host") or p["server"]
        stream["httpupgradeSettings"] = {"path": ho.get("path") or "/", "host": host}

    if dialer:
        stream.setdefault("sockopt", {})["dialerProxy"] = dialer
    return stream


def clash_to_xray(p: dict[str, Any], tag: str, dialer: str | None = None) -> dict[str, Any] | None:
    t = str(p.get("type", "")).lower()
    if t in SKIP_TYPES or t not in {"vless", "vmess", "ss", "trojan"}:
        return None
    server, port = p["server"], int(p["port"])
    stream = _stream_from_clash(p, dialer)

    if t == "vless":
        user: dict[str, Any] = {"id": p["uuid"], "encryption": "none"}
        if p.get("flow"):
            user["flow"] = p["flow"]
        return {
            "tag": tag,
            "protocol": "vless",
            "settings": {"vnext": [{"address": server, "port": port, "users": [user]}]},
            "streamSettings": stream,
        }
    if t == "vmess":
        return {
            "tag": tag,
            "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": server,
                    "port": port,
                    "users": [{
                        "id": p["uuid"],
                        "alterId": int(p.get("alterId") or 0),
                        "security": p.get("cipher") or "auto",
                    }],
                }]
            },
            "streamSettings": stream,
        }
    if t == "ss":
        outbound: dict[str, Any] = {
            "tag": tag,
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address": server,
                    "port": port,
                    "method": p.get("cipher") or "aes-128-gcm",
                    "password": p.get("password") or "",
                }]
            },
        }
        ss_stream: dict[str, Any] = {}
        if stream.get("network", "tcp") != "tcp" or stream.get("security"):
            ss_stream = dict(stream)
        if dialer:
            ss_stream.setdefault("sockopt", {})["dialerProxy"] = dialer
        if ss_stream:
            outbound["streamSettings"] = ss_stream
        return outbound
    if t == "trojan":
        return {
            "tag": tag,
            "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address": server,
                    "port": port,
                    "password": p.get("password") or "",
                }]
            },
            "streamSettings": stream,
        }
    return None


def build_v2rayng_chain(chain_proxies: list[dict[str, Any]]) -> dict[str, Any]:
    outbounds: list[dict[str, Any]] = []
    chain_tags: list[str] = []
    for i, p in enumerate(chain_proxies[:MAX_V2RAYNG_CHAIN], start=1):
        tag = f"n{i:02d}"
        ob = clash_to_xray(p, tag, dialer="front-cm")
        if not ob:
            continue
        outbounds.append(ob)
        chain_tags.append(tag)

    for p, tag in ((FRONT_FALLBACKS[0], "front-cm"), (FRONT_FALLBACKS[1], "front-visa")):
        ob = clash_to_xray(p, tag)
        if ob:
            outbounds.append(ob)

    outbounds.append({"tag": "direct", "protocol": "freedom", "settings": {}})
    outbounds.append({"tag": "block", "protocol": "blackhole", "settings": {}})

    rules: list[dict[str, Any]] = [
        {"type": "field", "outboundTag": "direct", "ip": ["geoip:private"]},
        {
            "type": "field",
            "outboundTag": "direct",
            "domain": [
                "geosite:cn",
                "domain:ggff.net",
                "domain:090227.xyz",
                "domain:visa.cn",
                "domain:jsdelivr.net",
            ],
        },
        {"type": "field", "outboundTag": "direct", "ip": ["geoip:cn"]},
    ]
    routing: dict[str, Any] = {"domainStrategy": "IPIfNonMatch", "rules": rules}
    observatory = None
    if chain_tags:
        routing["balancers"] = [{
            "tag": "chain",
            "selector": ["n"],
            "strategy": {"type": "leastPing"},
        }]
        rules.append({"type": "field", "network": "tcp,udp", "balancerTag": "chain"})
        observatory = {
            "subjectSelector": ["n"],
            "probeUrl": "https://www.gstatic.com/generate_204",
            "probeInterval": "1m",
            "enableConcurrency": True,
        }
    else:
        rules.append({"type": "field", "network": "tcp,udp", "outboundTag": "front-cm"})

    cfg: dict[str, Any] = {
        "remarks": "链式·家宽+台湾",
        "log": {"loglevel": "warning"},
        "dns": {
            "servers": [
                "https://dns.alidns.com/dns-query",
                "223.5.5.5",
                "8.8.8.8",
            ]
        },
        "inbounds": [
            {
                "tag": "socks",
                "listen": "127.0.0.1",
                "port": 10808,
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
            },
            {
                "tag": "http",
                "listen": "127.0.0.1",
                "port": 10809,
                "protocol": "http",
                "settings": {},
            },
        ],
        "outbounds": outbounds,
        "routing": routing,
    }
    if observatory:
        cfg["observatory"] = observatory
    return cfg


def patch_readme(res_count: int, tw_count: int, cache_bust: int) -> None:
    path = os.path.join(BASEDIR, "README.md")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    section = f"""{CHAIN_README_MARKER}

> 大陆直连免费节点通常不可用，这份配置会走 **本机 → 前置订阅 → 家宽/节点 → 目标**。
> iOS / Android 的 **Clash Meta** 订 YAML；Android **v2rayNG** 用自定义 JSON（内核须是 Xray）。
> 原版 Clash、Shadowrocket、Quantumult X 不能用链式配置。

| 客户端 | 用法 | 免翻 CDN | 官方 Raw |
| :--- | :--- | :--- | :--- |
| **Clash Meta**（iOS / Android） | 配置 → 添加 → **URL 订阅**（整份配置，不是代理集） | [CDN]({cdn_url("clash-tw-chain.yaml", cache_bust)}) | [Raw]({raw_url("clash-tw-chain.yaml")}) |
| **v2rayNG**（Android） | 右上角 `+` → **手动输入[自定义配置]** → 粘贴 JSON | [CDN]({cdn_url("output/v2rayng-chain.json", cache_bust)}) | [Raw]({raw_url("output/v2rayng-chain.json")}) |

**Clash Meta 导入后：** 打开 VPN / TUN → 代理组 **前置选择 = 前置自动**（不要选 DIRECT）→ **PROXIES = 家宽自动**（或 台湾自动 / 全部自动）。本轮写入 {res_count} 个可套链家宽、{tw_count} 个可套链台湾节点；Hysteria2 不会进链式。

**v2rayNG 导入后：** 选中「链式·家宽+台湾」这条自定义配置再连接。它会经兜底前置自动挑延迟最低的家宽/台湾节点。JSON 随 Actions 更新，重新打开链接粘贴即可。

---

"""
    if CHAIN_README_MARKER in text:
        start = text.index(CHAIN_README_MARKER)
        end = text.find("\n## ", start + 4)
        if end == -1:
            text = text[:start] + section
        else:
            text = text[:start] + section + text[end:]
    else:
        needle = "## 📌 全部节点总订阅链接"
        if needle in text:
            text = text.replace(needle, section + needle, 1)
        else:
            text = section + text

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("[+] README 已写入手机链式订阅说明")


def purge_cdn(rel_paths: list[str]) -> None:
    repo = repo_name()
    if "/" not in repo:
        return
    for rel in rel_paths:
        try:
            requests.get(f"https://purge.jsdelivr.net/gh/{repo}@main/{rel}", timeout=10)
        except Exception:
            pass


def dump_yaml(path: str, data: dict[str, Any]) -> None:
    header = (
        "# 前置链式订阅 · Clash Meta / Mihomo（iOS + Android）\n"
        "# 本机 → 前置订阅(直连下载) → 家宽/节点 → 目标\n"
        "# 原版 Clash、Shadowrocket、Quantumult X 不能用。\n"
        "# 前置选择请选「前置自动」。Hysteria2/TUIC 已排除。\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def main() -> None:
    cache_bust = int(time.time())
    res = uniquify([
        p for p in load_clash_proxies(os.path.join(OUTPUT_DIR, "residential-clash.yaml"))
        if is_chainable(p)
    ])
    tw_res = [
        p for p in load_clash_proxies(os.path.join(OUTPUT_DIR, "residential-by-country", "clash-TW.yaml"))
        if is_chainable(p)
    ]
    tw_all = [
        p for p in load_clash_proxies(os.path.join(OUTPUT_DIR, "by-country", "clash-TW.yaml"))
        if is_chainable(p)
    ]
    tw_baked = uniquify(tw_res + tw_all)
    baked = uniquify(res + tw_baked)
    baked_chain = [with_dialer(p) for p in baked]
    res_names = [p["name"] for p in res]
    tw_names = [p["name"] for p in tw_baked]

    clash_cfg = build_clash_chain(baked_chain, res_names, tw_names, cache_bust)
    root_yaml = os.path.join(BASEDIR, "clash-tw-chain.yaml")
    out_yaml = os.path.join(OUTPUT_DIR, "clash-chain.yaml")
    dump_yaml(root_yaml, clash_cfg)
    dump_yaml(out_yaml, clash_cfg)

    v2ray_cfg = build_v2rayng_chain(baked)
    v2ray_path = os.path.join(OUTPUT_DIR, "v2rayng-chain.json")
    with open(v2ray_path, "w", encoding="utf-8") as f:
        json.dump(v2ray_cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    patch_readme(len(res_names), len(tw_names), cache_bust)
    purge_cdn([
        "clash-tw-chain.yaml",
        "output/clash-chain.yaml",
        "output/v2rayng-chain.json",
        "README.md",
    ])
    print(
        f"[+] 链式配置已生成: 家宽可套链 {len(res_names)} | 台湾可套链 {len(tw_names)} | "
        f"v2rayNG 出站 {min(len(baked), MAX_V2RAYNG_CHAIN)}"
    )
    print(f"    {root_yaml}")
    print(f"    {v2ray_path}")


if __name__ == "__main__":
    main()

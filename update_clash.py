# update_clash.py
import requests
import yaml
from urllib.parse import urlparse, parse_qs
import os

# ==================== 配置区 ====================
SUB_URL = "https://cfxr.eu.org/getSub?host=hkg.fangwenchang.dpdns.org"
OUTPUT_FILE = "clash_config.yaml"

# 可选：GitHub 仓库信息（用于自动推送）
# 如果你不启用自动推送，可以留空
GITHUB_REPO = ""  # 格式: username/repo
GITHUB_BRANCH = "main"
GITHUB_TOKEN = ""  # 你的 Personal Access Token (https://github.com/settings/tokens)
COMMIT_MESSAGE = "auto: update proxy config"
# ===============================================

import subprocess

def fetch_subscription(url):
    """使用 curl 获取订阅内容（绕过 requests 的网络问题）"""
    try:
        print("📡 正在使用 curl 获取订阅...")
        result = subprocess.run(
            [
                "curl",
                "-H", "User-Agent: Clash Meta for Windows/0.20.0",
                "--connect-timeout", "30",
                "--max-time", "60",
                url
            ],
            capture_output=True,
            text=True,
            timeout=70,
            encoding='utf-8'  # 明确指定编码
        )

        if result.returncode == 0:
            raw_text = result.stdout.strip()
            if not raw_text:
                print("❌ curl 返回内容为空")
                return None

            if "vless://" not in raw_text:
                print("⚠️ 返回内容不包含 vless 节点")
                print("前 500 字符:", repr(raw_text[:500]))
                return None

            print(f"✅ curl 成功获取 {len(raw_text.splitlines())} 个节点")
            return raw_text
        else:
            print(f"❌ curl 执行失败: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        print("❌ curl 请求超时")
        return None
    except FileNotFoundError:
        print("❌ 未找到 curl 命令，请确保系统已安装 curl")
        print("Windows 用户：确保已安装 Git Bash 或 curl 工具")
        return None
    except Exception as e:
        print(f"❌ 执行 curl 时出错: {e}")
        return None
def parse_vless_link(link):
    """解析 vless:// 链接为 Clash 代理配置"""
    try:
        if '#' in link:
            link, tag = link.split('#', 1)
        else:
            tag = "VLESS"

        parsed = urlparse(link)
        query = parse_qs(parsed.query)

        host = parsed.hostname
        port = parsed.port or 443
        uuid = parsed.username

        security = query.get('security', ['none'])[0]
        sni = query.get('sni', [host])[0] if security == 'tls' else host

        network = query.get('type', ['tcp'])[0]
        ws_path = query.get('path', ['/'])[0]
        ws_host = query.get('host', [host])[0]

        return {
            "name": tag,
            "type": "vless",
            "server": host,
            "port": port,
            "uuid": uuid,
            "tls": security == "tls",
            "servername": sni,
            "client-fingerprint": "chrome",
            "network": network,
            "ws-opts": {
                "path": ws_path,
                "headers": {"Host": ws_host}
            } if network == "ws" else {}
        }
    except Exception as e:
        print(f"⚠️ 解析失败: {link} | {e}")
        return None

def generate_clash_config(proxies):
    """生成 Clash YAML 配置"""
    config = {
        "mixed-port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "dns": {
            "enable": True,
            "listen": "0.0.0.0:53",
            "enhanced-mode": "fake-ip",
            "nameserver": [
                "https://dns.google/dns-query",
                "https://cloudflare-dns.com/dns-query"
            ]
        },
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "PROXY",
                "type": "select",
                "proxies": ["自动选择", "故障转移", "负载均衡"] + [p["name"] for p in proxies]
            },
            {
                "name": "自动选择",
                "type": "url-test",
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "proxies": [p["name"] for p in proxies]
            },
            {
                "name": "故障转移",
                "type": "fallback",
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "proxies": [p["name"] for p in proxies]
            },
            {
                "name": "负载均衡",
                "type": "load-balance",
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "proxies": [p["name"] for p in proxies]
            }
        ],
        "rules": [
            "DOMAIN-SUFFIX,google.com,PROXY",
            "DOMAIN-SUFFIX,github.com,PROXY",
            "DOMAIN-KEYWORD,adsense,PROXY",
            "GEOIP,CN,DIRECT",
            "MATCH,DIRECT"
        ]
    }
    return config

def save_yaml(config, filename):
    """保存为 YAML 文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"✅ Clash 配置已保存: {filename}")

def push_to_github():
    """可选：推送到 GitHub（需配置 GITHUB_REPO 和 GITHUB_TOKEN）"""
    if not GITHUB_REPO or not GITHUB_TOKEN:
        print("ℹ️ 未配置 GitHub，跳过推送")
        return

    try:
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            repo_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
            
            subprocess.run(["git", "clone", "-b", GITHUB_BRANCH, repo_url, "."], check=True)
            subprocess.run(["cp", f"../{OUTPUT_FILE}", "."], check=True)
            subprocess.run(["git", "add", OUTPUT_FILE], check=True)
            subprocess.run(["git", "config", "user.name", "auto-bot"], check=True)
            subprocess.run(["git", "config", "user.email", "bot@example.com"], check=True)
            subprocess.run(["git", "commit", "-m", COMMIT_MESSAGE], check=True)
            subprocess.run(["git", "push"], check=True)

        print("✅ 已成功推送到 GitHub！")
    except Exception as e:
        print(f"❌ 推送 GitHub 失败: {e}")

def main():
    print("🚀 开始更新 Clash 订阅...")
    
    # 1. 获取订阅
    raw_nodes = fetch_subscription(SUB_URL)
    if not raw_nodes:
        return

    # 2. 解析节点
    proxies = []
    for line in raw_nodes.splitlines():
        line = line.strip()
        if line.startswith("vless://"):
            proxy = parse_vless_link(line)
            if proxy:
                proxies.append(proxy)

    if not proxies:
        print("❌ 未解析到任何有效节点")
        return

    # 3. 生成配置
    config = generate_clash_config(proxies)
    save_yaml(config, OUTPUT_FILE)

    # 4. 推送到 GitHub（可选）
    push_to_github()

    print("🎉 全部完成！")

if __name__ == "__main__":
    main()

from colorama import Fore, Style, init
import requests, json, time, os, pathlib, random, sys, datetime
from web3 import Web3
from eth_account.messages import encode_defunct
from eth_account import Account

init(autoreset=True)

banner = r"""
{0}     _   _           _  _____      
    | \ | |         | ||____ |     
    |  \| | ___   __| |    / /_ __ 
    | . ` |/ _ \ / _` |    \ \ '__|
    | |\  | (_) | (_| |.___/ / |   
    \_| \_/\___/ \__,_|\____/|_|   
                                   
    prdt-farmer 管理器
    TG: @nod3r
""".format(Fore.CYAN)

warn = f"""{Fore.YELLOW}注意！请勿使用持有资产的真实钱包进行挖矿。
所有私钥仅存储在您的本地。请勿分享 all_wallets.json 文件。
"""

header = f"""{Fore.LIGHTYELLOW_EX}所有私钥仅在本地存储。
绝不要在此使用主钱包或持有资产的钱包！{Style.RESET_ALL}
"""

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

SETTINGS_FILE = "prdt_settings.json"
DEFAULT_SETTINGS = {
    "cooldown_hours": 8,
    "gen_range_min": 3,
    "gen_range_max": 12,
    "referral_code": "",
    "wallets_file": "all_wallets.json",
    "proxies_file": "proxies.txt",
    "delay_min": 5,
    "delay_max": 15
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r") as f:
            s = json.load(f)
        for k, v in DEFAULT_SETTINGS.items():
            if k not in s:
                s[k] = v
        return s
    except Exception:
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def show_settings(settings, pause=True):
    print(Fore.LIGHTCYAN_EX + "\n当前设置：")
    print(f"  1. 挖矿间隔时间（小时）：{settings['cooldown_hours']}")
    print(f"  2. 钱包生成范围：{settings['gen_range_min']} - {settings['gen_range_max']}")
    print(f"  3. 邀请码：{settings['referral_code'] or '[未设置]'}")
    print(f"  4. 钱包文件路径：{settings['wallets_file']}")
    print(f"  5. 代理文件路径：{settings['proxies_file']}")
    print(f"  6. 账户间延迟：{settings['delay_min']}–{settings['delay_max']} 秒")
    if pause:
        input(Fore.YELLOW + "\n按 Enter 返回主菜单...")

def edit_settings(settings):
    while True:
        show_settings(settings, pause=False)
        print("  7. 重置为默认设置")
        print("  8. 返回菜单")
        c = input(Fore.YELLOW + "\n输入要更改的设置编号（或 8 退出）：").strip()
        if c == "1":
            h = input("输入挖矿间隔时间（小时，例如 8）：").strip()
            try:
                h = int(h)
                if h < 1 or h > 72:
                    print(Fore.RED + "无效值。范围为 1-72。")
                else:
                    settings["cooldown_hours"] = h
            except ValueError:
                print(Fore.RED + "输入错误。")
        elif c == "2":
            mi = input("最小值（例如 3）：").strip()
            ma = input("最大值（例如 12）：").strip()
            try:
                mi, ma = int(mi), int(ma)
                if mi < 1 or ma < mi:
                    print(Fore.RED + "范围错误。")
                else:
                    settings["gen_range_min"] = mi
                    settings["gen_range_max"] = ma
            except ValueError:
                print(Fore.RED + "输入错误。")
        elif c == "3":
            ref = input("输入新的邀请码（留空表示无）：").strip()
            settings["referral_code"] = ref
        elif c == "4":
            path = input("输入钱包文件路径：").strip()
            if path:
                settings["wallets_file"] = path
        elif c == "5":
            path = input("输入代理文件路径：").strip()
            if path:
                settings["proxies_file"] = path
        elif c == "6":
            mi = input("最小延迟（秒）：").strip()
            ma = input("最大延迟（秒）：").strip()
            try:
                mi, ma = int(mi), int(ma)
                if mi < 0 or ma < mi:
                    print(Fore.RED + "范围错误。")
                else:
                    settings["delay_min"] = mi
                    settings["delay_max"] = ma
            except ValueError:
                print(Fore.RED + "输入错误。")
        elif c == "7":
            confirm = input(Fore.RED + "是否重置所有设置为默认值？(y/n)：").strip().lower()
            if confirm == "y":
                for k in DEFAULT_SETTINGS:
                    settings[k] = DEFAULT_SETTINGS[k]
        elif c == "8":
            break
        else:
            print(Fore.YELLOW + "输入无效。")
        save_settings(settings)

def now_iso():
    return datetime.datetime.now().isoformat(timespec='seconds')

def hours_ahead(hours):
    return (datetime.datetime.now() + datetime.timedelta(hours=hours)).isoformat(timespec='seconds')

def is_cooldown(wallet):
    next_check = wallet.get('next_check')
    if not next_check:
        return False
    try:
        return datetime.datetime.fromisoformat(next_check) > datetime.datetime.now()
    except Exception:
        return False

def print_wallets(wallets):
    print(Fore.LIGHTCYAN_EX + "\n钱包列表：")
    for i, w in enumerate(wallets, 1):
        nc = w.get('next_check')
        cooldown_msg = ""
        if nc:
            try:
                rest = (datetime.datetime.fromisoformat(nc) - datetime.datetime.now()).total_seconds()
                if rest > 0:
                    cooldown_msg = f" [休息至 {nc}]"
            except Exception:
                pass
        print(f"  {i}. {w['address']} (代理: {w.get('proxy', '-')}) (创建时间: {w.get('created_at', 'n/a')}){cooldown_msg}")
    if not wallets:
        print(Fore.YELLOW + "暂无钱包。")

def load_wallets(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"加载钱包失败：{e}")
        return []

def save_wallets(wallets, file_path):
    try:
        pathlib.Path(os.path.dirname(file_path) or ".").mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(wallets, f, indent=2, ensure_ascii=False)
        print(Fore.GREEN + f"已保存 {len(wallets)} 个钱包。")
    except Exception as e:
        print(Fore.RED + f"保存失败：{e}")

def load_proxies(proxies_file):
    proxies = []
    if os.path.exists(proxies_file):
        with open(proxies_file, "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
    return proxies

def assign_proxies(wallets, proxies):
    used_proxies = set(w.get('proxy') for w in wallets if w.get('proxy'))
    proxies_cycle = [p for p in proxies if p not in used_proxies] or proxies
    j = 0
    for w in wallets:
        if not w.get('proxy'):
            w['proxy'] = proxies_cycle[j % len(proxies_cycle)] if proxies_cycle else None
            j += 1
    return wallets

def input_proxy():
    print(Fore.LIGHTCYAN_EX + "\n请将您的代理添加到 proxies.txt 文件（每行一个）：")
    print("  格式：user:pass@host:port 或 host:port")
    input(Fore.LIGHTYELLOW_EX + "添加代理到文件后按 Enter 继续..." + Style.RESET_ALL)

def generate_wallet(proxy=None):
    acc = Account.create()
    return {
        "private_key": acc.key.hex(),
        "address": acc.address.lower(),
        "proxy": proxy,
        "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "last_used": None,
        "next_check": None
    }

def remove_wallet(wallets, idx):
    try:
        w = wallets.pop(idx)
        print(Fore.GREEN + f"已删除：{w['address']}")
        return wallets
    except IndexError:
        print(Fore.RED + "编号无效。")
        return wallets

CONFIG = {
    "AUTH_URL": "https://api.prdt.finance",
    "TOKEN_URL": "https://tokenapi.prdt.finance",
    "HEADERS": {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://prdt.finance",
        "Referer": "https://prdt.finance/"
    },
    "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

class PrdtBot:
    def __init__(self, wallet, referral_code=""):
        self.web3 = Web3()
        self.wallet = wallet
        self.referral_code = referral_code
        self.session = requests.Session()
        proxy = self.wallet.get('proxy')
        if proxy:
            self.session.proxies = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
        self.session.headers.update(CONFIG["HEADERS"])
        self.session.headers["User-Agent"] = CONFIG["USER_AGENT"]

    def login(self):
        payload = {
            "address": self.wallet['address'],
            "chain": 1,
            "network": "evm"
        }
        try:
            resp = self.session.post(f"{CONFIG['AUTH_URL']}/auth/request-message", json=payload, timeout=15)
            if resp.status_code != 200:
                print(Fore.RED + f"获取消息失败：{resp.text}")
                return False
            data = resp.json()
            msg = data.get("message")
            nonce = data.get("nonce")
            pk = self.wallet['private_key']
            sig = self.web3.eth.account.sign_message(encode_defunct(text=msg), private_key=pk).signature.hex()
            verify_payload = {
                "message": msg,
                "nonce": nonce,
                "signature": sig,
                "address": self.wallet['address']
            }
            time.sleep(1)
            verify_resp = self.session.post(f"{CONFIG['AUTH_URL']}/auth/verify", json=verify_payload, timeout=15)
            if verify_resp.status_code != 200:
                print(Fore.RED + f"验证失败：{verify_resp.text}")
                return False
            print(Fore.GREEN + f"授权成功 {self.wallet['address']} (代理: {self.wallet.get('proxy')})！")
            return True
        except Exception as e:
            print(Fore.RED + f"授权错误：{e}")
            return False

    def start_mining(self):
        try:
            st = self.session.get(f"{CONFIG['TOKEN_URL']}/api/v1/mine/status", timeout=15)
            if st.status_code == 200:
                data = st.json()
                if data.get('success') and data.get('user', {}).get('miningActive', False):
                    print(Fore.GREEN + f"挖矿已启动 {self.wallet['address']}。速率: {data.get('user', {}).get('miningRate', 0)}")
                    return "already"
            p = {"referralCode": self.referral_code}
            r = self.session.post(f"{CONFIG['TOKEN_URL']}/api/v1/mine/start", json=p, timeout=15)
            if r.status_code == 200:
                rs = r.json()
                print(Fore.GREEN + f"挖矿启动 {self.wallet['address']}：{rs.get('message')}")
                return "started"
            else:
                try:
                    rs = r.json()
                    msg = rs.get("message", "")
                    if "already in progress" in msg.lower():
                        print(Fore.YELLOW + f"挖矿已启动 {self.wallet['address']} (响应: {msg})")
                        return "already"
                except Exception:
                    msg = r.text
                print(Fore.RED + f"启动挖矿失败：{msg}")
                return "fail"
        except Exception as e:
            print(Fore.RED + f"挖矿错误：{e}")
            return "fail"

    def checkin(self):
        try:
            r = self.session.post(f"{CONFIG['TOKEN_URL']}/api/v1/mine/checkin", json={}, timeout=15)
            if r.status_code != 200:
                print(Fore.RED + f"签到失败：{r.text}")
                return "fail"
            rs = r.json()
            print(Fore.GREEN + f"签到成功 {self.wallet['address']}：{rs.get('message')}")
            return "success"
        except Exception as e:
            print(Fore.RED + f"签到错误：{e}")
            return "fail"

def main():
    settings = load_settings()
    clear_screen()
    print(banner)
    print(warn)
    print(header)
    wallets = load_wallets(settings["wallets_file"])

    while True:
        print(Fore.LIGHTCYAN_EX + f"""
  1. 生成新钱包
  2. 查看所有钱包
  3. 为所有钱包启动挖矿
  4. 执行签到
  5. 设置代理
  6. 删除钱包
  7. 程序设置
  8. 退出
  9. 查看当前设置
""")
        choice = input(Fore.YELLOW + "选择操作： " + Style.RESET_ALL).strip()

        if choice == "1":
            print(Fore.LIGHTCYAN_EX + "输入生成钱包数量的范围：")
            min_def = settings["gen_range_min"]
            max_def = settings["gen_range_max"]
            min_n = input(f"  最小值：[{min_def}] ").strip()
            max_n = input(f"  最大值：[{max_def}] ").strip()
            try:
                min_v = int(min_n) if min_n else min_def
                max_v = int(max_n) if max_n else max_def
                if min_v > max_v or min_v < 1:
                    print(Fore.RED + "范围无效！将使用默认值。")
                    min_v, max_v = min_def, max_def
            except Exception:
                min_v, max_v = min_def, max_def
            count = random.randint(min_v, max_v)
            print(Fore.GREEN + f"将创建 {count} 个钱包。")
            proxies = load_proxies(settings["proxies_file"])
            for i in range(count):
                proxy = proxies[(len(wallets) + i) % len(proxies)] if proxies else None
                w = generate_wallet(proxy=proxy)
                wallets.append(w)
                print(Fore.GREEN + f"已创建：{w['address']} (代理: {w['proxy']})")
            save_wallets(wallets, settings["wallets_file"])

        elif choice == "2":
            print_wallets(wallets)

        elif choice == "3":
            if not wallets:
                print(Fore.YELLOW + "暂无钱包。")
                continue
            ref = input(Fore.LIGHTCYAN_EX + f"输入邀请码（回车使用当前：{settings['referral_code'] or '[未设置]'}）：").strip()
            if not ref:
                ref = settings["referral_code"]
            input_proxy()
            proxies = load_proxies(settings["proxies_file"])
            wallets = assign_proxies(wallets, proxies)
            save_wallets(wallets, settings["wallets_file"])
            for i, w in enumerate(wallets, 1):
                if is_cooldown(w):
                    print(Fore.LIGHTBLACK_EX + f"\n--- [{i}/{len(wallets)}] ---")
                    print(Fore.LIGHTBLACK_EX + f"钱包：{w['address']} | 代理：{w.get('proxy')} 休息至 {w.get('next_check')}")
                    continue
                print(Fore.LIGHTCYAN_EX + f"\n--- [{i}/{len(wallets)}] ---")
                print(Fore.LIGHTCYAN_EX + f"钱包：{w['address']} | 代理：{w.get('proxy')}")
                bot = PrdtBot(w, referral_code=ref)
                if bot.login():
                    time.sleep(1)
                    result = bot.start_mining()
                    if result == "started" or result == "already":
                        w['last_used'] = now_iso()
                        w['next_check'] = hours_ahead(settings["cooldown_hours"])
                    save_wallets(wallets, settings["wallets_file"])
                else:
                    print(Fore.YELLOW + "因授权失败跳过。")
                if i != len(wallets):
                    d = random.uniform(settings["delay_min"], settings["delay_max"])
                    print(Fore.LIGHTBLACK_EX + f"下一个账户前延迟：{d:.1f} 秒。\n")
                    time.sleep(d)

        elif choice == "4":
            if not wallets:
                print(Fore.YELLOW + "暂无钱包。")
                continue
            input_proxy()
            proxies = load_proxies(settings["proxies_file"])
            wallets = assign_proxies(wallets, proxies)
            save_wallets(wallets, settings["wallets_file"])
            for i, w in enumerate(wallets, 1):
                if is_cooldown(w):
                    print(Fore.LIGHTBLACK_EX + f"\n--- [{i}/{len(wallets)}] ---")
                    print(Fore.LIGHTBLACK_EX + f"钱包：{w['address']} | 代理：{w.get('proxy')} 休息至 {w.get('next_check')}")
                    continue
                print(Fore.LIGHTCYAN_EX + f"\n--- [{i}/{len(wallets)}] ---")
                print(Fore.LIGHTCYAN_EX + f"钱包：{w['address']} | 代理：{w.get('proxy')}")
                bot = PrdtBot(w)
                if bot.login():
                    time.sleep(1)
                    result = bot.checkin()
                    if result == "success":
                        w['last_used'] = now_iso()
                        w['next_check'] = hours_ahead(settings["cooldown_hours"])
                    save_wallets(wallets, settings["wallets_file"])
                else:
                    print(Fore.YELLOW + "因授权失败跳过。")
                if i != len(wallets):
                    d = random.uniform(settings["delay_min"], settings["delay_max"])
                    print(Fore.LIGHTBLACK_EX + f"下一个账户前延迟：{d:.1f} 秒。\n")
                    time.sleep(d)

        elif choice == "5":
            input_proxy()

        elif choice == "6":
            print_wallets(wallets)
            try:
                idx = int(input("要删除的编号：")) - 1
                wallets = remove_wallet(wallets, idx)
                save_wallets(wallets, settings["wallets_file"])
            except ValueError:
                print(Fore.RED + "错误：请输入编号。")
            except Exception as e:
                print(Fore.RED + f"错误：{e}")

        elif choice == "7":
            edit_settings(settings)
            save_settings(settings)
            wallets = load_wallets(settings["wallets_file"])
            clear_screen()
            print(banner)
            print(warn)
            print(header)

        elif choice == "8":
            print(Fore.CYAN + "再见 👋")
            break

        elif choice == "9":
            show_settings(settings)

        else:
            print(Fore.YELLOW + "选择无效！")

if __name__ == "__main__":
    main()

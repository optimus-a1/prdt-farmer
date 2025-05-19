from colorama import Fore, Style, init
import requests, json, time, os, pathlib, random, sys
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
                                   
    Менеджер prdt-farmer
      @nod3r - Мультиаккаунт версия
""".format(Fore.CYAN)

warn = f"""{Fore.YELLOW}ВНИМАНИЕ! Никогда не используйте реальные кошельки с активами для фарминга.
Все приватные ключи хранятся только у вас локально. Не делитесь файлом all_wallets.json.
"""

header = f"""{Fore.LIGHTYELLOW_EX}Все приватные ключи хранятся ТОЛЬКО локально.
Никогда не используйте здесь основные кошельки или кошельки с активами!{Style.RESET_ALL}
"""

menu = f"""{Fore.LIGHTCYAN_EX}
  1. Генерировать новые кошельки
  2. Посмотреть все кошельки
  3. Запустить фарминг для всех кошельков
  4. Сделать check-in
  5. Настроить прокси
  6. Удалить кошелек
  7. Выйти
"""

CONFIG = {
    "AUTH_URL": "https://api.prdt.finance",
    "TOKEN_URL": "https://tokenapi.prdt.finance",
    "WALLETS_FILE": "all_wallets.json",
    "PROXIES_FILE": "proxies.txt",
    "HEADERS": {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://prdt.finance",
        "Referer": "https://prdt.finance/"
    },
    "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def print_wallets(wallets):
    print(Fore.LIGHTCYAN_EX + "\nСписок кошельков:")
    for i, w in enumerate(wallets, 1):
        print(f"  {i}. {w['address']} (proxy: {w.get('proxy', '-')}) (создан: {w.get('created_at', 'n/a')})")
    if not wallets:
        print(Fore.YELLOW + "Кошельки отсутствуют.")

def load_wallets(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"Ошибка загрузки кошельков: {e}")
        return []

def save_wallets(wallets, file_path):
    try:
        pathlib.Path(os.path.dirname(file_path) or ".").mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(wallets, f, indent=2, ensure_ascii=False)
        print(Fore.GREEN + f"Сохранено {len(wallets)} кошельков.")
    except Exception as e:
        print(Fore.RED + f"Ошибка сохранения: {e}")

def load_proxies():
    proxies = []
    if os.path.exists(CONFIG["PROXIES_FILE"]):
        with open(CONFIG["PROXIES_FILE"], "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
    return proxies

def random_range_input(prompt, default_min=3, default_max=12):
    print(Fore.LIGHTCYAN_EX + prompt + f" (по умолчанию {default_min}-{default_max})")
    min_n = input(f"  Минимум: [{default_min}] ").strip()
    max_n = input(f"  Максимум: [{default_max}] ").strip()
    try:
        min_v = int(min_n) if min_n else default_min
        max_v = int(max_n) if max_n else default_max
        if min_v > max_v or min_v < 1:
            print(Fore.RED + "Некорректный диапазон! Используется по умолчанию.")
            min_v, max_v = default_min, default_max
    except Exception:
        min_v, max_v = default_min, default_max
    count = random.randint(min_v, max_v)
    print(Fore.GREEN + f"Будет создано {count} кошельков.")
    return count

def assign_proxies(wallets, proxies):
    """Назначает прокси только новым кошелькам, уже имеющим — не меняет."""
    used_proxies = set(w.get('proxy') for w in wallets if w.get('proxy'))
    proxies_cycle = [p for p in proxies if p not in used_proxies] or proxies
    j = 0
    for w in wallets:
        if not w.get('proxy'):
            w['proxy'] = proxies_cycle[j % len(proxies_cycle)] if proxies_cycle else None
            j += 1
    return wallets

def input_proxy():
    print(Fore.LIGHTCYAN_EX + "\nДобавьте ваши прокси в файл proxies.txt (по одному на строку):")
    print("  user:pass@host:port или host:port")
    input(Fore.LIGHTYELLOW_EX + "Нажмите Enter после добавления прокси в файл..." + Style.RESET_ALL)

def input_referral():
    ref = input("Введите реферальный код (или оставьте пустым): ").strip()
    if ref:
        print(Fore.GREEN + f"Реферальный код: {ref}")
    else:
        print(Fore.YELLOW + "Без реферального кода")
    return ref

def generate_wallet(proxy=None):
    acc = Account.create()
    return {
        "private_key": acc.key.hex(),
        "address": acc.address.lower(),
        "proxy": proxy,
        "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "last_used": None
    }

def remove_wallet(wallets, idx):
    try:
        w = wallets.pop(idx)
        print(Fore.GREEN + f"Удалён: {w['address']}")
        return wallets
    except IndexError:
        print(Fore.RED + "Некорректный номер.")
        return wallets

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
            resp = self.session.post(f"{CONFIG['AUTH_URL']}/auth/request-message", json=payload)
            if resp.status_code != 200:
                print(Fore.RED + f"Ошибка получения сообщения: {resp.text}")
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
            verify_resp = self.session.post(f"{CONFIG['AUTH_URL']}/auth/verify", json=verify_payload)
            if verify_resp.status_code != 200:
                print(Fore.RED + f"Ошибка верификации: {verify_resp.text}")
                return False
            print(Fore.GREEN + f"Авторизация {self.wallet['address']} (proxy: {self.wallet.get('proxy')}) успешна!")
            return True
        except Exception as e:
            print(Fore.RED + f"Ошибка авторизации: {e}")
            return False

    def start_mining(self):
        try:
            st = self.session.get(f"{CONFIG['TOKEN_URL']}/api/v1/mine/status")
            if st.status_code == 200:
                data = st.json()
                if data.get('success') and data.get('user', {}).get('miningActive', False):
                    print(Fore.GREEN + f"Майнинг уже запущен для {self.wallet['address']}. Rate: {data.get('user', {}).get('miningRate', 0)}")
                    return True
            p = {"referralCode": self.referral_code}
            r = self.session.post(f"{CONFIG['TOKEN_URL']}/api/v1/mine/start", json=p)
            if r.status_code == 200:
                rs = r.json()
                print(Fore.GREEN + f"Майнинг запущен для {self.wallet['address']}: {rs.get('message')}")
                return True
            else:
                print(Fore.RED + f"Ошибка запуска майнинга: {r.text}")
                return False
        except Exception as e:
            print(Fore.RED + f"Ошибка майнинга: {e}")
            return False

    def checkin(self):
        try:
            r = self.session.post(f"{CONFIG['TOKEN_URL']}/api/v1/mine/checkin", json={})
            if r.status_code != 200:
                print(Fore.RED + f"Ошибка check-in: {r.text}")
                return False
            rs = r.json()
            print(Fore.GREEN + f"Check-in для {self.wallet['address']}: {rs.get('message')}")
            return True
        except Exception as e:
            print(Fore.RED + f"Ошибка check-in: {e}")
            return False

def main():
    print(banner)
    print(warn)
    print(header)
    wallets = load_wallets(CONFIG["WALLETS_FILE"])

    while True:
        print(menu)
        choice = input(Fore.YELLOW + "Выберите действие: " + Style.RESET_ALL).strip()
        if choice == "1":
            count = random_range_input("Введите диапазон для генерации количества кошельков")
            proxies = load_proxies()
            # Назначаем прокси для новых кошельков
            for i in range(count):
                proxy = proxies[(len(wallets)+i) % len(proxies)] if proxies else None
                w = generate_wallet(proxy=proxy)
                wallets.append(w)
                print(Fore.GREEN + f"Создан: {w['address']} (proxy: {w['proxy']})")
            save_wallets(wallets, CONFIG["WALLETS_FILE"])

        elif choice == "2":
            print_wallets(wallets)

        elif choice == "3":
            if not wallets:
                print(Fore.YELLOW + "Нет кошельков.")
                continue
            ref = input_referral()
            input_proxy()
            proxies = load_proxies()
            wallets = assign_proxies(wallets, proxies)
            save_wallets(wallets, CONFIG["WALLETS_FILE"])
            for i, w in enumerate(wallets, 1):
                print(Fore.LIGHTCYAN_EX + f"\n--- [{i}/{len(wallets)}] ---")
                print(Fore.LIGHTCYAN_EX + f"Кошелек: {w['address']} | Прокси: {w.get('proxy')}")
                bot = PrdtBot(w, referral_code=ref)
                if bot.login():
                    time.sleep(1)
                    bot.start_mining()
                    time.sleep(random.uniform(1, 2))
                else:
                    print(Fore.YELLOW + "Пропущено из-за ошибки авторизации.")

        elif choice == "4":
            if not wallets:
                print(Fore.YELLOW + "Нет кошельков.")
                continue
            input_proxy()
            proxies = load_proxies()
            wallets = assign_proxies(wallets, proxies)
            save_wallets(wallets, CONFIG["WALLETS_FILE"])
            for i, w in enumerate(wallets, 1):
                print(Fore.LIGHTCYAN_EX + f"\n--- [{i}/{len(wallets)}] ---")
                print(Fore.LIGHTCYAN_EX + f"Кошелек: {w['address']} | Прокси: {w.get('proxy')}")
                bot = PrdtBot(w)
                if bot.login():
                    time.sleep(1)
                    bot.checkin()
                    time.sleep(random.uniform(1, 2))
                else:
                    print(Fore.YELLOW + "Пропущено из-за ошибки авторизации.")

        elif choice == "5":
            input_proxy()

        elif choice == "6":
            print_wallets(wallets)
            try:
                idx = int(input("Номер для удаления: ")) - 1
                wallets = remove_wallet(wallets, idx)
                save_wallets(wallets, CONFIG["WALLETS_FILE"])
            except ValueError:
                print(Fore.RED + "Ошибка: нужен номер.")
            except Exception as e:
                print(Fore.RED + f"Ошибка: {e}")

        elif choice == "7":
            print(Fore.CYAN + "Пока 👋")
            break

        else:
            print(Fore.YELLOW + "Некорректный выбор!")

if __name__ == "__main__":
    main()

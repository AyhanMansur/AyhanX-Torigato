#!/usr/bin/env python3
"""
🌐 TorVault - Multi-Location Tor Network Manager
A powerful tool to control Tor exit nodes across different countries
"""

import os
import sys
import time
import json
import subprocess
import requests
import socket
import signal
from typing import Optional, Dict, List
from dataclasses import dataclass
from colorama import init, Fore, Style, just_fix_windows_console
import stem
from stem import Signal
from stem.control import Controller
import random
from datetime import datetime
import threading
import platform
import traceback

# Fix Windows console for colorama
just_fix_windows_console()

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# ==================== ASCII ART BANNER ====================
BANNER = f"""
{Fore.CYAN}▄▄                              ▄▄▄   ▄▄▄        ▄▄▄▄▄▄▄                                  
{Fore.CYAN}   ▄█▀▀█▄         █▄                █▀▀██ ██▀        █▀▀██▀▀▀▀                         █▄      
{Fore.CYAN}   ██  ██         ██          ▄        ▀█▄█▀            ██         ▄    ▀▀    ▄▄      ▄██▄     
{Fore.CYAN}   ██▀▀██   ██ ██ ████▄ ▄▀▀█▄ ████▄     ███             ██   ▄███▄ ████▄██ ▄████ ▄▀▀█▄ ██ ▄███▄
{Fore.CYAN} ▄ ██  ██   ██▄██ ██ ██ ▄█▀██ ██ ██   ▄█▀██▄   ▀▀▀▀     ██   ██ ██ ██   ██ ██ ██ ▄█▀██ ██ ██ ██
{Fore.CYAN} ▀██▀  ▀█▄█▄▄▀██▀▄██ ██▄▀█▄██▄██ ▀█ ▀██▀  ▀██▄          ▀██▄▄▀███▀▄█▀  ▄██▄▀████▄▀█▄██▄██▄▀███▀
{Fore.CYAN}              ██                                                              ██               
{Fore.BLUE}            ▀▀▀                                                             ▀▀▀               
{Style.RESET_ALL}
{Fore.CYAN}╔══════════════════════════════════════════════════════════════════╗
{Fore.YELLOW}║     {Fore.CYAN}🌐 TorVault v2.1 - Multi-Location Tor Network Manager{Fore.YELLOW}     ║
{Fore.YELLOW}║     {Fore.GREEN}🔒 Secure • Anonymous • Global Access{Fore.YELLOW}               ║
{Fore.YELLOW}╚══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""

# Required packages for the script
REQUIRED_PACKAGES = {
    'stem': 'stem',
    'requests': 'requests',
    'colorama': 'colorama',
    'socks': 'pysocks',   # import name is "socks", pip name is "pysocks"
}


@dataclass
class TorLocation:
    """Data class for Tor location configuration"""
    country_code: str
    country_name: str
    flag: str
    capital: str = ""
    continent: str = ""
    nodes: List[str] = None

    def __post_init__(self):
        if self.nodes is None:
            self.nodes = []


class RequirementsInstaller:
    """Handles automatic installation of required packages"""

    @staticmethod
    def check_package(package_name: str) -> bool:
        try:
            __import__(package_name)
            return True
        except ImportError:
            return False

    @staticmethod
    def install_package(package_name: str) -> bool:
        try:
            print(f"{Fore.YELLOW}[+] Installing {package_name}...{Style.RESET_ALL}")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet", package_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"{Fore.GREEN}[+] Successfully installed {package_name}{Style.RESET_ALL}")
            return True
        except subprocess.CalledProcessError:
            print(f"{Fore.RED}[!] Failed to install {package_name}{Style.RESET_ALL}")
            return False

    @staticmethod
    def install_all_packages() -> bool:
        print(f"\n{Fore.CYAN}[i] Checking and installing required packages...{Style.RESET_ALL}")
        print("=" * 50)

        missing_packages = []
        for import_name, package_name in REQUIRED_PACKAGES.items():
            if not RequirementsInstaller.check_package(import_name):
                missing_packages.append(package_name)

        if not missing_packages:
            print(f"{Fore.GREEN}[+] All required packages are already installed!{Style.RESET_ALL}")
            return True

        print(f"{Fore.YELLOW}[*] Missing packages: {', '.join(missing_packages)}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] Installing missing packages...{Style.RESET_ALL}")

        success = True
        for package in missing_packages:
            if not RequirementsInstaller.install_package(package):
                success = False

        if success:
            print(f"\n{Fore.GREEN}[+] All packages installed successfully!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}[!] Some packages failed to install. Please install them manually.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[*] Command: pip install {' '.join(missing_packages)}{Style.RESET_ALL}")

        return success


class TorVault:
    """Main class to manage Tor connections with multi-location support"""

    LOCATIONS = {
        'BR': TorLocation('BR', 'Brazil', '🇧🇷', 'Brasília', 'South America'),
        'US': TorLocation('US', 'United States', '🇺🇸', 'Washington D.C.', 'North America'),
        'DE': TorLocation('DE', 'Germany', '🇩🇪', 'Berlin', 'Europe'),
        'FR': TorLocation('FR', 'France', '🇫🇷', 'Paris', 'Europe'),
        'GB': TorLocation('GB', 'United Kingdom', '🇬🇧', 'London', 'Europe'),
        'CA': TorLocation('CA', 'Canada', '🇨🇦', 'Ottawa', 'North America'),
        'AU': TorLocation('AU', 'Australia', '🇦🇺', 'Canberra', 'Oceania'),
        'JP': TorLocation('JP', 'Japan', '🇯🇵', 'Tokyo', 'Asia'),
        'IN': TorLocation('IN', 'India', '🇮🇳', 'New Delhi', 'Asia'),
        'NL': TorLocation('NL', 'Netherlands', '🇳🇱', 'Amsterdam', 'Europe'),
        'SE': TorLocation('SE', 'Sweden', '🇸🇪', 'Stockholm', 'Europe'),
        'CH': TorLocation('CH', 'Switzerland', '🇨🇭', 'Bern', 'Europe'),
        'RU': TorLocation('RU', 'Russia', '🇷🇺', 'Moscow', 'Europe/Asia'),
        'CN': TorLocation('CN', 'China', '🇨🇳', 'Beijing', 'Asia'),
        'ZA': TorLocation('ZA', 'South Africa', '🇿🇦', 'Pretoria', 'Africa'),
        'MX': TorLocation('MX', 'Mexico', '🇲🇽', 'Mexico City', 'North America'),
        'IT': TorLocation('IT', 'Italy', '🇮🇹', 'Rome', 'Europe'),
        'ES': TorLocation('ES', 'Spain', '🇪🇸', 'Madrid', 'Europe'),
        'PT': TorLocation('PT', 'Portugal', '🇵🇹', 'Lisbon', 'Europe'),
        'NO': TorLocation('NO', 'Norway', '🇳🇴', 'Oslo', 'Europe'),
        'FI': TorLocation('FI', 'Finland', '🇫🇮', 'Helsinki', 'Europe'),
        'NZ': TorLocation('NZ', 'New Zealand', '🇳🇿', 'Wellington', 'Oceania'),
        'SG': TorLocation('SG', 'Singapore', '🇸🇬', 'Singapore', 'Asia'),
        'AE': TorLocation('AE', 'UAE', '🇦🇪', 'Abu Dhabi', 'Asia'),
        'IL': TorLocation('IL', 'Israel', '🇮🇱', 'Jerusalem', 'Asia'),
        'TR': TorLocation('TR', 'Turkey', '🇹🇷', 'Ankara', 'Europe/Asia'),
        'AR': TorLocation('AR', 'Argentina', '🇦🇷', 'Buenos Aires', 'South America'),
        'CL': TorLocation('CL', 'Chile', '🇨🇱', 'Santiago', 'South America'),
        'CO': TorLocation('CO', 'Colombia', '🇨🇴', 'Bogotá', 'South America'),
        'PE': TorLocation('PE', 'Peru', '🇵🇪', 'Lima', 'South America'),
        'EG': TorLocation('EG', 'Egypt', '🇪🇬', 'Cairo', 'Africa'),
        'NG': TorLocation('NG', 'Nigeria', '🇳🇬', 'Abuja', 'Africa'),
        'KE': TorLocation('KE', 'Kenya', '🇰🇪', 'Nairobi', 'Africa'),
        'PK': TorLocation('PK', 'Pakistan', '🇵🇰', 'Islamabad', 'Asia'),
        'BD': TorLocation('BD', 'Bangladesh', '🇧🇩', 'Dhaka', 'Asia'),
        'PH': TorLocation('PH', 'Philippines', '🇵🇭', 'Manila', 'Asia'),
        'VN': TorLocation('VN', 'Vietnam', '🇻🇳', 'Hanoi', 'Asia'),
        'TH': TorLocation('TH', 'Thailand', '🇹🇭', 'Bangkok', 'Asia'),
        'MY': TorLocation('MY', 'Malaysia', '🇲🇾', 'Kuala Lumpur', 'Asia'),
        'ID': TorLocation('ID', 'Indonesia', '🇮🇩', 'Jakarta', 'Asia'),
    }

    # Configurable via env var instead of hardcoded to one machine.
    WINDOWS_TOR_PATH = os.environ.get(
        "TORVAULT_TOR_PATH",
        r"C:\Users\AyhansPC\Downloads\Projects\Tunnel Tools\Network Projects\tor.exe"
    )

    def __init__(self, tor_port: int = 9050, control_port: int = 9051, password: str = None):
        self.tor_port = tor_port
        self.control_port = control_port
        self.password = password or ""
        self.controller: Optional[Controller] = None
        self.controller_lock = threading.Lock()  # protects concurrent access from the rotation thread
        self.current_location: Optional[str] = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.connection_history: List[Dict] = []
        self.is_auto_rotating = False
        self.rotation_thread: Optional[threading.Thread] = None
        self.tor_process: Optional[subprocess.Popen] = None
        self.tor_started_manually = False

        self.log_file = f"torvault_{self.session_id}.log"
        self.setup_logging()

        self.stats = {
            'total_switches': 0,
            'successful_switches': 0,
            'failed_switches': 0,
            'start_time': datetime.now()
        }

        # Clean shutdown on Ctrl+C / SIGTERM instead of leaving the Tor
        # process or rotation thread running in the background.
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        self.logger.info(f"[*] Received signal {signum}, shutting down cleanly...")
        self.shutdown()
        sys.exit(0)

    def shutdown(self):
        """Stop rotation, close the controller, and stop any Tor process we started."""
        if self.is_auto_rotating:
            self.stop_auto_rotate()
        if self.controller:
            try:
                self.controller.close()
            except Exception:
                pass
            self.controller = None
        if platform.system() == 'Windows' and self.tor_process:
            self.stop_tor_windows()

    def setup_logging(self):
        """Initialize logging system with Windows encoding fix"""
        import logging

        class SafeStreamHandler(logging.StreamHandler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    if platform.system() == 'Windows':
                        replacements = {
                            '✅': '[OK]', '❌': '[ERROR]', '⚠️': '[WARN]', '🔄': '[ROTATE]',
                            '📦': '[PACKAGE]', '📊': '[STATS]', '🌐': '[NET]', '🔍': '[SEARCH]',
                            '📍': '[LOC]', '🏙️': '[CITY]', '🏛️': '[REGION]', '🏢': '[ISP]',
                            '🕐': '[TIME]', '🔌': '[PORT]', '🎮': '[CTRL]', '📅': '[DATE]',
                            '📁': '[FILE]', '📜': '[HISTORY]',
                        }
                        for emoji, replacement in replacements.items():
                            msg = msg.replace(emoji, replacement)
                    stream = self.stream
                    stream.write(msg + self.terminator)
                    self.flush()
                except Exception:
                    self.handleError(record)

        logger = logging.getLogger(__name__)
        logger.handlers.clear()

        handler = SafeStreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.setLevel(logging.INFO)
        self.logger = logger

    def display_banner(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(BANNER)
        print(f"{Fore.CYAN}[DATE] Session: {self.session_id}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[NET] Connected to Tor: {'[YES]' if self.check_tor_connection() else '[NO]'}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[i] Platform: {platform.system()}{Style.RESET_ALL}")
        self.display_contact_info()
        print("=" * 70)

    def display_contact_info(self):
        print(f"{Fore.YELLOW}[i] Email: umc.mansur13@icloud.com{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[i] GitHub: https://github.com/AyhanMansur{Style.RESET_ALL}")

    def create_torrc_with_controlport(self) -> bool:
        """Create or update torrc with ControlPort configuration"""
        try:
            torrc_paths = [
                os.path.join(os.environ.get("APPDATA", ""), "tor", "torrc"),
                os.path.join(os.path.dirname(self.WINDOWS_TOR_PATH), "torrc"),
                os.path.join(os.path.dirname(self.WINDOWS_TOR_PATH), "Data", "Tor", "torrc"),
            ]

            torrc_path = None
            for path in torrc_paths:
                if path and (os.path.exists(os.path.dirname(path)) or os.path.exists(path)):
                    torrc_path = path
                    break

            if not torrc_path:
                torrc_path = os.path.join(os.path.dirname(self.WINDOWS_TOR_PATH), "torrc")
                os.makedirs(os.path.dirname(torrc_path), exist_ok=True)

            if os.path.exists(torrc_path):
                with open(torrc_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'ControlPort' in content and '9051' in content:
                        self.logger.info("[i] ControlPort already configured in torrc")
                        return True

            # NOTE: previously this wrote a blank "HashedControlPassword"
            # line, which is invalid torrc syntax. CookieAuthentication
            # alone is sufficient for local use; add a real
            # HashedControlPassword (generated via `tor --hash-password`)
            # only if you want password auth instead of cookie auth.
            config = """
# Tor configuration for TorVault
SocksPort 9050
ControlPort 9051
CookieAuthentication 1
"""

            with open(torrc_path, 'w', encoding='utf-8') as f:
                f.write(config.strip())

            self.logger.info(f"[i] Created torrc with ControlPort at: {torrc_path}")
            self.logger.info("[i] Please restart Tor for changes to take effect")
            return True

        except Exception as e:
            self.logger.error(f"[!] Failed to create torrc: {e}")
            return False

    def start_tor_with_controlport(self) -> bool:
        """Start Tor with ControlPort enabled"""
        if platform.system() != 'Windows':
            self.logger.info(
                "[i] Non-Windows platform detected: please start Tor yourself, "
                "e.g. `tor -f /etc/tor/torrc` with ControlPort 9051 and "
                "CookieAuthentication 1 enabled."
            )
            return False

        if not os.path.exists(self.WINDOWS_TOR_PATH):
            self.logger.error(
                f"[!] tor.exe not found at {self.WINDOWS_TOR_PATH}. "
                f"Set the TORVAULT_TOR_PATH environment variable to the correct path."
            )
            return False

        try:
            self.create_torrc_with_controlport()

            os.system("taskkill /f /im tor.exe 2>nul")
            time.sleep(2)

            tor_dir = os.path.dirname(self.WINDOWS_TOR_PATH)

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            self.tor_process = subprocess.Popen(
                [self.WINDOWS_TOR_PATH, "-f", os.path.join(tor_dir, "torrc")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            self.logger.info("[i] Starting Tor with ControlPort enabled...")
            for i in range(15):
                time.sleep(1)
                if self.check_tor_connection():
                    self.logger.info("[OK] Tor started successfully with ControlPort!")
                    return True
                if i % 3 == 0:
                    print(".", end="", flush=True)

            self.logger.error("[!] Tor failed to start properly")
            return False

        except Exception as e:
            self.logger.error(f"[!] Failed to start Tor with ControlPort: {e}")
            return False

    def stop_tor_windows(self):
        if self.tor_process:
            try:
                self.logger.info("[i] Stopping Tor process...")
                self.tor_process.terminate()
                self.tor_process.wait(timeout=5)
                self.logger.info("[i] Tor process stopped")
            except Exception as e:
                self.logger.error(f"[!] Error stopping Tor: {e}")
                try:
                    self.tor_process.kill()
                except Exception:
                    pass
            finally:
                self.tor_process = None

    def check_tor_connection(self) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', self.tor_port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def connect_tor(self) -> bool:
        """Connect to Tor control port"""
        try:
            self.logger.info(f"[i] Connecting to Tor control port {self.control_port}...")

            for attempt in range(5):
                try:
                    self.controller = Controller.from_port(port=self.control_port)
                    # Fixed: previously the configured password was never
                    # actually passed to authenticate(), so password-protected
                    # ControlPorts would always fail.
                    if self.password:
                        self.controller.authenticate(password=self.password)
                    else:
                        self.controller.authenticate()
                    self.logger.info(f"[OK] Connected to Tor control port {self.control_port}")
                    return True
                except stem.SocketError as e:
                    if attempt < 4:
                        self.logger.info(f"[i] Attempt {attempt + 1} failed, retrying...")
                        time.sleep(2)
                    else:
                        raise e

            return False

        except Exception as e:
            self.logger.error(f"[!] Failed to connect to Tor control port: {e}")
            self.logger.error("[!] Make sure Tor is running with ControlPort enabled")
            self.logger.info("[i] Try running Tor with: tor -f torrc")
            return False

    def get_current_ip(self, use_tor: bool = True) -> Optional[str]:
        try:
            if use_tor:
                session = requests.Session()
                session.proxies = {
                    'http': f'socks5h://127.0.0.1:{self.tor_port}',
                    'https': f'socks5h://127.0.0.1:{self.tor_port}'
                }
                response = session.get('https://api.ipify.org?format=json', timeout=10)
            else:
                response = requests.get('https://api.ipify.org?format=json', timeout=10)

            if response.status_code == 200:
                return response.json().get('ip')
            return None
        except Exception as e:
            self.logger.error(f"[!] Failed to get IP: {e}")
            return None

    def get_geo_location(self, ip: str) -> Optional[Dict]:
        try:
            response = requests.get(f'http://ip-api.com/json/{ip}', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country'),
                        'country_code': data.get('countryCode'),
                        'city': data.get('city'),
                        'region': data.get('regionName'),
                        'isp': data.get('isp'),
                        'lat': data.get('lat'),
                        'lon': data.get('lon'),
                        'timezone': data.get('timezone')
                    }
            return None
        except Exception as e:
            self.logger.error(f"[!] Failed to get geolocation: {e}")
            return None

    def switch_location(self, country_code: str, retry_count: int = 3) -> bool:
        """Switch Tor exit node to a specific country.

        Fixed: previously this just called NEWNYM repeatedly and hoped the
        random circuit happened to land in the target country, which is
        unreliable for less common countries. Now it tells Tor which exit
        country to use via SETCONF ExitNodes before requesting a new circuit.
        """
        if country_code not in self.LOCATIONS:
            self.logger.error(f"[!] Invalid country code: {country_code}")
            return False

        if not self.controller:
            if not self.connect_tor():
                return False

        self.stats['total_switches'] += 1

        with self.controller_lock:
            try:
                self.controller.set_conf('ExitNodes', f'{{{country_code.lower()}}}')
                self.controller.set_conf('StrictNodes', '1')
            except Exception as e:
                self.logger.warning(f"[*] Could not set ExitNodes preference: {e}")

            for attempt in range(retry_count):
                try:
                    self.controller.signal(Signal.NEWNYM)
                    time.sleep(2 + attempt)

                    new_ip = self.get_current_ip(use_tor=True)

                    if new_ip:
                        location = self.get_geo_location(new_ip)
                        if location and location.get('country_code') == country_code:
                            self.current_location = country_code
                            self.stats['successful_switches'] += 1

                            switch_record = {
                                'timestamp': datetime.now().isoformat(),
                                'country': country_code,
                                'ip': new_ip,
                                'location': location
                            }
                            self.connection_history.append(switch_record)

                            self.logger.info(
                                f"[OK] Successfully switched to "
                                f"{self.LOCATIONS[country_code].flag} {self.LOCATIONS[country_code].country_name}"
                            )
                            self.logger.info(f"   [NET] New IP: {new_ip}")
                            self.logger.info(
                                f"   [LOC] Location: {location.get('city')}, "
                                f"{location.get('region')}, {location.get('country')}"
                            )
                            self.logger.info(f"   [ISP] ISP: {location.get('isp')}")
                            self.logger.info(f"   [TIME] Timezone: {location.get('timezone')}")
                            return True
                        else:
                            self.logger.warning(f"[*] Attempt {attempt + 1}: Not in correct country yet")
                    else:
                        self.logger.warning(f"[*] Attempt {attempt + 1}: Could not get IP")

                except Exception as e:
                    self.logger.error(f"[!] Attempt {attempt + 1} failed: {e}")
                    time.sleep(1)

            self.stats['failed_switches'] += 1
            self.logger.error(f"[!] Failed to switch to {country_code} after {retry_count} attempts")
            return False

    def rotate_location_randomly(self) -> bool:
        available_locations = list(self.LOCATIONS.keys())
        if self.current_location in available_locations:
            available_locations.remove(self.current_location)

        if not available_locations:
            return False

        random_location = random.choice(available_locations)
        return self.switch_location(random_location)

    def auto_rotate(self, interval: int = 30):
        self.is_auto_rotating = True

        def rotation_loop():
            while self.is_auto_rotating:
                self.rotate_location_randomly()
                for _ in range(interval):
                    if not self.is_auto_rotating:
                        break
                    time.sleep(1)

        self.rotation_thread = threading.Thread(target=rotation_loop, daemon=True)
        self.rotation_thread.start()
        self.logger.info(f"[ROTATE] Auto-rotation started (every {interval} seconds)")

    def stop_auto_rotate(self):
        self.is_auto_rotating = False
        if self.rotation_thread:
            self.rotation_thread.join(timeout=5)
        self.logger.info("[ROTATE] Auto-rotation stopped")

    def test_connection_speed(self) -> Dict:
        try:
            start_time = time.time()
            response = requests.get(
                'https://speedtest.tele2.net/10MB.zip',
                proxies={'http': f'socks5h://127.0.0.1:{self.tor_port}',
                         'https': f'socks5h://127.0.0.1:{self.tor_port}'},
                stream=True,
                timeout=60
            )

            total_size = 0
            chunk_count = 0
            for chunk in response.iter_content(chunk_size=8192):
                total_size += len(chunk)
                chunk_count += 1
                if chunk_count % 100 == 0:
                    print(".", end="", flush=True)

            elapsed_time = time.time() - start_time
            if elapsed_time <= 0:
                elapsed_time = 0.001  # guard against div-by-zero on very fast/cached responses

            speed_mbps = (total_size * 8) / (elapsed_time * 1024 * 1024)
            speed_kbps = speed_mbps * 1024

            return {
                'speed_mbps': round(speed_mbps, 2),
                'speed_kbps': round(speed_kbps, 2),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'time_seconds': round(elapsed_time, 2)
            }

        except Exception as e:
            self.logger.error(f"[!] Speed test failed: {e}")
            return {'error': str(e)}

    def show_statistics(self):
        uptime = datetime.now() - self.stats['start_time']

        print(f"\n{Fore.CYAN}[STATS] Connection Statistics{Style.RESET_ALL}")
        print("=" * 50)
        print(f"Uptime: {str(uptime).split('.')[0]}")
        print(f"Total switches: {self.stats['total_switches']}")
        print(f"Successful switches: {self.stats['successful_switches']}")
        print(f"Failed switches: {self.stats['failed_switches']}")

        success_rate = (self.stats['successful_switches'] / max(1, self.stats['total_switches'])) * 100
        print(f"Success rate: {success_rate:.1f}%")
        print(f"Connection history: {len(self.connection_history)} entries")

        if self.connection_history:
            print(f"\n{Fore.YELLOW}[i] Recent connections:{Style.RESET_ALL}")
            for entry in self.connection_history[-5:]:
                print(f"  • {entry['timestamp'][:19]} -> {entry['country']} ({entry['ip']})")

    def show_location_list(self):
        print(f"\n{Fore.CYAN}[NET] Available Tor Locations{Style.RESET_ALL}")
        print("=" * 70)
        print(f"{'Code':<6} {'Flag':<4} {'Country':<20} {'Capital':<15} {'Continent':<15}")
        print("-" * 70)

        for code, loc in sorted(self.LOCATIONS.items()):
            current = "[LOC]" if code == self.current_location else "    "
            print(f"{current} {code:<4} {loc.flag:<4} {loc.country_name:<20} {loc.capital:<15} {loc.continent:<15}")

    def show_current_status(self):
        print(f"\n{Fore.CYAN}[SEARCH] Current Connection Status{Style.RESET_ALL}")
        print("=" * 50)

        if self.current_location:
            loc = self.LOCATIONS.get(self.current_location)
            if loc:
                print(f"[LOC] Location: {loc.flag} {loc.country_name}")
                print(f"   Capital: {loc.capital}")
                print(f"   Continent: {loc.continent}")
        else:
            print("[LOC] Location: Not set")

        ip = self.get_current_ip(use_tor=True)
        if ip:
            print(f"[NET] IP Address: {ip}")
            location = self.get_geo_location(ip)
            if location:
                print(f"[CITY] City: {location.get('city', 'Unknown')}")
                print(f"[REGION] Region: {location.get('region', 'Unknown')}")
                print(f"[ISP] ISP: {location.get('isp', 'Unknown')}")
                print(f"[TIME] Timezone: {location.get('timezone', 'Unknown')}")
                if location.get('lat') and location.get('lon'):
                    print(f"[LOC] Coordinates: {location['lat']}, {location['lon']}")
        else:
            print("[NET] IP Address: Could not determine (Tor may not be connected)")

        print(f"[PORT] Tor Port: {self.tor_port}")
        print(f"[CTRL] Control Port: {self.control_port}")
        print(f"[DATE] Session ID: {self.session_id}")

        if self.is_auto_rotating:
            print(f"[ROTATE] Auto-rotation: Active")

    def show_connection_history(self):
        if not self.connection_history:
            print(f"\n{Fore.YELLOW}[i] No connection history available{Style.RESET_ALL}")
            return

        print(f"\n{Fore.CYAN}[HISTORY] Connection History{Style.RESET_ALL}")
        print("=" * 80)
        print(f"{'#':<4} {'Timestamp':<20} {'Country':<15} {'IP':<16} {'City':<15}")
        print("-" * 80)

        for i, entry in enumerate(reversed(self.connection_history[-20:]), 1):
            loc = self.LOCATIONS.get(entry['country'], None)
            flag = loc.flag if loc else ""
            city = entry['location'].get('city', 'N/A') if entry.get('location') else 'N/A'
            print(f"{i:<4} {entry['timestamp'][:19]:<20} {flag} {entry['country']:<11} {entry['ip']:<16} {city[:15]}")

    def export_history(self, filename: str = None):
        if not filename:
            filename = f"torvault_history_{self.session_id}.json"

        try:
            with open(filename, 'w') as f:
                json.dump(self.connection_history, f, indent=2)
            self.logger.info(f"[FILE] History exported to {filename}")
        except Exception as e:
            self.logger.error(f"[!] Failed to export history: {e}")

    def run_interactive(self):
        self.display_banner()

        if platform.system() == 'Windows':
            print(f"\n{Fore.YELLOW}[i] Starting Tor with ControlPort enabled...{Style.RESET_ALL}")
            if not self.start_tor_with_controlport():
                print(f"{Fore.YELLOW}[*] Could not auto-start Tor. Please start it manually.{Style.RESET_ALL}")
                print(f"   Tor path: {self.WINDOWS_TOR_PATH}")
                print(f"   Make sure to use: tor -f torrc")
            else:
                print(f"{Fore.GREEN}[OK] Tor is running with ControlPort enabled!{Style.RESET_ALL}")

        if not self.check_tor_connection():
            print(f"\n{Fore.RED}[!] Tor is not running!{Style.RESET_ALL}")
            print("Please start Tor with ControlPort enabled:")
            print(f"  tor -f torrc")
            input(f"\n{Fore.YELLOW}[i] Press Enter after starting Tor...{Style.RESET_ALL}")

            if not self.check_tor_connection():
                print(f"{Fore.RED}[!] Still cannot connect to Tor. Exiting...{Style.RESET_ALL}")
                return

        if not self.connect_tor():
            print(f"{Fore.RED}[!] Failed to connect to Tor control port.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[i] Make sure ControlPort 9051 is enabled in torrc{Style.RESET_ALL}")
            return

        self.show_current_status()

        try:
            while True:
                print("\n" + "=" * 70)
                print(f"{Fore.CYAN}[MENU] Main Menu{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}┌─────────────────────────────────────────────────────────────────────┐{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}1{Fore.YELLOW}. Switch to specific location                                      │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}2{Fore.YELLOW}. Switch to random location                                       │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}3{Fore.YELLOW}. Show current status                                             │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}4{Fore.YELLOW}. Test connection speed                                           │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}5{Fore.YELLOW}. Show available locations                                        │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}6{Fore.YELLOW}. Auto-rotate locations                                           │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}7{Fore.YELLOW}. Show statistics                                                │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}8{Fore.YELLOW}. Show connection history                                         │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}9{Fore.YELLOW}. Export history                                                  │")
                print(f"{Fore.YELLOW}│ {Fore.GREEN}0{Fore.YELLOW}. Exit                                                             │")
                print(f"{Fore.YELLOW}└─────────────────────────────────────────────────────────────────────┘{Style.RESET_ALL}")

                choice = input(f"\n{Fore.GREEN}[i] Select option (0-9): {Style.RESET_ALL}").strip()

                if choice == '1':
                    print("\n" + "=" * 70)
                    print(f"{Fore.CYAN}[NET] Select Target Location{Style.RESET_ALL}")
                    print("=" * 70)
                    print(f"{'Code':<6} {'Flag':<4} {'Country':<20} {'Capital':<15}")
                    print("-" * 50)

                    locations_list = sorted(self.LOCATIONS.items())
                    for i, (code, loc) in enumerate(locations_list[:15], 1):
                        print(f"{code:<6} {loc.flag:<4} {loc.country_name:<20} {loc.capital:<15}")
                    if len(locations_list) > 15:
                        print(f"... and {len(locations_list) - 15} more locations")

                    country = input(f"\n{Fore.GREEN}[i] Enter country code (e.g., BR, US): {Style.RESET_ALL}").strip().upper()
                    self.switch_location(country)

                elif choice == '2':
                    print(f"\n{Fore.YELLOW}[ROTATE] Switching to random location...{Style.RESET_ALL}")
                    self.rotate_location_randomly()

                elif choice == '3':
                    self.show_current_status()

                elif choice == '4':
                    print(f"\n{Fore.YELLOW}[i] Testing connection speed...{Style.RESET_ALL}")
                    print("This may take a moment...")
                    results = self.test_connection_speed()
                    if 'error' in results:
                        print(f"{Fore.RED}[!] Speed test failed: {results['error']}{Style.RESET_ALL}")
                    else:
                        print(f"\n{Fore.GREEN}[STATS] Speed Test Results:{Style.RESET_ALL}")
                        print(f"  • Download speed: {results['speed_mbps']} Mbps ({results['speed_kbps']} Kbps)")
                        print(f"  • File size: {results['total_size_mb']} MB")
                        print(f"  • Time: {results['time_seconds']} seconds")

                elif choice == '5':
                    self.show_location_list()

                elif choice == '6':
                    if self.is_auto_rotating:
                        self.stop_auto_rotate()
                    else:
                        try:
                            interval = int(input(f"{Fore.GREEN}[i] Enter rotation interval in seconds (default 30): {Style.RESET_ALL}") or 30)
                            self.auto_rotate(interval)
                        except ValueError:
                            print(f"{Fore.RED}[!] Invalid interval. Using default 30 seconds.{Style.RESET_ALL}")
                            self.auto_rotate(30)

                elif choice == '7':
                    self.show_statistics()

                elif choice == '8':
                    self.show_connection_history()

                elif choice == '9':
                    filename = input(f"{Fore.GREEN}[i] Enter filename (press Enter for default): {Style.RESET_ALL}").strip()
                    self.export_history(filename if filename else None)

                elif choice == '0':
                    print(f"\n{Fore.GREEN}[+] Thank you for using TorVault! Stay anonymous!{Style.RESET_ALL}")
                    self.display_contact_info()
                    break

                else:
                    print(f"{Fore.RED}[!] Invalid option. Please try again.{Style.RESET_ALL}")
        finally:
            self.shutdown()


def main():
    """Main entry point"""
    try:
        if not RequirementsInstaller.install_all_packages():
            print(f"\n{Fore.RED}[!] Failed to install required packages.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}[i] Please install them manually: pip install stem requests colorama pysocks{Style.RESET_ALL}")
            sys.exit(1)

        manager = TorVault()
        manager.run_interactive()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[*] Interrupted by user{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Goodbye!{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[!] An error occurred: {e}{Style.RESET_ALL}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
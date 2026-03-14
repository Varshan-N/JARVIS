from langchain.tools import tool
from AppOpener import open, close
from bs4 import BeautifulSoup
from pathlib import Path
import screen_brightness_control as sbc
from whtsapp_automation import start_whatsapp, get_unread_contacts
import time, requests, webbrowser, subprocess, pyautogui, os, pytz, win32gui, win32con, random
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import psutil, threading, pyperclip, smtplib, imaplib
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from crompton import fan_on, fan_off, fan_speed


load_dotenv()
useragent = os.getenv("USER_AGENT")
GMAIL_ADDRESS  = os.getenv("GMAIL_ADDRESS")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
NEWS_API_KEY   = os.getenv("NEWS_API_KEY")

_assistant = None
_reminders: list[dict] = []

def set_assistant(assistant_instance):
    global _assistant
    _assistant = assistant_instance


@tool
def OpenApp(app_name: str) -> str:
    """
    Opens a desktop application by name.
    If the application is not installed, searches the web
    and opens the official website in the browser.
    """
    import urllib.parse
    app_name = app_name.lower().strip()

    try:
        open(app_name, match_closest=True, output=True, throw_error=True)
        return f"{app_name} opened successfully. SIR"

    except Exception:
        try:
            query = f"{app_name} official website"
            url = f"https://duckduckgo.com/html/?q={query}"
            headers = {"User-Agent": useragent}
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, "html.parser")
            links = soup.find_all("a")

            for link in links:
                href = link.get("href")
                if not href:
                    continue
                if "uddg=" in href:
                    parsed = urllib.parse.parse_qs(
                        urllib.parse.urlparse(href).query
                    )
                    real_url = parsed.get("uddg", [None])[0]
                    if real_url:
                        webbrowser.open(real_url)
                        return f"Opened {app_name} website. SIR"
                elif href.startswith("http") and "duckduckgo.com" not in href:
                    webbrowser.open(href)
                    return f"Opened {app_name} website. SIR"

            return f"Could not find website for {app_name}."

        except Exception as e:
            return f"Search failed: {str(e)}"


@tool
def CloseApp(app_name: str) -> str:
    """
    Closes a desktop application by name.
    """
    try:
        close(app_name, match_closest=True, output=True, throw_error=True)
        return f"{app_name} closed successfully. SIR"
    except Exception as e:
        return f"Failed to close {app_name}. Error: {str(e)}"


@tool
def youtube_search(query: str) -> str:
    """
    Opens the YouTube search results page for the given query in the browser.

    Use this tool ONLY when the user explicitly wants to BROWSE or SEE
    search results on YouTube.
    Do NOT use this tool if the user wants to PLAY or WATCH a specific video.
    """
    import urllib.parse

    encoded = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    webbrowser.open(url)
    return url


@tool
def open_url(last_url: str) -> str:
    """
    Opens the given URL in the default web browser.

    Use this tool when the user asks to open a website,
    open a video link, or says phrases like "open it" or "open the URL".

    Parameters:
        last_url (str): The full URL to open in the browser.
    """
    webbrowser.open(last_url)
    return f"Opened {last_url}"


@tool
def web_search(query: str) -> str:
    """
    Searches the web for the given query and returns the first relevant result URL.

    Use this tool when the user asks to search for information,
    websites, articles, services, videos, or general web content.
    This tool does NOT open the website — use open_url for that.

    Parameters:
        query (str): The search term to look up on the web.
    """
    import urllib.parse
    url = f"https://duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": useragent}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a"):
        href = link.get("href")
        if href and "uddg=" in href:
            parsed = urllib.parse.parse_qs(
                urllib.parse.urlparse(href).query
            )
            real_url = parsed.get("uddg", [None])[0]
            if real_url:
                return real_url

    return "No result found."


@tool
def GoogleSearchByTopic(topic: str) -> str:
    """
    Searches Google and opens the results page in the browser.
    Returns the search URL.

    Parameters:
        topic (str): The topic to search for on Google.
    """
    import urllib.parse

    encoded = urllib.parse.quote(topic)
    url = f"https://www.google.com/search?q={encoded}"
    webbrowser.open(url)
    return url


@tool
def fetch_whatsapp_unread(filter: str = "all") -> str:
    """
    Fetches unread messages from WhatsApp Web.
    Use this when the user asks for unread WhatsApp messages.

    Parameters:
        filter (str): Always use 'all' (default) to fetch all unread messages.
    """
    driver = start_whatsapp()
    contacts = get_unread_contacts(driver)

    if not contacts:
        return "BOSS, you have no unread messages in WhatsApp."

    response_lines = [
        f"{c['count']} unread message(s) from {c['contact']}" for c in contacts
    ]
    return "SIR, " + ", ".join(response_lines) + "."


@tool
def set_volume(level: int) -> str:
    """
    Set system volume level between 0 and 100.

    Parameters:
        level (int): Volume level from 0 (mute) to 100 (max).
    """
    level = max(0, min(100, level))
    win_volume = int(level * 65535 / 100)
    subprocess.run(f"nircmd.exe setsysvolume {win_volume}", shell=True)
    return f"Volume set to {level}%."


@tool
def set_brightness(level: int) -> str:
    """
    Set screen brightness level between 0 and 100.

    Parameters:
        level (int): Brightness level from 0 (dim) to 100 (full).
    """
    level = max(0, min(100, level))
    sbc.set_brightness(level)
    return f"Brightness set to {level}%."


@tool
def control_youtube(action: str, value: int = 0) -> str:
    """
    Control YouTube video playback using keyboard shortcuts.

    Actions: pause, resume, fullscreen, exit_fullscreen,
             volume_up, volume_down, volume_percent, next, previous, mute

    Parameters:
        action (str): The playback action to perform.
        value (int): Used only for volume_percent (0-100).
    """
    time.sleep(1)
    action = action.lower()

    if action in ["pause", "resume"]:
        pyautogui.press("k")
    elif action == "fullscreen":
        pyautogui.press("f")
    elif action == "exit_fullscreen":
        pyautogui.press("f")
    elif action == "volume_up":
        pyautogui.press("up")
    elif action == "volume_down":
        pyautogui.press("down")
    elif action == "volume_percent":
        value = max(0, min(100, int(value)))
        for _ in range(25):
            pyautogui.press("down")
            time.sleep(0.01)
        steps = value // 5
        for _ in range(steps):
            pyautogui.press("up")
            time.sleep(0.01)
        return f"YouTube volume set to {value}%, SIR."
    elif action == "next":
        pyautogui.hotkey("shift", "n")
    elif action == "previous":
        pyautogui.hotkey("shift", "p")
    elif action == "mute":
        pyautogui.click()
        time.sleep(0.1)
        pyautogui.press("m")
        return "YouTube mute toggled, SIR."

    return f"YouTube {action} executed, SIR."


@tool
def window_control(action: str) -> str:
    """
    Controls system window behaviour.

    Actions: minimize, maximize, switch_window, task_view, new_desktop

    Parameters:
        action (str): The window action to perform.
    """
    time.sleep(0.5)
    action = action.lower()

    if action == "minimize":
        pyautogui.hotkey("win", "down")
    elif action == "maximize":
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    elif action == "switch_window":
        pyautogui.hotkey("alt", "tab")
    elif action == "task_view":
        pyautogui.hotkey("win", "tab")
    elif action == "new_desktop":
        pyautogui.hotkey("win", "ctrl", "d")
    else:
        return "Unknown window action."

    return f"{action} executed, SIR."


@tool
def desktop_control(action: str, number: int = 0) -> str:
    """
    Controls virtual desktops.

    Actions: new, close, next, previous, switch_to (requires number)

    Parameters:
        action (str): Desktop action to perform.
        number (int): Desktop number for switch_to action.
    """
    time.sleep(0.3)

    if action == "new":
        pyautogui.hotkey("win", "ctrl", "d")
        _assistant.total_desktops += 1
        _assistant.current_desktop += 1
        return f"Created desktop {_assistant.current_desktop}, SIR."

    elif action == "close":
        if _assistant.total_desktops > 1:
            pyautogui.hotkey("win", "ctrl", "f4")
            _assistant.total_desktops -= 1
            _assistant.current_desktop = max(1, _assistant.current_desktop - 1)
            return "Desktop closed, SIR."
        else:
            return "Only one desktop exists, SIR."

    elif action == "next":
        pyautogui.hotkey("win", "ctrl", "right")
        _assistant.current_desktop = min(
            _assistant.total_desktops, _assistant.current_desktop + 1
        )
        return f"Switched to desktop {_assistant.current_desktop}, SIR."

    elif action == "previous":
        pyautogui.hotkey("win", "ctrl", "left")
        _assistant.current_desktop = max(1, _assistant.current_desktop - 1)
        return f"Switched to desktop {_assistant.current_desktop}, SIR."

    elif action == "switch_to":
        if number < 1:
            return "Invalid desktop number."
        while _assistant.total_desktops < number:
            pyautogui.hotkey("win", "ctrl", "d")
            _assistant.total_desktops += 1
        while _assistant.current_desktop > 1:
            pyautogui.hotkey("win", "ctrl", "left")
            _assistant.current_desktop -= 1
            time.sleep(0.1)
        for _ in range(number - 1):
            pyautogui.hotkey("win", "ctrl", "right")
            _assistant.current_desktop += 1
            time.sleep(0.1)
        return f"Switched to desktop {number}, SIR."

    else:
        return "Unknown desktop action."


@tool
def file_manager(path: str, mode: str = "auto") -> str:
    """
    Universal file manager tool to open or list files and folders.

    Modes:
    - auto (default): auto-detect open or list
    - list: list contents of a directory
    - open: open a file or folder

    Parameters:
        path (str): File or folder path, or a single drive letter like C.
        mode (str): One of auto, list, open.
    """
    try:
        path = path.strip()
        if len(path) == 1 and path.isalpha():
            path = f"{path.upper()}:\\"
        elif len(path) == 2 and path[1] == ":":
            path = path + "\\"

        p = Path(path)

        if not p.exists():
            return (
                f"SIR, the path '{path}' does not exist on this system. "
                f"Please check the drive letter or folder name and try again."
            )

        if mode == "list":
            if not p.is_dir():
                return f"SIR, '{path}' is a file, not a folder. Cannot list its contents."
            folders = sorted([f.name for f in p.iterdir() if f.is_dir()])
            files   = sorted([f.name for f in p.iterdir() if f.is_file()])
            return (
                f"SIR, contents of {path}:\n"
                f"Folders: {folders if folders else 'None'}\n"
                f"Files: {files if files else 'None'}"
            )

        if mode in ["auto", "open"]:
            os.startfile(str(p))
            kind = "file" if p.is_file() else "folder"
            return f"SIR, opened {kind}: {p}"

        return "SIR, invalid mode. Use auto, list, or open."

    except PermissionError:
        return f"SIR, access denied to '{path}'. Try running JARVIS as administrator."
    except Exception as e:
        return f"SIR, file manager error: {str(e)}"


@tool
def get_time(timezone: str = "IST") -> str:
    """
    Returns the current time in human-readable format.

    Use this when the user asks what time it is.

    Parameters:
        timezone (str): Always use 'IST' (default). India Standard Time.
    """
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    return now.strftime("The current time is %I:%M %p, SIR.")


@tool
def get_date_and_day(timezone: str = "IST") -> str:
    """
    Returns the current date and day of the week.

    Use this when the user asks for today's date or day.

    Parameters:
        timezone (str): Always use 'IST' (default). India Standard Time.
    """
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    return now.strftime("Today is %A, %d %B %Y, SIR.")


@tool
def get_weather(city: str = "Chennai") -> str:
    """
    Returns the current weather for a given city including temperature,
    wind speed, humidity, and chance of rain.

    Use this when the user asks about the weather or temperature.

    Parameters:
        city (str): City name. Defaults to Chennai.
    """
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
        geo_res = requests.get(geo_url, timeout=5).json()

        if not geo_res.get("results"):
            return f"SIR, I couldn't find the city '{city}'."

        loc     = geo_res["results"][0]
        lat     = loc["latitude"]
        lon     = loc["longitude"]
        name    = loc["name"]
        country = loc.get("country", "")

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current_weather=true"
            f"&hourly=relativehumidity_2m,precipitation_probability,weathercode"
            f"&timezone=Asia/Kolkata"
            f"&forecast_days=1"
        )
        weather_res = requests.get(weather_url, timeout=5).json()
        current     = weather_res.get("current_weather", {})

        temp      = current.get("temperature")
        windspeed = current.get("windspeed")
        code      = current.get("weathercode")

        def describe(code):
            if code == 0:              return "clear sky"
            elif code in [1, 2]:       return "partly cloudy"
            elif code == 3:            return "overcast"
            elif code in [45, 48]:     return "foggy"
            elif code in [51, 53]:     return "drizzling"
            elif code == 55:           return "heavy drizzle"
            elif code in [61, 63]:     return "rainy"
            elif code == 65:           return "heavy rain"
            elif code in [71, 73, 75]: return "snowing"
            elif code in [80, 81, 82]: return "rain showers"
            elif code in [95, 96, 99]: return "thunderstorm"
            else:                      return "unknown conditions"

        condition  = describe(code)
        hourly     = weather_res.get("hourly", {})
        humidity   = (hourly.get("relativehumidity_2m") or ["N/A"])[0]
        rain_chance= (hourly.get("precipitation_probability") or ["N/A"])[0]

        return (
            f"SIR, current weather in {name}, {country}: "
            f"{temp}°C, {condition}. "
            f"Wind speed is {windspeed} km/h, "
            f"humidity is {humidity}%, "
            f"and there is a {rain_chance}% chance of rain."
        )

    except Exception as e:
        return f"SIR, I couldn't fetch the weather right now. Error: {str(e)}"


@tool
def take_screenshot(save_to: str = "desktop") -> str:
    """
    Takes a screenshot of the current screen and saves it.

    Use this when the user asks to take a screenshot or capture the screen.

    Parameters:
        save_to (str): Where to save the screenshot. Use 'desktop' (default)
                       or provide a full folder path like 'C:\\Users\\varsh\\Pictures'.
    """
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    if save_to.lower() == "desktop":
        candidates = [
            os.path.join(os.path.expanduser("~"), "Desktop"),
            os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
            os.path.join(os.path.expanduser("~"), "OneDrive - Personal", "Desktop"),
        ]
        folder = next((p for p in candidates if os.path.isdir(p)), None)

        if folder is None:
            folder = os.path.expanduser("~")
    else:
        folder = save_to

    os.makedirs(folder, exist_ok=True)

    path = os.path.join(folder, filename)
    pyautogui.screenshot(path)
    return f"SIR, screenshot saved as {filename} in {folder}."


@tool
def get_battery_status(unit: str = "percent") -> str:
    """
    Returns the current battery percentage and charging status.

    Use this when the user asks about battery level or charging status.

    Parameters:
        unit (str): Always use 'percent' (default). No other values needed.
    """
    b = psutil.sensors_battery()
    if b is None:
        return "SIR, no battery detected. You may be on a desktop."
    status = "charging" if b.power_plugged else "not charging"
    return f"SIR, battery is at {int(b.percent)}% and is currently {status}."


@tool
def get_system_stats(detail: str = "all") -> str:
    """
    Returns current CPU usage, RAM usage, and disk space.

    Use this when the user asks about system performance or resources.

    Parameters:
        detail (str): Always use 'all' (default) to get full stats.
    """
    cpu       = psutil.cpu_percent(interval=1)
    ram       = psutil.virtual_memory()
    disk      = psutil.disk_usage("C:\\")
    ram_used  = round(ram.used   / (1024**3), 1)
    ram_total = round(ram.total  / (1024**3), 1)
    disk_free = round(disk.free  / (1024**3), 1)
    disk_total= round(disk.total / (1024**3), 1)

    return (
        f"SIR, system status: "
        f"CPU at {cpu}%, "
        f"RAM usage {ram_used} GB of {ram_total} GB, "
        f"Disk has {disk_free} GB free out of {disk_total} GB."
    )


@tool
def set_reminder(message: str, minutes: int) -> str:
    """
    Sets a reminder that will trigger a desktop notification after a given number of minutes.

    Use this when the user says things like "remind me to ... in X minutes".

    Parameters:
        message (str): What to remind about.
        minutes (int): How many minutes from now to trigger the reminder.
    """
    from plyer import notification

    trigger_time = datetime.now() + timedelta(minutes=minutes)
    _reminders.append({"message": message, "time": trigger_time, "done": False})
    idx = len(_reminders) - 1

    def fire():
        _reminders[idx]["done"] = True
        notification.notify(title="JARVIS Reminder", message=message, timeout=10)

    threading.Timer(minutes * 60, fire).start()
    return f"SIR, reminder set. I will alert you about '{message}' in {minutes} minute(s)."


@tool
def get_reminders(filter: str = "pending") -> str:
    """
    Lists all pending reminders.

    Use this when the user asks what reminders are set.

    Parameters:
        filter (str): Always use 'pending' (default) to list active reminders.
    """
    pending = [r for r in _reminders if not r["done"]]
    if not pending:
        return "SIR, you have no pending reminders."
    lines = [f"- '{r['message']}' at {r['time'].strftime('%I:%M %p')}" for r in pending]
    return "SIR, your pending reminders:\n" + "\n".join(lines)


@tool
def send_whatsapp_message(phone_number: str, message: str) -> str:
    """
    Sends a WhatsApp message to a phone number via WhatsApp Web.

    Use this when the user asks to send a WhatsApp message to someone.

    Parameters:
        phone_number (str): Phone number with country code e.g. +919876543210
        message (str): The message text to send.
    """
    import pywhatkit
    pywhatkit.sendwhatmsg_instantly(phone_number, message, wait_time=10, tab_close=True)
    return f"SIR, WhatsApp message sent to {phone_number}."


@tool
def get_news_headlines(category: str = "general") -> str:
    """
    Fetches the latest top news headlines using Google News RSS (no API key needed).

    Use this when the user asks for news or headlines.

    Parameters:
        category (str): One of general, technology, sports, business,
                        entertainment, health, science. Defaults to general.
    """
    topic_map = {
        "general":       "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
        "technology":    "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "sports":        "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGQ2YVhjU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "business":      "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "entertainment": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "health":        "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ?hl=en-IN&gl=IN&ceid=IN:en",
        "science":       "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
    }

    rss_url = topic_map.get(category.lower(), topic_map["general"])

    try:
        headers = {"User-Agent": useragent}
        response = requests.get(rss_url, headers=headers, timeout=8)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "xml")
        items = soup.find_all("item")[:5]

        if not items:
            soup = BeautifulSoup(response.content, "html.parser")
            items = soup.find_all("item")[:5]

        if not items:
            return "SIR, I couldn't find any news articles right now."

        headlines = []
        for i, item in enumerate(items, 1):
            title_tag = item.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
                headlines.append(f"{i}. {title}")

        if not headlines:
            return "SIR, I couldn't parse the news headlines right now."

        return f"SIR, top {category} headlines:\n" + "\n".join(headlines)

    except Exception as e:
        return f"SIR, I couldn't fetch the news right now. Error: {str(e)}"



@tool
def send_email(to: str, subject: str, body: str) -> str:
    """
    Sends an email via Gmail.

    Use this when the user asks to send an email to someone.

    Parameters:
        to (str): Recipient email address.
        subject (str): Subject line of the email.
        body (str): Body text of the email.
    """
    try:
        msg = MIMEMultipart()
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            s.sendmail(GMAIL_ADDRESS, to, msg.as_string())

        return f"SIR, email sent to {to} with subject '{subject}'."
    except Exception as e:
        return f"SIR, failed to send email. Error: {str(e)}"


@tool
def read_emails(count: int = 5) -> str:
    """
    Reads the latest unread emails from the Gmail inbox.

    Use this when the user asks to check or read emails.

    Parameters:
        count (int): Number of unread emails to fetch. Defaults to 5.
    """
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
        mail.select("inbox")

        _, data = mail.search(None, "UNSEEN")
        ids = data[0].split()[-count:]

        if not ids:
            return "SIR, you have no unread emails."

        results = []
        for i in reversed(ids):
            _, msg_data = mail.fetch(i, "(RFC822)")
            msg     = email_lib.message_from_bytes(msg_data[0][1])
            sender  = msg.get("From", "Unknown")
            subject = msg.get("Subject", "No Subject")
            results.append(f"- From: {sender} | Subject: {subject}")

        mail.logout()
        return "SIR, your unread emails:\n" + "\n".join(results)
    except Exception as e:
        return f"SIR, failed to read emails. Error: {str(e)}"


@tool
def clipboard_manager(action: str, text: str = "") -> str:
    """
    Reads from or writes to the system clipboard.

    Use this when the user asks to copy text or check what's in the clipboard.

    Parameters:
        action (str): 'read' to get clipboard contents, 'write' to set them.
        text (str): Text to copy (only used when action is 'write').
    """
    if action == "read":
        content = pyperclip.paste()
        return f"SIR, clipboard contains: {content}" if content else "SIR, clipboard is empty."
    elif action == "write":
        pyperclip.copy(text)
        return f"SIR, copied to clipboard: {text}"
    return "SIR, invalid clipboard action. Use 'read' or 'write'."



@tool
def get_stock_price(ticker: str) -> str:
    """
    Returns the latest stock price for a given ticker symbol.
    Supports any Yahoo Finance ticker. No extra packages needed.

    Use this when the user asks about a stock price.

    Parameters:
        ticker (str): Stock ticker e.g. AAPL, TSLA, GOOG, RELIANCE.NS, TCS.NS
                      For Indian stocks add .NS suffix e.g. TCS.NS, RELIANCE.NS
    """
    name_map = {
        "google": "GOOG", "alphabet": "GOOG",
        "apple": "AAPL",
        "microsoft": "MSFT",
        "amazon": "AMZN",
        "meta": "META", "facebook": "META",
        "netflix": "NFLX",
        "tesla": "TSLA",
        "nvidia": "NVDA",
        "samsung": "005930.KS",
        "tcs": "TCS.NS", "tata consultancy": "TCS.NS",
        "infosys": "INFY.NS",
        "reliance": "RELIANCE.NS",
        "wipro": "WIPRO.NS",
        "hdfc": "HDFCBANK.NS",
    }

    resolved = name_map.get(ticker.lower().strip(), ticker.upper().strip())

    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{resolved}"
            f"?interval=1m&range=1d"
        )
        headers = {
            "User-Agent": useragent,
            "Accept": "application/json",
        }
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        result   = data.get("chart", {}).get("result")
        if not result:
            error_msg = data.get("chart", {}).get("error", {})
            return f"SIR, I couldn't find ticker '{resolved}'. Please check the symbol. ({error_msg})"

        meta     = result[0].get("meta", {})
        price    = meta.get("regularMarketPrice") or meta.get("previousClose")
        currency = meta.get("currency", "")
        name     = meta.get("longName") or meta.get("shortName") or resolved
        exchange = meta.get("exchangeName", "")

        if price is None:
            return f"SIR, price data unavailable for {resolved} right now."

        price = round(float(price), 2)
        return (
            f"SIR, {name} ({resolved}) on {exchange} "
            f"is currently trading at {price} {currency}."
        )

    except Exception as e:
        return f"SIR, couldn't fetch stock price for {resolved}. Error: {str(e)}"


@tool
def get_calendar_events(days_ahead: int = 1) -> str:
    """
    Fetches upcoming events from Google Calendar.

    Use this when the user asks about their schedule or meetings.

    Parameters:
        days_ahead (int): How many days ahead to look. Defaults to 1 (today).
    """
    try:
        service = _get_calendar_service()
        now     = datetime.now(timezone.utc)
        end     = now + timedelta(days=days_ahead)

        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=10,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        if not events:
            return "SIR, you have no upcoming events."

        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            lines.append(f"- {e['summary']} at {start}")

        return "SIR, your upcoming events:\n" + "\n".join(lines)

    except Exception as ex:
        return f"SIR, calendar error: {str(ex)}"


@tool
def system_power(action: str, delay_minutes: int = 0) -> str:
    """
    Controls system power state: lock, shutdown, restart, or cancel scheduled shutdown.

    Use this when the user asks to lock, shut down, or restart the PC.

    Parameters:
        action (str): One of lock, shutdown, restart, cancel.
        delay_minutes (int): Delay in minutes before shutdown or restart. 0 means immediately.
    """
    action     = action.lower()
    delay_secs = delay_minutes * 60

    if action == "lock":
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "SIR, workstation locked."
    elif action == "shutdown":
        os.system(f"shutdown /s /t {delay_secs}")
        msg = "immediately" if delay_secs == 0 else f"in {delay_minutes} minute(s)"
        return f"SIR, system will shut down {msg}."
    elif action == "restart":
        os.system(f"shutdown /r /t {delay_secs}")
        msg = "immediately" if delay_secs == 0 else f"in {delay_minutes} minute(s)"
        return f"SIR, system will restart {msg}."
    elif action == "cancel":
        os.system("shutdown /a")
        return "SIR, scheduled shutdown has been cancelled."

    return "SIR, unknown power action. Use lock, shutdown, restart, or cancel."


CALENDAR_ID = "varshan.n2005@gmail.com"

def _get_calendar_service():
    """
    Authenticates using a Service Account JSON key — no browser, no redirects.
    Requires service_account.json in the JARVIS folder.
    Your Google Calendar must be shared with the service account email.
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    SCOPES   = ["https://www.googleapis.com/auth/calendar"]
    SA_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_account.json")

    if not os.path.exists(SA_FILE):
        raise FileNotFoundError(
            "service_account.json not found. "
            "Please create a Service Account in Google Cloud Console, "
            "download the JSON key, rename it service_account.json and "
            "place it in your JARVIS folder."
        )

    creds = service_account.Credentials.from_service_account_file(SA_FILE, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)


@tool
def create_calendar_event(
    title: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    description: str = "",
    reminder_minutes: int = 10
) -> str:
    """
    Creates an event on Google Calendar with a notification reminder.

    Use this when the user asks to schedule a meeting or add an event to the calendar.

    Parameters:
        title (str): Event title e.g. Team Meeting
        date (str): Date in YYYY-MM-DD format e.g. 2026-03-10
        time (str): Time in HH:MM 24-hour format e.g. 14:00 for 2pm
        duration_minutes (int): Duration in minutes. Defaults to 60.
        description (str): Optional notes about the event.
        reminder_minutes (int): Minutes before event to send notification. Defaults to 10.
    """
    try:
        service  = _get_calendar_service()
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt   = start_dt + timedelta(minutes=duration_minutes)
        tz       = "Asia/Kolkata"

        event = {
            "summary":     title,
            "description": description,
            "start": {"dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz},
            "end":   {"dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),   "timeZone": tz},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": reminder_minutes},
                    {"method": "email", "minutes": reminder_minutes},
                ]
            }
        }

        created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        link    = created.get("htmlLink", "")
        return (
            f"SIR, event '{title}' has been scheduled on {date} at {time} IST "
            f"for {duration_minutes} minutes. "
            f"You will be notified {reminder_minutes} minute(s) before. "
            f"View it here: {link}"
        )
    except Exception as e:
        return f"SIR, failed to create event. Error: {str(e)}"


@tool
def list_schedule(days_ahead: int = 1) -> str:
    """
    Lists all scheduled calendar events for today or upcoming days.

    Use this when the user asks about their schedule or plans.

    Parameters:
        days_ahead (int): Number of days to look ahead. 1 = today, 7 = this week.
    """
    try:
        service = _get_calendar_service()
        now     = datetime.now(timezone.utc)
        end     = now + timedelta(days=days_ahead)

        result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=20,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = result.get("items", [])
        if not events:
            label = "today" if days_ahead == 1 else f"the next {days_ahead} days"
            return f"SIR, you have no scheduled events for {label}."

        lines = []
        for e in events:
            start_raw = e["start"].get("dateTime", e["start"].get("date"))
            try:
                dt       = datetime.fromisoformat(start_raw)
                time_str = dt.strftime("%d %b, %I:%M %p")
            except Exception:
                time_str = start_raw
            desc     = e.get("description", "")
            desc_str = f" — {desc}" if desc else ""
            lines.append(f"• {e['summary']} at {time_str}{desc_str}")

        label = "today" if days_ahead == 1 else f"the next {days_ahead} days"
        return f"SIR, your schedule for {label}:\n" + "\n".join(lines)

    except Exception as e:
        return f"SIR, failed to fetch schedule. Error: {str(e)}"


@tool
def delete_calendar_event(title: str) -> str:
    """
    Finds and deletes a calendar event by title (partial match).

    Use this when the user asks to cancel or remove an event from the calendar.

    Parameters:
        title (str): The name or partial name of the event to delete.
    """
    try:
        service = _get_calendar_service()
        now     = datetime.now(timezone.utc)
        end     = now + timedelta(days=30)

        result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=50,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events  = result.get("items", [])
        matches = [e for e in events if title.lower() in e.get("summary", "").lower()]

        if not matches:
            return f"SIR, I couldn't find any upcoming event matching '{title}'."

        event_to_delete = matches[0]
        service.events().delete(
            calendarId=CALENDAR_ID, eventId=event_to_delete["id"]
        ).execute()

        return f"SIR, event '{event_to_delete['summary']}' has been cancelled and removed from your calendar."

    except Exception as e:
        return f"SIR, failed to delete event. Error: {str(e)}"


@tool
def mark_event_done(title: str) -> str:
    """
    Marks a calendar event as completed by adding a checkmark to its title.

    Use this when the user says they completed or finished an event.

    Parameters:
        title (str): The name or partial name of the event to mark as done.
    """
    try:
        service = _get_calendar_service()
        now     = datetime.now(timezone.utc)
        start   = now - timedelta(hours=24)
        end     = now + timedelta(days=7)

        result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            maxResults=50,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events  = result.get("items", [])
        matches = [
            e for e in events
            if title.lower() in e.get("summary", "").lower()
            and "✅" not in e.get("summary", "")
        ]

        if not matches:
            return f"SIR, no pending event found matching '{title}'."

        event           = matches[0]
        event["summary"]= "✅ " + event["summary"]

        updated = service.events().update(
            calendarId=CALENDAR_ID, eventId=event["id"], body=event
        ).execute()

        return f"SIR, '{updated['summary']}' has been marked as completed on your calendar."

    except Exception as e:
        return f"SIR, failed to mark event. Error: {str(e)}"
    

@tool
def control_fan(command: str) -> str:
    """
    Controls the Crompton smart fan.
    Use this when the user says anything about the fan — turning it on/off or changing speed.
    
    command examples:
      "on"         → turns fan on
      "off"        → turns fan off
      "speed 3"    → sets speed to 3 (valid range: 1-6)
      "on speed 5" → turns on and sets speed to 5
    """
    command = command.lower().strip()

    speed = None
    for word in command.split():
        if word.isdigit() and 1 <= int(word) <= 6:
            speed = int(word)
            break

    try:
        if "off" in command:
            fan_off()
            return "SIR, the fan has been turned off."
        elif "on" in command or "start" in command or "turn" in command:
            fan_on()
            if speed:
                fan_speed(speed)
                return f"SIR, the fan has been turned on at speed {speed}."
            return "SIR, the fan has been turned on."
        elif "speed" in command and speed is not None:
            fan_speed(speed)
            return f"SIR, fan speed set to {speed}."
        else:
            return f"SIR, I didn't understand the fan command: '{command}'. Try 'on', 'off', or 'speed 1-6'."
    except Exception as e:
        return f"SIR, fan control failed: {str(e)}"

@tool
def create_file_or_folder(path: str, kind: str = "folder") -> str:
    """
    Creates a new file or folder at the given path.

    Use this when the user asks to create a new folder or a new file.

    Parameters:
        path (str): Full path where the file or folder should be created.
                    Examples:
                      "D:/projects/new_project"         → creates a folder
                      "D:/projects/notes.txt"           → creates a file
                      "C:/Users/Username/Desktop/work"  → creates a folder on desktop
        kind (str): "folder" to create a directory, "file" to create an empty file.
                    Default is "folder". Auto-detected from path extension if possible.
    """
    import shutil
    try:
        path = path.strip()
        p = Path(path)

        # Auto-detect kind from extension if not explicitly set
        if kind == "folder" and p.suffix:
            kind = "file"

        if kind == "file":
            if p.exists():
                return f"SIR, the file '{path}' already exists."
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
            return f"SIR, file '{p.name}' has been created at {p.parent}."

        else:  # folder
            if p.exists():
                return f"SIR, the folder '{path}' already exists."
            p.mkdir(parents=True, exist_ok=True)
            return f"SIR, folder '{p.name}' has been created at {p.parent}."

    except PermissionError:
        return f"SIR, access denied. Try running JARVIS as administrator."
    except Exception as e:
        return f"SIR, could not create '{path}': {str(e)}"


@tool
def delete_file_or_folder(path: str) -> str:
    """
    Permanently deletes a file or folder at the given path.

    Use this when the user asks to delete a file or folder.
    WARNING: This is permanent and cannot be undone.

    Parameters:
        path (str): Full path of the file or folder to delete.
                    Examples:
                      "D:/projects/old_project"   → deletes a folder and all its contents
                      "D:/projects/notes.txt"     → deletes a file
    """
    import shutil
    try:
        path = path.strip()
        p = Path(path)

        if not p.exists():
            return f"SIR, '{path}' does not exist."

        if p.is_file():
            p.unlink()
            return f"SIR, file '{p.name}' has been deleted."

        elif p.is_dir():
            shutil.rmtree(p)
            return f"SIR, folder '{p.name}' and all its contents have been deleted."

    except PermissionError:
        return f"SIR, access denied to '{path}'. Try running JARVIS as administrator."
    except Exception as e:
        return f"SIR, could not delete '{path}': {str(e)}"


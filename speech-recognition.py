from selenium import webdriver 
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os
from dotenv import load_dotenv
import mtranslate as mt

load_dotenv()

Input_Language="ta-IN"

HtmlCode = '''<!DOCTYPE html>
<html lang="en">
<head>
    <title>Speech Recognition</title>
</head>
<body>
    <button id="start" onclick="startRecognition()">Start Recognition</button>
    <button id="end" onclick="stopRecognition()">Stop Recognition</button>
    <p id="output"></p>
    <script>
        const output = document.getElementById('output');
        let recognition;

        function startRecognition() {
            recognition = new webkitSpeechRecognition() || new SpeechRecognition();
            recognition.lang = '';
            recognition.continuous = true;

            recognition.onresult = function(event) {
                const transcript = event.results[event.results.length - 1][0].transcript;
                output.textContent += transcript;
            };

            recognition.onend = function() {
                recognition.start();
            };
            recognition.start();
        }

        function stopRecognition() {
            recognition.stop();
            output.innerHTML = "";
        }
    </script>
</body>
</html>'''

HtmlCode=str(HtmlCode).replace("recognition.lang = '';",f"recognition.lang ='{Input_Language}';")

with open(r"Voice.html","w") as f:
    f.write(HtmlCode)

current_dic= os.getcwd()

Link=f"{current_dic}/Voice.html"

chrome_options = Options()
user_agent=os.getenv("USER_AGENT")
chrome_options.add_argument(f"user-agent={user_agent}")
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--use-fake-device-for-media-stream")
chrome_options.add_argument("--headless=new")

service=Service(ChromeDriverManager().install())
driver=webdriver.Chrome(service=service, options=chrome_options)

def querymodifier(Query):
    new_query=Query.lower().strip()
    query_words=new_query.split()
    question_words=["how","what","who","where","when","why","which","whose","whom","can you","what's"]
    
    if any(word + " " in new_query for word in question_words):
        if query_words[-1][-1] in ['.','?','!']:
            new_query = new_query[:-1] + "?"
        else:
            new_query += "?"
    else:
        if query_words[-1][-1] in ['.','?','!']:
            new_query = new_query[:-1]+"."
        else:
            new_query += "."
    return new_query.capitalize()

def is_tamil(text):
    """Check if the text contains any Tamil unicode characters."""
    return any('\u0B80' <= ch <= '\u0BFF' for ch in text)

def universaltranslator(Text):
    eng_tanslation=mt.translate(Text,"en","auto")
    return eng_tanslation.capitalize()

def speechrecognition():
    driver.get("file:///" + Link)
    driver.find_element(by=By.ID, value="start").click()
    Text = ""
    while True:
        try:
            Text = driver.find_element(by=By.ID, value="output").text
            if Text:
                driver.find_element(by=By.ID, value="end").click()

                if is_tamil(Text):
                    # Tamil script detected — translate to English first
                    print(f"[Tamil detected] {Text}")
                    return querymodifier(universaltranslator(Text))
                else:
                    # Already English (or Tanglish) — use directly
                    return querymodifier(Text)
        except Exception as e:
            pass


if __name__ == "__main__":
    while True:
        Text=speechrecognition()
        print(Text)
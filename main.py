import sounddevice as sd
import edge_tts as tts
import soundfile as sf
import queue, numpy, time, pyttsx3, sys, operator, os,io, soundfile, re, asyncio,tempfile, pygame, tools as tools_module
from PyQt5.QtCore import QThread, pyqtSignal, QCoreApplication, QTimer
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage, ToolMessage
from typing import TypedDict, Annotated
from groq import Groq
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import mtranslate as mt
from dotenv import load_dotenv
from tools import OpenApp,CloseApp,open_url,web_search,GoogleSearchByTopic,fetch_whatsapp_unread,\
                  set_volume,set_brightness,control_youtube,window_control,desktop_control,file_manager,youtube_search,\
                  get_time, get_date_and_day, get_weather, send_whatsapp_message, send_email, read_emails, get_news_headlines,\
                  get_stock_price, set_reminder, get_reminders, create_calendar_event, list_schedule, delete_calendar_event,\
                  mark_event_done, take_screenshot, get_battery_status, get_system_stats, control_fan, system_power,\
                  create_file_or_folder, delete_file_or_folder

load_dotenv()

api_key=os.getenv("GROQ_API_KEY")

client=Groq(api_key=api_key)

samplerate=16000
block_size=int(samplerate * 0.3)
energy_threshold=0.03
silence_timeout=1.3
tts_rate=200
tts_volume=1.0
channels=1
edge_voice=os.getenv("EDGE_VOICE")

Input_Language=os.getenv("INPUT_LANGUAGE")

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

#------Audio capturing thread ------#
class Audiocapturerthread(QThread):
    speech_start    = pyqtSignal()
    speech_detected = pyqtSignal(str)   
    speech_interrupt = pyqtSignal(str)  
    energy_update   = pyqtSignal(float) 

    def __init__(self):
        super().__init__()
        self.is_running       = False
        self.tts_active       = False
        self._tts_end_time    = 0.0
        self.TTS_COOLDOWN     = 1.5   
    
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


    def _is_noise(self, text):
        """Returns True only if we're in the TTS cooldown window (speaker bleed)."""
        if not self.tts_active and (time.time() - self._tts_end_time) < self.TTS_COOLDOWN:
            print(f"[STT] Ignored (TTS cooldown): {text}")
            return True
        return False

    def run(self):
        self.is_running = True
        driver.get("file:///" + Link)
        driver.find_element(by=By.ID, value="start").click()
        self.speech_start.emit()
        print("[STT] Web Speech recognition started")
        Text = ""
        while True:
            try:
                current = driver.find_element(by=By.ID, value="output").text.strip()
                if current and current != Text:
                    new_part=current[len(Text):].strip()
                    if new_part:
                        if self._is_noise(new_part):
                            print(f"[STT] Ignored (noise): {new_part}")
                            Text=current
                            continue
                        if Audiocapturerthread.is_tamil(new_part):
                            translated_txt=mt.translate(new_part,"en","auto")
                            result=Audiocapturerthread.querymodifier(translated_txt)
                        else:
                            result=Audiocapturerthread.querymodifier(new_part)
                        if self.tts_active:
                            self.speech_interrupt.emit(result)
                        else:
                            self.speech_detected.emit(result)
                    Text=current
                time.sleep(0.3)
            except Exception as e:
                if self.is_running:
                    print(f"[STT] Error: {e}")
                break

    def reset(self):
        """Clear Chrome output and reset — call when mic is toggled back on."""
        try:
            driver.find_element(By.ID, "end").click()
            time.sleep(0.2)
            driver.find_element(By.ID, "start").click()
            print("[STT] Reset — listening fresh")
        except Exception as e:
            print(f"[STT] Reset error: {e}")

    def stop(self):
        self.is_running = False
        try:
            driver.find_element(By.ID, "end").click()
        except Exception:
            pass
        self.quit()
        self.wait(3000)
        if self.isRunning():
            self.terminate()
    
#-------Audio Transcriber Thread----------
class Audiotranscriber(QThread):
    transcription_ready=pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.data=""

    def set_audio_data(self, text):
        self.data=text
    
    def run(self):
        self.transcription_ready.emit(self.data)

# --------Text-To-Speech Thread-------
class TTSThread(QThread):
    finished_speaking = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.text_queue = queue.Queue()
        self.is_running = True
        self._stream     = None
        self.should_stop = False
        
    def add_text(self, text):
        self.text_queue.put(text)
    
    def run(self):
        while self.is_running:
            try:
                text = self.text_queue.get(timeout=1)
                self.should_stop = False
                try:
                    asyncio.run(self._speak(text))
                except Exception as e:
                    print(f"TTS Engine Error: {e}")
                self.finished_speaking.emit()                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS Thread Error: {e}")
    
    async def _speak(self, text):
        communicate = tts.Communicate(text, edge_voice)

        # Save to temp mp3
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        await communicate.save(tmp_path)

        if self.should_stop:
            os.remove(tmp_path)
            return

        # Play with pygame — starts almost instantly, much lower latency than sounddevice+soundfile
        pygame.mixer.init()
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()

        # Wait until done or interrupted
        while pygame.mixer.music.get_busy():
            if self.should_stop:
                pygame.mixer.music.stop()
                break
            time.sleep(0.05)

        pygame.mixer.quit()
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    def stop_speaking(self):
        self.should_stop = True
        try:
            import pygame
            pygame.mixer.music.stop()
        except Exception:
            pass
                
    def stop(self):
        self.is_running = False
        try:
            pass
        except Exception:
            pass
        self.quit()
        self.wait(2000)
        if self.isRunning():
            self.terminate()

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
    last_url: str | None
    file_location: str | None

class GraphThread(QThread):
    finished_response = pyqtSignal(str)

    def __init__(self, graph, text, assistant):
        super().__init__()
        self.graph = graph
        self.text = text
        self.assistant=assistant

    def run(self):
        self.assistant.state["llm_calls"] = 0
        # Append user message to persistent state
        self.assistant.state["messages"].append(
            HumanMessage(content=self.text)
        )

        results = self.graph.invoke(self.assistant.state)

        self.assistant.state = results

        msgs = self.assistant.state["messages"]
        if len(msgs) > 7:
            msgs = msgs[-7:]
            while msgs and not isinstance(msgs[0], HumanMessage):
                msgs = msgs[1:]
            self.assistant.state["messages"] = msgs

        msgs = results.get("messages", [])
        if not msgs:
            self.finished_response.emit("")
            return

        # Walk back to find the last AI text message (skip tool calls/results)
        reply = ""
        for msg in reversed(msgs):
            content = getattr(msg, "content", "")
            # skip tool messages and AI messages that are pure tool calls (no text)
            if content and isinstance(content, str) and content.strip():
                reply = content
                break

        self.finished_response.emit(reply)
#------------LLm Assistant-------------
class LLMassistant:
        
    class _Signals(QThread):
        speech_detected = pyqtSignal()
        user_text_ready = pyqtSignal(str)
        ai_reply_ready  = pyqtSignal(str)
        tts_started     = pyqtSignal()
        tts_finished    = pyqtSignal()
        energy          = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.current_desktop = 1
        self.total_desktops = 1
        tools_module.set_assistant(self)

        self.llm=ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0,
            api_key=api_key,
            reasoning_effort="low",
            model_kwargs={"max_completion_tokens":4000
                          }
            )

        self.state = {
        "messages": [],
        "llm_calls": 0,
        "last_url": None,
        "file_location":None
        }
    
        tools = [OpenApp, CloseApp, open_url, web_search, GoogleSearchByTopic,
                fetch_whatsapp_unread, set_volume, set_brightness, control_youtube,
                window_control, desktop_control, file_manager, youtube_search,
                get_time, get_date_and_day, get_weather, take_screenshot,
                get_battery_status, get_system_stats, set_reminder, get_reminders,
                send_whatsapp_message, get_news_headlines, send_email, read_emails, get_stock_price, system_power,
                create_calendar_event, list_schedule, delete_calendar_event, mark_event_done, control_fan, create_file_or_folder, delete_file_or_folder]   

        self.llm_with_tools=self.llm.bind_tools(tools)

        def llm_call(state: AgentState):
            response = self.llm_with_tools.invoke(
                [SystemMessage(
                    content="You are JARVIS. "
                            "You must always Address me as SIR. "
                            "If the user asks to open any application or website, "
                            "you MUST call the OpenApp tool. "
                            "If the user asks to close an application, "
                            "you MUST call the CloseApp tool. "
                            "If the user asks to PLAY or WATCH a video on YouTube, "
                            "you MUST first call web_search and then use the open_url to open the video, "
                            "then call open_url with the returned URL. "
                            "Do NOT use youtube_search tool for playing videos. "
                            "Only use youtube_search when user wants to SEE search results. "
                            "Do not refuse. Do not explain. "
                            "Respond concisely. "
                            "If user asks to control system settings like volume, brightness, WiFi, Bluetooth, "
                            "you MUST call the appropriate tool."
                            "you must not responsd with any special characters when questioned or requested by the user. just conversation without special characters just like JARVIS and IRONMAN"
                )] + state["messages"]
            )

            last_url = state.get("last_url")
            location= state.get("file_location")

            if state["messages"]:
                last_msg = state["messages"][-1]
                file_location_content=state["messages"][-1]
                if isinstance(last_msg, ToolMessage):
                    content = str(last_msg.content)
                    if content.startswith("http"):
                        last_url = content
                if isinstance(file_location_content,ToolMessage):
                    loc_content=str(file_location_content.content)
                    if loc_content.startswith(r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]*"):
                        location=loc_content

            return {
                "messages": state["messages"] + [response],
                "llm_calls": state.get("llm_calls", 0) + 1,
                "last_url": last_url,
                "file_location":location
            }        
        
        def router(state: AgentState):
            if state.get("llm_calls", 0) > 3:
                return "end"
            last_msg=state['messages'][-1]
            return 'tools' if getattr(last_msg,'tool_calls',None) else 'end'
        
        tool_node=ToolNode(tools)

        builder=StateGraph(AgentState)
        builder.add_node('llm',llm_call)
        builder.add_node('tools',tool_node)

        builder.add_edge(START,'llm')
        builder.add_edge('tools','llm')
        builder.add_conditional_edges('llm', router,{'tools':'tools','end':END})

        self.graph=builder.compile()

        self.sig = LLMassistant._Signals()
        self.audio_thread = Audiocapturerthread()
        self.tts_thread = TTSThread()
        
        self.audio_thread.speech_start.connect(lambda: print("[STT] Listening..."))
        self.audio_thread.speech_detected.connect(self.process_speech)
        self.audio_thread.speech_interrupt.connect(self.check_interrupt)
        self.audio_thread.energy_update.connect(self.sig.energy.emit)
        self.tts_thread.finished_speaking.connect(self.on_tts_finished)
        
        self.is_listening = False
        self.is_tts_active = False
        self.user_speaking = False
        
        self.tts_thread.start()

        self.audio_thread.speech_start.connect(lambda: self.sig.speech_detected.emit())
        self.audio_thread.energy_update.connect(self.sig.energy.emit)

    
    def start(self):
        print("[Assistant] Listening started. Say something!")
        self.is_listening=True
        self.audio_thread.start()
        
    def stop(self):
        print("[Assistant] Stopping...")
        self.is_listening=False

        if self.audio_thread.isRunning():
            self.audio_thread.stop()
            
        if self.tts_thread.isRunning():
            self.tts_thread.stop()
            
    def process_speech(self, data):
        if not self.is_listening:
            print("[Assistant] Mic is off, ignoring speech")
            return
        if self.is_tts_active:
            print("[Assistant] Ignoring speech while TTS is active")
            return

        self.transcriber = Audiotranscriber()
        self.transcriber.set_audio_data(data)
        self.transcriber.transcription_ready.connect(self.handle_transcription)
        self.transcriber.start()
    
    def handle_transcription(self,text):
        if not text or text.strip() == "":
            return
        
        print(f"You: {text}")
        self.sig.user_text_ready.emit(text)
        if any(cmd in text.lower() for cmd in ["stop.","wait.","pause.","mute."]):
            if self.is_tts_active:
                print("[Assistant] Stopping speech...")
                self.tts_thread.stop()
            return
        
        self.graph_thread = GraphThread(self.graph, text,self)
        self.graph_thread.finished_response.connect(self.handle_response)
        self.graph_thread.start()
                
    def handle_response(self, reply):
        if not reply or reply.strip() == "":
            return
            
        print(f"AI: {reply}")
        self.sig.ai_reply_ready.emit(reply)  
        
        if "```" in reply:
            print("[Assistant] Skipping code speech. Saying acknowledgment...")
            reply = "Here is the code."

        if "https:" in reply.lower():
            print("[Assistant] Replacing link in speech...")
            reply = re.sub(r'https?://\S+', 'here is the link', reply)
        
        self.is_tts_active = True
        self.audio_thread.tts_active = True
        self.sig.tts_started.emit() 
        self.tts_thread.add_text(reply)
        
    def check_interrupt(self, text):
        if self.is_tts_active:
            print(f"[Assistant] Interrupted: {text}")
            self.tts_thread.stop_speaking()
            self.audio_thread.tts_active = False
            QTimer.singleShot(500, lambda: setattr(self, 'is_tts_active', False))
            QTimer.singleShot(600, lambda: self.handle_transcription(text))

    def on_tts_finished(self):
        self.is_tts_active = False
        self.audio_thread.tts_active = False
        self.audio_thread._tts_end_time = time.time()   # start cooldown window
        self.sig.tts_finished.emit()
        print("[Assistant] Ready for next command")

    def process_text(self, text):
        """Called by UI when user types a message in the canvas."""
        if not text or not text.strip():
            return
        self.sig.user_text_ready.emit(text)
        self.graph_thread = GraphThread(self.graph, text, self)
        self.graph_thread.finished_response.connect(self.handle_response)
        self.graph_thread.start()
    

if __name__ == "__main__":
    app = QCoreApplication(sys.argv)
    assistant = LLMassistant()
    assistant.start()

    try:
        sys.exit(app.exec_())
    except KeyboardInterrupt:
        assistant.stop()
        print("\n[System] Terminated by user.")
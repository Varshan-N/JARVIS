import sounddevice as sd
import edge_tts as tts
import queue, numpy, time, sys, operator, os,io, soundfile, re, asyncio,tempfile, pygame, tools as tools_module
from PyQt5.QtCore import QThread, pyqtSignal, QCoreApplication, QTimer
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage, ToolMessage
from typing import TypedDict, Annotated
from groq import Groq
from dotenv import load_dotenv
from tools import OpenApp,CloseApp,open_url,web_search,GoogleSearchByTopic,fetch_whatsapp_unread,\
                  set_volume,set_brightness,control_youtube,window_control,desktop_control,file_manager,youtube_search,\
                  get_time, get_date_and_day, get_weather, send_whatsapp_message, send_email, read_emails, get_news_headlines,\
                  get_stock_price, set_reminder, get_reminders, create_calendar_event, list_schedule, delete_calendar_event,\
                  mark_event_done, take_screenshot, get_battery_status, get_system_stats, control_fan, system_power,\
                  create_file_or_folder, delete_file_or_folder

load_dotenv()

api_key=os.getenv("GROQ_API_KEY")
edge_voice=os.getenv("EDGE_VOICE")

client=Groq(api_key=api_key)

samplerate=16000
block_size=int(samplerate * 0.5)
energy_threshold=0.02     
silence_timeout=1.0
channels=1

#------Audio capturing thread ------#
class Audiocapturerthread(QThread):
    speech_start=pyqtSignal()
    speech_end=pyqtSignal(numpy.ndarray)
    energy_update=pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.audio_queue=queue.Queue()
        self.is_running=False
        self.audio_buffer=[]
        self.recording=False
        
    def audio_callback(self,indata,frames,time,status):
        self.is_running=True
        if self.is_running:
            self.audio_queue.put(indata.copy())
            energy=numpy.sqrt(numpy.mean(indata.astype(numpy.float32) ** 2))
            self.energy_update.emit(energy)

    def audio_recorder(self):
        with sd.InputStream(samplerate=samplerate,channels=channels,blocksize=block_size,callback=self.audio_callback):
            while self.is_running:
                self.process_audio()

    def process_audio(self):
        try:
            block=self.audio_queue.get()
            block_flatten=block.flatten()
            energy=numpy.sqrt(numpy.mean(block_flatten.astype(numpy.float32) ** 2))

            if energy > energy_threshold:
                if not self.recording:
                    self.speech_start.emit()
                    self.recording=True
                    self.audio_buffer = []
                self.audio_buffer.append(block_flatten)
                self.last_speech_time=time.time() 
            elif self.recording:
                if time.time() - self.last_speech_time > silence_timeout:
                    self.recording=False
                    if self.audio_buffer:
                        complete_audio=numpy.concatenate(self.audio_buffer).astype(numpy.float32)   
                        self.speech_end.emit(complete_audio)
                        self.audio_buffer=[]
        except queue.Empty:
            pass

    def run(self):
        self.is_running = True
        self.audio_recorder()

    def stop(self):
        self.is_running=False
        self.audio_queue.put(numpy.zeros((block_size, 1), dtype=numpy.float32))  # unblock queue.get()
        self.quit()
        self.wait(2000)
        if self.isRunning():
            self.terminate()

#-------Audio Transcriber Thread----------
class Audiotranscriber(QThread):
    transcription_ready=pyqtSignal(str)
 
    def __init__(self):
        super().__init__()
        self.audio_data=None
 
    def set_audio_data(self, audio_data):
        self.audio_data=audio_data
    
    def run(self):
        if self.audio_data is not None:
            try:
                audio = self.audio_data.copy().astype(numpy.float32)
 
                # --- Whistle/tone detector (spectral flatness) ---
                # Speech has energy spread across many frequencies.
                # A whistle is a single pure tone — energy concentrated in one spot.
                # Spectral flatness close to 0 = pure tone (whistle). Close to 1 = speech.
                fft = numpy.abs(numpy.fft.rfft(audio))
                fft = fft + 1e-10  # avoid log(0)
                geometric_mean = numpy.exp(numpy.mean(numpy.log(fft)))
                arithmetic_mean = numpy.mean(fft)
                spectral_flatness = geometric_mean / arithmetic_mean
                if spectral_flatness < 0.1:  # pure tone detected
                    print(f"[STT] Rejected unwanted/murmuring sound (flatness={spectral_flatness:.4f})")
                    self.transcription_ready.emit("")
                    return
 
                # Boost volume 6x then normalize
                audio = audio * 8.0
                max_val = numpy.max(numpy.abs(audio))
                if max_val > 0.007:
                    audio = audio / max_val * 0.95
                else:
                    self.transcription_ready.emit("")
                    return
 
                # High-pass filter — removes Bluetooth hum/rumble
                alpha = 0.97
                filtered = numpy.zeros_like(audio)
                filtered[0] = audio[0]
                for i in range(1, len(audio)):
                    filtered[i] = alpha * (filtered[i-1] + audio[i] - audio[i-1])
                audio = filtered
 
                wav_buffer=io.BytesIO()
                soundfile.write(wav_buffer, audio, samplerate, format="WAV")
                wav_buffer.seek(0)
                transcription=client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    temperature=0,
                    file=("audio.wav",wav_buffer.read()),
                    language="en",
                    prompt="Jarvis, open, close, play, search, volume, brightness, speed, folder, file, create, delete, send, weather, time, date, news"
                )
                transcribed_text=transcription.text
 
                self.transcription_ready.emit(transcribed_text)
            except Exception as e:
                print("Groq STT Error:", e)
                self.transcription_ready.emit("")

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

        reply = results["messages"][-1].content
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
            max_tokens=300,
            api_key=api_key,
            reasoning_effort="low",
            model_kwargs={"max_completion_tokens":5000
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
                    content="You are JARVIS.\
                            You must always Address me as SIR.\
                            If the user asks to open any application or website,\
                            you MUST call the OpenApp tool.\
                            If the user asks to close an application,\
                            you MUST call the CloseApp tool.\
                            If the user asks to PLAY or WATCH a video on YouTube,\
                            you MUST first call web_search and then use the open_url to open the video,\
                            then call open_url with the returned URL.\
                            Do NOT use youtube_search tool for playing videos.\
                            Only use youtube_search when user wants to SEE search results.\
                            Do not refuse. Do not explain.\
                            Respond concisely.\
                            If user asks to control system settings like volume, brightness\
                            you MUST call the appropriate tool.\
                            you must not responsd with any special characters when questioned or requested by the user. just conversation without special characters just like JARVIS and IRONMAN"
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

        self.audio_thread = Audiocapturerthread()
        self.tts_thread = TTSThread()
        
        self.audio_thread.speech_start.connect(lambda: print("Speech Detected"))
        self.audio_thread.speech_end.connect(self.process_speech)
        self.audio_thread.energy_update.connect(self.check_interrupt)
        self.tts_thread.finished_speaking.connect(self.on_tts_finished)
        
        self.is_listening = False
        self.is_tts_active = False
        self.user_speaking = False
        
        self.tts_thread.start()


        self.sig = LLMassistant._Signals()
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
            
    def process_speech(self,audio_data):


        if not self.is_listening:
            print("[Assistant] Mic is off, ignoring speech")
            return        

        if self.is_tts_active:
            print("[Assistant] Ignoring speech while TTS is active")
            return

        print("[Assistant] Transcribing...")
        self.transcriber=Audiotranscriber()
        self.transcriber.set_audio_data(audio_data)
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
        self.sig.tts_started.emit() 
        self.tts_thread.add_text(reply)
        
    def check_interrupt(self,energy):
        if self.is_tts_active and energy > energy_threshold * 3:
            print("[Assistant] Interrupting speech...")
            self.tts_thread.stop_speaking()
            QTimer.singleShot(500, lambda: setattr(self, 'is_tts_active', False))

    def on_tts_finished(self):
        self.is_tts_active = False
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
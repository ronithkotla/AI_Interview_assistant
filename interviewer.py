import streamlit as st
from pdfminer.high_level import extract_text
import os
import pyttsx3
from groq import Groq
import pyaudio
import threading
import queue
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
import time

# Configuration
DEEPGRAM_API_KEY = "e21a974486aeb911305b820d385299deb86483f0"
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

# Initialize Deepgram client
deepgram = DeepgramClient(DEEPGRAM_API_KEY)


st.title("AI Interviewer")
if 'job_desc_box' not in st.session_state:
    st.session_state.job_desc_box = False
if 'job_desc' not in st.session_state:
    st.session_state.job_desc = ""

if 'pdf_processed' not in st.session_state:
        st.session_state.pdf_processed = False

if 'resume' not in st.session_state:
        st.session_state.resume = ""

if "messages" not in st.session_state:
        st.session_state.messages = []

if 'level_form' not in st.session_state:
        st.session_state.level_form = False

if 'voice_index' not in st.session_state:
        st.session_state.voice_index = 0

# Session state management
if 'transcription' not in st.session_state:
    st.session_state.transcription = []
if 'recording' not in st.session_state:
    st.session_state.recording = False

if "final_report" not in st.session_state:
    st.session_state.final_report=False


def get_bot_response():
    client = Groq(
    api_key="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",
    )
    chat_completion = client.chat.completions.create(
        messages=st.session_state.messages,
        model="llama-3.3-70b-versatile",
        max_tokens=70
    )
    bot_response=chat_completion.choices[0].message.content
    
    if bot_response:
        # Add user message to chat history
        st.session_state.messages.append({"role": "assistant", "content": bot_response})
    
    
    # Call the function to render messages
    display_messages()
    try:
        if voice_enabled:
            #Convert LLM output to speech 
            text_to_speech(bot_response, rate=200, volume=1.0, voice_index=st.session_state.voice_index)
    except:
        st.info("Donot reply while the interviewer is speaking.")
    
    


def display_messages():
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            if msg['role'] == 'user':
                st.markdown(f"""
                <div style='
                    display: flex; 
                    justify-content: flex-end; 
                    margin-bottom: 15px;
                    width: 100%;
                '>
                    <div style='
                        background-color: #414A4C; 
                        color: white;
                        border-radius: 15px;
                        padding: 12px 15px;
                        max-width: 80%;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                        border-bottom-right-radius: 5px;
                    '>
                        <div style='
                            font-weight: 600; 
                            margin-bottom: 5px; 
                            color: #A0A0A0;
                            font-size: 0.8em;
                        '>You</div>
                        {msg['content']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            elif msg['role'] == 'assistant':
                st.markdown(f"""
                <div style='
                    display: flex; 
                    justify-content: flex-start; 
                    margin-bottom: 15px;
                    width: 100%;
                '>
                    <div style='
                        background-color: #000000; 
                        color: white;
                        border-radius: 15px;
                        padding: 12px 15px;
                        max-width: 80%;
                        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                        border-bottom-left-radius: 5px;
                    '>
                        <div style='
                            font-weight: 600; 
                            margin-bottom: 5px; 
                            color: #A0A0A0;
                            font-size: 0.8em;
                        '>Interviewer</div>
                        {msg['content']}
                    </div>
                </div>
                """, unsafe_allow_html=True)


def setup_sidebar():
    try:
        if st.session_state.voice_index==1:
            video_path = "C:/Users/ronit/OneDrive/Desktop/ai_interviewer/female_interviewer.mp4"
        if st.session_state.voice_index==0:
            video_path = "C:/Users/ronit/OneDrive/Desktop/ai_interviewer/male_interviewer.mp4"
        if os.path.exists(video_path):
            video_file = open(video_path, "rb")
            video_bytes = video_file.read()
            st.sidebar.video(video_bytes, autoplay=True, loop=True)
            video_file.close()
        else:
            st.sidebar.warning("Video file not found. Please update the path.")
    except Exception as e:
        st.sidebar.error(f"Error loading video: {str(e)}")

    voice_enabled = st.sidebar.toggle("Interviewer's Voice", value=True)
    

    camera_enable = st.sidebar.checkbox("Enable camera")
    st.sidebar.camera_input("Take a picture", disabled=not camera_enable)
    
    return voice_enabled

def text_to_speech(text, rate=180, volume=1.0, voice_index=0):
    # Initialize the TTS engine
    engine = pyttsx3.init()

    # Set speech rate
    engine.setProperty('rate', rate)

    # Set volume level
    engine.setProperty('volume', volume)

    # Get available voices
    voices = engine.getProperty('voices')

    # Ensure the voice_index is within the valid range
    if 0 <= voice_index < len(voices):
        engine.setProperty('voice', voices[voice_index].id)
    else:
        print(f"Invalid voice index: {voice_index}. Using default voice.")

    # Convert text to speech
    
    engine.say(text)
    engine.runAndWait()
# Thread control
recording_event = threading.Event()
audio_queue = queue.Queue()
transcript_queue = queue.Queue()

def handle_transcript(self, result, **kwargs):
    """Corrected callback signature"""
    sentence = result.channel.alternatives[0].transcript
    if len(sentence.strip()) > 0:
        transcript_queue.put(sentence)

def audio_capture_thread():
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    while recording_event.is_set():
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_queue.put(data)
    
    stream.stop_stream()
    stream.close()
    p.terminate()

def deepgram_thread():
    dg_connection = deepgram.listen.websocket.v("1")
    dg_connection.on(LiveTranscriptionEvents.Transcript, handle_transcript)
    
    options = LiveOptions(
        model="nova-3",
        language="en-US",
        smart_format=True,
        encoding="linear16",
        sample_rate=RATE,
        channels=CHANNELS
    )
    
    if dg_connection.start(options):
        while recording_event.is_set():
            try:
                data = audio_queue.get(timeout=1)
                dg_connection.send(data)
            except queue.Empty:
                continue
    dg_connection.finish()
def speech_to_text():
    

    # Pills for recording control
    options = ["Record 🎙️"]
    selected_option = st.sidebar.pills("Record", options)

    # Handle recording state changes
    if selected_option == "Record 🎙️" and not st.session_state.recording:
        st.session_state.recording = True
        recording_event.set()
        threading.Thread(target=audio_capture_thread).start()
        threading.Thread(target=deepgram_thread).start()

    else:
        st.session_state.recording = False
        recording_event.clear()
        time.sleep(0.5)  # Allow threads to finish

    while st.session_state.recording:
        try:
            transcript = transcript_queue.get(timeout=1)
            st.session_state.transcription.append(transcript)
            st.sidebar.write(transcript)
            
        except queue.Empty:
            continue

    if not st.session_state.recording and st.session_state.transcription:
        user_speech_input="\n".join(st.session_state.transcription)
        st.session_state.messages.append({"role": "user", "content": user_speech_input})

        st.session_state.transcription = []

    

# Function to extract text from PDF
def extract_pdf_text(uploaded_file):
    try:
        extracted_text = extract_text(uploaded_file)
        return extracted_text
    except Exception as e:
        st.error(f"Error extracting text from PDF: {str(e)}")
        return "Could not extract text from the PDF file."
 # Process PDF upload if not already done
if (not st.session_state.pdf_processed):
    st.subheader("Upload your Resume/CV (PDF)")
    uploaded_file = st.file_uploader("Upload your Resume/CV (PDF)", type="pdf",label_visibility="hidden")
    
    if uploaded_file is not None:
        with st.spinner("Processing PDF..."):
            st.session_state.resume = extract_pdf_text(uploaded_file)
            st.session_state.pdf_processed = True
            
            st.rerun()

# Only show the form if job_desc is False
if (not st.session_state.job_desc_box) and (st.session_state.pdf_processed):
    form = st.form("Job_description_form")
    
    st.session_state.job_desc = form.text_area("Enter the Job description:")
    submitted = form.form_submit_button("Submit & Proceed")
    no_job_desc=form.form_submit_button("Continue without Job description")
    if submitted:
        st.session_state.job_desc_box = True
        st.rerun()
    if no_job_desc:
        st.session_state.job_desc_box = True
        st.session_state.job_desc="Candidate didnt provide any job description, Proceed without job description." 
        st.rerun()



if (not st.session_state.level_form) and (st.session_state.pdf_processed) and (st.session_state.job_desc_box) :

    options = ["Easy", "Medium", "Hard"]
    level_selected= st.pills(
        "Select the Interview level :", options, selection_mode="single"
    )
    st.write("")
    options = ["Male", "Female"]
    interviewer_selected= st.pills(
        "Select the Interviewer :", options, selection_mode="single"
    )
    
   
    if st.button("Start Interview"):
        if interviewer_selected=="Male":
            st.session_state.voice_index=0
        else:
            st.session_state.voice_index=1

        st.session_state.level_form=True
        prompt=f"""
        # Context:
        -You are an Interviewer , who asks tailored Interview questions based on provided resume and job description.
        # Instruction:
        - Initial message should Thank the user for providing the resume and ask the question.
        - Each response should contain only one single short question.
        - Verify the answer given by the candidate , if it answer is satisfied move to next question.
        - If the candidate is unable to understand the question , simplify it.
        - Skip the question if candidate is unable to answer it correctly.
        - Questions should contain both HR related and Technical questions.
        
        # Inputs:
        - Candidate's resume : {st.session_state.resume}
        ---
        - Job Description : {st.session_state.job_desc}
        ---
        - Interview Questions Level:{level_selected},
                
        # Warning:
        - Keep the question very short and concise less than 50 words. Donot give answers or any help to candidate.
        - Questions should try to evaluate if the candidate is fit for the job description.
        - Ask questions based on the interview questions level specified ,Easy - basics, Medium - Intermediatory, Hard - Tough.
        - Donot answer questions or queries other than interview , Stick to the context .No help should be provided to answer the questions.
        - When the candidate feels bored, not interested or gives rude replies  , Tell them that they can press "exit" to stop the interview.
                """
        st.session_state.messages.append({"role": "system", "content": prompt})
      
        st.rerun()


if (not st.session_state.final_report) and(st.session_state.level_form) and (st.session_state.pdf_processed) and (st.session_state.job_desc_box):
    voice_enabled=setup_sidebar()
    if user_input := st.chat_input("Enter your answer or Type 'exit' to end the interview"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        if user_input=="exit":
            st.success("Interview completed Sucessfully!")
            st.session_state.final_report=True
            st.rerun()

    speech_to_text()

    get_bot_response()
    

    
if (st.session_state.final_report) and (st.session_state.level_form) and (st.session_state.pdf_processed) and (st.session_state.job_desc_box):
    final_place=st.info("Please wait , Generating the Report...")
    client = Groq(
    api_key="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",
    )

    report_prompt=f"""

    # Context:
    You are a Report generator, who generates reports after an interview based on candidate resume and how well it matches with the job description, and a interview conversation log with the candidate.

    # Instruction:
    - Evaluate if the candidate is having required skills,etc. and also consider the level of knowledge he has based on the interview conversation.
    - Assess whether the candidate has relevant experience mentioned in the job description.
    - Rate his projects based on creativity, uniqueness, and knowledge he has on it.
    - Check if he is having any certifications related to courses , hackathon participations,etc that could add weight.
    - Provide suggestions where he can improve to be a good match for that job description.
    - Suggest improvements regarding the answers he gave during the interview .
    - Provide Key points based on job description which can help the candidate perform well and add weight in a real interview.
    - Provide a brief final overview of everything .

    # Inputs:
    - AI Interview Conversation with candidate :{st.session_state.messages}
    - Extract candidate's resume and job description from the provided Interview conversation system prompt.
    # Warning:
    - Donot say who you are and what your goal,work is ,just give the report without any extra information.
    - Use necessary emojies for better display. 
    - Output should be markdown.
    """
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": report_prompt}],
        model="llama-3.3-70b-versatile",
    )
    report=chat_completion.choices[0].message.content
    st.markdown(f"""
                <div style='text-align: left; background-color: #000000; padding: 10px; border-radius: 10px; margin: 5px 0;'>
                 {report}
                </div>
                """, unsafe_allow_html=True)
    st.write("Download your report here:")
    st.download_button(
        label="Download Report",
        data=report,
        file_name="output.txt",
        icon=":material/download:",
    )
    final_place.success("Report generated successfully!")
    st.write("Keep skilling up! , All the Best for your future growth.")
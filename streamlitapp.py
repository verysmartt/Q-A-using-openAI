import os
import json
import traceback
import pandas as pd
import streamlit as st
import pyaudio
import wave
import speech_recognition as sr
from dotenv import load_dotenv
from langchain.globals import set_verbose
from langchain_community.callbacks import get_openai_callback
from PyPDF2 import PdfReader  # Import for reading PDF files
from src.mcq_generator.utils import read_file, get_table_data
from src.mcq_generator.MCQGenerator import generate_and_evaluate_quiz

# Load environment variables
load_dotenv()

# Set background gradient and style
st.markdown(
    """
    <style>
    body {
        background: linear-gradient(to right, #ff7e5f, #feb47b);
        color: white;
        font-family: 'Arial';
    }
    .reportview-container .main .block-container {
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .reportview-container .main .block-container .widget.stTextInput>div>div>input {
        background-color: rgba(255, 255, 255, 0.2);
        color: white;
    }
    .reportview-container .main .block-container .stNumberInput>div>div>div>input {
        background-color: rgba(255, 255, 255, 0.2);
        color: white;
    }
    .reportview-container .main .block-container .stTextInput>div>label,
    .reportview-container .main .block-container .stNumberInput>div>label,
    .reportview-container .main .block-container .stTextArea>div>label {
        color: white;
    }
    .reportview-container .main .block-container .stTextArea>div>div>textarea {
        background-color: rgba(255, 255, 255, 0.2);
        color: white;
    }
    .reportview-container .main .block-container .stButton>button {
        background-color: #ff6348;
        color: white;
        font-weight: bold;
        border-radius: 8px;
    }
    .reportview-container .main .block-container .stButton>button:hover {
        background-color: #ff3e20;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Load response JSON
with open('Response.json', 'r') as file:
    RESPONSE_JSON = json.load(file)

# Initialize Streamlit variables
st_key = "Test@123"
recording = False

# Function to start/stop audio recording
def toggle_recording():
    global recording
    recording = not recording
    if recording:
        record_audio("recorded_audio.wav")
    else:
        st.info("Recording stopped.")

# Function to record audio
def record_audio(filename, duration=15):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 2
    RATE = 44100

    audio = pyaudio.PyAudio()

    stream = audio.open(format=FORMAT, channels=CHANNELS,
                        rate=RATE, input=True,
                        frames_per_buffer=CHUNK)

    frames = []

    st.write("Recording...")
    for _ in range(0, int(RATE / CHUNK * duration)):
        if not recording:
            break
        data = stream.read(CHUNK)
        frames.append(data)
    st.write("Recording finished!")

    stream.stop_stream()
    stream.close()
    audio.terminate()

    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

# Function to transcribe audio to text
def transcribe_audio(filename):
    r = sr.Recognizer()
    with sr.AudioFile(filename) as source:
        audio_data = r.record(source)
        text = r.recognize_google(audio_data)
        return text

# Function to generate MCQs from audio
def generate_mcqs_from_audio():
    filename = "recorded_audio.wav"
    if os.path.exists(filename):
        st.audio(filename, format='audio/wav')
    else:
        st.warning("No recorded audio found.")
        return

    with st.form("audio_mcq_form"):
        mcq_count = st.number_input("No of Questions", min_value=3, max_value=50)
        subject = st.text_input("Insert the Subject", max_chars=20)
        tone = st.text_input("Complexity level of Questions", max_chars=20, placeholder="Simple")
        input_key = st.text_input("Enter the secret key", max_chars=50, placeholder="Password")
        create_button = st.form_submit_button("Create MCQs")
        
        if create_button:
            if input_key == st_key:
                with st.spinner("Loading..."):
                    try:
                        text = transcribe_audio(filename)
                        with get_openai_callback() as cb:
                            response = generate_and_evaluate_quiz(
                                {
                                    "text": text,
                                    "number": mcq_count,
                                    "subject": subject,
                                    "tone": tone,
                                    "response_json": json.dumps(RESPONSE_JSON)
                                }
                            )
                        print(f"Total Tokens: {cb.total_tokens}")
                        print(f"Prompt Tokens: {cb.prompt_tokens}")
                        print(f"Completion Tokens: {cb.completion_tokens}")
                        print(f"Total Cost: {cb.total_cost}")
                        if isinstance(response, dict):
                            quiz = response.get("quiz", None)
                            if quiz is not None:
                                table_data = get_table_data(quiz)
                                if table_data is not None:
                                    df = pd.DataFrame(table_data)
                                    df.index = df.index + 1
                                    st.table(df)
                                    st.text_area(label="Review", value=response["review"])
                                else:
                                    st.error("Error in the table data")
                        else:
                            st.write(response)
                    except Exception as e:
                        traceback.print_exception(type(e), e, e.__traceback__)
                        st.error("Error")
            else:
                st.error("Wrong Password")

# Function to read PDF file
def read_pdf(file):
    pdf_reader = PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Function to generate MCQs from uploaded file
def generate_mcqs_from_file(uploaded_file, mcq_count, subject, tone):
    if uploaded_file is not None:
        with st.spinner("Loading..."):
            try:
                if uploaded_file.type == "application/pdf":
                    text = read_pdf(uploaded_file)
                else:
                    text = read_file(uploaded_file)
                with get_openai_callback() as cb:
                    response = generate_and_evaluate_quiz(
                        {
                            "text": text,
                            "number": mcq_count,
                            "subject": subject,
                            "tone": tone,
                            "response_json": json.dumps(RESPONSE_JSON)
                        }
                    )
                print(f"Total Tokens: {cb.total_tokens}")
                print(f"Prompt Tokens: {cb.prompt_tokens}")
                print(f"Completion Tokens: {cb.completion_tokens}")
                print(f"Total Cost: {cb.total_cost}")
                if isinstance(response, dict):
                    quiz = response.get("quiz", None)
                    if quiz is not None:
                        table_data = get_table_data(quiz)
                        if table_data is not None:
                            df = pd.DataFrame(table_data)
                            df.index = df.index + 1
                            st.table(df)
                            st.text_area(label="Review", value=response["review"])
                        else:
                            st.error("Error in the table data")
                else:
                    st.write(response)
            except Exception as e:
                traceback.print_exception(type(e), e, e.__traceback__)
                st.error("Error")
    else:
        st.warning("Please upload a PDF or text file.")

# Streamlit app
def main():
    st.title("Q&A Generator with Audio Transcription")

    # Display UI
    file_option = st.radio("Select Input Option", ("Upload PDF/Text", "Record Audio"))

    if file_option == "Upload PDF/Text":
        with st.form("pdf_text_form"):
            uploaded_file = st.file_uploader("Upload a PDF or text file")
            mcq_count = st.number_input("No of Questions", min_value=3, max_value=50)
            subject = st.text_input("Insert the Subject", max_chars=20)
            tone = st.text_input("Complexity level of Questions", max_chars=20, placeholder="Simple")
            input_key = st.text_input("Enter the secret key", max_chars=50, placeholder="Password")
            create_button = st.form_submit_button("Create Q&A")
            
            if create_button:
                if input_key == st_key:
                    if uploaded_file is not None:
                        generate_mcqs_from_file(uploaded_file, mcq_count, subject, tone)
                    else:
                        st.warning("Please upload a PDF or text file.")
                else:
                    st.error("Wrong Password")

    elif file_option == "Record Audio":
        st.info("Click the 'Record Audio' button below to start/stop recording.")
        if st.button("Record Audio"):
            toggle_recording()

        generate_mcqs_from_audio()

if __name__ == "__main__":
    main()

import whisper

# load whisper model
model = whisper.load_model("base")

# transcribe audio file
result = model.transcribe(r"C:\Users\HP\Documents\GitHub\pawpingphils\extract\audio.wav")

print("Language:", result["language"])
print("Transcript:", result["text"])
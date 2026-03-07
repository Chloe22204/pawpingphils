import whisper

# load whisper model
model = whisper.load_model("base")

# transcribe audio file
result = model.transcribe(r"/Users/chloecheo/Documents/GitHub/pawpingphils/extract/jiunweiaudio1.wav")

print("Language:", result["language"])
print("Transcript:", result["text"])
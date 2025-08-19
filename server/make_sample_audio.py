from gtts import gTTS

out_path = r"D:\Projects\speakgenie-voice-tutor\media\stt\test.mp3"
text = "Hello! My name is Sam. How are you today?"
gTTS(text).save(out_path)
print("Saved:", out_path)

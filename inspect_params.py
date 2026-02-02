
import ChatTTS

chat = ChatTTS.Chat()

print("\n--- params_refine_text defaults ---")
# Instantiate default params
try:
    defaults = chat.RefineTextParams()
    print(dir(defaults))
    # Print public attributes
    for attr in dir(defaults):
        if not attr.startswith('__'):
            print(f"{attr}: {getattr(defaults, attr)}")
except Exception as e:
    print(f"Error inspecting RefineTextParams: {e}")

print("\n--- params_infer_code defaults ---")
try:
    defaults = chat.InferCodeParams()
    print(dir(defaults))
    for attr in dir(defaults):
        if not attr.startswith('__'):
            val = getattr(defaults, attr)
            # Summarize long values or tensors
            print(f"{attr}: {val}")
except Exception as e:
    print(f"Error inspecting InferCodeParams: {e}")

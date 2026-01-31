
import ChatTTS
import inspect

chat = ChatTTS.Chat()

print("--- Chat.infer arguments ---")
try:
    sig = inspect.signature(chat.infer)
    print(sig)
    # Check default params if available in docstring or signature
except Exception as e:
    print(f"Could not get signature: {e}")

print("\n--- Chat.load arguments ---")
try:
    sig = inspect.signature(chat.load)
    print(sig)
except Exception as e:
    print(f"Could not get signature: {e}")

# Check if there are specific conditioning params usually used in other projects
# like 'params_infer_code', 'params_refine_text'

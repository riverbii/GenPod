
import ChatTTS
import torch

# Load Model
chat = ChatTTS.Chat()
chat.load(compile=False)

# Segment 002 Text
text = """今天咱们得把视野拉开。
不仅要看Google的绝地反击。
还要聊聊一个可能颠覆咱们认知的底层发现：也许我们以前用的Prompt技巧。
全都是错的。

首先。
咱们得聊聊Google昨天凌晨的“炸场”发布。[break_6]
大家都在盯着Gemini三Flash的速度。
[break_6]没错。[break_6]
它把视频交互延迟压到了亚秒级。
而且还搞了个“主动视觉代理”。"""

seed = 7470000
torch.manual_seed(seed)
spk_emb = chat.sample_random_speaker()

print("\n--- 1. Normalization ---")
normalized_text = chat.normalizer(text, do_text_normalization=True, do_homophone_replacement=True)
print(f"Norm Text ({len(normalized_text)}):\n{normalized_text}")

print("\n--- 2. Refine ---")
params_refine = chat.RefineTextParams(
    temperature=0.7,
    top_P=0.7,
    prompt='[laugh_0][break_4]',
    max_new_token=8192,
    manual_seed=seed
)
refined_text_raw = chat.infer([text], params_refine_text=params_refine, refine_text_only=True, split_text=True)
refined_text_combined = " ".join(refined_text_raw)
print(f"Refined Text ({len(refined_text_combined)}):\n{refined_text_combined}")

print("\n--- 3. Alignment ---")
# Import our aligner (assuming functionality)
# I'll just copy-paste the function here for standalone testing to be sure
def align_text(normalized_text, refined_text):
    result = ""
    i_norm = 0
    i_ref = 0
    len_norm = len(normalized_text)
    len_ref = len(refined_text)
    while i_norm < len_norm:
        char_norm = normalized_text[i_norm]
        if char_norm == '[': # Manual tag in Norm
            tag_end = normalized_text.find(']', i_norm)
            if tag_end != -1:
                result += normalized_text[i_norm:tag_end+1]
                i_norm = tag_end + 1
                if i_ref < len_ref and refined_text[i_ref] == '[':
                     ref_tag_end = refined_text.find(']', i_ref)
                     if ref_tag_end != -1 and refined_text[i_ref:ref_tag_end+1] == normalized_text[i_norm-len(result.split(']')[-2])-1:i_norm]: # simplified check
                         i_ref = ref_tag_end + 1
                continue
        while i_ref < len_ref and refined_text[i_ref] == '[': # Ref tags
            tag_end = refined_text.find(']', i_ref)
            if tag_end != -1:
                tag = refined_text[i_ref:tag_end+1]
                if not result.endswith(tag): result += tag
                i_ref = tag_end + 1
            else: break
        if i_ref >= len_ref:
            result += char_norm
            i_norm += 1
            continue
        char_ref = refined_text[i_ref]
        if char_ref == char_norm:
            result += char_ref
            i_norm += 1
            i_ref += 1
            continue
        
        # Lookahead
        found_in_ref = -1
        for k in range(1, 10):
            if i_ref + k < len_ref and refined_text[i_ref + k] == char_norm:
                found_in_ref = k
                break
        found_in_norm = -1
        for k in range(1, 10):
            if i_norm + k < len_norm and normalized_text[i_norm + k] == char_ref:
                found_in_norm = k
                break
        
        if found_in_ref != -1 and (found_in_norm == -1 or found_in_ref < found_in_norm):
            i_ref += 1
        elif found_in_norm != -1:
             result += char_norm
             i_norm += 1
        else: # Mismatch -> Trust Norm
             result += char_norm
             i_norm += 1
             i_ref += 1
    return result

# Use the ACTUAL aligner implementation from the file would be better, but let's test the logic.
# Actually let's import it to be safe.
import sys
sys.path.insert(0, ".")
from src.genpod.text_aligner import align_text

aligned_text = align_text(normalized_text, refined_text_combined)
print(f"Aligned Text ({len(aligned_text)}):\n{aligned_text}")

print("\n--- 4. Final Prep ---")
final_text = aligned_text.replace('[uv_break]', '[break_6]').replace('[laugh]', '[laugh_0]')
print(f"Final Text ({len(final_text)}):\n{final_text}")

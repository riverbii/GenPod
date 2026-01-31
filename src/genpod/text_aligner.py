
import logging

logger = logging.getLogger(__name__)

def align_text(normalized_text, refined_text):
    """
    Aligns Refined Text (Source of Tags) with Normalized Text (Source of Truth).
    
    Goal: Produce a text string that:
    1. Contains 100% of the characters from `normalized_text` (Content Truth).
    2. Contains inserted Tags (e.g., [uv_break]) from `refined_text` (Prosody).
    3. Respects manual tags already present in `normalized_text`.
    
    Strategy: 
    Iterate through `normalized_text` char by char.
    Match against `refined_text`.
    - If Match: Advance both.
    - If Refined has Tag: Insert Tag, Advance Ref.
    - If Mismatch: Use Lookahead to decide if Refined has extra chars (Hallucination) or missing chars (Deletion).
      - Hallucination: Skip Ref chars.
      - Deletion: Keep Norm chars.
    """
    result = ""
    i_norm = 0
    i_ref = 0
    
    len_norm = len(normalized_text)
    len_ref = len(refined_text)
    
    while i_norm < len_norm:
        char_norm = normalized_text[i_norm]
        
        # 0. Check if Norm has a Tag (Manual Tag Preservation)
        # We must consume it from Norm to progress.
        if char_norm == '[':
            tag_end = normalized_text.find(']', i_norm)
            if tag_end != -1:
                # Found manual tag in Norm. KEEP IT unconditionally.
                tag_content = normalized_text[i_norm:tag_end+1]
                result += tag_content
                i_norm = tag_end + 1
                
                # Check if Ref is ALSO at a tag.
                # If Ref has the exact same tag, consume it to keep sync.
                if i_ref < len_ref and refined_text[i_ref] == '[':
                     ref_tag_end = refined_text.find(']', i_ref)
                     if ref_tag_end != -1:
                         ref_tag = refined_text[i_ref:ref_tag_end+1]
                         if ref_tag == tag_content:
                             # Exact match, consume Ref tag too
                             i_ref = ref_tag_end + 1
                continue

        # 1. Check if Ref has a Tag at current position (AI Tag Insertion)
        # We process ALL tags at current ref position before moving on
        # WHITELISTED_TAGS: only allow valid prosody tags, filter out [speaker_...] etc.
        WHITELIST_PREFIXES = ('break_', 'laugh', 'oral_', 'speed_')
        
        while i_ref < len_ref and refined_text[i_ref] == '[':
            tag_end = refined_text.find(']', i_ref)
            if tag_end != -1:
                tag_content = refined_text[i_ref:tag_end+1]
                inner_tag = tag_content[1:-1].lower()
                
                # Whitelist Check
                is_whitelisted = any(inner_tag.startswith(p) for p in WHITELIST_PREFIXES)
                if not is_whitelisted:
                    logger.warning(f"     ⚠️  Skipping non-whitelisted Tag from AI: {tag_content}")
                    i_ref = tag_end + 1
                    continue

                # Duplicate Check: Prevent adding a tag if we JUST added the exact same one from Norm
                if result.endswith(tag_content):
                     i_ref = tag_end + 1
                     continue
                     
                result += tag_content
                i_ref = tag_end + 1
            else:
                break # Malformed tag

        if i_ref >= len_ref:
            # Ref exhausted, just append remaining Norm
            result += char_norm
            i_norm += 1
            continue

        char_ref = refined_text[i_ref]

        # 2. Match
        if char_ref == char_norm:
            result += char_ref
            i_norm += 1
            i_ref += 1
            continue
            
        # 3. Mismatch Handling with Lookahead
        # Goal: Find where they sync up again.
        
        # Lookahead in Ref (Is Ref inserting stuff?)
        # Search for current `char_norm` in the next few chars of `refined_text`
        found_in_ref = -1
        window = 10
        for k in range(1, window):
            if i_ref + k < len_ref and refined_text[i_ref + k] == char_norm:
                found_in_ref = k
                break
        
        # Lookahead in Norm (Is Ref deleting stuff?)
        # Search for current `char_ref` in the next few chars of `normalized_text`
        found_in_norm = -1
        for k in range(1, window):
            if i_norm + k < len_norm and normalized_text[i_norm + k] == char_ref:
                found_in_norm = k
                break
        
        # DECISION LOGIC
        if found_in_ref != -1 and (found_in_norm == -1 or found_in_ref < found_in_norm):
            # Ref has extra chars (Insertion/Hallucination) -> Skip Ref chars until match
            i_ref += 1
        elif found_in_norm != -1:
             # Ref missing chars (Deletion) -> Keep Norm char (restore), advance i_norm
             result += char_norm
             i_norm += 1
        else:
             # Total mismatch (Mutation?) -> Trust Norm.
             # Assume Ref char is garbage/wrong.
             i_ref += 1
             result += char_norm
             i_norm += 1

    return result

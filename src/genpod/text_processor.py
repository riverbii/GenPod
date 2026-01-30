import re
from pathlib import Path


def number_to_chinese(num_str):
    """将阿拉伯数字转换为汉字数字读法"""
    # 数字映射
    num_map = {
        '0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
        '5': '五', '6': '六', '7': '七', '8': '八', '9': '九'
    }
    
    # 单位映射
    unit_map = ['', '十', '百', '千', '万']
    
    def convert_number(n):
        """转换数字为汉字（支持完整读法，如25 -> 二十五，年份逐位转换如2026 -> 二零二六）"""
        n_int = int(float(n))
        n_str = str(n_int)
        
        # 年份特殊处理：4位数且 >= 1000 的年份使用逐位转换（如2026 -> 二零二六）
        if 1000 <= n_int < 10000 and len(n_str) == 4:
            return ''.join([num_map.get(d, d) for d in n_str])
        
        # 对于较小的数字（<10000），使用完整读法
        if n_int < 10000:
            if n_int == 0:
                return '零'
            if n_int < 10:
                return num_map[str(n_int)]
            if n_int < 20:
                if n_int == 10:
                    return '十'
                return '十' + num_map[str(n_int % 10)]
            if n_int < 100:
                tens = n_int // 10
                ones = n_int % 10
                result = num_map[str(tens)] + '十'
                if ones > 0:
                    result += num_map[str(ones)]
                return result
            if n_int < 1000:
                hundreds = n_int // 100
                remainder = n_int % 100
                result = num_map[str(hundreds)] + '百'
                if remainder > 0:
                    if remainder < 10:
                        result += '零' + num_map[str(remainder)]
                    else:
                        result += convert_number(remainder)
                return result
            if n_int < 10000:
                thousands = n_int // 1000
                remainder = n_int % 1000
                result = num_map[str(thousands)] + '千'
                if remainder > 0:
                    if remainder < 100:
                        result += '零' + convert_number(remainder)
                    else:
                        result += convert_number(remainder)
                return result
        else:
            # 对于大数字，逐位转换
            return ''.join([num_map.get(d, d) for d in n_str])
    
    def replace_number(match):
        """替换数字为汉字"""
        num_str = match.group(0)
        # 如果是小数
        if '.' in num_str:
            parts = num_str.split('.')
            int_part = convert_number(parts[0])
            dec_part = ''.join([num_map.get(d, d) for d in parts[1]])
            return int_part + '点' + dec_part
        else:
            return convert_number(num_str)
    
    # 先处理带单位的数字（如"25万"、"100万"）
    # 匹配模式：数字 + 单位（万、千、百等）
    def replace_with_unit(match):
        num_part = match.group(1)
        unit = match.group(2)
        converted_num = convert_number(num_part)
        return converted_num + unit
    
    # 先替换带单位的数字
    result = re.sub(r'(\d+\.?\d*)([万千百十])', replace_with_unit, num_str)
    # 再替换剩余的数字
    result = re.sub(r'\d+\.?\d*', replace_number, result)
    
    return result


def clean_text(text):
    """清洗文本：
    1. 阿拉伯数字转汉字
    2. 逗号改句号
    3. 每句一行
    4. 去掉所有空格
    """
    # 1. 阿拉伯数字转汉字
    text = number_to_chinese(text)
    
    # 2. 逗号改句号
    text = text.replace('，', '。').replace(',', '。')
    
    # 3. 按句号分割，每句一行
    sentences = text.split('。')
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # 4. 去掉每句中的空格
    cleaned_sentences = [s.replace(' ', '') for s in sentences]
    
    # 重新组合，每句一行，最后加句号
    result = '\n'.join([s + '。' for s in cleaned_sentences if s])
    
    return result


def split_by_paragraph(text):
    """按段落拆分文本"""
    # 按双换行符或更多换行符分割段落
    paragraphs = re.split(r'\n\s*\n+', text.strip())
    # 过滤空段落
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    return paragraphs


def merge_paragraphs(paragraphs, min_chars=50, max_chars=200):
    """智能合并段落
    参数：
        paragraphs: 段落列表
        min_chars: 最小字数，低于此值会合并多个段落
        max_chars: 最大字数，超过此值会拆分段落
    返回：
        合并后的段落列表
    """
    if not paragraphs:
        return []
    
    def split_long_text(text, max_len, depth=0):
        """拆分超长文本为多个段落，保持清洗后的格式（每句一行）
        
        参数：
            text: 要拆分的文本
            max_len: 最大长度
            depth: 递归深度（防止无限递归）
        """
        # 防止无限递归
        if depth > 10:
            # 如果递归深度超过10，强制截断
            return [text[:max_len]] if len(text) > max_len else [text]
        
        if len(text) <= max_len:
            return [text]
        
        # 检查文本格式：如果包含换行符，说明是清洗后的格式（每句一行）
        if '\n' in text:
            # 按行拆分（每行是一句）
            lines = text.split('\n')
            lines = [line.strip() for line in lines if line.strip()]
        else:
            # 如果没有换行符，按句号拆分
            lines = [s.strip() + '。' for s in text.split('。') if s.strip()]
        
        result = []
        current = []
        current_len = 0
        
        for line in lines:
            line_len = len(line)
            
            # 如果单个句子就超过max_len，需要特殊处理
            if line_len > max_len:
                # 先保存当前累积的内容
                if current:
                    seg = '\n'.join(current)
                    result.append(seg)
                    current = []
                    current_len = 0
                
                # 尝试在句子内找合适的截断点（句号、逗号、[uv_break]等）
                # 如果找不到，就强制截断
                if line_len > max_len:
                    # 尝试在max_len附近找句号、逗号或[uv_break]
                    cut_pos = max_len
                    for marker in ['。', '，', '[uv_break]', '。', '、']:
                        pos = line.rfind(marker, 0, max_len)
                        if pos > max_len * 0.7:  # 至少要在70%的位置
                            cut_pos = pos + len(marker)
                            break
                    
                    # 截断并保存前半部分
                    first_part = line[:cut_pos].strip()
                    remaining_part = line[cut_pos:].strip()
                    
                    if first_part:
                        result.append(first_part)
                    if remaining_part:
                        # 递归处理剩余部分
                        if len(remaining_part) > max_len:
                            result.extend(split_long_text(remaining_part, max_len, depth + 1))
                        else:
                            current.append(remaining_part)
                            current_len = len(remaining_part)
                else:
                    current.append(line)
                    current_len = line_len
            elif current_len + line_len >= max_len and current:
                # 保存当前累积（保持每句一行的格式）
                # 注意：这里current_len是累积长度（不包括换行符），seg是实际文本（包括换行符）
                # 需要检查实际文本长度是否超过max_len
                seg = '\n'.join(current)
                seg_len = len(seg)
                
                # 如果当前累积的内容不超过max_len，且加上新行也不会超过max_len，继续累积
                # 否则保存当前累积，把新行放到下一个段落
                if seg_len <= max_len and seg_len + line_len + 1 <= max_len:  # +1是换行符
                    current.append(line)
                    current_len += line_len
                else:
                    # 保存当前累积的内容
                    if seg_len <= max_len:
                        result.append(seg)
                    else:
                        # 如果超过max_len，需要拆分
                        result.extend(split_long_text(seg, max_len, depth + 1))
                    current = [line]
                    current_len = line_len
            else:
                current.append(line)
                current_len += line_len
        
        # 保存剩余的段落
        if current:
            seg = '\n'.join(current)
            # 确保剩余段落不超过max_len
            if len(seg) > max_len:
                # 如果超过max_len，尝试拆分
                result.extend(split_long_text(seg, max_len, depth + 1))
            else:
                result.append(seg)
        
        return result
    
    # 目标字数：尽量让每个合并后的段落在合理范围内
    target_chars = max_chars * 0.75  # 150字左右
    
    merged = []
    current_segment = []
    current_length = 0
    
    for para in paragraphs:
        para_length = len(para)
        
        # 如果当前段落超过最大值，先拆分
        if para_length > max_chars:
            # 先保存当前累积的段落
            if current_segment:
                seg_text = '\n\n'.join(current_segment)
                if len(seg_text) > max_chars:
                    # 如果累积的段落也超过最大值，需要拆分
                    merged.extend(split_long_text(seg_text, max_chars, 0))
                else:
                    merged.append(seg_text)
                current_segment = []
                current_length = 0
            
            # 拆分超长段落
            merged.extend(split_long_text(para, max_chars, 0))
        else:
            # 检查合并后是否会超过最大值
            if current_length + para_length > max_chars and current_segment:
                # 保存当前累积
                seg_text = '\n\n'.join(current_segment)
                if len(seg_text) > max_chars:
                    merged.extend(split_long_text(seg_text, max_chars, 0))
                else:
                    merged.append(seg_text)
                current_segment = [para]
                current_length = para_length
            else:
                # 继续累积
                current_segment.append(para)
                current_length += para_length
                
                # 如果累积长度达到目标字数或接近最大值，保存
                if current_length >= target_chars or current_length >= max_chars * 0.9:
                    seg_text = '\n\n'.join(current_segment)
                    if len(seg_text) > max_chars:
                        merged.extend(split_long_text(seg_text, max_chars, 0))
                        current_segment = []
                        current_length = 0
                    else:
                        merged.append(seg_text)
                        current_segment = []
                        current_length = 0
    
    # 保存剩余的段落
    if current_segment:
        seg_text = '\n\n'.join(current_segment)
        if len(seg_text) > max_chars:
            merged.extend(split_long_text(seg_text, max_chars, 0))
        else:
            # 如果剩余段落太短，尝试合并到上一个段落
            if len(seg_text) < min_chars and merged:
                last_length = len(merged[-1])
                if last_length + len(seg_text) <= max_chars:
                    merged[-1] = merged[-1] + '\n\n' + seg_text
                else:
                    merged.append(seg_text)
            else:
                merged.append(seg_text)
    
    # 最终检查：确保所有段落都不超过max_chars
    final_merged = []
    for seg in merged:
        if len(seg) > max_chars:
            final_merged.extend(split_long_text(seg, max_chars, 0))
        else:
            final_merged.append(seg)
    
    return final_merged


def filter_markdown_metadata(content):
    """过滤掉Markdown文件的元数据（标题、TTS设置建议等）
    
    移除：
    - 以 # 开头的标题行
    - 包含 **[TTS Setting Suggestion]** 的段落
    - 以 * ** 开头的列表项（TTS设置建议）
    """
    lines = content.split('\n')
    filtered_lines = []
    skip_next = False
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # 跳过以 # 开头的标题行
        if stripped.startswith('#'):
            continue
        
        # 跳过包含 TTS Setting Suggestion 的行
        if 'TTS Setting Suggestion' in stripped or 'TTSSettingSuggestion' in stripped:
            skip_next = True
            continue
        
        # 跳过 TTS 设置建议的列表项（以 * ** 开头）
        if stripped.startswith('* **') and ('Role' in stripped or 'Speed' in stripped or 'Note' in stripped):
            continue
        
        # 如果上一行是TTS设置建议标题，跳过后续的空行和列表项
        if skip_next:
            if not stripped or stripped.startswith('*'):
                continue
            else:
                skip_next = False
        
        filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)


def process_markdown_file(file_path, min_chars=50, max_chars=200):
    """处理markdown文件：读取、清洗、按段落拆分、智能合并
    
    参数：
        file_path: 文件路径
        min_chars: 最小字数（默认50），低于此值会合并多个段落
        max_chars: 最大字数（默认200），超过此值会拆分段落
    返回：
        处理后的段落列表
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 先过滤掉Markdown元数据
    content = filter_markdown_metadata(content)
    
    # 再按段落拆分
    paragraphs = split_by_paragraph(content)
    
    # 清洗每个段落
    cleaned_paragraphs = [clean_text(p) for p in paragraphs]
    
    # 智能合并段落
    merged_paragraphs = merge_paragraphs(cleaned_paragraphs, min_chars, max_chars)
    
    return merged_paragraphs


if __name__ == "__main__":
    # 测试
    test_text = "今天是2026年1月28日。兄弟们，AI圈这24小时发生的事，基本上宣告了只会聊天的大模型时代正式结束了。"
    print("原始文本:")
    print(test_text)
    print("\n清洗后:")
    print(clean_text(test_text))
    
    print("\n段落拆分测试:")
    test_paragraphs = "段落1\n\n段落2\n\n段落3"
    print(split_by_paragraph(test_paragraphs))
